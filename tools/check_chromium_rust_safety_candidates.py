#!/usr/bin/env python3
"""Validate and report Chromium Rust candidates ranked by memory safety value."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_MANIFEST = Path("chromium_rust_safety_candidates.json")
DEFAULT_P0_REGISTRY = Path("p0_hot_leaf_registry.json")
DEFAULT_REPORT = Path("target/reports/chromium_rust_safety_candidates_report.json")
DEFAULT_MARKDOWN = Path("target/reports/chromium_rust_safety_candidates_report.md")
ALLOWED_TIERS = {
    "tier_1_hot_leaf",
    "tier_2_parser_leaf",
    "tier_2_validator",
    "tier_2_generated_validator",
    "tier_2_metadata_leaf",
    "tier_3_boundary_only",
}
ALLOWED_STATUSES = {
    "production_candidate",
    "prototype_size_candidate",
    "prototype_perf_candidate",
    "planned",
    "exploratory",
}
ALLOWED_FEASIBILITY = {"high", "medium", "low"}


@dataclass(frozen=True)
class SafetyCandidateViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(
    path: Path,
    repo_root: Path,
    p0_registry_path: Path,
) -> tuple[dict[str, Any], list[SafetyCandidateViolation]]:
    try:
        payload = _load_json(path)
    except OSError as exc:
        return {}, [SafetyCandidateViolation("manifest read failed", str(exc))]
    except json.JSONDecodeError as exc:
        return {}, [SafetyCandidateViolation("manifest JSON invalid", str(exc))]
    if not isinstance(payload, dict):
        return {}, [SafetyCandidateViolation("invalid manifest", "top-level value must be object")]

    violations: list[SafetyCandidateViolation] = []
    if payload.get("schema_version") != 1:
        violations.append(SafetyCandidateViolation("invalid schema_version", "expected schema_version 1"))

    criteria = payload.get("selection_criteria")
    if not isinstance(criteria, list) or len(criteria) < 5:
        violations.append(SafetyCandidateViolation("invalid selection_criteria", "expected at least 5 criteria"))

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return payload, violations + [
            SafetyCandidateViolation("invalid candidates", "candidates must be non-empty array")
        ]

    p0_components: set[str] = set()
    if p0_registry_path.exists():
        registry = _load_json(p0_registry_path)
        for component in registry.get("components", []):
            if isinstance(component, dict) and isinstance(component.get("name"), str):
                p0_components.add(component["name"])

    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    previous_score: int | None = None
    for index, candidate in enumerate(candidates):
        violations.extend(_validate_candidate(repo_root, index, candidate, seen_ids, seen_ranks, p0_components))
        if isinstance(candidate, dict):
            score = candidate.get("memory_safety_score")
            if isinstance(score, int) and previous_score is not None and score > previous_score:
                violations.append(
                    SafetyCandidateViolation(
                        "ranking order",
                        f"{candidate.get('id')}: score {score} is higher than previous rank",
                    )
                )
            if isinstance(score, int):
                previous_score = score
    return payload, violations


def build_report(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates", [])
    tier_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for candidate in candidates:
        tier = candidate["tier"]
        status = candidate["status"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": 1,
        "candidate_count": len(candidates),
        "top_memory_safety_candidate": candidates[0]["id"] if candidates else None,
        "tier_counts": tier_counts,
        "status_counts": status_counts,
        "candidates": [
            {
                "rank": candidate["rank"],
                "id": candidate["id"],
                "name": candidate["name"],
                "tier": candidate["tier"],
                "memory_safety_score": candidate["memory_safety_score"],
                "status": candidate["status"],
                "feasibility": candidate["feasibility"],
                "p0_component": candidate.get("p0_component"),
                "next_chromium_task": candidate.get("next_chromium_task"),
            }
            for candidate in candidates
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chromium Rust Safety Candidate Ranking",
        "",
        "Ranking axis: memory safety value. Chromium merge still requires perf, size, differential, fuzz, and rollback gates.",
        "",
        "## Selection Criteria",
        "",
    ]
    lines.extend(f"- {criterion}" for criterion in payload.get("selection_criteria", []))
    lines.extend(["", "## Blocked Areas", ""])
    for blocked in payload.get("blocked_areas", []):
        lines.extend(
            [
                f"### {blocked['area']}",
                "",
                f"- Reason: {blocked['reason']}",
                f"- Examples: `{', '.join(blocked.get('examples', []))}`",
                "",
            ]
        )
    lines.extend(["", "## Ranked Candidates", ""])
    for candidate in payload.get("candidates", []):
        p0_component = candidate.get("p0_component")
        next_task = candidate.get("next_chromium_task")
        lines.extend(
            [
                f"## {candidate['rank']}. {candidate['name']} (`{candidate['id']}`)",
                "",
                f"- Tier: `{candidate['tier']}`",
                f"- Memory safety score: `{candidate['memory_safety_score']}`",
                f"- Status: `{candidate['status']}`",
                f"- Feasibility: `{candidate['feasibility']}`",
                f"- Chromium location: `{candidate['chromium_location']}`",
                f"- P0 component: `{p0_component}`" if p0_component else "- P0 component: `none`",
                f"- Next Chromium task: `{next_task}`" if next_task else "- Next Chromium task: `none`",
                "",
                f"Safety rationale: {candidate['memory_safety_rationale']}",
                "",
                "Typical bug classes:",
                "",
            ]
        )
        lines.extend(f"- {bug_class}" for bug_class in candidate.get("typical_bug_classes", []))
        lines.extend(["", "Do not expand into:", ""])
        lines.extend(f"- {item}" for item in candidate.get("do_not_expand_into", []))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _validate_candidate(
    repo_root: Path,
    index: int,
    candidate: Any,
    seen_ids: set[str],
    seen_ranks: set[int],
    p0_components: set[str],
) -> list[SafetyCandidateViolation]:
    if not isinstance(candidate, dict):
        return [SafetyCandidateViolation("invalid candidate", f"candidates[{index}] must be object")]
    violations: list[SafetyCandidateViolation] = []
    candidate_id = candidate.get("id")
    label = candidate_id if isinstance(candidate_id, str) and candidate_id else f"candidates[{index}]"

    for field in ("id", "name", "chromium_location", "memory_safety_rationale", "roadmap_matrix_area"):
        value = candidate.get(field)
        if not isinstance(value, str) or not value:
            violations.append(SafetyCandidateViolation("missing candidate field", f"{label}: {field}"))

    rank = candidate.get("rank")
    if not isinstance(rank, int) or rank < 1:
        violations.append(SafetyCandidateViolation("invalid rank", f"{label}: {rank!r}"))
    elif rank in seen_ranks:
        violations.append(SafetyCandidateViolation("duplicate rank", f"{label}: {rank}"))
    else:
        seen_ranks.add(rank)

    if not isinstance(candidate_id, str) or not candidate_id:
        violations.append(SafetyCandidateViolation("invalid candidate id", f"candidates[{index}]"))
    elif candidate_id in seen_ids:
        violations.append(SafetyCandidateViolation("duplicate candidate id", candidate_id))
    else:
        seen_ids.add(candidate_id)

    if candidate.get("tier") not in ALLOWED_TIERS:
        violations.append(SafetyCandidateViolation("invalid tier", f"{label}: {candidate.get('tier')!r}"))
    if candidate.get("status") not in ALLOWED_STATUSES:
        violations.append(SafetyCandidateViolation("invalid status", f"{label}: {candidate.get('status')!r}"))
    if candidate.get("feasibility") not in ALLOWED_FEASIBILITY:
        violations.append(
            SafetyCandidateViolation("invalid feasibility", f"{label}: {candidate.get('feasibility')!r}")
        )

    score = candidate.get("memory_safety_score")
    if not isinstance(score, int) or not (0 <= score <= 100):
        violations.append(SafetyCandidateViolation("invalid memory_safety_score", f"{label}: {score!r}"))

    for field in ("typical_bug_classes", "do_not_expand_into", "evidence"):
        value = candidate.get(field)
        if not isinstance(value, list) or not value:
            violations.append(SafetyCandidateViolation("invalid candidate list", f"{label}: {field}"))

    p0_component = candidate.get("p0_component")
    if p0_component is not None:
        if not isinstance(p0_component, str) or not p0_component:
            violations.append(SafetyCandidateViolation("invalid p0_component", f"{label}: {p0_component!r}"))
        elif p0_components and p0_component not in p0_components:
            violations.append(SafetyCandidateViolation("unknown p0_component", f"{label}: {p0_component}"))

    next_task = candidate.get("next_chromium_task")
    if next_task is not None and (not isinstance(next_task, str) or not next_task):
        violations.append(SafetyCandidateViolation("invalid next_chromium_task", f"{label}: {next_task!r}"))

    for evidence in candidate.get("evidence", []):
        if not isinstance(evidence, str) or not evidence:
            violations.append(SafetyCandidateViolation("invalid evidence", f"{label}: {evidence!r}"))
        elif not (repo_root / evidence).exists():
            violations.append(SafetyCandidateViolation("missing evidence", f"{label}: {evidence}"))
    return violations


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--p0-registry", type=Path, default=DEFAULT_P0_REGISTRY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    payload, violations = validate_manifest(args.manifest, Path.cwd(), args.p0_registry)
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        report = build_report(payload)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        args.markdown.write_text(render_markdown(payload), encoding="utf-8")
        print(f"Chromium Rust safety candidates OK: {args.manifest}")
        print(f"Safety candidates report written: {args.report}")
        print(f"Safety candidates Markdown written: {args.markdown}")
        print(f"Top memory-safety candidate: {report['top_memory_safety_candidate']}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))