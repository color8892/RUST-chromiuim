from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from tools.rust_hot_leaf_guard import ArtifactPolicy, GuardRunner, RustSourcePolicy


class RustHotLeafGuardTest(unittest.TestCase):
    def test_accepts_no_std_leaf_without_forbidden_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "lib.rs"
            src.write_text(
                "\n".join(
                    [
                        "#![cfg_attr(not(test), no_std)]",
                        "pub extern \"C\" fn scan(data: *const u8, len: usize) -> u32 {",
                        "    if data.is_null() && len != 0 { return 1; }",
                        "    0",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            violations = RustSourcePolicy().check_file(src)

            self.assertEqual([], violations)

    def test_rejects_missing_no_std_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "lib.rs"
            src.write_text("pub extern \"C\" fn scan() -> u32 { 0 }\n", encoding="utf-8")

            violations = RustSourcePolicy().check_file(src)

            self.assertEqual("missing no_std gate", violations[0].rule)

    def test_rejects_panic_formatting_and_owned_allocations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "lib.rs"
            src.write_text(
                "\n".join(
                    [
                        "#![no_std]",
                        "pub fn bad() {",
                        "    let _s: String = format!(\"{}\", 1);",
                        "    let _v: Vec<u8> = Vec::new();",
                        "    panic!(\"bad\");",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            rules = {violation.rule for violation in RustSourcePolicy().check_file(src)}

            self.assertIn("formatting macro", rules)
            self.assertIn("panic macro", rules)
            self.assertIn("owned String in hot crate", rules)
            self.assertIn("owned Vec in hot crate", rules)

    def test_ignores_test_module_assertions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "lib.rs"
            src.write_text(
                "\n".join(
                    [
                        "#![no_std]",
                        "pub extern \"C\" fn scan() -> u32 { 0 }",
                        "#[cfg(test)]",
                        "mod tests {",
                        "    #[test]",
                        "    fn accepts_test_assertions() {",
                        "        assert_eq!(1, 1);",
                        "        println!(\"test-only\");",
                        "    }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            violations = RustSourcePolicy().check_file(src)

            self.assertEqual([], violations)

    def test_rejects_artifact_panic_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "lib.a"
            artifact.write_bytes(b"prefix core::fmt suffix")

            violations = ArtifactPolicy().check_file(artifact)

            self.assertEqual("forbidden artifact symbol/string", violations[0].rule)

    def test_runner_reports_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.a"

            violations = GuardRunner(RustSourcePolicy(), ArtifactPolicy()).check_artifacts([missing])

            self.assertEqual("missing artifact", violations[0].rule)


if __name__ == "__main__":
    unittest.main()
