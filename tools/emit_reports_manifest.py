#!/usr/bin/env python3
"""Emit an index for generated standalone report artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_OUTPUT = Path("target/reports/reports_manifest.json")

REPORTS = [
    {
        "name": "standalone_readiness",
        "order": 1,
        "json": "target/reports/standalone_readiness_report.json",
        "markdown": "target/reports/standalone_readiness_report.md",
        "purpose": "Top-level status, remaining blockers, and next commands.",
    },
    {
        "name": "chromium_cl_handoff",
        "order": 2,
        "json": "target/reports/chromium_cl_handoff.json",
        "markdown": "target/reports/chromium_cl_handoff.md",
        "purpose": "First Chromium CL handoff checklist and rollback plan.",
    },
    {
        "name": "chromium_checkout_preflight",
        "order": 3,
        "json": "target/reports/chromium_checkout_preflight.json",
        "markdown": None,
        "purpose": "Non-mutating Chromium checkout path readiness report.",
    },
    {
        "name": "chromium_import",
        "order": 4,
        "json": "target/reports/chromium_import_report.json",
        "markdown": None,
        "purpose": "Dry-run import file list and missing-entry status.",
    },
    {
        "name": "chromium_next_tasks",
        "order": 5,
        "json": "target/reports/chromium_next_tasks_report.json",
        "markdown": "target/reports/chromium_next_tasks_report.md",
        "purpose": "Agent-ready task graph for work that requires a real Chromium checkout.",
    },
    {
        "name": "chromium_next_task_selection",
        "order": 6,
        "json": "target/reports/chromium_next_task_selection.json",
        "markdown": None,
        "purpose": "Current next actionable Chromium integration task based on checkout preflight state.",
    },
    {
        "name": "chromium_rust_safety_candidates",
        "order": 7,
        "json": "target/reports/chromium_rust_safety_candidates_report.json",
        "markdown": "target/reports/chromium_rust_safety_candidates_report.md",
        "purpose": "Memory-safety-ranked Chromium Rust migration candidates and blocked areas.",
    },
    {
        "name": "chromium_integration_checklist",
        "order": 8,
        "json": "target/reports/chromium_integration_checklist_report.json",
        "markdown": None,
        "purpose": "Standalone-complete versus Chromium-checkout-required item counts.",
    },
    {
        "name": "p0_artifacts",
        "order": 9,
        "json": "target/reports/p0_artifact_summary.json",
        "markdown": None,
        "purpose": "P0 component artifact, size, rollback, and fuzz seed summary.",
    },
    {
        "name": "fuzz_corpus",
        "order": 10,
        "json": "target/reports/fuzz_corpus_report.json",
        "markdown": None,
        "purpose": "P0 fuzz corpus category and seed coverage summary.",
    },
]


def build_manifest(repo_root: Path) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for report in REPORTS:
        json_path = repo_root / report["json"]
        markdown = report["markdown"]
        markdown_path = repo_root / markdown if markdown is not None else None
        reports.append(
            {
                **report,
                "json_exists": json_path.exists(),
                "markdown_exists": markdown_path.exists() if markdown_path is not None else None,
            }
        )
    return {
        "schema_version": 1,
        "report_count": len(reports),
        "reports": reports,
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    manifest = build_manifest(Path.cwd())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    missing = [
        report["name"]
        for report in manifest["reports"]
        if not report["json_exists"] or report["markdown_exists"] is False
    ]
    print(f"Reports manifest written: {args.output}")
    print(f"Reports indexed: {manifest['report_count']} Missing artifacts: {len(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
