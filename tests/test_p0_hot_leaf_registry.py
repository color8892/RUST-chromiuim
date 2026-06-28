from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_p0_hot_leaf_registry import P0HotLeafRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


class P0HotLeafRegistryTest(unittest.TestCase):
    def test_repository_registry_is_valid(self) -> None:
        violations = P0HotLeafRegistry(REPO_ROOT).validate_file(
            REPO_ROOT / "p0_hot_leaf_registry.json"
        )

        self.assertEqual([], [violation.render() for violation in violations])

    def test_rejects_missing_component_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "budgets").mkdir()
            (root / "budgets" / "rust_artifacts_size.json").write_text(
                json.dumps({"artifacts": [{"path": "target/release/missing.rlib"}]}),
                encoding="utf-8",
            )
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "components": [
                            {
                                "name": "missing",
                                "status": "production_candidate",
                                "rust_crate": "missing_crate",
                                "ffi_header": "missing.h",
                                "cpp_adapter": ["missing.cc"],
                                "cpp_baseline": "missing_baseline.h",
                                "perf_budget": "missing_perf.json",
                                "size_artifact": "target/release/missing.rlib",
                                "differential_harness": "missing_test.cc",
                                "benchmark_harness": "missing_bench.cc",
                                "fuzz_harness": "missing_fuzz.cc",
                                "rollback_symbol": "Missing::SetRollbackEnabled",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            violations = P0HotLeafRegistry(root).validate_file(registry)

        self.assertIn("missing path", {violation.rule for violation in violations})


if __name__ == "__main__":
    unittest.main()
