#!/usr/bin/env python3
"""Emit a machine-readable coverage report for the P0 fuzz corpus manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_MANIFEST = Path("fuzz_corpus_manifest.json")
DEFAULT_OUTPUT = Path("target/reports/fuzz_corpus_report.json")


def _seed_len(seed: dict[str, Any]) -> int:
    if "text" in seed:
        return len(seed["text"].encode("utf-8"))
    return len(bytes.fromhex(seed["hex"]))


def build_report(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    components: list[dict[str, Any]] = []
    total_seeds = 0
    for component in payload["components"]:
        category_counts = {category: 0 for category in component["required_categories"]}
        max_seed_bytes = 0
        for seed in component["seeds"]:
            category_counts[seed["category"]] = category_counts.get(seed["category"], 0) + 1
            max_seed_bytes = max(max_seed_bytes, _seed_len(seed))
        total = len(component["seeds"])
        total_seeds += total
        missing = [
            category
            for category in component["required_categories"]
            if category_counts.get(category, 0) == 0
        ]
        components.append(
            {
                "name": component["name"],
                "harness": component["harness"],
                "seed_count": total,
                "required_categories": component["required_categories"],
                "category_counts": category_counts,
                "missing_categories": missing,
                "max_seed_bytes": max_seed_bytes,
            }
        )
    return {
        "schema_version": 1,
        "manifest": str(manifest_path),
        "component_count": len(components),
        "seed_count": total_seeds,
        "components": components,
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    report = build_report(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"P0 fuzz corpus report written: {args.output}")
    print(f"Components: {report['component_count']} Seeds: {report['seed_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
