from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_chromium_checkout_preflight import build_preflight_report


class ChromiumCheckoutPreflightTest(unittest.TestCase):
    def test_without_chromium_root_is_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(
                json.dumps({"required_chromium_paths": ["build/config/rust.gni"]}),
                encoding="utf-8",
            )

            report, violations = build_preflight_report(None, manifest)

        self.assertEqual([], violations)
        self.assertEqual("needs_chromium_root", report["status"])
        self.assertGreater(len(report["next_commands"]), 0)

    def test_ready_fake_checkout_passes_required_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chromium_root = root / "chromium" / "src"
            for relative in [
                "build/config/rust.gni",
                "mojo",
                "third_party/blink",
                "v8",
            ]:
                path = chromium_root / relative
                if "." in path.name:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("# fake\n", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"required_chromium_paths": ["build/config/rust.gni"]}),
                encoding="utf-8",
            )

            report, violations = build_preflight_report(chromium_root, manifest)

        self.assertEqual([], [violation.render() for violation in violations])
        self.assertEqual("ready", report["status"])

    def test_missing_required_path_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chromium_root = root / "chromium" / "src"
            chromium_root.mkdir(parents=True)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"required_chromium_paths": ["build/config/rust.gni"]}),
                encoding="utf-8",
            )

            report, violations = build_preflight_report(chromium_root, manifest)

        self.assertEqual("blocked", report["status"])
        self.assertIn("missing required Chromium path", {violation.rule for violation in violations})


if __name__ == "__main__":
    unittest.main()
