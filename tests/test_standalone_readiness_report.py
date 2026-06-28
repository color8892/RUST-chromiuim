from __future__ import annotations

from pathlib import Path
import unittest

from tools.emit_standalone_readiness_report import build_readiness_report, render_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]


class StandaloneReadinessReportTest(unittest.TestCase):
    def test_report_summarizes_standalone_status(self) -> None:
        report = build_readiness_report(REPO_ROOT)

        self.assertEqual("standalone_ready_for_chromium_checkout", report["status"])
        self.assertGreater(report["standalone_percent"], 50.0)
        self.assertEqual("needs_chromium_root", report["preflight_status_without_root"])
        self.assertEqual("chromium-preflight", report["next_chromium_task"])
        self.assertEqual(
            "requires --chromium-root before this task can run",
            report["next_chromium_task_blocked_reason"],
        )
        self.assertEqual("http-header-scanner", report["top_memory_safety_candidate"])
        self.assertEqual("blink-css-tokenizer", report["next_planned_safety_candidate"])
        self.assertIn("Android supersize diff", report["external_blockers"])

    def test_markdown_contains_next_commands(self) -> None:
        markdown = render_markdown(build_readiness_report(REPO_ROOT))

        self.assertIn("# Standalone Readiness Report", markdown)
        self.assertIn("chromium-preflight", markdown)
        self.assertIn("python tools/check_chromium_checkout_preflight.py", markdown)
        self.assertIn("External Blockers", markdown)


if __name__ == "__main__":
    unittest.main()
