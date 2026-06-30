from __future__ import annotations

from pathlib import Path
import unittest

from tools.emit_progress_report import build_progress_report, render_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]


class ProgressReportTest(unittest.TestCase):
    def test_progress_report_distinguishes_standalone_and_overall(self) -> None:
        report = build_progress_report(REPO_ROOT)

        self.assertGreater(report["standalone_percent"], 50.0)
        self.assertGreater(report["overall_chromium_migration_percent"], 0.0)
        self.assertLess(
            report["overall_chromium_migration_percent"],
            report["standalone_percent"],
        )
        self.assertEqual("chromium-preflight", report["next_task"])

    def test_markdown_contains_percentages_and_blockers(self) -> None:
        markdown = render_markdown(build_progress_report(REPO_ROOT))

        self.assertIn("# Chromium Rust Migration Progress", markdown)
        self.assertIn("Standalone repo readiness", markdown)
        self.assertIn("Overall Chromium migration", markdown)
        self.assertIn("External Blockers", markdown)


if __name__ == "__main__":
    unittest.main()
