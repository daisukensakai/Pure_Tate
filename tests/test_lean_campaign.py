import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate import lean_campaign


class LeanCampaignTests(unittest.TestCase):
    def _write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _fixture(self, base):
        root = Path(base)
        formal = root / "formal"
        campaigns = formal / "campaigns"
        attempts = formal / "attempts"
        reviews = formal / "reviews"
        source = root / "proof" / "attempts" / "ATT-0135.json"
        source.parent.mkdir(parents=True)
        source_value = {
            "id": "ATT-0135",
            "theorem_statement": "exact theorem",
            "claims": [{"id": "CLM-%d" % number} for number in range(1, 7)],
        }
        source.write_text(json.dumps(source_value) + "\n", encoding="utf-8")
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        trusted_text = (
            "structure BMTargetIndex where\n"
            "  genus : Int\n"
            "  markings : Int\n"
            "  homologicalDegree : Int\n"
            "  weight : Int\n"
            "  tateIndex : Int\n\n"
            "def exactC66BMTarget : BMTargetIndex := {\n"
            "  genus := 6\n"
            "  markings := 6\n"
            "  homologicalDegree := 16\n"
            "  weight := -16\n"
            "  tateIndex := 8\n"
            "}\n\n"
            "axiom BMIsFiniteTateSum : BMTargetIndex -> Prop\n"
            "-- LEAN-AXIOM BMIsFiniteTateSum => VOCAB -- exact target predicate\n"
        )
        trusted_path = formal / "TrustedC66Target.lean.inc"
        trusted_path.parent.mkdir(parents=True, exist_ok=True)
        trusted_path.write_text(trusted_text, encoding="utf-8")
        obligations = [
            {"id": "OBL-%d" % number, "source_claim_id": "CLM-%d" % number,
             "statement": "statement %d" % number}
            for number in range(1, 7)
        ]
        campaign = {
            "schema_version": 1,
            "id": "LC66-001",
            "source_attempt_id": "ATT-0135",
            "source_attempt_path": "proof/attempts/ATT-0135.json",
            "source_attempt_sha256": source_sha,
            "claim_contract_id": "C66-EXACT-TARGET-V1",
            "exact_theorem": "exact theorem",
            "lean_target_contract": "exact Lean target contract",
            "target_signature": "fixture-exact-target",
            "trusted_prelude_path": "formal/TrustedC66Target.lean.inc",
            "trusted_prelude_sha256": hashlib.sha256(
                trusted_path.read_bytes()
            ).hexdigest(),
            "required_theorem_type": "BMIsFiniteTateSum exactC66BMTarget",
            "toolchain": "leanprover/lean4:v4.32.1",
            "minimum_independent_reviews": 2,
            "obligations": obligations,
        }
        self._write_json(campaigns / "LC66-001.json", campaign)
        (formal / "lean-toolchain").write_text(
            "leanprover/lean4:v4.32.1\n", encoding="utf-8"
        )
        directory = attempts / "LATT-0001-fixture"
        directory.mkdir(parents=True)
        manifest = {
            "schema_version": 1,
            "id": "LATT-0001",
            "campaign_id": "LC66-001",
            "source_attempt_id": "ATT-0135",
            "source_attempt_sha256": source_sha,
            "claim_contract_id": "C66-EXACT-TARGET-V1",
            "prover_engine": "prover",
            "formalization_scope": "local deduction over audited black boxes",
        }
        self._write_json(directory / "manifest.json", manifest)
        lines = [
            "set_option autoImplicit false",
            "-- LEAN-CAMPAIGN LC66-001",
            "-- LEAN-ATTEMPT LATT-0001",
            "-- LEAN-SOURCE-ATTEMPT ATT-0135",
            "-- LEAN-CLAIM-CONTRACT C66-EXACT-TARGET-V1",
            "-- LEAN-TARGET-SIGNATURE fixture-exact-target",
            "-- LEAN-THEOREM exactTarget",
            "-- LEAN-WEIGHT all six premises carry the mathematical content",
            "-- LEAN-TRUSTED-PRELUDE-BEGIN",
            *trusted_text.rstrip("\n").splitlines(),
            "-- LEAN-TRUSTED-PRELUDE-END",
        ]
        names = []
        for number in range(1, 7):
            name = "a%d" % number
            names.append(name)
            lines.extend(
                [
                    (
                        "axiom %s : True" % name
                        if number < 6
                        else "axiom a6 : True -> True -> True -> True -> True -> "
                        "BMIsFiniteTateSum exactC66BMTarget"
                    ),
                    "-- LEAN-AXIOM %s => OBL-%d -- fixture" % (name, number),
                ]
            )
        lines.extend(
            [
                "theorem exactTarget : BMIsFiniteTateSum exactC66BMTarget := "
                "a6 a1 a2 a3 a4 a5",
                "#print axioms exactTarget",
            ]
        )
        (directory / "Claim.lean").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (directory / "Model.lean").write_text(
            "set_option autoImplicit false\n"
            "-- LEAN-MODEL-WITNESS propositions are interpreted as True\n"
            "-- LEAN-NONCOLLAPSE a separate Boolean witness is false\n"
            "-- LEAN-MODELS BMIsFiniteTateSum a1 a2 a3 a4 a5 a6\n"
            "-- LEAN-MODEL-THEOREM modelWitness\n"
            "theorem witness : True := True.intro\n"
            "theorem noncollapse : (false : Bool) != true := by decide\n"
            "theorem modelWitness : True ∧ ((false : Bool) != true) := "
            "And.intro witness noncollapse\n"
            "#print axioms modelWitness\n",
            encoding="utf-8",
        )
        return root, formal, campaigns, attempts, reviews, directory, campaign

    def _patches(self, root, formal, campaigns, attempts, reviews):
        return mock.patch.multiple(
            lean_campaign,
            ROOT=root,
            FORMAL=formal,
            CAMPAIGNS=campaigns,
            ATTEMPTS=attempts,
            REVIEWS=reviews,
        )

    def test_valid_attempt_elaborates_and_report_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, directory, _campaign = fixture
            with self._patches(root, formal, campaigns, attempts, reviews):
                result, report = lean_campaign.check_attempt("LATT-0001", write=True)
                self.assertEqual(result.errors, [])
                self.assertEqual(report["result"], "PASS")
                status = lean_campaign.campaign_status()
            self.assertEqual(status["attempts"][0]["status"], "candidate")
            self.assertTrue(status["attempts"][0]["committed_report_matches"])

    def test_sorry_in_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, directory, _campaign = fixture
            (directory / "Model.lean").write_text(
                "set_option autoImplicit false\n"
                "-- LEAN-MODEL-WITNESS fixture\n"
                "-- LEAN-NONCOLLAPSE fixture\n"
                "-- LEAN-MODELS BMIsFiniteTateSum a1 a2 a3 a4 a5 a6\n"
                "-- LEAN-MODEL-THEOREM bad\n"
                "theorem bad : True := by sorry\n",
                encoding="utf-8",
            )
            with self._patches(root, formal, campaigns, attempts, reviews):
                result, _report = lean_campaign.check_attempt("LATT-0001")
            self.assertTrue(any("forbidden Model.lean" in error for error in result.errors))

    def test_spoofable_eval_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, directory, _campaign = fixture
            claim_path = directory / "Claim.lean"
            text = claim_path.read_text(encoding="utf-8").replace(
                "#print axioms exactTarget",
                "#eval IO.println \"'exactTarget' depends on axioms: [a1, a2, a3, a4, a5, a6]\"\n"
                "#print axioms exactTarget",
            )
            claim_path.write_text(text, encoding="utf-8")
            with self._patches(root, formal, campaigns, attempts, reviews):
                result, _report = lean_campaign.check_attempt("LATT-0001")
            self.assertTrue(any("spoofable output" in error for error in result.errors))

    def test_command_macro_cannot_replace_print_axioms(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, directory, _campaign = fixture
            claim_path = directory / "Claim.lean"
            text = claim_path.read_text(encoding="utf-8").replace(
                "theorem exactTarget",
                "macro \"#print\" \"axioms\" n:ident : command => "
                "`(command| #eval IO.println \"forged\")\n"
                "theorem exactTarget",
            )
            claim_path.write_text(text, encoding="utf-8")
            with self._patches(root, formal, campaigns, attempts, reviews):
                result, _report = lean_campaign.check_attempt("LATT-0001")
            self.assertTrue(any("extend commands" in error for error in result.errors))

    def test_exported_theorem_type_is_checked_by_lean_not_comments(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, directory, _campaign = fixture
            claim_path = directory / "Claim.lean"
            text = claim_path.read_text(encoding="utf-8")
            text = text.replace(
                "theorem exactTarget : BMIsFiniteTateSum exactC66BMTarget := "
                "a6 a1 a2 a3 a4 a5",
                "/-\ntheorem exactTarget : BMIsFiniteTateSum exactC66BMTarget :=\n-/\n"
                "theorem exactTarget : True := True.intro",
            )
            claim_path.write_text(text, encoding="utf-8")
            with self._patches(root, formal, campaigns, attempts, reviews):
                result, _report = lean_campaign.check_attempt("LATT-0001")
            self.assertTrue(any("failed elaboration" in error for error in result.errors))

    def test_audit_fails_closed_after_an_unreviewed_attempt_exists(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, _directory, _campaign = fixture
            with self._patches(root, formal, campaigns, attempts, reviews):
                lean_campaign.check_attempt("LATT-0001", write=True)
                result = lean_campaign.audit_campaign()
            self.assertTrue(
                any("no independently verified attempt" in error for error in result.errors)
            )

    def test_two_distinct_nonprover_reviews_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = self._fixture(temporary)
            root, formal, campaigns, attempts, reviews, directory, campaign = fixture
            with self._patches(root, formal, campaigns, attempts, reviews):
                result, report = lean_campaign.check_attempt("LATT-0001", write=True)
                self.assertTrue(result.ok)
                report_path = directory / "report.json"
                common = {
                    "schema_version": 1,
                    "attempt_id": "LATT-0001",
                    "campaign_id": "LC66-001",
                    "independent": True,
                    "verdict": "confirmed",
                    "campaign_sha256": hashlib.sha256(
                        (campaigns / "LC66-001.json").read_bytes()
                    ).hexdigest(),
                    "claim_sha256": report["claim_sha256"],
                    "model_sha256": report["model_sha256"],
                    "manifest_sha256": report["manifest_sha256"],
                    "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                    "checked_obligations": ["OBL-%d" % number for number in range(1, 7)],
                    "target_checks": {
                        "stack_not_coarse": True,
                        "rational_coefficients": True,
                        "genus_6": True,
                        "markings_6": True,
                        "bm_degree_16": True,
                        "bm_weight_minus_16": True,
                        "bm_tate_index_8": True,
                        "ordinary_degree_26": True,
                        "ordinary_weight_26": True,
                        "ordinary_tate_index_minus_13": True,
                        "dimension_and_twist_21": True,
                        "zero_rank_allowed": True,
                        "whole_group_not_proxy": True,
                    },
                    "axiom_checks": [
                        {
                            "axiom": "BMIsFiniteTateSum",
                            "obligation_id": "VOCAB",
                            "verdict": "confirmed",
                            "note": "trusted exact-target predicate",
                        },
                        *[
                        {
                            "axiom": "a%d" % number,
                            "obligation_id": "OBL-%d" % number,
                            "verdict": "confirmed",
                            "note": "fixture axiom %d reconstructed" % number,
                        }
                        for number in range(1, 7)
                        ],
                    ],
                    "statement_faithfulness": "field-by-field match",
                    "axiom_faithfulness": "all premises reconstructed",
                    "model_faithfulness": "model vocabulary and witnesses reconstructed",
                    "model_checks": {
                        "models_every_claim_axiom": True,
                        "witness_is_axiom_free": True,
                        "noncollapse_is_material": True,
                        "model_matches_claim_vocabulary": True,
                    },
                    "strongest_attack": "countermodel attempt failed",
                }
                for number, engine in ((1, "review-a"), (2, "review-b")):
                    review_id = "LREV-000%d" % number
                    task_id = "TASK-LV-LATT-0001-P%d" % number
                    run_path = root / "reports" / "runs" / ("RUN-LC66-%d.json" % number)
                    review = dict(
                        common,
                        id=review_id,
                        reviewer_engine=engine,
                        review_pass=number,
                        review_task_id=task_id,
                        review_run_path=str(run_path.relative_to(root)),
                    )
                    review_path = reviews / (review_id + ".json")
                    self._write_json(review_path, review)
                    self._write_json(
                        run_path,
                        {
                            "status": "completed",
                            "events": [
                                {
                                    "phase": "lean-review",
                                    "state": "completed",
                                    "review_id": review_id,
                                    "target_attempt_id": "LATT-0001",
                                    "review_pass": number,
                                    "engine": engine,
                                    "task_id": task_id,
                                    "output": str(review_path.relative_to(root)),
                                    "artifact_sha256": hashlib.sha256(
                                        review_path.read_bytes()
                                    ).hexdigest(),
                                }
                            ],
                        },
                    )
                status = lean_campaign.campaign_status()
                self.assertEqual(status["verified_attempts"], ["LATT-0001"])
                second_path = reviews / "LREV-0002.json"
                second = json.loads(second_path.read_text(encoding="utf-8"))
                second["reviewer_engine"] = "review-a"
                self._write_json(second_path, second)
                status = lean_campaign.campaign_status()
            self.assertEqual(status["verified_attempts"], [])


if __name__ == "__main__":
    unittest.main()
