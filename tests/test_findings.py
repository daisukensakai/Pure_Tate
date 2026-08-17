import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.findings import (
    adjudicate_finding,
    load_findings,
    record_review_findings,
    repair_finding_audit_corpus,
    repair_finding_audit_sources,
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
                    supporting_audit_id="FAUD-TEST",
                    supporting_scope={"base": "geometrically connected"},
                    adjudicated_statement=(
                        "A precise local obstruction over a geometrically "
                        "connected base."
                    ),
                )
                self.assertEqual(decision["id"], "FADJ-0001")
                promoted = load_findings()[0]
                self.assertEqual(promoted["status"], "corroborated")
                self.assertEqual(
                    promoted["scope"], {"base": "geometrically connected"}
                )
                self.assertEqual(
                    promoted["statement"],
                    "A precise local obstruction over a geometrically connected base.",
                )
                self.assertEqual(
                    promoted["pre_adjudication_statement"],
                    "A precise local obstruction.",
                )
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


class FindingSourceRepairTests(unittest.TestCase):
    def _public_record(self, digest="f" * 64, source_type="stacks_project"):
        return {
            "query_family": "exact-finding-check",
            "retrieved_at": "2026-08-16T00:00:00Z",
            "url": "https://stacks.math.columbia.edu/tag/00NX",
            "source_type": source_type,
            "doi": None,
            "arxiv_id": None,
            "arxiv_version": None,
            "content_sha256": digest,
        }

    def _audit(self, **overrides):
        artifact = {
            "schema_version": 1,
            "id": "FAUD-9001",
            "task_id": "TASK-F-FND-9001",
            "campaign_id": "C66-001",
            "finding_id": "FND-9001",
            "verdict": "promote",
            "scope": {"case": {"g": 6, "n": 6}},
            "evidence_class": "primary_source",
            "source_records": [self._public_record()],
            "contradiction_resolution": "No contradiction.",
            "adjudicated_statement": "A corrected statement.",
            "engine": "grok",
            "independent": True,
        }
        artifact.update(overrides)
        return artifact

    def test_public_placeholder_hash_is_replaced(self):
        content = b"harness-fetched finding source"
        actual = hashlib.sha256(content).hexdigest()
        artifact = self._audit()
        with mock.patch(
            "pure_tate.novelty.fetch_public_source", return_value=content
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "attested")
        record = artifact["source_records"][0]
        self.assertEqual(record["content_sha256"], actual)
        self.assertEqual(record["reported_content_sha256"], "f" * 64)
        self.assertEqual(record["hash_attested_by"], "pure_tate_harness")
        self.assertEqual(record["source_type"], "reference")
        self.assertTrue(artifact["sources_verified"])
        self.assertEqual(artifact["verdict"], "promote")

    def test_null_hash_is_attested(self):
        content = b"null-hash source"
        actual = hashlib.sha256(content).hexdigest()
        artifact = self._audit(
            source_records=[self._public_record(digest=None, source_type="journal")]
        )
        with mock.patch(
            "pure_tate.novelty.fetch_public_source", return_value=content
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "attested")
        self.assertEqual(artifact["source_records"][0]["content_sha256"], actual)
        self.assertIsNone(artifact["source_records"][0]["reported_content_sha256"])

    def test_local_and_internal_urls_move_to_local_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "proof" / "packets" / "generated"
            packet.mkdir(parents=True)
            packet_path = packet / "C66-001-v4.md"
            packet_path.write_text("packet text\n", encoding="utf-8")
            artifact = self._audit(
                source_records=[
                    self._public_record(source_type="preprint"),
                    {
                        "query_family": "packet-cross-check",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "url": "file://proof/packets/generated/C66-001-v4.md",
                        "source_type": "campaign_packet",
                        "doi": None,
                        "arxiv_id": None,
                        "arxiv_version": None,
                        "content_sha256": None,
                    },
                    {
                        "query_family": "foundational",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "url": "internal:brill-noether-theory",
                        "source_type": "foundational",
                        "doi": None,
                        "arxiv_id": None,
                        "arxiv_version": None,
                        "content_sha256": "0" * 64,
                    },
                ]
            )
            with mock.patch("pure_tate.findings.ROOT", root), mock.patch(
                "pure_tate.novelty.fetch_public_source", return_value=b"public"
            ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
                result = repair_finding_audit_sources(artifact)
            self.assertEqual(result["status"], "attested")
            self.assertEqual(len(artifact["source_records"]), 1)
            self.assertTrue(
                artifact["source_records"][0]["url"].startswith("https://")
            )
            locals_ = artifact["local_evidence_records"]
            self.assertEqual(len(locals_), 2)
            hashed = next(
                item
                for item in locals_
                if item["url"].startswith("file://")
            )
            self.assertEqual(
                hashed["content_sha256"],
                hashlib.sha256(b"packet text\n").hexdigest(),
            )
            self.assertEqual(hashed["hash_attested_by"], "pure_tate_harness")
            internal = next(
                item
                for item in locals_
                if str(item["url"]).startswith("internal:")
            )
            self.assertNotIn("hash_attested_by", internal)

    def test_partial_fetch_does_not_mark_verified(self):
        first = self._public_record()
        second = dict(self._public_record())
        second["url"] = "https://link.springer.com/blocked"
        artifact = self._audit(source_records=[first, second])

        def fake_fetch(url, timeout=30):
            if "stacks" in url:
                return b"ok-source"
            raise OSError("paywall")

        with mock.patch(
            "pure_tate.novelty.fetch_public_source", side_effect=fake_fetch
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "partial")
        self.assertNotEqual(artifact.get("sources_verified"), True)
        self.assertEqual(len(artifact["source_records"]), 2)
        attested = [
            item
            for item in artifact["source_records"]
            if item.get("hash_attested_by") == "pure_tate_harness"
        ]
        self.assertEqual(len(attested), 1)

    def test_already_verified_audits_are_skipped(self):
        artifact = self._audit(sources_verified=True, verified_source_count=1)
        original = dict(artifact["source_records"][0])
        result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "already_verified")
        self.assertEqual(artifact["source_records"][0], original)
        self.assertNotIn("source_attestation_migration", artifact)

    def test_local_only_audit_is_not_marked_verified(self):
        artifact = self._audit(
            source_records=[
                {
                    "query_family": "packet",
                    "retrieved_at": "2026-08-16T00:00:00Z",
                    "url": "proof/packets/generated/C66-001-v4.md",
                    "source_type": "campaign_packet",
                    "doi": None,
                    "arxiv_id": None,
                    "arxiv_version": None,
                    "content_sha256": None,
                }
            ]
        )
        result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "skipped_no_public")
        self.assertNotEqual(artifact.get("sources_verified"), True)
        self.assertEqual(artifact["source_records"], [])
        self.assertEqual(len(artifact["local_evidence_records"]), 1)

    def test_corpus_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_dir = root / "research" / "finding-audits"
            audit_dir.mkdir(parents=True)
            (root / "proof" / "migrations").mkdir(parents=True)
            artifact = self._audit()
            path = audit_dir / "FAUD-9001.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            original = path.read_bytes()
            with mock.patch("pure_tate.findings.ROOT", root), mock.patch(
                "pure_tate.novelty.fetch_public_source", return_value=b"ok"
            ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
                result = repair_finding_audit_corpus(dry_run=True)
            self.assertTrue(result["dry_run"])
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(
                (root / "proof" / "migrations" / "finding-source-attestation.json").exists()
            )
            self.assertFalse((audit_dir / "raw-pre-attestation").exists())

    def test_substitution_replaces_blocked_url_before_fetch(self):
        blocked = self._public_record()
        blocked["url"] = "https://eudml.org/doc/143338"
        blocked["query_family"] = "vcd-harer"
        kept = self._public_record(source_type="preprint")
        kept["url"] = "https://arxiv.org/abs/2307.08830"
        artifact = self._audit(source_records=[blocked, kept])
        fetched = []

        def fake_fetch(url, timeout=30):
            fetched.append(url)
            return ("body-" + url).encode("utf-8")

        with mock.patch(
            "pure_tate.findings._load_source_url_substitutions",
            return_value={
                "https://eudml.org/doc/143338": "https://arxiv.org/pdf/2003.10913"
            },
        ), mock.patch(
            "pure_tate.novelty.fetch_public_source", side_effect=fake_fetch
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "attested")
        self.assertTrue(artifact["sources_verified"])
        urls = [item["url"] for item in artifact["source_records"]]
        self.assertIn("https://arxiv.org/pdf/2003.10913", urls)
        self.assertNotIn("https://eudml.org/doc/143338", urls)
        self.assertIn("https://arxiv.org/pdf/2003.10913", fetched)
        replaced = next(
            item
            for item in artifact["source_records"]
            if item["url"] == "https://arxiv.org/pdf/2003.10913"
        )
        self.assertEqual(replaced["arxiv_id"], "2003.10913")
        self.assertEqual(replaced["query_family"], "vcd-harer")

    def test_substitution_drop_lets_remaining_public_verify(self):
        blocked = self._public_record()
        blocked["url"] = "https://math.stackexchange.com/questions/1221839/x"
        kept = self._public_record(source_type="reference")
        artifact = self._audit(source_records=[blocked, kept])
        with mock.patch(
            "pure_tate.findings._load_source_url_substitutions",
            return_value={
                "https://math.stackexchange.com/questions/1221839/x": None
            },
        ), mock.patch(
            "pure_tate.novelty.fetch_public_source", return_value=b"ok"
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "attested")
        self.assertEqual(len(artifact["source_records"]), 1)
        self.assertTrue(artifact["sources_verified"])
        self.assertIn(
            "dropped unfetchable https://math.stackexchange.com/questions/1221839/x",
            result["transformations"],
        )
        self.assertEqual(artifact["verdict"], "promote")

    def test_rerun_does_not_duplicate_local_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "proof" / "packets" / "generated"
            packet.mkdir(parents=True)
            (packet / "C66-001-v4.md").write_text("packet\n", encoding="utf-8")
            blocked = self._public_record()
            blocked["url"] = "https://math.stackexchange.com/questions/1221839/x"
            artifact = self._audit(
                source_records=[
                    self._public_record(source_type="preprint"),
                    blocked,
                    {
                        "query_family": "packet",
                        "retrieved_at": "2026-08-16T00:00:00Z",
                        "url": "file://proof/packets/generated/C66-001-v4.md",
                        "source_type": "campaign_packet",
                        "doi": None,
                        "arxiv_id": None,
                        "arxiv_version": None,
                        "content_sha256": None,
                    },
                ]
            )

            def fake_fetch(url, timeout=30):
                if "stackexchange" in url:
                    raise OSError("403")
                return b"public"

            with mock.patch("pure_tate.findings.ROOT", root), mock.patch(
                "pure_tate.novelty.fetch_public_source", side_effect=fake_fetch
            ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
                first = repair_finding_audit_sources(artifact)
                self.assertEqual(first["status"], "partial")
                self.assertEqual(len(artifact["local_evidence_records"]), 1)
                with mock.patch(
                    "pure_tate.findings._load_source_url_substitutions",
                    return_value={
                        "https://math.stackexchange.com/questions/1221839/x": None
                    },
                ):
                    second = repair_finding_audit_sources(artifact)
            self.assertEqual(second["status"], "attested")
            self.assertEqual(len(artifact["local_evidence_records"]), 1)
            self.assertTrue(artifact["sources_verified"])

    def test_allowlisted_additions_close_local_only_audit(self):
        artifact = self._audit(
            id="FAUD-9001",
            source_records=[],
        )
        extra = {
            "query_family": "clifford-special-divisors",
            "retrieved_at": "2026-08-17T00:00:00Z",
            "url": "https://en.wikipedia.org/wiki/Clifford%27s_theorem_on_special_divisors",
            "source_type": "encyclopedia",
            "doi": None,
            "arxiv_id": None,
            "arxiv_version": None,
        }
        with mock.patch(
            "pure_tate.findings._load_source_additions",
            return_value=[extra],
        ), mock.patch(
            "pure_tate.novelty.fetch_public_source", return_value=b"clifford"
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "attested")
        self.assertTrue(artifact["sources_verified"])
        self.assertEqual(len(artifact["source_records"]), 1)
        self.assertEqual(
            artifact["source_records"][0]["url"], extra["url"]
        )
        self.assertIn("added public source %s" % extra["url"], result["transformations"])
        self.assertEqual(artifact["verdict"], "promote")

    def test_allowlisted_addition_does_not_duplicate_existing_url(self):
        extra = self._public_record(source_type="encyclopedia")
        extra["url"] = "https://en.wikipedia.org/wiki/Clifford%27s_theorem_on_special_divisors"
        artifact = self._audit(source_records=[extra])
        with mock.patch(
            "pure_tate.findings._load_source_additions",
            return_value=[dict(extra)],
        ), mock.patch(
            "pure_tate.novelty.fetch_public_source", return_value=b"clifford"
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            result = repair_finding_audit_sources(artifact)
        self.assertEqual(result["status"], "attested")
        self.assertEqual(len(artifact["source_records"]), 1)
        self.assertFalse(
            any(
                str(item).startswith("added public source")
                for item in result["transformations"]
            )
        )

    def test_hash_overlay_replaces_supporting_artifact_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "proof"
            proof.mkdir()
            old = "a" * 64
            new = "b" * 64
            (proof / "findings.jsonl").write_text(
                json.dumps(
                    {
                        "id": "FND-9001",
                        "status": "corroborated",
                        "statement": "A finding.",
                        "case": {"g": 6, "n": 6},
                        "supporting_artifact_hashes": [old, "c" * 64],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (proof / "migrations").mkdir()
            (proof / "migrations" / "finding-source-attestation.json").write_text(
                json.dumps({"finding_hash_replacements": {old: new}}),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.findings.ROOT", root):
                findings = load_findings()
            self.assertEqual(
                findings[0]["supporting_artifact_hashes"], [new, "c" * 64]
            )
            self.assertEqual(findings[0]["status"], "corroborated")

    def test_hash_overlay_resolves_repeated_attestation_rewrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "proof"
            proof.mkdir()
            old = "a" * 64
            intermediate = "b" * 64
            current = "c" * 64
            (proof / "findings.jsonl").write_text(
                json.dumps(
                    {
                        "id": "FND-9002",
                        "status": "corroborated",
                        "statement": "A repeatedly attested finding.",
                        "case": {"g": 6, "n": 6},
                        "supporting_artifact_hashes": [old],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (proof / "migrations").mkdir()
            (proof / "migrations" / "finding-source-attestation.json").write_text(
                json.dumps(
                    {
                        "finding_hash_replacements": {
                            old: intermediate,
                            intermediate: current,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.findings.ROOT", root):
                findings = load_findings()
            self.assertEqual(
                findings[0]["supporting_artifact_hashes"], [current]
            )

    def test_hash_overlay_cycle_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = root / "proof"
            proof.mkdir()
            old = "a" * 64
            intermediate = "b" * 64
            (proof / "findings.jsonl").write_text(
                json.dumps(
                    {
                        "id": "FND-9003",
                        "status": "corroborated",
                        "statement": "A finding with malformed provenance.",
                        "case": {"g": 6, "n": 6},
                        "supporting_artifact_hashes": [old],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (proof / "migrations").mkdir()
            (proof / "migrations" / "finding-source-attestation.json").write_text(
                json.dumps(
                    {
                        "finding_hash_replacements": {
                            old: intermediate,
                            intermediate: old,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.findings.ROOT", root):
                findings = load_findings()
            self.assertEqual(
                findings[0]["supporting_artifact_hashes"], [old]
            )


if __name__ == "__main__":
    unittest.main()
