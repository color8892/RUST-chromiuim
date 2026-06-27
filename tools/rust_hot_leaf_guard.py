#!/usr/bin/env python3
"""Policy guard for performance-first Chromium Rust hot leaf modules."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable, Sequence


FORBIDDEN_SOURCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("formatting macro", re.compile(r"\b(?:format|print|println|eprint|eprintln|dbg|write|writeln)!\s*\(")),
    ("panic macro", re.compile(r"\b(?:panic|todo|unimplemented)!\s*\(")),
    ("panic-prone unwrap/expect", re.compile(r"\.(?:unwrap|expect)\s*\(")),
    ("Debug derive in hot crate", re.compile(r"#\s*\[\s*derive\s*\([^\]]*\bDebug\b")),
    ("owned String in hot crate", re.compile(r"\bString\b")),
    ("owned Vec in hot crate", re.compile(r"\bVec\s*<")),
    ("cxx owned bridge in hot path", re.compile(r"\bcxx::(?:CxxString|UniquePtr|CxxVector)\b")),
    ("public generic API", re.compile(r"\bpub\s+(?:extern\s+\"C\"\s+)?fn\s+[A-Za-z_][A-Za-z0-9_]*\s*<")),
)

FORBIDDEN_ARTIFACT_BYTES: tuple[bytes, ...] = (
    b"core::fmt",
    b"panicking",
    b"panic_fmt",
    b"panic_bounds_check",
    b"panic_const",
)

TEST_MODULE_PATTERN = re.compile(r"(?ms)^\s*#\[cfg\(test\)\]\s*mod\s+tests\s*\{.*\}\s*$")


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


class RustSourcePolicy:
    def check_file(self, path: Path) -> list[Violation]:
        text = path.read_text(encoding="utf-8")
        stripped_text = self._strip_test_modules(text)
        violations: list[Violation] = []

        if path.name == "lib.rs" and not self._has_no_std_gate(stripped_text):
            violations.append(
                Violation(
                    path,
                    1,
                    "missing no_std gate",
                    "hot leaf lib.rs must use #![no_std] or #![cfg_attr(not(test), no_std)]",
                )
            )

        for rule, pattern in FORBIDDEN_SOURCE_PATTERNS:
            for match in pattern.finditer(stripped_text):
                violations.append(
                    Violation(
                        path,
                        self._line_for_offset(stripped_text, match.start()),
                        rule,
                        match.group(0),
                    )
                )

        return violations

    @staticmethod
    def _has_no_std_gate(text: str) -> bool:
        return (
            "#![no_std]" in text or
            "#![cfg_attr(not(test), no_std)]" in text or
            '#![cfg_attr(all(not(test), not(feature = "std")), no_std)]' in text
        )

    @staticmethod
    def _strip_test_modules(text: str) -> str:
        return TEST_MODULE_PATTERN.sub("", text)

    @staticmethod
    def _line_for_offset(text: str, offset: int) -> int:
        return text.count("\n", 0, offset) + 1


class ArtifactPolicy:
    def check_file(self, path: Path) -> list[Violation]:
        data = path.read_bytes()
        violations: list[Violation] = []
        for needle in FORBIDDEN_ARTIFACT_BYTES:
            offset = data.find(needle)
            if offset >= 0:
                violations.append(
                    Violation(
                        path,
                        1,
                        "forbidden artifact symbol/string",
                        f"{needle.decode('ascii')} at byte offset {offset}",
                    )
                )
        return violations


class GuardRunner:
    def __init__(self, source_policy: RustSourcePolicy, artifact_policy: ArtifactPolicy) -> None:
        self._source_policy = source_policy
        self._artifact_policy = artifact_policy

    def check_sources(self, roots: Sequence[Path]) -> list[Violation]:
        violations: list[Violation] = []
        for path in self._rust_files(roots):
            violations.extend(self._source_policy.check_file(path))
        return violations

    def check_artifacts(self, artifacts: Sequence[Path]) -> list[Violation]:
        violations: list[Violation] = []
        for artifact in artifacts:
            if artifact.exists():
                violations.extend(self._artifact_policy.check_file(artifact))
            else:
                violations.append(
                    Violation(artifact, 1, "missing artifact", "artifact path does not exist")
                )
        return violations

    @staticmethod
    def _rust_files(roots: Sequence[Path]) -> Iterable[Path]:
        for root in roots:
            if root.is_file() and root.suffix == ".rs":
                yield root
            elif root.is_dir():
                yield from sorted(root.rglob("*.rs"))


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path, help="Rust hot leaf source roots")
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        type=Path,
        help="compiled release artifact to scan for panic/fmt strings",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = _parse_args(argv)
    runner = GuardRunner(RustSourcePolicy(), ArtifactPolicy())
    violations = runner.check_sources(args.roots)
    violations.extend(runner.check_artifacts(args.artifact))

    for violation in violations:
        print(violation.render(), file=sys.stderr)

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
