from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumImportTest(unittest.TestCase):
    def test_manifest_lists_required_scaffold_and_excludes_artifacts(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "chromium_import_manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual(
            "third_party/rust/chromium_rust_perf",
            manifest["default_destination"],
        )
        self.assertIn("build/config/rust.gni", manifest["required_chromium_paths"])
        self.assertIn("rust", manifest["files"])
        self.assertIn("include", manifest["files"])
        self.assertIn("tools", manifest["files"])
        self.assertIn("*.lib", manifest["exclude"])
        self.assertIn("target", manifest["exclude"])

    def test_prepare_chromium_import_dry_run(self) -> None:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is required for import dry-run test")

        with tempfile.TemporaryDirectory() as tmp:
            chromium_root = Path(tmp) / "chromium" / "src"
            (chromium_root / "build" / "config").mkdir(parents=True)
            (chromium_root / "build" / "config" / "rust.gni").write_text(
                "# fake rust.gni\n",
                encoding="utf-8",
            )
            (chromium_root / "third_party" / "blink").mkdir(parents=True)
            (chromium_root / "v8").mkdir()
            (chromium_root / "mojo").mkdir()

            completed = subprocess.run(
                [
                    powershell,
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(REPO_ROOT / "tools" / "prepare_chromium_import.ps1"),
                    "-ChromiumRoot",
                    str(chromium_root),
                    "-DryRun",
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Mode:          dry-run", completed.stdout)
            self.assertIn("No files were copied.", completed.stdout)
            self.assertFalse(
                (chromium_root / "third_party" / "rust" / "chromium_rust_perf").exists()
            )


if __name__ == "__main__":
    unittest.main()
