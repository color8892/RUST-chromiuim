from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.rust_size_gate import ArtifactSizeGate, BudgetFile, CargoLockGate, CargoMetadataGate


class RustSizeGateTest(unittest.TestCase):
    def test_measures_artifact_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact.lib"
            artifact.write_bytes(b"12345")

            measurements, violations = ArtifactSizeGate().measure([artifact])

            self.assertEqual([], violations)
            self.assertEqual(5, measurements[0].size_bytes)

    def test_reports_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.lib"

            measurements, violations = ArtifactSizeGate().measure([missing])

            self.assertEqual([], measurements)
            self.assertEqual("missing artifact", violations[0].rule)

    def test_enforces_budget_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.lib"
            budget = root / "budget.json"
            artifact.write_bytes(b"123456")
            budget.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "path": str(artifact),
                                "max_bytes": 5,
                                "baseline_bytes": 3,
                                "max_growth_bytes": 2,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            budgets = BudgetFile.load(budget)
            measurements, measure_violations = ArtifactSizeGate().measure([artifact])
            budget_violations = ArtifactSizeGate().check_budgets(
                measurements, budgets, max_total_bytes=None
            )

            self.assertEqual([], measure_violations)
            self.assertEqual(
                {"artifact size exceeded", "artifact growth exceeded"},
                {violation.rule for violation in budget_violations},
            )

    def test_enforces_total_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "a.lib"
            second = Path(tmp) / "b.lib"
            first.write_bytes(b"123")
            second.write_bytes(b"456")

            measurements, violations = ArtifactSizeGate().measure([first, second])
            violations.extend(
                ArtifactSizeGate().check_budgets(measurements, [], max_total_bytes=5)
            )

            self.assertEqual("total size exceeded", violations[0].rule)

    def test_counts_registry_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "Cargo.lock"
            lockfile.write_text(
                '\n'.join(
                    [
                        "[[package]]",
                        'name = "local"',
                        "[[package]]",
                        'name = "external"',
                        'source = "registry+https://github.com/rust-lang/crates.io-index"',
                    ]
                ),
                encoding="utf-8",
            )

            count, violations = CargoLockGate().check(lockfile, max_registry_packages=0)

            self.assertEqual(1, count)
            self.assertEqual("registry dependency budget exceeded", violations[0].rule)

    def test_counts_only_reachable_metadata_registry_dependencies(self) -> None:
        metadata = {
            "packages": [
                {"id": "path+root", "name": "root", "source": None},
                {"id": "path+local", "name": "local", "source": None},
                {
                    "id": "registry+used",
                    "name": "used",
                    "source": "registry+https://github.com/rust-lang/crates.io-index",
                },
                {
                    "id": "registry+unused",
                    "name": "unused",
                    "source": "registry+https://github.com/rust-lang/crates.io-index",
                },
            ],
            "resolve": {
                "nodes": [
                    {
                        "id": "path+root",
                        "deps": [{"pkg": "path+local"}, {"pkg": "registry+used"}],
                    },
                    {"id": "path+local", "deps": []},
                    {"id": "registry+used", "deps": []},
                    {"id": "registry+unused", "deps": []},
                ]
            },
        }
        completed = mock.Mock(stdout=json.dumps(metadata))

        with mock.patch("tools.rust_size_gate.subprocess.run", return_value=completed) as run:
            count, violations = CargoMetadataGate().check(
                "root",
                no_default_features=True,
                features=[],
                max_registry_packages=0,
            )

        self.assertEqual(1, count)
        self.assertEqual("registry dependency budget exceeded", violations[0].rule)
        run.assert_called_once()
        self.assertIn("--no-default-features", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
