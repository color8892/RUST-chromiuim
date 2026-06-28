#!/usr/bin/env python3
"""Validate and summarize the Chromium integration checklist."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_CHECKLIST = Path("chromium_integration_checklist.json")
DEFAULT_REPORT = Path("target/reports/chromium_integration_checklist_report.json")
ALLOWED_PHASE_STATUSES = {"complete", "in_progress", "blocked_external"}
ALLOWED_ITEM_STATUSES = {
    "complete",
    "in_progress",
    "requires_chromium_checkout",
    "blocked_external",
}


@dataclass(frozen=True)
class ChecklistViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def validate_checklist(path: Path, repo_root: Path) -> tuple[dict[str, Any], list[ChecklistViolation]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, [ChecklistViolation("checklist read failed", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [ChecklistViolation("checklist JSON invalid", str(exc))]
    if not isinstance(payload, dict):
        return {}, [ChecklistViolation("invalid checklist", "top-level value must be object")]

    violations: list[ChecklistViolation] = []
    if payload.get("schema_version") != 1:
        violations.append(ChecklistViolation("invalid schema_version", "expected schema_version 1"))

    phases = payload.get("phases")
    if not isinstance(phases, list) or not phases:
        return payload, violations + [
            ChecklistViolation("invalid phases", "phases must be a non-empty array")
        ]

    seen_phases: set[str] = set()
    for phase_index, phase in enumerate(phases):
        violations.extend(_validate_phase(repo_root, phase_index, phase, seen_phases))
    return payload, violations


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    phases = payload.get("phases", [])
    item_counts: dict[str, int] = {}
    phase_reports: list[dict[str, Any]] = []
    for phase in phases:
        phase_item_counts: dict[str, int] = {}
        for item in phase.get("items", []):
            status = item["status"]
            item_counts[status] = item_counts.get(status, 0) + 1
            phase_item_counts[status] = phase_item_counts.get(status, 0) + 1
        phase_reports.append(
            {
                "name": phase["name"],
                "status": phase["status"],
                "item_count": len(phase.get("items", [])),
                "item_status_counts": phase_item_counts,
            }
        )
    return {
        "schema_version": 1,
        "phase_count": len(phases),
        "item_status_counts": item_counts,
        "phases": phase_reports,
    }


def _validate_phase(
    repo_root: Path,
    phase_index: int,
    phase: Any,
    seen_phases: set[str],
) -> list[ChecklistViolation]:
    if not isinstance(phase, dict):
        return [ChecklistViolation("invalid phase", f"phases[{phase_index}] must be object")]
    violations: list[ChecklistViolation] = []
    name = phase.get("name")
    label = name if isinstance(name, str) and name else f"phases[{phase_index}]"
    if not isinstance(name, str) or not name:
        violations.append(ChecklistViolation("invalid phase name", f"phases[{phase_index}]"))
    elif name in seen_phases:
        violations.append(ChecklistViolation("duplicate phase", name))
    else:
        seen_phases.add(name)

    status = phase.get("status")
    if status not in ALLOWED_PHASE_STATUSES:
        violations.append(ChecklistViolation("invalid phase status", f"{label}: {status!r}"))

    items = phase.get("items")
    if not isinstance(items, list) or not items:
        return violations + [ChecklistViolation("invalid phase items", label)]
    seen_items: set[str] = set()
    for item_index, item in enumerate(items):
        violations.extend(_validate_item(repo_root, label, item_index, item, seen_items))
    return violations


def _validate_item(
    repo_root: Path,
    phase_label: str,
    item_index: int,
    item: Any,
    seen_items: set[str],
) -> list[ChecklistViolation]:
    if not isinstance(item, dict):
        return [ChecklistViolation("invalid item", f"{phase_label}.items[{item_index}] must be object")]
    violations: list[ChecklistViolation] = []
    name = item.get("name")
    label = name if isinstance(name, str) and name else f"{phase_label}.items[{item_index}]"
    if not isinstance(name, str) or not name:
        violations.append(ChecklistViolation("invalid item name", f"{phase_label}.items[{item_index}]"))
    elif name in seen_items:
        violations.append(ChecklistViolation("duplicate item", f"{phase_label}: {name}"))
    else:
        seen_items.add(name)

    status = item.get("status")
    if status not in ALLOWED_ITEM_STATUSES:
        violations.append(ChecklistViolation("invalid item status", f"{label}: {status!r}"))

    evidence = item.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return violations + [ChecklistViolation("invalid evidence", label)]
    for evidence_path in evidence:
        if not isinstance(evidence_path, str) or not evidence_path:
            violations.append(ChecklistViolation("invalid evidence path", f"{label}: {evidence_path!r}"))
        elif not (repo_root / evidence_path).exists():
            violations.append(ChecklistViolation("missing evidence", f"{label}: {evidence_path}"))
    return violations


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    payload, violations = validate_checklist(args.checklist, Path.cwd())
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        report = build_report(payload)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Chromium integration checklist OK: {args.checklist}")
        print(f"Checklist report written: {args.report}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
