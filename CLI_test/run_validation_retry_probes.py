#!/usr/bin/env python3
"""Offline probes for mechanical validation repair (coerce + feedback retry).

Nothing here is loaded by the Pure Tate harness. Results land under
CLI_test/results/validation_retry/.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pure_tate.agents import _validate_artifact, run_task  # noqa: E402
from pure_tate.validation_repair import (  # noqa: E402
    assemble_validation_repair_prompt,
    is_mechanical_validation_error,
    validation_repair_settings,
)

RESULTS = Path(__file__).resolve().parent / "results" / "validation_retry"


def _ts() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def probe_classifier() -> Dict[str, Any]:
    cases = [
        ("campaign review theorem_statement does not match task", True),
        ("artifact engine 'x' does not match selected engine claude", True),
        ("agent artifact lacks fields: summary", True),
        ("mathematics claims must be structured claim objects", True),
        ("finding audit has invalid verdict", True),
        ("artifact target contradicts the task target: g=5", False),
        ("forced-proof requires complete resolution: gaps", False),
        ("forced-proof completion_attestation.resolves_exact_target must be true", False),
        ("confirmed review contains a failed or unresolved structured check", False),
        ("agent failed with exit 1: connection refused", False),
    ]
    rows = []
    ok = True
    for message, expected in cases:
        got = is_mechanical_validation_error(message)
        rows.append({"message": message, "expected": expected, "got": got, "pass": got == expected})
        if got != expected:
            ok = False
    return {"name": "classifier", "pass": ok, "cases": rows}


def probe_coerce_review_theorem() -> Dict[str, Any]:
    from pure_tate.campaigns import campaign_packet_record, load_campaign
    from pure_tate.paired import forced_task, working_context_records
    from pure_tate.store import ROOT as HARNESS_ROOT

    campaign = load_campaign("C66-001")
    packet = campaign_packet_record("C66-001")
    base = forced_task(campaign, packet, working_context_records(campaign))
    review_task = {
        "id": "TASK-V-ATT-PROBE-P1",
        "phase": "review",
        "review_pass": 1,
        "target_attempt_id": "ATT-PROBE",
        "target_claim_id": "RED-0001",
        "context_revision": 2,
        "packet_id": base["packet_id"],
        "packet_sha256": base["packet_sha256"],
        "packet_binding_sha256": base.get("packet_binding_sha256"),
        "target": base["target"],
        "campaign_id": "C66-001",
        "campaign_revision": base["campaign_revision"],
        "subproblem_id": "C66-FULL",
        "theorem_statement": "Exact attempt theorem for coerce probe.",
        "prover_engine": "claude",
        "input_packet": base["input_packet"],
    }
    artifact = {
        "schema_version": 3,
        "id": "REV-WRONG",
        "review_task_id": review_task["id"],
        "review_pass": 1,
        "attempt_id": "ATT-PROBE",
        "context_revision": 2,
        "packet_id": base["packet_id"],
        "packet_sha256": base["packet_sha256"],
        "target": base["target"],
        "campaign_id": "C66-001",
        "campaign_revision": base["campaign_revision"],
        "subproblem_id": "C66-FULL",
        "theorem_statement": "Paraphrased theorem (would previously hard-fail).",
        "verdict": "incomplete",
        "reviewer_engine": "wrong",
        "independent": True,
        "checked_claims": [{"verdict": "failed"}],
        "strongest_attack": "gap",
        "finding_candidates": [],
        "proof_dependency_checks": [],
    }
    output = HARNESS_ROOT / "proof" / "reviews" / "REV-PROBE1.json"
    try:
        _validate_artifact("review", review_task, artifact, output, "grok")
        passed = (
            artifact["theorem_statement"] == review_task["theorem_statement"]
            and artifact["id"] == "REV-PROBE1"
            and artifact["reviewer_engine"] == "grok"
        )
        return {
            "name": "coerce_review_theorem",
            "pass": passed,
            "theorem": artifact.get("theorem_statement"),
            "id": artifact.get("id"),
            "engine": artifact.get("reviewer_engine"),
            "normalizations": artifact.get("ingest_normalizations"),
        }
    except Exception as exc:
        return {
            "name": "coerce_review_theorem",
            "pass": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def probe_repair_loop() -> Dict[str, Any]:
    from pure_tate.campaigns import campaign_packet_record, load_campaign
    from pure_tate.paired import forced_task, working_context_records

    campaign = load_campaign("C66-001")
    packet = campaign_packet_record("C66-001")
    task = forced_task(campaign, packet, working_context_records(campaign))
    task = {k: v for k, v in task.items() if k != "paired_turn_kind"}
    task["phase"] = "mathematics"

    good = {
        "schema_version": 3,
        "id": "ATT-PROBE-REPAIR",
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
        "theorem_statement": "Probe lemma.",
        "summary": "Summary after repair.",
        "argument_markdown": "Argument after repair.",
        "claims": [{"statement": "Claim.", "status": "proved"}],
        "proof_dependencies": [],
        "experiment_ids": [],
        "experiment_uses": [],
        "novelty_claims": [],
        "gap_markers": ["open"],
        "failed_approaches_addressed": [],
        "methods_used": [],
        "new_inputs": [],
        "status": "proposed",
        "source_claim_ids": [],
        "engine": "claude",
    }
    bad = copy.deepcopy(good)
    del bad["summary"]

    calls: List[str] = []

    class FakeProcess:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = 0

    def fake_run(command, **kwargs):
        # Capture whether the prompt looks like a repair turn.
        joined = " ".join(str(x) for x in command)
        calls.append(joined)
        payload = bad if len(calls) == 1 else good
        body = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": json.dumps(payload),
            }
        )
        return FakeProcess(body + "\n")

    # Capture repair prompt via _engine_argv side channel.
    prompts: List[str] = []

    def fake_argv(engine_id, prompt, last_message, **kwargs):
        prompts.append(prompt)
        return ["true"]

    from pure_tate.store import ROOT as HARNESS_ROOT

    out = HARNESS_ROOT / "proof" / "attempts" / "ATT-PROBE-REPAIR.json"
    if out.exists():
        out.unlink()
    try:
        with mock.patch(
            "pure_tate.agents.run_captured_process", side_effect=fake_run
        ), mock.patch(
            "pure_tate.agents._engine_argv", side_effect=fake_argv
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
        ):
            result = run_task(task, "claude", out, timeout=30)

        repair_prompt_ok = any("VALIDATION REPAIR" in p for p in prompts)
        err0 = (result.get("validation_repair", {}).get("errors") or [""])[0]
        return {
            "name": "repair_loop",
            "pass": (
                len(calls) == 2
                and result.get("validation_repair", {}).get("repaired") is True
                and repair_prompt_ok
                and "summary" in err0
                and result.get("id") == "ATT-PROBE-REPAIR"
            ),
            "engine_calls": len(calls),
            "repair_prompt_seen": repair_prompt_ok,
            "validation_repair": result.get("validation_repair"),
            "artifact_id": result.get("id"),
            "settings": validation_repair_settings(
                {"validation_repair": {"enabled": True, "retry_limit": 1}}
            ),
        }
    except Exception as exc:
        return {
            "name": "repair_loop",
            "pass": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "prompts": [p[:200] for p in prompts],
            "calls": len(calls),
        }
    finally:
        if out.exists():
            out.unlink()


def probe_no_retry_substantive() -> Dict[str, Any]:
    from pure_tate.campaigns import campaign_packet_record, load_campaign
    from pure_tate.paired import SubstantiveAttemptError, forced_task, working_context_records

    campaign = load_campaign("C66-001")
    packet = campaign_packet_record("C66-001")
    task = forced_task(campaign, packet, working_context_records(campaign))
    incomplete = {
        "schema_version": 3,
        "id": "ATT-PROBE-SUB",
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
        "summary": "Incomplete forced proof.",
        "argument_markdown": "Gap remains.",
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

    from pure_tate.store import ROOT as HARNESS_ROOT

    out = HARNESS_ROOT / "proof" / "attempts" / "ATT-PROBE-SUB.json"
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
                "id": "TRACE-PROBE",
                "path": "research/paired-traces/TRACE-PROBE.json",
                "sha256": "b" * 64,
            },
        ):
            raised = None
            try:
                run_task(task, "claude", out, timeout=30)
            except SubstantiveAttemptError as exc:
                raised = str(exc)
        return {
            "name": "no_retry_substantive",
            "pass": calls["n"] == 1
            and raised is not None
            and "complete resolution" in (raised or ""),
            "engine_calls": calls["n"],
            "error": raised,
        }
    except Exception as exc:
        return {
            "name": "no_retry_substantive",
            "pass": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        if out.exists():
            out.unlink()



def probe_repair_prompt_shape() -> Dict[str, Any]:
    prompt = assemble_validation_repair_prompt(
        base_prompt="# Execution contract\n\nReturn JSON.",
        phase="mathematics",
        task={"id": "TASK-X", "target_claim_id": "RED-0001"},
        output_stem="ATT-0001",
        engine_id="claude",
        previous_artifact={"id": "ATT-BAD", "engine": "x"},
        validation_errors=["artifact engine 'x' does not match selected engine claude"],
    )
    checks = {
        "has_base": "Execution contract" in prompt,
        "has_header": "VALIDATION REPAIR" in prompt,
        "has_error": "does not match selected engine" in prompt,
        "has_previous": "ATT-BAD" in prompt,
        "has_expected_id": "ATT-0001" in prompt,
    }
    return {
        "name": "repair_prompt_shape",
        "pass": all(checks.values()),
        "checks": checks,
        "prompt_chars": len(prompt),
    }


def main() -> int:
    stamp = _ts()
    out_dir = RESULTS / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    probes = [
        probe_classifier,
        probe_coerce_review_theorem,
        probe_repair_prompt_shape,
        probe_repair_loop,
        probe_no_retry_substantive,
    ]
    results = []
    for probe in probes:
        print("RUN", probe.__name__, flush=True)
        result = probe()
        results.append(result)
        _write(out_dir / (result["name"] + ".json"), result)
        print(" ", "PASS" if result.get("pass") else "FAIL", result["name"], flush=True)

    manifest = {
        "created_at": stamp,
        "all_pass": all(r.get("pass") for r in results),
        "probes": [{k: r.get(k) for k in ("name", "pass")} for r in results],
    }
    _write(out_dir / "manifest.json", manifest)
    (RESULTS / "latest.txt").write_text(stamp + "\n", encoding="utf-8")
    print("ALL_PASS" if manifest["all_pass"] else "SOME_FAILED", out_dir, flush=True)
    return 0 if manifest["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
