from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.emit_reports_manifest import REPORTS, build_manifest


class ReportsManifestTest(unittest.TestCase):
    def test_manifest_reports_missing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_manifest(Path(tmp))

        self.assertEqual(len(REPORTS), manifest["report_count"])
        self.assertFalse(manifest["reports"][0]["json_exists"])

    def test_manifest_reports_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for report in REPORTS:
                json_path = root / report["json"]
                json_path.parent.mkdir(parents=True, exist_ok=True)
                json_path.write_text("{}\n", encoding="utf-8")
                if report["markdown"] is not None:
                    md_path = root / report["markdown"]
                    md_path.write_text("# report\n", encoding="utf-8")

            manifest = build_manifest(root)

        self.assertTrue(all(report["json_exists"] for report in manifest["reports"]))
        self.assertNotIn(False, [report["markdown_exists"] for report in manifest["reports"]])


if __name__ == "__main__":
    unittest.main()
