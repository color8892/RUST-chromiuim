from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.select_chromium_next_task import probe_completed_task_ids, select_next_task


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

    def test_ready_checkout_selects_gn_target_import(self) -> None:
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
                json.dumps(
                    {
                        "required_chromium_paths": ["build/config/rust.gni"],
                        "default_destination": "third_party/rust/chromium_rust_perf",
                        "files": [],
                        "exclude": [],
                    }
                ),
                encoding="utf-8",
            )

            selection = select_next_task(
                REPO_ROOT,
                REPO_ROOT / "chromium_next_tasks.json",
                manifest,
                chromium_root,
            )

        self.assertEqual("chromium-gn-target-import", selection["selected_task"]["id"])
        self.assertEqual(
            ["chromium-import-dry-run", "chromium-preflight"],
            selection["completed_task_ids"],
        )

    def test_imported_scaffold_marks_gn_target_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chromium_root = root / "chromium" / "src"
            destination = chromium_root / "third_party" / "rust" / "chromium_rust_perf"
            destination.mkdir(parents=True)
            (destination / "BUILD.gn").write_text("# imported\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "default_destination": "third_party/rust/chromium_rust_perf",
                        "required_chromium_paths": ["build/config/rust.gni"],
                        "files": [],
                        "exclude": [],
                    }
                ),
                encoding="utf-8",
            )

            completed = probe_completed_task_ids(
                REPO_ROOT,
                chromium_root,
                manifest,
                {"status": "ready"},
                [],
            )

        self.assertIn("chromium-gn-target-import", completed)

    def test_imported_scaffold_selects_differential_tests(self) -> None:
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
            destination = chromium_root / "third_party" / "rust" / "chromium_rust_perf"
            destination.mkdir(parents=True)
            (destination / "BUILD.gn").write_text("# imported\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "required_chromium_paths": ["build/config/rust.gni"],
                        "default_destination": "third_party/rust/chromium_rust_perf",
                        "files": [],
                        "exclude": [],
                    }
                ),
                encoding="utf-8",
            )

            selection = select_next_task(
                REPO_ROOT,
                REPO_ROOT / "chromium_next_tasks.json",
                manifest,
                chromium_root,
            )

        self.assertEqual("chromium-differential-tests", selection["selected_task"]["id"])
        self.assertIn("chromium-gn-target-import", selection["completed_task_ids"])


if __name__ == "__main__":
    unittest.main()
