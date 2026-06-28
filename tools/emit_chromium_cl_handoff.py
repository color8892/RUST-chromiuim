#!/usr/bin/env python3
"""Emit the first Chromium CL handoff package for this standalone scaffold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.emit_chromium_import_report import build_report as build_import_report
from tools.emit_p0_artifact_summary import build_summary as build_artifact_summary


DEFAULT_OUTPUT_JSON = Path("target/reports/chromium_cl_handoff.json")
DEFAULT_OUTPUT_MD = Path("target/reports/chromium_cl_handoff.md")


def build_handoff(repo_root: Path) -> dict[str, Any]:
    import_report = build_import_report(repo_root, repo_root / "chromium_import_manifest.json")
    artifact_summary = build_artifact_summary(
        repo_root / "p0_hot_leaf_registry.json",
        repo_root / "fuzz_corpus_manifest.json",
        repo_root / "budgets" / "rust_artifacts_size.json",
    )
    production_candidates = [
        component
        for component in artifact_summary["components"]
        if component["status"] == "production_candidate"
    ]
    first_component = production_candidates[0] if production_candidates else artifact_summary["components"][0]
    destination = import_report["default_destination"]

    return {
        "schema_version": 1,
        "recommended_first_component": first_component["name"],
        "chromium_destination": destination,
        "import_file_count": import_report["file_count"],
        "required_chromium_paths": import_report["required_chromium_paths"],
        "gn_wiring_checklist": [
            f"Import scaffold under //{destination}",
            f"Add dependency on //{destination}:rust_perf_adapters from the selected Chromium leaf target",
            "Keep existing C++ implementation behind runtime rollback while measuring Rust path",
            "Do not wire P3 areas such as LayoutNG core, V8 JIT/GC, TaskRunner, or GPU runtime",
        ],
        "local_preflight_commands": [
            "python -m unittest discover -s tests",
            "powershell -ExecutionPolicy Bypass -File tools/run_all_gates.ps1",
            "python tools/check_chromium_import_consistency.py",
            "python tools/check_chromium_integration_checklist.py",
        ],
        "chromium_checkout_commands": [
            "powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 -ChromiumRoot C:\\path\\to\\chromium\\src -DryRun",
            "powershell -ExecutionPolicy Bypass -File tools/prepare_chromium_import.ps1 -ChromiumRoot C:\\path\\to\\chromium\\src",
            "gn gen out/rust-perf",
            f"autoninja -C out/rust-perf //{destination}:rust_perf_unittests",
            "tools/binary_size/supersize.py archive --output-directory out/rust-perf size-after.size",
            "tools/binary_size/supersize.py diff size-before.size size-after.size",
        ],
        "rollback_plan": [
            f"Use {first_component['rollback_symbol']} to force the C++ baseline path at runtime",
            "Keep the old C++ implementation in the same CL as the Rust path",
            "Attach rollback gate output from tools/run_rollback_gate.ps1 to the CL description",
            "If perf, size, or correctness regresses, revert only the Chromium callsite wiring first",
        ],
        "external_gates_not_satisfied_in_this_repo": [
            "Real Chromium GN graph link",
            "Android official build",
            "Android supersize diff",
            "Chromium libFuzzer or ClusterFuzz target",
            "Blink web_tests or WPT",
            "Browser startup, memory, Speedometer, and page-load perf waterfalls",
        ],
        "components": artifact_summary["components"],
    }


def render_markdown(handoff: dict[str, Any]) -> str:
    lines = [
        "# Chromium CL Handoff Package",
        "",
        f"Recommended first component: `{handoff['recommended_first_component']}`",
        f"Chromium destination: `//{handoff['chromium_destination']}`",
        f"Import file count: `{handoff['import_file_count']}`",
        "",
        "## GN Wiring Checklist",
        "",
    ]
    lines.extend(f"- {item}" for item in handoff["gn_wiring_checklist"])
    lines.extend(["", "## Local Preflight Commands", ""])
    lines.extend(f"```powershell\n{command}\n```" for command in handoff["local_preflight_commands"])
    lines.extend(["", "## Chromium Checkout Commands", ""])
    lines.extend(f"```powershell\n{command}\n```" for command in handoff["chromium_checkout_commands"])
    lines.extend(["", "## Rollback Plan", ""])
    lines.extend(f"- {item}" for item in handoff["rollback_plan"])
    lines.extend(["", "## External Gates Not Satisfied Here", ""])
    lines.extend(f"- {item}" for item in handoff["external_gates_not_satisfied_in_this_repo"])
    lines.extend(["", "## Components", ""])
    for component in handoff["components"]:
        lines.extend(
            [
                f"### {component['name']}",
                "",
                f"- Status: `{component['status']}`",
                f"- Rust crate: `{component['rust_crate']}`",
                f"- FFI header: `{component['ffi_header']}`",
                f"- Rollback symbol: `{component['rollback_symbol']}`",
                f"- Fuzz seeds: `{component['fuzz_seed_count']}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    handoff = build_handoff(Path.cwd())
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(handoff), encoding="utf-8")
    print(f"Chromium CL handoff JSON written: {args.output_json}")
    print(f"Chromium CL handoff Markdown written: {args.output_md}")
    print(f"Recommended first component: {handoff['recommended_first_component']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
