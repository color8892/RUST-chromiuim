#!/usr/bin/env python3
"""Select the next actionable Chromium integration task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.check_chromium_checkout_preflight import build_preflight_report
from tools.check_chromium_next_tasks import validate_manifest
from tools.emit_chromium_import_report import build_report as build_import_report


DEFAULT_TASKS = Path("chromium_next_tasks.json")
DEFAULT_IMPORT_MANIFEST = Path("chromium_import_manifest.json")
DEFAULT_OUTPUT = Path("target/reports/chromium_next_task_selection.json")


def probe_completed_task_ids(
    repo_root: Path,
    chromium_root: Path | None,
    import_manifest_path: Path,
    preflight: dict[str, Any],
    preflight_violations: list[Any],
) -> set[str]:
    completed: set[str] = set()
    if chromium_root is None or preflight_violations or preflight["status"] != "ready":
        return completed

    completed.add("chromium-preflight")
    import_report = build_import_report(repo_root, import_manifest_path)
    if not import_report["missing_entries"]:
        completed.add("chromium-import-dry-run")

    manifest = json.loads(import_manifest_path.read_text(encoding="utf-8"))
    destination = chromium_root / manifest["default_destination"]
    if (destination / "BUILD.gn").exists():
        completed.add("chromium-gn-target-import")
    return completed


def select_next_task(
    repo_root: Path,
    tasks_path: Path,
    import_manifest_path: Path,
    chromium_root: Path | None,
) -> dict[str, Any]:
    payload, violations = validate_manifest(tasks_path, repo_root)
    if violations:
        raise ValueError("; ".join(violation.render() for violation in violations))
    tasks = payload["tasks"]
    task_by_id = {task["id"]: task for task in tasks}
    preflight, preflight_violations = build_preflight_report(chromium_root, import_manifest_path)
    completed = probe_completed_task_ids(
        repo_root,
        chromium_root,
        import_manifest_path,
        preflight,
        preflight_violations,
    )

    for task in tasks:
        if task["id"] in completed:
            continue
        dependencies = set(task["depends_on"])
        if dependencies.issubset(completed):
            blocked_reason = None
            if chromium_root is None:
                blocked_reason = "requires --chromium-root before this task can run"
            return {
                "schema_version": 1,
                "selected_task": {
                    "id": task["id"],
                    "title": task["title"],
                    "status": task["status"],
                    "blocked_reason": blocked_reason,
                    "entry_commands": task["entry_commands"],
                    "acceptance_gates": task["acceptance_gates"],
                },
                "completed_task_ids": sorted(completed),
                "preflight_status": preflight["status"],
                "known_task_ids": list(task_by_id),
            }

    return {
        "schema_version": 1,
        "selected_task": None,
        "completed_task_ids": sorted(completed),
        "preflight_status": preflight["status"],
        "known_task_ids": list(task_by_id),
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium-root", type=Path)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--import-manifest", type=Path, default=DEFAULT_IMPORT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    selection = select_next_task(Path.cwd(), args.tasks, args.import_manifest, args.chromium_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    task = selection["selected_task"]
    print(f"Chromium next task selection written: {args.output}")
    if task is None:
        print("Selected task: none")
    else:
        print(f"Selected task: {task['id']}")
        if task["blocked_reason"]:
            print(f"Blocked: {task['blocked_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
