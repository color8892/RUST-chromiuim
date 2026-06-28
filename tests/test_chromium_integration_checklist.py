from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_chromium_integration_checklist import build_report, validate_checklist


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumIntegrationChecklistTest(unittest.TestCase):
    def test_repository_checklist_is_valid(self) -> None:
        payload, violations = validate_checklist(
            REPO_ROOT / "chromium_integration_checklist.json",
            REPO_ROOT,
        )
        report = build_report(payload)

        self.assertEqual([], [violation.render() for violation in violations])
        self.assertEqual(2, report["phase_count"])
        self.assertGreater(report["item_status_counts"]["complete"], 0)
        self.assertGreater(report["item_status_counts"]["requires_chromium_checkout"], 0)

    def test_rejects_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checklist = root / "checklist.json"
            checklist.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "phases": [
                            {
                                "name": "standalone",
                                "status": "complete",
                                "items": [
                                    {
                                        "name": "missing",
                                        "status": "complete",
                                        "evidence": ["missing.txt"],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            _, violations = validate_checklist(checklist, root)

        self.assertIn("missing evidence", {violation.rule for violation in violations})


if __name__ == "__main__":
    unittest.main()
