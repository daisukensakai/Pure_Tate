import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.findings import (
    adjudicate_finding,
    load_findings,
    record_review_findings,
)


class FindingAdjudicationTests(unittest.TestCase):
    def _review(self, review_id, engine, candidate):
        return {
            "id": review_id,
            "reviewer_engine": engine,
            "created_on": "2026-07-30",
            "finding_candidates": [candidate],
        }

    def test_matching_candidate_keys_require_explicit_adjudication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "proof").mkdir()
            (root / "proof" / "findings.jsonl").write_text("", encoding="utf-8")
            attempt = {
                "id": "ATT-0100",
                "approach_id": "approach",
                "target": {"g": 5, "n": 8},
            }
            candidate = {
                "key": "local-obstruction",
                "kind": "obstruction",
                "statement": "A precise local obstruction.",
            }
            with mock.patch("pure_tate.findings.ROOT", root):
                first = record_review_findings(
                    self._review("REV-0100", "grok", candidate), attempt
                )[0]
                second = record_review_findings(
                    self._review("REV-0101", "claude", candidate), attempt
                )[0]
                self.assertEqual(first["id"], second["id"])
                self.assertEqual(second["status"], "candidate")
                self.assertTrue(second["corroboration_ready"])

                decision = adjudicate_finding(
                    second["id"],
                    "corroborate",
                    "Two independent engines checked the same local claim.",
                    adjudicator="test",
                )
                self.assertEqual(decision["id"], "FADJ-0001")
                promoted = load_findings()[0]
                self.assertEqual(promoted["status"], "corroborated")
                with self.assertRaisesRegex(ValueError, "already adjudicated"):
                    adjudicate_finding(
                        promoted["id"],
                        "retire",
                        "A contradictory second decision.",
                    )

    def test_same_key_in_different_cases_does_not_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "proof").mkdir()
            (root / "proof" / "findings.jsonl").write_text("", encoding="utf-8")
            candidate = {
                "key": "same-spelling",
                "kind": "obstruction",
                "statement": "Case-local statement.",
            }
            with mock.patch("pure_tate.findings.ROOT", root):
                for ordinal, case in enumerate(({"g": 5, "n": 8}, {"g": 6, "n": 6})):
                    record_review_findings(
                        self._review(
                            "REV-%04d" % (200 + ordinal),
                            "grok",
                            candidate,
                        ),
                        {
                            "id": "ATT-%04d" % (200 + ordinal),
                            "approach_id": "approach",
                            "target": case,
                        },
                    )
                findings = load_findings()
                self.assertEqual(len(findings), 2)
                self.assertEqual(
                    {(item["case"]["g"], item["case"]["n"]) for item in findings},
                    {(5, 8), (6, 6)},
                )


if __name__ == "__main__":
    unittest.main()
