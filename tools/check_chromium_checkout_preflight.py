#!/usr/bin/env python3
"""Emit and validate a Chromium checkout preflight report."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_IMPORT_MANIFEST = Path("chromium_import_manifest.json")
DEFAULT_OUTPUT = Path("target/reports/chromium_checkout_preflight.json")

REQUIRED_PATHS = [
    "build/config/rust.gni",
    "mojo",
    "third_party/blink",
    "v8",
]

OPTIONAL_BUT_EXPECTED_PATHS = [
    "build/android",
    "testing/libfuzzer",
    "third_party/blink/web_tests",
    "tools/binary_size/supersize.py",
    "tools/mb/mb.py",
]


@dataclass(frozen=True)
class PreflightViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def build_preflight_report(
    chromium_root: Path | None,
    import_manifest_path: Path,
) -> tuple[dict[str, Any], list[PreflightViolation]]:
    manifest = json.loads(import_manifest_path.read_text(encoding="utf-8"))
    required_paths = list(dict.fromkeys(manifest.get("required_chromium_paths", []) + REQUIRED_PATHS))
    report: dict[str, Any] = {
        "schema_version": 1,
        "chromium_root": str(chromium_root) if chromium_root is not None else None,
        "status": "needs_chromium_root",
        "required": [],
        "optional": [],
        "next_commands": [],
    }
    if chromium_root is None:
        report["next_commands"] = [
            "python tools/check_chromium_checkout_preflight.py --chromium-root C:\\path\\to\\chromium\\src",
            "powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 -ChromiumRoot C:\\path\\to\\chromium\\src -DryRun",
        ]
        return report, []

    violations: list[PreflightViolation] = []
    root_exists = chromium_root.exists() and chromium_root.is_dir()
    report["root_exists"] = root_exists
    if not root_exists:
        report["status"] = "blocked"
        return report, [PreflightViolation("missing chromium root", str(chromium_root))]

    missing_required: list[str] = []
    for relative in required_paths:
        exists = (chromium_root / relative).exists()
        report["required"].append({"path": relative, "exists": exists})
        if not exists:
            missing_required.append(relative)
            violations.append(PreflightViolation("missing required Chromium path", relative))

    for relative in OPTIONAL_BUT_EXPECTED_PATHS:
        exists = (chromium_root / relative).exists()
        report["optional"].append({"path": relative, "exists": exists})

    report["status"] = "ready" if not missing_required else "blocked"
    report["next_commands"] = [
        f"powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 -ChromiumRoot {chromium_root} -DryRun",
        f"powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 -ChromiumRoot {chromium_root}",
        "gn gen out/rust-perf",
        "autoninja -C out/rust-perf //third_party/rust/chromium_rust_perf:rust_perf_unittests",
        "tools/binary_size/supersize.py archive --output-directory out/rust-perf size-after.size",
    ]
    return report, violations


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium-root", type=Path)
    parser.add_argument("--import-manifest", type=Path, default=DEFAULT_IMPORT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    report, violations = build_preflight_report(args.chromium_root, args.import_manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    print(f"Chromium checkout preflight report written: {args.output}")
    print(f"Status: {report['status']}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
