from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class StandaloneReadinessRunnerTest(unittest.TestCase):
    def test_runner_invokes_required_lightweight_gates(self) -> None:
        script = (REPO_ROOT / "tools" / "run_standalone_readiness.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("python -m unittest discover -s tests", script)
        self.assertIn("tools/check_p0_hot_leaf_registry.py", script)
        self.assertIn("tools/check_chromium_import_consistency.py", script)
        self.assertIn("tools/check_chromium_checkout_preflight.py", script)
        self.assertIn("tools/emit_standalone_readiness_report.py", script)

    def test_runner_does_not_replace_heavy_ci(self) -> None:
        script = (REPO_ROOT / "tools" / "run_standalone_readiness.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("does not replace", script)
        self.assertNotIn("tools/run_cpp_bench.ps1", script)
        self.assertNotIn("tools/run_local_fuzz.ps1", script)


if __name__ == "__main__":
    unittest.main()
