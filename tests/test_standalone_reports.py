from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.emit_chromium_import_report import build_report as build_import_report
from tools.emit_fuzz_corpus_report import build_report as build_fuzz_report
from tools.emit_p0_artifact_summary import build_summary
from tools.emit_rollback_gate import ROLLBACK_SOURCE


REPO_ROOT = Path(__file__).resolve().parents[1]


class StandaloneReportsTest(unittest.TestCase):
    def test_repository_fuzz_corpus_report_counts_categories(self) -> None:
        report = build_fuzz_report(REPO_ROOT / "fuzz_corpus_manifest.json")

        self.assertEqual(4, report["component_count"])
        self.assertGreaterEqual(report["seed_count"], 19)
        for component in report["components"]:
            self.assertEqual([], component["missing_categories"])
            self.assertGreater(component["seed_count"], 0)

    def test_artifact_summary_joins_registry_fuzz_and_size_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact.lib"
            artifact.write_bytes(b"1234")
            registry = root / "registry.json"
            fuzz = root / "fuzz.json"
            size = root / "size.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "components": [
                            {
                                "name": "http_header_scanner",
                                "status": "production_candidate",
                                "rust_crate": "rust/http",
                                "ffi_header": "include/http.h",
                                "cpp_adapter": ["cpp/http.cc"],
                                "perf_budget": "budgets/http.json",
                                "size_artifact": str(artifact),
                                "rollback_symbol": "HttpHeaderScanner::SetRollbackEnabled",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            fuzz.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "components": [
                            {
                                "name": "http_header_scanner",
                                "required_categories": ["valid"],
                                "seeds": [{"name": "a", "category": "valid", "text": "x"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            size.write_text(
                json.dumps({"artifacts": [{"path": str(artifact), "max_bytes": 8}]}),
                encoding="utf-8",
            )

            summary = build_summary(registry, fuzz, size)

        component = summary["components"][0]
        self.assertTrue(component["size_artifact_exists"])
        self.assertEqual(4, component["size_bytes"])
        self.assertEqual(1, component["fuzz_seed_count"])

    def test_import_report_excludes_generated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "keep.cc").write_text("// keep\n", encoding="utf-8")
            (root / "src" / "drop.obj").write_text("obj\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "default_destination": "third_party/rust/test",
                        "required_chromium_paths": ["build/config/rust.gni"],
                        "files": ["src"],
                        "exclude": ["*.obj"],
                    }
                ),
                encoding="utf-8",
            )

            report = build_import_report(root, manifest)

        self.assertEqual(1, report["file_count"])
        self.assertEqual("src/keep.cc", report["files"][0]["source"])

    def test_rollback_generator_covers_all_p0_components(self) -> None:
        self.assertIn("TestHttpRollback", ROLLBACK_SOURCE)
        self.assertIn("TestUrlRollback", ROLLBACK_SOURCE)
        self.assertIn("TestMojoRollback", ROLLBACK_SOURCE)
        self.assertIn("TestCssRollback", ROLLBACK_SOURCE)
        self.assertIn("SetRollbackEnabled(true)", ROLLBACK_SOURCE)


if __name__ == "__main__":
    unittest.main()
