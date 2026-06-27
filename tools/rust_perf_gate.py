#!/usr/bin/env python3
"""Performance gate for local C++/Rust benchmark JSON reports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


@dataclass(frozen=True)
class PerfViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class BenchmarkMeasurement:
    name: str
    rust_ns: float
    cpp_ns: float
    speedup: float

    @staticmethod
    def from_json(item: dict[str, Any], index: int) -> "BenchmarkMeasurement":
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"benchmarks[{index}].name must be a non-empty string")
        rust_ns = _number(item, "rust_ns", index)
        cpp_ns = _number(item, "cpp_ns", index)
        speedup = _number(item, "speedup", index)
        if rust_ns <= 0 or cpp_ns <= 0 or speedup <= 0:
            raise ValueError(f"benchmarks[{index}] values must be positive")
        return BenchmarkMeasurement(name=name, rust_ns=rust_ns, cpp_ns=cpp_ns, speedup=speedup)


@dataclass(frozen=True)
class BenchmarkBudget:
    name: str
    min_speedup: float | None = None
    max_rust_ns: float | None = None
    baseline_rust_ns: float | None = None
    max_regression_percent: float | None = None

    @staticmethod
    def from_json(item: dict[str, Any], index: int) -> "BenchmarkBudget":
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"benchmarks[{index}].name must be a non-empty string")
        return BenchmarkBudget(
            name=name,
            min_speedup=_optional_number(item, "min_speedup", index),
            max_rust_ns=_optional_number(item, "max_rust_ns", index),
            baseline_rust_ns=_optional_number(item, "baseline_rust_ns", index),
            max_regression_percent=_optional_number(item, "max_regression_percent", index),
        )

    def validate(self) -> list[PerfViolation]:
        violations: list[PerfViolation] = []
        for label, value in (
            ("min_speedup", self.min_speedup),
            ("max_rust_ns", self.max_rust_ns),
            ("baseline_rust_ns", self.baseline_rust_ns),
            ("max_regression_percent", self.max_regression_percent),
        ):
            if value is not None and value < 0:
                violations.append(
                    PerfViolation("invalid benchmark budget", f"{self.name}: {label} must be >= 0")
                )
        return violations


class BenchmarkReport:
    @staticmethod
    def load(path: Path) -> list[BenchmarkMeasurement]:
        payload = _load_json_object(path, "benchmark report")
        raw_benchmarks = payload.get("benchmarks")
        if not isinstance(raw_benchmarks, list):
            raise ValueError("benchmark report must contain a benchmarks array")
        return [
            BenchmarkMeasurement.from_json(item, index)
            for index, item in enumerate(_objects(raw_benchmarks, "benchmarks"))
        ]


class PerfBudgetFile:
    @staticmethod
    def load(path: Path) -> list[BenchmarkBudget]:
        payload = _load_json_object(path, "performance budget")
        raw_benchmarks = payload.get("benchmarks")
        if not isinstance(raw_benchmarks, list):
            raise ValueError("performance budget must contain a benchmarks array")
        return [
            BenchmarkBudget.from_json(item, index)
            for index, item in enumerate(_objects(raw_benchmarks, "benchmarks"))
        ]


class PerfGate:
    def check(
        self,
        measurements: Sequence[BenchmarkMeasurement],
        budgets: Sequence[BenchmarkBudget],
        default_min_speedup: float | None,
    ) -> list[PerfViolation]:
        violations: list[PerfViolation] = []
        measurement_by_name = {measurement.name: measurement for measurement in measurements}

        if default_min_speedup is not None:
            for measurement in measurements:
                if measurement.speedup < default_min_speedup:
                    violations.append(
                        PerfViolation(
                            "speedup below default",
                            f"{measurement.name}: {measurement.speedup:.4f}x < {default_min_speedup:.4f}x",
                        )
                    )

        for budget in budgets:
            violations.extend(budget.validate())
            measurement = measurement_by_name.get(budget.name)
            if measurement is None:
                violations.append(PerfViolation("missing benchmark", budget.name))
                continue
            violations.extend(self._check_one(measurement, budget))
        return violations

    @staticmethod
    def _check_one(
        measurement: BenchmarkMeasurement, budget: BenchmarkBudget
    ) -> list[PerfViolation]:
        violations: list[PerfViolation] = []
        if budget.min_speedup is not None and measurement.speedup < budget.min_speedup:
            violations.append(
                PerfViolation(
                    "speedup below budget",
                    f"{measurement.name}: {measurement.speedup:.4f}x < {budget.min_speedup:.4f}x",
                )
            )
        if budget.max_rust_ns is not None and measurement.rust_ns > budget.max_rust_ns:
            violations.append(
                PerfViolation(
                    "latency above budget",
                    f"{measurement.name}: {measurement.rust_ns:.4f} ns > {budget.max_rust_ns:.4f} ns",
                )
            )
        if budget.baseline_rust_ns is not None and budget.max_regression_percent is not None:
            allowed = budget.baseline_rust_ns * (1.0 + budget.max_regression_percent / 100.0)
            if measurement.rust_ns > allowed:
                violations.append(
                    PerfViolation(
                        "latency regression above budget",
                        f"{measurement.name}: {measurement.rust_ns:.4f} ns > {allowed:.4f} ns",
                    )
                )
        return violations


def _objects(items: list[Any], label: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{index}] must be an object")
        result.append(item)
    return result


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be an object")
    return payload


def _number(item: dict[str, Any], key: str, index: int) -> float:
    value = item.get(key)
    if not isinstance(value, int | float):
        raise ValueError(f"benchmarks[{index}].{key} must be a number")
    return float(value)


def _optional_number(item: dict[str, Any], key: str, index: int) -> float | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise ValueError(f"benchmarks[{index}].{key} must be a number")
    return float(value)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--budget-file", type=Path)
    parser.add_argument("--default-min-speedup", type=float)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    measurements = BenchmarkReport.load(args.report)
    budgets = PerfBudgetFile.load(args.budget_file) if args.budget_file else []
    violations = PerfGate().check(measurements, budgets, args.default_min_speedup)

    for measurement in measurements:
        print(
            f"{measurement.name}: rust={measurement.rust_ns:.4f}ns "
            f"cpp={measurement.cpp_ns:.4f}ns speedup={measurement.speedup:.4f}x"
        )
    for violation in violations:
        print(violation.render(), file=sys.stderr)

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
