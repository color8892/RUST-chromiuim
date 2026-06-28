from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.emit_fuzz_corpus_replay import emit_replay_source


class EmitFuzzCorpusReplayTest(unittest.TestCase):
    def test_emits_seed_arrays_and_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "max_seed_bytes": 128,
                        "components": [
                            {
                                "name": "http_header_scanner",
                                "harness": "cpp_fuzz/main.cc",
                                "required_categories": ["valid"],
                                "seeds": [
                                    {
                                        "name": "basic",
                                        "category": "valid",
                                        "text": "Host: example.test\r\n\r\n",
                                    }
                                ],
                            },
                            {
                                "name": "mojo_validator",
                                "harness": "cpp_fuzz/main.cc",
                                "required_categories": ["valid"],
                                "seeds": [
                                    {
                                        "name": "header",
                                        "category": "valid",
                                        "hex": "1000000000000000",
                                    }
                                ],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            source = emit_replay_source(manifest)

        self.assertIn("static const uint8_t kSeed0[]", source)
        self.assertIn("0x48, 0x6f, 0x73, 0x74", source)
        self.assertIn('"http_header_scanner"', source)
        self.assertIn('"mojo_validator"', source)
        self.assertIn("ReplaySeed", source)


if __name__ == "__main__":
    unittest.main()
