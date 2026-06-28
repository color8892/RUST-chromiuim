#!/usr/bin/env python3
"""Emit a standalone P0 hot-leaf artifact summary report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_REGISTRY = Path("p0_hot_leaf_registry.json")
DEFAULT_FUZZ_MANIFEST = Path("fuzz_corpus_manifest.json")
DEFAULT_SIZE_BUDGET = Path("budgets/rust_artifacts_size.json")
DEFAULT_OUTPUT = Path("target/reports/p0_artifact_summary.json")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_summary(registry_path: Path, fuzz_manifest_path: Path, size_budget_path: Path) -> dict[str, Any]:
    registry = _load(registry_path)
    fuzz_manifest = _load(fuzz_manifest_path)
    size_budget = _load(size_budget_path)
    fuzz_by_component = {component["name"]: component for component in fuzz_manifest["components"]}
    size_by_path = {artifact["path"]: artifact for artifact in size_budget["artifacts"]}

    components: list[dict[str, Any]] = []
    for component in registry["components"]:
        size_path = component["size_artifact"]
        size_info = size_by_path.get(size_path, {})
        fuzz_info = fuzz_by_component.get(component["name"], {"seeds": [], "required_categories": []})
        artifact_path = Path(size_path)
        artifact_size = artifact_path.stat().st_size if artifact_path.exists() else None
        components.append(
            {
                "name": component["name"],
                "status": component["status"],
                "rust_crate": component["rust_crate"],
                "ffi_header": component["ffi_header"],
                "cpp_adapter": component["cpp_adapter"],
                "perf_budget": component["perf_budget"],
                "size_artifact": size_path,
                "size_artifact_exists": artifact_path.exists(),
                "size_bytes": artifact_size,
                "max_size_bytes": size_info.get("max_bytes"),
                "rollback_symbol": component["rollback_symbol"],
                "fuzz_seed_count": len(fuzz_info["seeds"]),
                "fuzz_required_categories": fuzz_info["required_categories"],
            }
        )

    return {
        "schema_version": 1,
        "component_count": len(components),
        "components": components,
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--fuzz-manifest", type=Path, default=DEFAULT_FUZZ_MANIFEST)
    parser.add_argument("--size-budget", type=Path, default=DEFAULT_SIZE_BUDGET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    summary = build_summary(args.registry, args.fuzz_manifest, args.size_budget)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"P0 artifact summary written: {args.output}")
    print(f"Components: {summary['component_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
