#!/usr/bin/env python3
"""Validate benchmark stability settings for standalone P0 gates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Sequence


DEFAULT_RUNNER = Path("tools/run_cpp_bench.ps1")
DEFAULT_MIN_SAMPLES = 21
REQUIRED_BUDGETS = [
    Path("budgets/http_header_scanner_perf.json"),
    Path("budgets/url_canonicalizer_perf.json"),
    Path("budgets/mojo_validator_perf.json"),
    Path("budgets/css_tokenizer_perf.json"),
    Path("budgets/cookie_canonicalizer_perf.json"),
]


@dataclass(frozen=True)
class StabilityViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def check_perf_stability(runner: Path, min_samples: int) -> list[StabilityViolation]:
    violations: list[StabilityViolation] = []
    try:
        text = runner.read_text(encoding="utf-8")
    except OSError as exc:
        return [StabilityViolation("runner read failed", str(exc))]

    for mode in ("header", "url", "mojo", "css", "cookie"):
        pattern = re.compile(rf"--mode\s+{re.escape(mode)}\s+--json\s+\$[A-Za-z]+Report\s+--samples\s+(\d+)")
        match = pattern.search(text)
        if not match:
            violations.append(StabilityViolation("missing benchmark samples", mode))
            continue
        samples = int(match.group(1))
        if samples < min_samples:
            violations.append(
                StabilityViolation(
                    "benchmark samples below minimum",
                    f"{mode}: {samples} < {min_samples}",
                )
            )

    for budget in REQUIRED_BUDGETS:
        if not budget.exists():
            violations.append(StabilityViolation("missing perf budget", str(budget)))
            continue
        try:
            payload = json.loads(budget.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(StabilityViolation("invalid perf budget JSON", f"{budget}: {exc}"))
            continue
        benchmarks = payload.get("benchmarks")
        if not isinstance(benchmarks, list) or not benchmarks:
            violations.append(StabilityViolation("empty perf budget", str(budget)))

    return violations


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    violations = check_perf_stability(args.runner, args.min_samples)
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        print(f"Perf stability settings OK: min_samples={args.min_samples}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
