from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_fuzz_corpus_manifest import FuzzCorpusManifest


REPO_ROOT = Path(__file__).resolve().parents[1]


class FuzzCorpusManifestTest(unittest.TestCase):
    def test_repository_manifest_is_valid(self) -> None:
        violations = FuzzCorpusManifest(REPO_ROOT).validate_file(
            REPO_ROOT / "fuzz_corpus_manifest.json"
        )

        self.assertEqual([], [violation.render() for violation in violations])

    def test_rejects_missing_required_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fuzz.cc").write_text("// fuzz harness\n", encoding="utf-8")
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "components": [{"name": "http_header_scanner"}],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "max_seed_bytes": 128,
                        "components": [
                            {
                                "name": "http_header_scanner",
                                "harness": "fuzz.cc",
                                "required_categories": ["valid", "malformed"],
                                "seeds": [
                                    {
                                        "name": "valid_basic",
                                        "category": "valid",
                                        "text": "Host: example.test\r\n\r\n",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            violations = FuzzCorpusManifest(root, root / "registry.json").validate_file(manifest)

        self.assertIn("missing seed category", {violation.rule for violation in violations})

    def test_rejects_invalid_hex_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fuzz.cc").write_text("// fuzz harness\n", encoding="utf-8")
            (root / "registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "components": [{"name": "mojo_validator"}],
                    }
                ),
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "max_seed_bytes": 128,
                        "components": [
                            {
                                "name": "mojo_validator",
                                "harness": "fuzz.cc",
                                "required_categories": ["valid"],
                                "seeds": [
                                    {
                                        "name": "bad_hex",
                                        "category": "valid",
                                        "hex": "not-hex",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            violations = FuzzCorpusManifest(root, root / "registry.json").validate_file(manifest)

        self.assertIn("invalid seed hex", {violation.rule for violation in violations})


if __name__ == "__main__":
    unittest.main()
