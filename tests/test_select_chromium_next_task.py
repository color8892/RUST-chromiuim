from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.select_chromium_next_task import select_next_task


REPO_ROOT = Path(__file__).resolve().parents[1]


class SelectChromiumNextTaskTest(unittest.TestCase):
    def test_without_chromium_root_selects_preflight(self) -> None:
        selection = select_next_task(
            REPO_ROOT,
            REPO_ROOT / "chromium_next_tasks.json",
            REPO_ROOT / "chromium_import_manifest.json",
            None,
        )

        self.assertEqual("chromium-preflight", selection["selected_task"]["id"])
        self.assertEqual("needs_chromium_root", selection["preflight_status"])
        self.assertEqual(
            "requires --chromium-root before this task can run",
            selection["selected_task"]["blocked_reason"],
        )

    def test_ready_checkout_selects_import_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chromium_root = root / "chromium" / "src"
            for relative in ["build/config/rust.gni", "mojo", "third_party/blink", "v8"]:
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

            selection = select_next_task(
                REPO_ROOT,
                REPO_ROOT / "chromium_next_tasks.json",
                manifest,
                chromium_root,
            )

        self.assertEqual("chromium-import-dry-run", selection["selected_task"]["id"])
        self.assertEqual(["chromium-preflight"], selection["completed_task_ids"])


if __name__ == "__main__":
    unittest.main()
