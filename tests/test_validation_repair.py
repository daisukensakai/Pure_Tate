"""Tests for mechanical validation repair (coerce + feedback retry)."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.agents import _validate_artifact, run_task
from pure_tate.store import ROOT
from pure_tate.validation_repair import (
    assemble_validation_repair_prompt,
    is_mechanical_validation_error,
    validation_repair_settings,
)


class MechanicalClassifierTests(unittest.TestCase):
    def test_exact_match_errors_are_mechanical(self):
        for message in (
            "campaign review theorem_statement does not match task",
            "artifact engine 'gpt' does not match selected engine claude",
            "artifact id 'ATT-0001' does not match output filename ATT-0002.json",
            "agent artifact lacks fields: summary, claims",
            "mathematics claims must be structured claim objects",
            "mathematics artifact status must use the exact schema enum (got 'done')",
            "finding audit task_id does not match task",
            "finding audit has invalid verdict",
        ):
            self.assertTrue(
                is_mechanical_validation_error(message), msg=message
            )

    def test_substantive_errors_are_not_mechanical(self):
        for message in (
            "artifact target contradicts the task target: g=5 (task 6)",
            "forced-proof requires complete resolution: has gap markers",
            "forced-proof completion_attestation.resolves_exact_target must be true",
            "confirmed review contains a failed or unresolved structured check",
            "agent failed with exit 1: connection refused",
        ):
            self.assertFalse(
                is_mechanical_validation_error(message), msg=message
            )

    def test_settings_defaults(self):
        settings = validation_repair_settings({})
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["retry_limit"], 1)
        settings = validation_repair_settings(
            {"validation_repair": {"enabled": False, "retry_limit": 9}}
        )
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["retry_limit"], 2)  # capped


class CoerceIdentityTests(unittest.TestCase):
    def setUp(self):
        from pure_tate.campaigns import campaign_packet_record, load_campaign
        from pure_tate.paired import forced_task, working_context_records

        self.campaign = load_campaign("C66-001")
        packet = campaign_packet_record("C66-001")
        self.task = forced_task(
            self.campaign, packet, working_context_records(self.campaign)
        )
        self.output = ROOT / "proof" / "attempts" / "ATT-9998.json"

    def _full_math(self):
        return {
            "schema_version": 3,
            "id": "ATT-WRONG",
            "task_id": self.task["id"],
            "campaign_id": "C66-001",
            "campaign_revision": self.task["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "lane": "full-resolution",
            "result_type": "lemma",
            "target_claim_id": "RED-0001",
            "context_revision": 2,
            "packet_id": self.task["packet_id"],
            "packet_path": self.task["input_packet"],
            "packet_sha256": self.task["packet_sha256"],
            "target": self.task["target"],
            "theorem_statement": "A weak lemma.",
            "summary": "Summary.",
            "argument_markdown": "Argument.",
            "claims": [{"statement": "Claim.", "status": "proved"}],
            "proof_dependencies": [],
            "experiment_ids": [],
            "experiment_uses": [],
            "novelty_claims": [],
            "gap_markers": [],
            "failed_approaches_addressed": [],
            "methods_used": [],
            "new_inputs": [],
            "status": "proposed",
            "source_claim_ids": [],
            "engine": "wrong-engine",
        }

    def test_engine_and_id_coerced(self):
        artifact = self._full_math()
        # Drop paired_turn_kind so forced-proof completeness does not apply.
        task = {
            key: value
            for key, value in self.task.items()
            if key != "paired_turn_kind"
        }
        _validate_artifact("mathematics", task, artifact, self.output, "claude")
        self.assertEqual(artifact["id"], "ATT-9998")
        self.assertEqual(artifact["engine"], "claude")
        rules = [
            row.get("rule")
            for row in artifact.get("ingest_normalizations") or []
        ]
        self.assertIn("HARNESS-IDENTITY-COERCE-0001", rules)

    def test_review_theorem_statement_coerced_from_task(self):
        review_task = {
            "id": "TASK-V-ATT-9998-P1",
            "phase": "review",
            "review_pass": 1,
            "target_attempt_id": "ATT-9998",
            "target_claim_id": "RED-0001",
            "context_revision": 2,
            "packet_id": self.task["packet_id"],
            "packet_sha256": self.task["packet_sha256"],
            "packet_binding_sha256": self.task.get("packet_binding_sha256"),
            "target": self.task["target"],
            "campaign_id": "C66-001",
            "campaign_revision": self.task["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "theorem_statement": "Exact attempt theorem statement.",
            "prover_engine": "claude",
            "input_packet": self.task["input_packet"],
        }
        artifact = {
            "schema_version": 3,
            "id": "REV-WRONG",
            "review_task_id": "TASK-V-ATT-9998-P1",
            "review_pass": 1,
            "attempt_id": "ATT-9998",
            "context_revision": 2,
            "packet_id": self.task["packet_id"],
            "packet_sha256": self.task["packet_sha256"],
            "target": self.task["target"],
            "campaign_id": "C66-001",
            "campaign_revision": self.task["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "theorem_statement": "Paraphrased theorem with different wording.",
            "verdict": "incomplete",
            "reviewer_engine": "grok",
            "independent": True,
            "checked_claims": [{"verdict": "failed"}],
            "strongest_attack": "gap",
            "finding_candidates": [],
            "proof_dependency_checks": [],
        }
        output = ROOT / "proof" / "reviews" / "REV-9998.json"
        _validate_artifact("review", review_task, artifact, output, "grok")
        self.assertEqual(
            artifact["theorem_statement"], "Exact attempt theorem statement."
        )
        self.assertEqual(artifact["id"], "REV-9998")
        self.assertEqual(artifact["reviewer_engine"], "grok")


class RepairPromptTests(unittest.TestCase):
    def test_prompt_includes_error_and_previous_json(self):
        prompt = assemble_validation_repair_prompt(
            base_prompt="BASE CONTRACT",
            phase="mathematics",
            task={"id": "TASK-1", "target_claim_id": "RED-0001"},
            output_stem="ATT-0001",
            engine_id="claude",
            previous_artifact={"id": "ATT-BAD", "engine": "x", "summary": "s"},
            validation_errors=["artifact engine 'x' does not match selected engine claude"],
        )
        self.assertIn("BASE CONTRACT", prompt)
        self.assertIn("VALIDATION REPAIR", prompt)
        self.assertIn("does not match selected engine", prompt)
        self.assertIn("ATT-BAD", prompt)
        self.assertIn('engine: "claude"', prompt)


class RunTaskRepairLoopTests(unittest.TestCase):
    def test_run_task_retries_once_on_mechanical_failure(self):
        # Minimal research task path is simpler than campaign math (no packet).
        # Use mathematics with heavy mocks instead.
        from pure_tate.campaigns import campaign_packet_record, load_campaign
        from pure_tate.paired import forced_task, working_context_records

        campaign = load_campaign("C66-001")
        packet = campaign_packet_record("C66-001")
        task = forced_task(campaign, packet, working_context_records(campaign))
        task = {
            key: value
            for key, value in task.items()
            if key != "paired_turn_kind"
        }
        task["phase"] = "mathematics"

        good = {
            "schema_version": 3,
            "id": "ATT-REPAIR1",
            "task_id": task["id"],
            "campaign_id": "C66-001",
            "campaign_revision": task["campaign_revision"],
            "subproblem_id": task["subproblem_id"],
            "lane": task.get("lane") or "geometry",
            "result_type": "lemma",
            "target_claim_id": task["target_claim_id"],
            "context_revision": 2,
            "packet_id": task["packet_id"],
            "packet_path": task["input_packet"],
            "packet_sha256": task["packet_sha256"],
            "target": task["target"],
            "theorem_statement": "Weak lemma.",
            "summary": "Summary text.",
            "argument_markdown": "Argument text.",
            "claims": [{"statement": "A claim.", "status": "proved"}],
            "proof_dependencies": [],
            "experiment_ids": [],
            "experiment_uses": [],
            "novelty_claims": [],
            "gap_markers": ["open gap"],
            "failed_approaches_addressed": [],
            "methods_used": [],
            "new_inputs": [],
            "status": "proposed",
            "source_claim_ids": [],
            "engine": "claude",
        }
        # Mechanical failure that survives coerce: missing required field.
        bad = copy.deepcopy(good)
        del bad["summary"]

        calls = {"n": 0}

        class FakeProcess:
            def __init__(self, stdout: str):
                self.stdout = stdout
                self.stderr = ""
                self.returncode = 0

        def fake_run(*args, **kwargs):
            calls["n"] += 1
            payload = bad if calls["n"] == 1 else good
            # Claude stream-json envelope
            body = json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": json.dumps(payload),
                }
            )
            return FakeProcess(body + "\n")

        out = ROOT / "proof" / "attempts" / "ATT-REPAIR1.json"
        if out.exists():
            out.unlink()
        try:
            with mock.patch(
                "pure_tate.agents.run_captured_process", side_effect=fake_run
            ), mock.patch(
                "pure_tate.agents._engine_argv",
                return_value=["true"],
            ), mock.patch(
                "pure_tate.agents.load_engines",
                return_value={
                    "claude": {
                        "family": "claude",
                        "command": ["claude"],
                        "max_output_tokens": 1000,
                    }
                },
            ), mock.patch(
                "pure_tate.agents.load_engines_config",
                return_value={
                    "validation_repair": {"enabled": True, "retry_limit": 1},
                    "grok_workers": {"enabled": False, "max_workers": 0},
                },
            ), mock.patch(
                "pure_tate.agents._engine_has_web_access", return_value=False
            ), mock.patch(
                "pure_tate.health.engine_runtime_issue", return_value=None
            ), mock.patch(
                "pure_tate.capabilities.capability_is_attested", return_value=True
            ), mock.patch(
                "pure_tate.grok_workers.prepare_worker_session", return_value=None
            ), mock.patch(
                "pure_tate.grok_workers.max_grok_workers_from_config",
                return_value=0,
            ), mock.patch(
                "pure_tate.grok_workers.merge_worker_env",
                side_effect=lambda env, workers: env,
            ), mock.patch(
                "pure_tate.grok_workers.record_parent_mcp_events"
            ), mock.patch(
                "pure_tate.agents.build_isolated_context",
                return_value=["TASK.json"],
            ):
                result = run_task(task, "claude", out, timeout=30)

            self.assertEqual(calls["n"], 2)
            self.assertTrue(out.is_file())
            self.assertEqual(result["id"], "ATT-REPAIR1")
            self.assertTrue(result.get("validation_repair", {}).get("repaired"))
            self.assertEqual(len(result["validation_repair"]["errors"]), 1)
            self.assertIn("summary", result["validation_repair"]["errors"][0])
        finally:
            if out.exists():
                out.unlink()

    def test_run_task_does_not_retry_substantive_error(self):
        from pure_tate.campaigns import campaign_packet_record, load_campaign
        from pure_tate.paired import forced_task, working_context_records
        from pure_tate.paired import SubstantiveAttemptError

        campaign = load_campaign("C66-001")
        packet = campaign_packet_record("C66-001")
        task = forced_task(campaign, packet, working_context_records(campaign))
        # Keep forced-proof turn kind so incompleteness is substantive.
        incomplete = {
            "schema_version": 3,
            "id": "ATT-REPAIR2",
            "task_id": task["id"],
            "campaign_id": "C66-001",
            "campaign_revision": task["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "lane": "full-resolution",
            "result_type": "proof",
            "target_claim_id": "RED-0001",
            "context_revision": 2,
            "packet_id": task["packet_id"],
            "packet_path": task["input_packet"],
            "packet_sha256": task["packet_sha256"],
            "target": task["target"],
            "theorem_statement": task["exact_theorem"],
            "summary": "Incomplete.",
            "argument_markdown": "Has a gap.",
            "claims": [{"statement": "Open.", "status": "source_backed"}],
            "proof_dependencies": [],
            "experiment_ids": [],
            "experiment_uses": [],
            "novelty_claims": [],
            "gap_markers": ["gap"],
            "failed_approaches_addressed": [],
            "methods_used": [],
            "new_inputs": [],
            "completion_attestation": {
                "resolves_exact_target": True,
                "no_undischarged_dependencies": True,
                "not_reduction_only": True,
                "no_problem_status_claim": True,
                "exact_problem_web_search_used": False,
            },
            "status": "claimed_complete",
            "source_claim_ids": [],
            "engine": "claude",
        }
        calls = {"n": 0}

        class FakeProcess:
            def __init__(self, stdout: str):
                self.stdout = stdout
                self.stderr = ""
                self.returncode = 0

        def fake_run(*args, **kwargs):
            calls["n"] += 1
            body = json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": json.dumps(incomplete),
                }
            )
            return FakeProcess(body + "\n")

        out = ROOT / "proof" / "attempts" / "ATT-REPAIR2.json"
        if out.exists():
            out.unlink()
        try:
            with mock.patch(
                "pure_tate.agents.run_captured_process", side_effect=fake_run
            ), mock.patch(
                "pure_tate.agents._engine_argv", return_value=["true"]
            ), mock.patch(
                "pure_tate.agents.load_engines",
                return_value={
                    "claude": {
                        "family": "claude",
                        "command": ["claude"],
                        "max_output_tokens": 1000,
                    }
                },
            ), mock.patch(
                "pure_tate.agents.load_engines_config",
                return_value={
                    "validation_repair": {"enabled": True, "retry_limit": 1},
                    "grok_workers": {"enabled": False, "max_workers": 0},
                },
            ), mock.patch(
                "pure_tate.health.engine_runtime_issue", return_value=None
            ), mock.patch(
                "pure_tate.grok_workers.prepare_worker_session", return_value=None
            ), mock.patch(
                "pure_tate.grok_workers.max_grok_workers_from_config",
                return_value=0,
            ), mock.patch(
                "pure_tate.grok_workers.merge_worker_env",
                side_effect=lambda env, workers: env,
            ), mock.patch(
                "pure_tate.grok_workers.record_parent_mcp_events"
            ), mock.patch(
                "pure_tate.agents.build_isolated_context",
                return_value=["TASK.json"],
            ), mock.patch(
                "pure_tate.paired.write_observable_trace",
                return_value={
                    "id": "TRACE-TEST",
                    "path": "research/paired-traces/TRACE-TEST.json",
                    "sha256": "a" * 64,
                },
            ):
                with self.assertRaises(SubstantiveAttemptError):
                    run_task(task, "claude", out, timeout=30)

            self.assertEqual(calls["n"], 1)
            self.assertFalse(out.is_file())
        finally:
            if out.exists():
                out.unlink()


if __name__ == "__main__":
    unittest.main()
