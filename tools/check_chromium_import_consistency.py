#!/usr/bin/env python3
"""Check consistency between P0 registry, BUILD.gn, and import manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


DEFAULT_REGISTRY = Path("p0_hot_leaf_registry.json")
DEFAULT_BUILD = Path("BUILD.gn")
DEFAULT_IMPORT_MANIFEST = Path("chromium_import_manifest.json")


@dataclass(frozen=True)
class ImportConsistencyViolation:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


def check_consistency(
    registry_path: Path,
    build_path: Path,
    import_manifest_path: Path,
) -> list[ImportConsistencyViolation]:
    violations: list[ImportConsistencyViolation] = []
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        manifest = json.loads(import_manifest_path.read_text(encoding="utf-8"))
        build_text = build_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [ImportConsistencyViolation("read failed", str(exc))]
    except json.JSONDecodeError as exc:
        return [ImportConsistencyViolation("JSON invalid", str(exc))]

    components = registry.get("components")
    if not isinstance(components, list) or not components:
        return [ImportConsistencyViolation("invalid registry", "components must be non-empty array")]

    for component in components:
        if not isinstance(component, dict):
            violations.append(ImportConsistencyViolation("invalid component", repr(component)))
            continue
        violations.extend(_check_component_build(build_text, component))

    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        violations.append(ImportConsistencyViolation("invalid import manifest", "files must be array"))
    else:
        for required in ("BUILD.gn", "chromium_integration_checklist.json", "rust", "cpp", "include", "tools"):
            if required not in manifest_files:
                violations.append(
                    ImportConsistencyViolation("missing import manifest file", required)
                )

    excludes = manifest.get("exclude")
    if not isinstance(excludes, list):
        violations.append(ImportConsistencyViolation("invalid import manifest", "exclude must be array"))
    else:
        for required in ("target", "*.obj", "*.exe", "*.lib", "*.rlib"):
            if required not in excludes:
                violations.append(
                    ImportConsistencyViolation("missing import manifest exclude", required)
                )

    if 'import("//build/config/rust.gni")' not in build_text:
        violations.append(
            ImportConsistencyViolation("missing GN rust import", "//build/config/rust.gni")
        )
    if 'rust_static_library("chromium_rust_perf_bridge")' not in build_text:
        violations.append(
            ImportConsistencyViolation("missing GN static library", "chromium_rust_perf_bridge")
        )
    if 'source_set("rust_perf_adapters")' not in build_text:
        violations.append(
            ImportConsistencyViolation("missing GN adapter target", "rust_perf_adapters")
        )

    return violations


def _check_component_build(
    build_text: str,
    component: dict[str, Any],
) -> list[ImportConsistencyViolation]:
    violations: list[ImportConsistencyViolation] = []
    name = component.get("name", "<unknown>")
    rust_crate = component.get("rust_crate")
    if isinstance(rust_crate, str):
        crate_root = f'{rust_crate}/src/lib.rs'
        if f'"{crate_root}"' not in build_text:
            violations.append(ImportConsistencyViolation("missing GN crate root", f"{name}: {crate_root}"))
        target = f'chromium_rust_{name}'
        if f'rust_library("{target}")' not in build_text:
            violations.append(ImportConsistencyViolation("missing GN rust target", f"{name}: {target}"))

    ffi_header = component.get("ffi_header")
    if isinstance(ffi_header, str) and f'"{ffi_header}"' not in build_text:
        violations.append(ImportConsistencyViolation("missing GN public header", f"{name}: {ffi_header}"))

    adapters = component.get("cpp_adapter")
    if isinstance(adapters, list):
        for adapter in adapters:
            if isinstance(adapter, str) and f'"{adapter}"' not in build_text:
                violations.append(ImportConsistencyViolation("missing GN adapter source", f"{name}: {adapter}"))

    return violations


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--build", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--import-manifest", type=Path, default=DEFAULT_IMPORT_MANIFEST)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    violations = check_consistency(args.registry, args.build, args.import_manifest)
    for violation in violations:
        print(violation.render(), file=sys.stderr)
    if not violations:
        print("Chromium import consistency OK")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
