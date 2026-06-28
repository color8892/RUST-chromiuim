from __future__ import annotations

from pathlib import Path
import unittest

from tools.emit_chromium_cl_handoff import build_handoff, render_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumClHandoffTest(unittest.TestCase):
    def test_handoff_identifies_first_component_and_external_gates(self) -> None:
        handoff = build_handoff(REPO_ROOT)

        self.assertEqual(1, handoff["schema_version"])
        self.assertIn(
            handoff["recommended_first_component"],
            {"http_header_scanner", "url_canonicalizer"},
        )
        self.assertGreater(handoff["import_file_count"], 0)
        self.assertIn("Android supersize diff", handoff["external_gates_not_satisfied_in_this_repo"])

    def test_markdown_contains_commands_and_rollback_plan(self) -> None:
        markdown = render_markdown(build_handoff(REPO_ROOT))

        self.assertIn("# Chromium CL Handoff Package", markdown)
        self.assertIn("gn gen out/rust-perf", markdown)
        self.assertIn("tools/run_rollback_gate.ps1", markdown)
        self.assertIn("External Gates Not Satisfied Here", markdown)


if __name__ == "__main__":
    unittest.main()
