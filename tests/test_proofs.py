import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.proofs import audit_proofs
from pure_tate.store import load_repository


class ProofAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _config, _target, _sources, cls.claims, _edges = load_repository()

    def _write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_claimed_complete_cannot_keep_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root / "proof" / "attempts" / "ATT-0001.json",
                {
                    "id": "ATT-0001",
                    "target_claim_id": "RED-0001",
                    "approach": "test",
                    "status": "claimed_complete",
                    "source_claim_ids": ["THM-0002"],
                    "gap_markers": ["still open"],
                },
            )
            with mock.patch("pure_tate.proofs.ROOT", root):
                result = audit_proofs(self.claims)
            self.assertTrue(any("gap markers" in item for item in result.errors))

    def test_verified_requires_two_cross_engine_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root / "proof" / "attempts" / "ATT-0001.json",
                {
                    "id": "ATT-0001",
                    "target_claim_id": "RED-0001",
                    "approach": "test",
                    "status": "verified",
                    "source_claim_ids": ["THM-0002"],
                    "gap_markers": [],
                },
            )
            self._write(
                root / "proof" / "reviews" / "REV-0001.json",
                {
                    "id": "REV-0001",
                    "attempt_id": "ATT-0001",
                    "verdict": "confirmed",
                    "reviewer_engine": "engine-a",
                    "independent": True,
                    "strongest_attack": "attack",
                },
            )
            with mock.patch("pure_tate.proofs.ROOT", root):
                result = audit_proofs(self.claims)
            self.assertTrue(any("two independent" in item for item in result.errors))

    def test_two_cross_engine_reviews_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root / "proof" / "attempts" / "ATT-0001.json",
                {
                    "id": "ATT-0001",
                    "target_claim_id": "RED-0001",
                    "approach": "test",
                    "status": "verified",
                    "source_claim_ids": ["THM-0002"],
                    "gap_markers": [],
                },
            )
            for number, engine in ((1, "engine-a"), (2, "engine-b")):
                self._write(
                    root / "proof" / "reviews" / ("REV-000%d.json" % number),
                    {
                        "id": "REV-000%d" % number,
                        "attempt_id": "ATT-0001",
                        "verdict": "confirmed",
                        "reviewer_engine": engine,
                        "independent": True,
                        "strongest_attack": "attack %d" % number,
                    },
                )
            with mock.patch("pure_tate.proofs.ROOT", root):
                result = audit_proofs(self.claims)
            self.assertEqual(result.errors, [])

    def test_packet_visible_finding_is_allowed_in_source_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root / "proof" / "attempts" / "ATT-0001.json",
                {
                    "id": "ATT-0001",
                    "target_claim_id": "RED-0001",
                    "approach": "test",
                    "status": "proposed",
                    "source_claim_ids": ["THM-0002"],
                    "source_ids": ["FND-TEST"],
                    "gap_markers": ["test gap"],
                },
            )
            finding = {
                "id": "FND-TEST",
                "status": "corroborated",
                "statement": "A packet-visible test finding.",
            }
            with mock.patch("pure_tate.proofs.ROOT", root), mock.patch(
                "pure_tate.proofs.load_findings", return_value=[finding]
            ):
                result = audit_proofs(self.claims)
            self.assertFalse(
                any("unknown source FND-TEST" in item for item in result.errors)
            )


if __name__ == "__main__":
    unittest.main()
