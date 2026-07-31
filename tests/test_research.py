import datetime
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from pure_tate.research import audit_research_gate, stage_two_ready
from pure_tate.store import load_repository


EXPECTED = [[3, 12], [5, 8], [6, 6], [7, 4], [8, 0], [8, 1], [8, 2]]


class ResearchGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _target, cls.sources, cls.claims, _edges = load_repository()

    def _write_agreeing_audit(self, root):
        path = root / "research" / "audits" / "RAUD-0001.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "id": "RAUD-0001",
                    "target_claim_id": "RED-0001",
                    "verdict": "agree",
                    "inferred_pairs": EXPECTED,
                    "source_ids": ["SRC-0001", "SRC-0002", "SRC-0004"],
                    "locators_checked": [
                        "SRC-0002 Theorem 1.5(3)",
                        "SRC-0002 Equation (6.1)",
                        "SRC-0002 Table 1",
                    ],
                    "forward_citation_check_date": datetime.date.today().isoformat(),
                    "reviewer_engine": "independent-engine",
                    "independent": True,
                    "notes": "Clean-context derivation.",
                }
            ),
            encoding="utf-8",
        )

    def test_no_audit_keeps_extracted_reduction_blocked(self):
        extracted = dict(self.claims)
        extracted["RED-0001"] = replace(
            extracted["RED-0001"], verification_status="extracted"
        )
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("pure_tate.research.ROOT", Path(directory)):
                result = audit_research_gate(
                    self.config, extracted, self.sources
                )
                ready = stage_two_ready(self.config, extracted, self.sources)
        self.assertTrue(result.ok)
        self.assertTrue(any("Stage 2 blocked" in item for item in result.warnings))
        self.assertFalse(ready)

    def test_agreeing_audit_still_requires_explicit_promotion(self):
        extracted = dict(self.claims)
        extracted["RED-0001"] = replace(
            extracted["RED-0001"], verification_status="extracted"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_agreeing_audit(root)
            with mock.patch("pure_tate.research.ROOT", root):
                result = audit_research_gate(
                    self.config, extracted, self.sources
                )
                ready = stage_two_ready(self.config, extracted, self.sources)
        self.assertTrue(result.ok)
        self.assertTrue(any("not been promoted" in item for item in result.warnings))
        self.assertFalse(ready)

    def test_promotion_without_audit_is_an_error(self):
        promoted = dict(self.claims)
        promoted["RED-0001"] = replace(
            promoted["RED-0001"], verification_status="cross_checked"
        )
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch("pure_tate.research.ROOT", Path(directory)):
                result = audit_research_gate(
                    self.config, promoted, self.sources
                )
        self.assertTrue(
            any("without an agreeing independent audit" in item for item in result.errors)
        )

    def test_agreement_plus_promotion_unlocks_stage_two(self):
        promoted = dict(self.claims)
        promoted["RED-0001"] = replace(
            promoted["RED-0001"], verification_status="cross_checked"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_agreeing_audit(root)
            with mock.patch("pure_tate.research.ROOT", root):
                result = audit_research_gate(
                    self.config, promoted, self.sources
                )
                ready = stage_two_ready(self.config, promoted, self.sources)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertTrue(ready)


if __name__ == "__main__":
    unittest.main()
