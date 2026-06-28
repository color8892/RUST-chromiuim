#!/usr/bin/env python3
"""Validate the P0 fuzz corpus manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_MANIFEST = Path("fuzz_corpus_manifest.json")
DEFAULT_REGISTRY = Path("p0_hot_leaf_registry.json")


@dataclass(frozen=True)
class FuzzCorpusViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


class FuzzCorpusManifest:
    def __init__(self, repo_root: Path, registry_path: Path = DEFAULT_REGISTRY) -> None:
        self._repo_root = repo_root
        self._registry_path = registry_path

    def validate_file(self, path: Path) -> list[FuzzCorpusViolation]:
        payload, read_violations = self._read_json(path, "manifest")
        if read_violations:
            return read_violations
        registry_names, registry_violations = self._load_registry_names()
        if registry_violations:
            return registry_violations

        violations: list[FuzzCorpusViolation] = []
        if payload.get("schema_version") != 1:
            violations.append(
                FuzzCorpusViolation("invalid schema_version", "expected schema_version 1")
            )

        max_seed_bytes = payload.get("max_seed_bytes")
        if not isinstance(max_seed_bytes, int) or max_seed_bytes <= 0:
            violations.append(
                FuzzCorpusViolation("invalid max_seed_bytes", "expected positive integer")
            )
            max_seed_bytes = 0

        components = payload.get("components")
        if not isinstance(components, list) or not components:
            return violations + [
                FuzzCorpusViolation("invalid components", "components must be a non-empty array")
            ]

        seen_names: set[str] = set()
        for index, component in enumerate(components):
            violations.extend(
                self._validate_component(index, component, registry_names, seen_names, max_seed_bytes)
            )

        missing_components = registry_names.difference(seen_names)
        for name in sorted(missing_components):
            violations.append(FuzzCorpusViolation("missing component", name))

        return violations

    def _validate_component(
        self,
        index: int,
        component: Any,
        registry_names: set[str],
        seen_names: set[str],
        max_seed_bytes: int,
    ) -> list[FuzzCorpusViolation]:
        if not isinstance(component, dict):
            return [FuzzCorpusViolation("invalid component", f"components[{index}] must be object")]

        violations: list[FuzzCorpusViolation] = []
        name = component.get("name")
        label = name if isinstance(name, str) and name else f"components[{index}]"
        if not isinstance(name, str) or not name:
            violations.append(FuzzCorpusViolation("invalid name", f"components[{index}]"))
        elif name in seen_names:
            violations.append(FuzzCorpusViolation("duplicate name", name))
        else:
            seen_names.add(name)
            if name not in registry_names:
                violations.append(FuzzCorpusViolation("unknown component", name))

        harness = component.get("harness")
        if not isinstance(harness, str) or not harness:
            violations.append(FuzzCorpusViolation("invalid harness", label))
        elif not (self._repo_root / harness).exists():
            violations.append(FuzzCorpusViolation("missing harness", f"{label}: {harness}"))

        required_categories = component.get("required_categories")
        if not isinstance(required_categories, list) or not required_categories:
            violations.append(FuzzCorpusViolation("invalid required_categories", label))
            required_category_set: set[str] = set()
        else:
            required_category_set = set()
            for category in required_categories:
                if isinstance(category, str) and category:
                    required_category_set.add(category)
                else:
                    violations.append(
                        FuzzCorpusViolation("invalid required category", f"{label}: {category!r}")
                    )

        seeds = component.get("seeds")
        if not isinstance(seeds, list) or not seeds:
            return violations + [FuzzCorpusViolation("invalid seeds", label)]

        seed_categories: set[str] = set()
        seen_seed_names: set[str] = set()
        for seed_index, seed in enumerate(seeds):
            seed_label = f"{label}.seeds[{seed_index}]"
            category = seed.get("category") if isinstance(seed, dict) else None
            if isinstance(category, str) and category:
                seed_categories.add(category)
            violations.extend(
                self._validate_seed(seed_label, seed, seen_seed_names, max_seed_bytes)
            )

        missing_categories = required_category_set.difference(seed_categories)
        for category in sorted(missing_categories):
            violations.append(
                FuzzCorpusViolation("missing seed category", f"{label}: {category}")
            )
        return violations

    def _validate_seed(
        self,
        label: str,
        seed: Any,
        seen_seed_names: set[str],
        max_seed_bytes: int,
    ) -> list[FuzzCorpusViolation]:
        if not isinstance(seed, dict):
            return [FuzzCorpusViolation("invalid seed", f"{label} must be object")]

        violations: list[FuzzCorpusViolation] = []
        name = seed.get("name")
        if not isinstance(name, str) or not name:
            violations.append(FuzzCorpusViolation("invalid seed name", label))
        elif name in seen_seed_names:
            violations.append(FuzzCorpusViolation("duplicate seed name", f"{label}: {name}"))
        else:
            seen_seed_names.add(name)

        category = seed.get("category")
        if not isinstance(category, str) or not category:
            violations.append(FuzzCorpusViolation("invalid seed category", label))

        has_text = "text" in seed
        has_hex = "hex" in seed
        if has_text == has_hex:
            violations.append(
                FuzzCorpusViolation("invalid seed data", f"{label}: use exactly one of text or hex")
            )
            return violations

        data_len = 0
        if has_text:
            text = seed.get("text")
            if not isinstance(text, str) or not text:
                violations.append(FuzzCorpusViolation("invalid seed text", label))
            else:
                data_len = len(text.encode("utf-8"))
        else:
            hex_data = seed.get("hex")
            if not isinstance(hex_data, str) or not hex_data:
                violations.append(FuzzCorpusViolation("invalid seed hex", label))
            else:
                try:
                    data_len = len(bytes.fromhex(hex_data))
                except ValueError:
                    violations.append(FuzzCorpusViolation("invalid seed hex", label))

        if max_seed_bytes > 0 and data_len > max_seed_bytes:
            violations.append(
                FuzzCorpusViolation(
                    "seed too large",
                    f"{label}: {data_len} bytes exceeds {max_seed_bytes}",
                )
            )
        return violations

    def _load_registry_names(self) -> tuple[set[str], list[FuzzCorpusViolation]]:
        registry, violations = self._read_json(self._registry_path, "registry")
        if violations:
            return set(), violations
        components = registry.get("components")
        if not isinstance(components, list):
            return set(), [FuzzCorpusViolation("invalid registry", "components must be array")]
        names = {
            component["name"]
            for component in components
            if isinstance(component, dict) and isinstance(component.get("name"), str)
        }
        return names, []

    def _read_json(
        self, path: Path, label: str
    ) -> tuple[dict[str, Any], list[FuzzCorpusViolation]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return {}, [FuzzCorpusViolation(f"{label} read failed", str(exc))]
        except json.JSONDecodeError as exc:
            return {}, [FuzzCorpusViolation(f"{label} JSON invalid", str(exc))]
        if not isinstance(payload, dict):
            return {}, [FuzzCorpusViolation(f"invalid {label}", "top-level value must be object")]
        return payload, []


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="P0 fuzz corpus manifest JSON file",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="P0 hot-leaf registry JSON file",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    repo_root = Path.cwd()
    violations = FuzzCorpusManifest(repo_root, args.registry).validate_file(args.manifest)
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        print(f"P0 fuzz corpus manifest OK: {args.manifest}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
