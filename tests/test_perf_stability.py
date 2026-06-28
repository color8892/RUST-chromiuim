from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.check_perf_stability import check_perf_stability


class PerfStabilityTest(unittest.TestCase):
    def test_repository_perf_stability_settings_are_valid(self) -> None:
        violations = check_perf_stability(Path("tools/run_cpp_bench.ps1"), 21)

        self.assertEqual([], [violation.render() for violation in violations])

    def test_rejects_low_sample_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = Path(tmp) / "run_cpp_bench.ps1"
            runner.write_text(
                """
& $outputExe --mode header --json $headerReport --samples 3
& $outputExe --mode url --json $urlReport --samples 21
& $outputExe --mode mojo --json $mojoReport --samples 21
""",
                encoding="utf-8",
            )

            violations = check_perf_stability(runner, 21)

        self.assertIn("benchmark samples below minimum", {violation.rule for violation in violations})


if __name__ == "__main__":
    unittest.main()
