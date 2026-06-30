#!/usr/bin/env python3
"""Emit high-level progress estimates for the Chromium Rust migration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.emit_standalone_readiness_report import build_readiness_report


DEFAULT_OUTPUT_JSON = Path("target/reports/progress_report.json")
DEFAULT_OUTPUT_MD = Path("target/reports/progress_report.md")


def build_progress_report(repo_root: Path) -> dict[str, Any]:
    readiness = build_readiness_report(repo_root)
    standalone_percent = float(readiness["standalone_percent"])
    chromium_integration_weight = 0.18
    overall_percent = round(standalone_percent * chromium_integration_weight, 1)

    return {
        "schema_version": 1,
        "standalone_percent": standalone_percent,
        "overall_chromium_migration_percent": overall_percent,
        "status": readiness["status"],
        "next_task": readiness["next_chromium_task"],
        "next_task_title": readiness["next_chromium_task_title"],
        "preflight_status_without_root": readiness["preflight_status_without_root"],
        "recommended_first_component": readiness["recommended_first_component"],
        "top_memory_safety_candidate": readiness["top_memory_safety_candidate"],
        "interpretation": {
            "standalone": "Repository scaffold and local P0 gates are ready for Chromium checkout handoff.",
            "overall": "Real Chromium migration remains early until GN wiring, Android official build, supersize diff, Chromium fuzzing, and web_tests/WPT run in a real checkout.",
        },
        "external_blockers": readiness["external_blockers"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Chromium Rust Migration Progress",
        "",
        f"Standalone repo readiness: `{report['standalone_percent']}%`",
        f"Overall Chromium migration: `{report['overall_chromium_migration_percent']}%`",
        f"Status: `{report['status']}`",
        f"Next task: `{report['next_task']}`",
        f"Next task title: `{report['next_task_title']}`",
        f"Preflight without root: `{report['preflight_status_without_root']}`",
        f"Recommended first component: `{report['recommended_first_component']}`",
        f"Top memory-safety candidate: `{report['top_memory_safety_candidate']}`",
        "",
        "## Interpretation",
        "",
        f"- Standalone: {report['interpretation']['standalone']}",
        f"- Overall: {report['interpretation']['overall']}",
        "",
        "## External Blockers",
        "",
    ]
    lines.extend(f"- {blocker}" for blocker in report["external_blockers"])
    return "\n".join(lines).rstrip() + "\n"


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    report = build_progress_report(Path.cwd())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"Progress JSON written: {args.output_json}")
    print(f"Progress Markdown written: {args.output_md}")
    print(
        "Progress: "
        f"standalone={report['standalone_percent']}% "
        f"overall={report['overall_chromium_migration_percent']}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
