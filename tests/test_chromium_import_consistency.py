from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_chromium_import_consistency import check_consistency


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumImportConsistencyTest(unittest.TestCase):
    def test_repository_import_consistency_is_valid(self) -> None:
        violations = check_consistency(
            REPO_ROOT / "p0_hot_leaf_registry.json",
            REPO_ROOT / "BUILD.gn",
            REPO_ROOT / "chromium_import_manifest.json",
        )

        self.assertEqual([], [violation.render() for violation in violations])

    def test_rejects_missing_gn_adapter_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.json"
            build = root / "BUILD.gn"
            manifest = root / "manifest.json"
            registry.write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "name": "http_header_scanner",
                                "rust_crate": "rust/hot_leaf/http_header_scanner",
                                "ffi_header": "include/http.h",
                                "cpp_adapter": ["cpp/missing.cc"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            build.write_text(
                """
import("//build/config/rust.gni")
source_set("rust_perf_adapters") {
  public = [ "include/http.h" ]
}
rust_static_library("chromium_rust_perf_bridge") {}
rust_library("chromium_rust_http_header_scanner") {
  crate_root = "rust/hot_leaf/http_header_scanner/src/lib.rs"
}
""",
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            "BUILD.gn",
                            "chromium_integration_checklist.json",
                            "rust",
                            "cpp",
                            "include",
                            "tools",
                        ],
                        "exclude": ["target", "*.obj", "*.exe", "*.lib", "*.rlib"],
                    }
                ),
                encoding="utf-8",
            )

            violations = check_consistency(registry, build, manifest)

        self.assertIn("missing GN adapter source", {violation.rule for violation in violations})
