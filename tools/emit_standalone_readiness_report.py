#!/usr/bin/env python3
"""Emit a standalone readiness report for the P0 Chromium Rust scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.check_chromium_checkout_preflight import build_preflight_report
from tools.check_chromium_integration_checklist import build_report as build_checklist_report
from tools.check_chromium_integration_checklist import validate_checklist
from tools.emit_chromium_cl_handoff import build_handoff
from tools.select_chromium_next_task import select_next_task


DEFAULT_OUTPUT_JSON = Path("target/reports/standalone_readiness_report.json")
DEFAULT_OUTPUT_MD = Path("target/reports/standalone_readiness_report.md")


def build_readiness_report(repo_root: Path) -> dict[str, Any]:
    checklist, violations = validate_checklist(
        repo_root / "chromium_integration_checklist.json",
        repo_root,
    )
    if violations:
        raise ValueError("; ".join(violation.render() for violation in violations))
    checklist_report = build_checklist_report(checklist)
    handoff = build_handoff(repo_root)
    preflight, preflight_violations = build_preflight_report(
        None,
        repo_root / "chromium_import_manifest.json",
    )
    if preflight_violations:
        raise ValueError("; ".join(violation.render() for violation in preflight_violations))
    next_task = select_next_task(
        repo_root,
        repo_root / "chromium_next_tasks.json",
        repo_root / "chromium_import_manifest.json",
        None,
    )
    selected = next_task["selected_task"]

    complete_items = checklist_report["item_status_counts"].get("complete", 0)
    chromium_required_items = checklist_report["item_status_counts"].get(
        "requires_chromium_checkout",
        0,
    )
    total_items = complete_items + chromium_required_items
    standalone_percent = round((complete_items / total_items) * 100.0, 1) if total_items else 0.0

    return {
        "schema_version": 1,
        "status": "standalone_ready_for_chromium_checkout",
        "standalone_percent": standalone_percent,
        "complete_items": complete_items,
        "requires_chromium_checkout_items": chromium_required_items,
        "recommended_first_component": handoff["recommended_first_component"],
        "chromium_destination": handoff["chromium_destination"],
        "import_file_count": handoff["import_file_count"],
        "preflight_status_without_root": preflight["status"],
        "next_chromium_task": selected["id"] if selected is not None else None,
        "next_chromium_task_title": selected["title"] if selected is not None else None,
        "next_chromium_task_blocked_reason": selected["blocked_reason"] if selected is not None else None,
        "local_preflight_commands": handoff["local_preflight_commands"],
        "chromium_checkout_commands": handoff["chromium_checkout_commands"],
        "external_blockers": handoff["external_gates_not_satisfied_in_this_repo"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Standalone Readiness Report",
        "",
        f"Status: `{report['status']}`",
        f"Standalone completion: `{report['standalone_percent']}%`",
        f"Complete standalone items: `{report['complete_items']}`",
        f"Requires Chromium checkout: `{report['requires_chromium_checkout_items']}`",
        f"Recommended first component: `{report['recommended_first_component']}`",
        f"Chromium destination: `//{report['chromium_destination']}`",
        f"Import file count: `{report['import_file_count']}`",
        f"Preflight status without root: `{report['preflight_status_without_root']}`",
        f"Next Chromium task: `{report['next_chromium_task']}`",
        f"Next Chromium task title: `{report['next_chromium_task_title']}`",
    ]
    if report["next_chromium_task_blocked_reason"]:
        lines.append(f"Next Chromium task blocked: `{report['next_chromium_task_blocked_reason']}`")
    lines.extend(
        [
            "",
            "## Local Preflight Commands",
            "",
        ]
    )
    lines.extend(f"```powershell\n{command}\n```" for command in report["local_preflight_commands"])
    lines.extend(["", "## Chromium Checkout Commands", ""])
    lines.extend(f"```powershell\n{command}\n```" for command in report["chromium_checkout_commands"])
    lines.extend(["", "## External Blockers", ""])
    lines.extend(f"- {blocker}" for blocker in report["external_blockers"])
    return "\n".join(lines).rstrip() + "\n"


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    report = build_readiness_report(Path.cwd())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"Standalone readiness JSON written: {args.output_json}")
    print(f"Standalone readiness Markdown written: {args.output_md}")
    print(f"Status: {report['status']} ({report['standalone_percent']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
