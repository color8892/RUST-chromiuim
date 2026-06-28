from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.chromium_checkout_config import default_config, load_config, resolve_chromium_root


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumCheckoutConfigTest(unittest.TestCase):
    def test_default_config_uses_standard_windows_paths(self) -> None:
        config = default_config(REPO_ROOT)

        self.assertEqual(r"C:\src\chromium\src", config["chromium_root"])
        self.assertEqual(r"C:\src\depot_tools", config["depot_tools"])

    def test_resolve_chromium_root_prefers_explicit_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "custom" / "src"
            explicit.mkdir(parents=True)

            resolved = resolve_chromium_root(REPO_ROOT, explicit)

        self.assertEqual(explicit, resolved)

    def test_load_config_reads_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "chromium_checkout.local.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "chromium_root": "D:\\chromium\\src",
                        "depot_tools": "D:\\depot_tools",
                        "checkout_parent": "D:\\chromium",
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(root, config_path)

        self.assertEqual("D:\\chromium\\src", config["chromium_root"])


if __name__ == "__main__":
    unittest.main()