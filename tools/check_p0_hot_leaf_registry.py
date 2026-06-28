#!/usr/bin/env python3
"""Validate the P0 hot-leaf migration registry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REQUIRED_COMPONENT_FIELDS = {
    "name",
    "status",
    "rust_crate",
    "ffi_header",
    "cpp_adapter",
    "cpp_baseline",
    "perf_budget",
    "size_artifact",
    "differential_harness",
    "benchmark_harness",
    "fuzz_harness",
    "rollback_symbol",
}

ALLOWED_STATUSES = {
    "production_candidate",
    "prototype_size_candidate",
    "prototype_perf_candidate",
}


@dataclass(frozen=True)
class RegistryViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


class P0HotLeafRegistry:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def validate_file(self, path: Path) -> list[RegistryViolation]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return [RegistryViolation("registry read failed", str(exc))]
        except json.JSONDecodeError as exc:
            return [RegistryViolation("registry JSON invalid", str(exc))]

        violations: list[RegistryViolation] = []
        if payload.get("schema_version") != 1:
            violations.append(
                RegistryViolation("invalid schema_version", "expected schema_version 1")
            )

        components = payload.get("components")
        if not isinstance(components, list) or not components:
            return violations + [
                RegistryViolation("invalid components", "components must be a non-empty array")
            ]

        seen_names: set[str] = set()
        size_budget_paths = self._load_size_budget_paths()
        for index, component in enumerate(components):
            violations.extend(
                self._validate_component(index, component, seen_names, size_budget_paths)
            )
        return violations

    def _validate_component(
        self,
        index: int,
        component: Any,
        seen_names: set[str],
        size_budget_paths: set[str],
    ) -> list[RegistryViolation]:
        if not isinstance(component, dict):
            return [RegistryViolation("invalid component", f"components[{index}] must be object")]

        violations: list[RegistryViolation] = []
        name = component.get("name")
        label = name if isinstance(name, str) and name else f"components[{index}]"
        missing = REQUIRED_COMPONENT_FIELDS.difference(component)
        for field in sorted(missing):
            violations.append(RegistryViolation("missing field", f"{label}: {field}"))

        if not isinstance(name, str) or not name:
            violations.append(RegistryViolation("invalid name", f"components[{index}]"))
        elif name in seen_names:
            violations.append(RegistryViolation("duplicate name", name))
        else:
            seen_names.add(name)

        status = component.get("status")
        if status not in ALLOWED_STATUSES:
            violations.append(
                RegistryViolation("invalid status", f"{label}: {status!r}")
            )

        path_fields = [
            "rust_crate",
            "ffi_header",
            "cpp_baseline",
            "perf_budget",
            "differential_harness",
            "benchmark_harness",
            "fuzz_harness",
        ]
        for field in path_fields:
            value = component.get(field)
            if isinstance(value, str):
                violations.extend(self._check_path(label, field, value))

        adapters = component.get("cpp_adapter")
        if not isinstance(adapters, list) or not adapters:
            violations.append(RegistryViolation("invalid cpp_adapter", label))
        else:
            for adapter in adapters:
                if isinstance(adapter, str):
                    violations.extend(self._check_path(label, "cpp_adapter", adapter))
                else:
                    violations.append(
                        RegistryViolation("invalid cpp_adapter", f"{label}: {adapter!r}")
                    )

        size_artifact = component.get("size_artifact")
        if isinstance(size_artifact, str) and size_artifact not in size_budget_paths:
            violations.append(
                RegistryViolation(
                    "missing size budget",
                    f"{label}: {size_artifact} not listed in budgets/rust_artifacts_size.json",
                )
            )

        rollback_symbol = component.get("rollback_symbol")
        if isinstance(rollback_symbol, str) and "::SetRollbackEnabled" not in rollback_symbol:
            violations.append(
                RegistryViolation("invalid rollback symbol", f"{label}: {rollback_symbol}")
            )

        return violations

    def _check_path(self, label: str, field: str, value: str) -> list[RegistryViolation]:
        path = self._repo_root / value
        if not path.exists():
            return [RegistryViolation("missing path", f"{label}.{field}: {value}")]
        return []

    def _load_size_budget_paths(self) -> set[str]:
        budget_path = self._repo_root / "budgets" / "rust_artifacts_size.json"
        try:
            payload = json.loads(budget_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        paths: set[str] = set()
        for artifact in payload.get("artifacts", []):
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                paths.add(artifact["path"])
        return paths


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("p0_hot_leaf_registry.json"),
        help="P0 hot-leaf registry JSON file",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    repo_root = Path.cwd()
    violations = P0HotLeafRegistry(repo_root).validate_file(args.registry)
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        print(f"P0 hot-leaf registry OK: {args.registry}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
