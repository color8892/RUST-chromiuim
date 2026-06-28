#!/usr/bin/env python3
"""Emit a standalone dry-run report for the Chromium import manifest."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_MANIFEST = Path("chromium_import_manifest.json")
DEFAULT_OUTPUT = Path("target/reports/chromium_import_report.json")


def _is_excluded(relative_path: str, patterns: Sequence[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    for pattern in patterns:
        if normalized == pattern or fnmatch.fnmatch(normalized, pattern):
            return True
        if normalized.startswith(f"{pattern}/"):
            return True
    return False


def build_report(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files: list[dict[str, Any]] = []
    missing_entries: list[str] = []
    exclude = manifest.get("exclude", [])
    for entry in manifest["files"]:
        source = repo_root / entry
        if not source.exists():
            missing_entries.append(entry)
            continue
        if source.is_dir():
            for child in source.rglob("*"):
                if child.is_file():
                    relative = child.relative_to(repo_root).as_posix()
                    if not _is_excluded(relative, exclude):
                        files.append({"source": relative, "destination": relative})
        else:
            relative = source.relative_to(repo_root).as_posix()
            if not _is_excluded(relative, exclude):
                files.append({"source": relative, "destination": relative})

    return {
        "schema_version": 1,
        "manifest": str(manifest_path),
        "default_destination": manifest["default_destination"],
        "required_chromium_paths": manifest["required_chromium_paths"],
        "file_count": len(files),
        "missing_entries": missing_entries,
        "files": sorted(files, key=lambda item: item["source"]),
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    report = build_report(Path.cwd(), args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Chromium import dry-run report written: {args.output}")
    print(f"Files: {report['file_count']} Missing entries: {len(report['missing_entries'])}")
    return 1 if report["missing_entries"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
