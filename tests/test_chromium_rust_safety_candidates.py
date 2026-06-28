from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.check_chromium_rust_safety_candidates import build_report, render_markdown, validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChromiumRustSafetyCandidatesTest(unittest.TestCase):
    def test_repository_candidates_are_valid_and_ranked(self) -> None:
        payload, violations = validate_manifest(
            REPO_ROOT / "chromium_rust_safety_candidates.json",
            REPO_ROOT,
            REPO_ROOT / "p0_hot_leaf_registry.json",
        )
        report = build_report(payload)

        self.assertEqual([], [violation.render() for violation in violations])
        self.assertGreaterEqual(report["candidate_count"], 10)
        self.assertEqual("http-header-scanner", report["top_memory_safety_candidate"])
        ranks = [candidate["rank"] for candidate in payload["candidates"]]
        scores = [candidate["memory_safety_score"] for candidate in payload["candidates"]]
        self.assertEqual(sorted(ranks), ranks)
        self.assertEqual(sorted(scores, reverse=True), scores)

    def test_markdown_renders_blocked_areas_and_ranked_candidates(self) -> None:
        payload, violations = validate_manifest(
            REPO_ROOT / "chromium_rust_safety_candidates.json",
            REPO_ROOT,
            REPO_ROOT / "p0_hot_leaf_registry.json",
        )
        markdown = render_markdown(payload)

        self.assertEqual([], [violation.render() for violation in violations])
        self.assertIn("# Chromium Rust Safety Candidate Ranking", markdown)
        self.assertIn("Blink LayoutNG core", markdown)
        self.assertIn("http-header-scanner", markdown)
        self.assertIn("Do not expand into", markdown)

    def test_rejects_unknown_p0_component(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence.txt"
            evidence.write_text("ok\n", encoding="utf-8")
            registry = root / "p0.json"
            registry.write_text(
                json.dumps({"components": [{"name": "known_component"}]}),
                encoding="utf-8",
            )
            manifest = root / "candidates.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "selection_criteria": ["a", "b", "c", "d", "e"],
                        "blocked_areas": [],
                        "candidates": [
                            {
                                "rank": 1,
                                "id": "candidate-a",
                                "name": "Candidate A",
                                "chromium_location": "net/",
                                "tier": "tier_1_hot_leaf",
                                "memory_safety_score": 90,
                                "memory_safety_rationale": "test",
                                "typical_bug_classes": ["oob"],
                                "feasibility": "high",
                                "status": "planned",
                                "p0_component": "missing_component",
                                "next_chromium_task": None,
                                "roadmap_matrix_area": "area",
                                "do_not_expand_into": ["runtime"],
                                "evidence": ["evidence.txt"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            _, violations = validate_manifest(manifest, root, registry)

        self.assertIn("unknown p0_component", {violation.rule for violation in violations})


if __name__ == "__main__":
    unittest.main()