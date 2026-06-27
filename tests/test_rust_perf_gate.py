from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.rust_perf_gate import BenchmarkReport, PerfBudgetFile, PerfGate


class RustPerfGateTest(unittest.TestCase):
    def test_loads_benchmark_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "bench.json"
            report.write_text(
                json.dumps(
                    {
                        "iterations": 10,
                        "benchmarks": [
                            {
                                "name": "Large Header",
                                "rust_ns": 300.0,
                                "cpp_ns": 450.0,
                                "speedup": 1.5,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            measurements = BenchmarkReport.load(report)

            self.assertEqual("Large Header", measurements[0].name)
            self.assertEqual(1.5, measurements[0].speedup)

    def test_default_min_speedup_fails_slow_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "bench.json"
            report.write_text(
                json.dumps(
                    {
                        "benchmarks": [
                            {
                                "name": "Malformed Header",
                                "rust_ns": 15.0,
                                "cpp_ns": 14.0,
                                "speedup": 0.93,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            violations = PerfGate().check(
                BenchmarkReport.load(report), [], default_min_speedup=1.0
            )

            self.assertEqual("speedup below default", violations[0].rule)

    def test_budget_file_enforces_latency_and_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "bench.json"
            budget = root / "budget.json"
            report.write_text(
                json.dumps(
                    {
                        "benchmarks": [
                            {
                                "name": "Small Header",
                                "rust_ns": 31.0,
                                "cpp_ns": 32.0,
                                "speedup": 1.03,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            budget.write_text(
                json.dumps(
                    {
                        "benchmarks": [
                            {
                                "name": "Small Header",
                                "min_speedup": 1.05,
                                "max_rust_ns": 30.0,
                                "baseline_rust_ns": 28.0,
                                "max_regression_percent": 5.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            violations = PerfGate().check(
                BenchmarkReport.load(report),
                PerfBudgetFile.load(budget),
                default_min_speedup=None,
            )

            self.assertEqual(
                {
                    "speedup below budget",
                    "latency above budget",
                    "latency regression above budget",
                },
                {violation.rule for violation in violations},
            )

    def test_missing_benchmark_fails_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "bench.json"
            budget = root / "budget.json"
            report.write_text(json.dumps({"benchmarks": []}), encoding="utf-8")
            budget.write_text(
                json.dumps({"benchmarks": [{"name": "Large Header"}]}), encoding="utf-8"
            )

            violations = PerfGate().check(
                BenchmarkReport.load(report),
                PerfBudgetFile.load(budget),
                default_min_speedup=None,
            )

            self.assertEqual("missing benchmark", violations[0].rule)


if __name__ == "__main__":
    unittest.main()
