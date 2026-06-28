from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_chromium_next_tasks import build_report, render_markdown, validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumNextTasksTest(unittest.TestCase):
    def test_repository_next_tasks_are_valid(self) -> None:
        payload, violations = validate_manifest(REPO_ROOT / "chromium_next_tasks.json", REPO_ROOT)
        report = build_report(payload)

        self.assertEqual([], [violation.render() for violation in violations])
        self.assertGreaterEqual(report["task_count"], 5)
        self.assertEqual(report["task_count"], report["status_counts"]["requires_chromium_checkout"])

    def test_markdown_renders_agent_brief(self) -> None:
        payload, violations = validate_manifest(REPO_ROOT / "chromium_next_tasks.json", REPO_ROOT)
        markdown = render_markdown(payload)

        self.assertEqual([], [violation.render() for violation in violations])
        self.assertIn("# Chromium Next Tasks", markdown)
        self.assertIn("chromium-preflight", markdown)
        self.assertIn("Acceptance gates", markdown)

    def test_rejects_unknown_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence.txt"
            evidence.write_text("ok\n", encoding="utf-8")
            manifest = root / "tasks.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "tasks": [
                            {
                                "id": "task-a",
                                "title": "Task A",
                                "phase": "phase",
                                "status": "requires_chromium_checkout",
                                "depends_on": ["missing"],
                                "entry_commands": ["run"],
                                "acceptance_gates": ["pass"],
                                "evidence": ["evidence.txt"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            _, violations = validate_manifest(manifest, root)

        self.assertIn("unknown dependency", {violation.rule for violation in violations})
