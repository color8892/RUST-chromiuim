#!/usr/bin/env python3
"""Validate Chromium checkout next-task manifest and emit a report."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_MANIFEST = Path("chromium_next_tasks.json")
DEFAULT_REPORT = Path("target/reports/chromium_next_tasks_report.json")
DEFAULT_MARKDOWN = Path("target/reports/chromium_next_tasks_report.md")
ALLOWED_STATUSES = {"ready", "requires_chromium_checkout", "blocked_external"}


@dataclass(frozen=True)
class NextTaskViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def validate_manifest(path: Path, repo_root: Path) -> tuple[dict[str, Any], list[NextTaskViolation]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [NextTaskViolation("manifest read failed", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [NextTaskViolation("manifest JSON invalid", str(exc))]
    if not isinstance(payload, dict):
        return {}, [NextTaskViolation("invalid manifest", "top-level value must be object")]

    violations: list[NextTaskViolation] = []
    if payload.get("schema_version") != 1:
        violations.append(NextTaskViolation("invalid schema_version", "expected schema_version 1"))
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return payload, violations + [NextTaskViolation("invalid tasks", "tasks must be non-empty array")]

    ids: set[str] = set()
    for index, task in enumerate(tasks):
        violations.extend(_validate_task(repo_root, index, task, ids))
    for task in tasks:
        if isinstance(task, dict):
            task_id = task.get("id")
            for dependency in task.get("depends_on", []):
                if dependency not in ids:
                    violations.append(
                        NextTaskViolation("unknown dependency", f"{task_id}: {dependency}")
                    )
    return payload, violations


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    tasks = payload.get("tasks", [])
    status_counts: dict[str, int] = {}
    for task in tasks:
        status = task["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": 1,
        "task_count": len(tasks),
        "status_counts": status_counts,
        "tasks": [
            {
                "id": task["id"],
                "title": task["title"],
                "status": task["status"],
                "depends_on": task["depends_on"],
            }
            for task in tasks
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chromium Next Tasks",
        "",
        "These tasks require a real Chromium checkout. They are ordered so an agent can pick the first unblocked task and produce reviewable evidence.",
        "",
    ]
    for task in payload.get("tasks", []):
        lines.extend(
            [
                f"## {task['id']}: {task['title']}",
                "",
                f"- Status: `{task['status']}`",
                f"- Phase: `{task['phase']}`",
                f"- Depends on: `{', '.join(task['depends_on']) if task['depends_on'] else 'none'}`",
                "",
                "Entry commands:",
                "",
            ]
        )
        lines.extend(f"```powershell\n{command}\n```" for command in task["entry_commands"])
        lines.extend(["", "Acceptance gates:", ""])
        lines.extend(f"- {gate}" for gate in task["acceptance_gates"])
        lines.extend(["", "Evidence:", ""])
        lines.extend(f"- `{evidence}`" for evidence in task["evidence"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _validate_task(
    repo_root: Path,
    index: int,
    task: Any,
    ids: set[str],
) -> list[NextTaskViolation]:
    if not isinstance(task, dict):
        return [NextTaskViolation("invalid task", f"tasks[{index}] must be object")]
    violations: list[NextTaskViolation] = []
    task_id = task.get("id")
    label = task_id if isinstance(task_id, str) and task_id else f"tasks[{index}]"
    if not isinstance(task_id, str) or not task_id:
        violations.append(NextTaskViolation("invalid task id", f"tasks[{index}]"))
    elif task_id in ids:
        violations.append(NextTaskViolation("duplicate task id", task_id))
    else:
        ids.add(task_id)

    for field in ("title", "phase"):
        value = task.get(field)
        if not isinstance(value, str) or not value:
            violations.append(NextTaskViolation("missing task field", f"{label}: {field}"))
    if task.get("status") not in ALLOWED_STATUSES:
        violations.append(NextTaskViolation("invalid task status", f"{label}: {task.get('status')!r}"))
    for field in ("depends_on", "entry_commands", "acceptance_gates", "evidence"):
        value = task.get(field)
        if not isinstance(value, list):
            violations.append(NextTaskViolation("invalid task list", f"{label}: {field}"))
    for evidence in task.get("evidence", []):
        if not isinstance(evidence, str) or not evidence:
            violations.append(NextTaskViolation("invalid evidence", f"{label}: {evidence!r}"))
        elif not (repo_root / evidence).exists():
            violations.append(NextTaskViolation("missing evidence", f"{label}: {evidence}"))
    if not task.get("entry_commands"):
        violations.append(NextTaskViolation("missing entry command", label))
    if not task.get("acceptance_gates"):
        violations.append(NextTaskViolation("missing acceptance gate", label))
    return violations


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    payload, violations = validate_manifest(args.manifest, Path.cwd())
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        report = build_report(payload)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        args.markdown.write_text(render_markdown(payload), encoding="utf-8")
        print(f"Chromium next tasks OK: {args.manifest}")
        print(f"Next tasks report written: {args.report}")
        print(f"Next tasks Markdown written: {args.markdown}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
