#!/usr/bin/env python3
"""Reproduce review validation failure without preserving observable stdout."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pure_tate.agents import run_task
from pure_tate.campaigns import campaign_packet_record, load_campaign
from pure_tate.store import ROOT
from pure_tate.targets import CONTEXT_REVISION


def main() -> None:
    campaign = load_campaign("C66-001")
    packet = campaign_packet_record("C66-001")
    attempt_path = ROOT / "proof" / "attempts" / "ATT-0026.json"
    if not attempt_path.is_file():
        # Fall back to any current campaign attempt.
        attempts = sorted((ROOT / "proof" / "attempts").glob("ATT-*.json"))
        attempt_path = attempts[-1]
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    output = ROOT / "proof" / "reviews" / "REV-9998.json"
    if output.exists():
        output.unlink()

    body = {
        "schema_version": 3,
        "id": "REV-9998",
        "review_task_id": "TASK-V-%s-P1" % attempt["id"],
        "review_pass": 1,
        "attempt_id": attempt["id"],
        "campaign_id": attempt.get("campaign_id", "C66-001"),
        "campaign_revision": attempt.get(
            "campaign_revision", campaign["campaign_revision"]
        ),
        "subproblem_id": attempt.get("subproblem_id", "C66-FULL"),
        "context_revision": CONTEXT_REVISION,
        "packet_id": packet["packet_id"],
        "packet_sha256": packet["packet_sha256"],
        "target": attempt["target"],
        "theorem_statement": attempt.get(
            "theorem_statement",
            campaign["paired_attempt_policy"]["exact_theorem"],
        ),
        "verdict": "confirmed",
        "reviewer_engine": "grok",
        "independent": True,
        "checked_claims": [
            {
                "claim_id": "CLM-X",
                "result": "refuted",
                "note": "Synthetic adverse check for reproduction.",
            }
        ],
        "proof_dependency_checks": [],
        "strongest_attack": "X" * 170000,
        "finding_candidates": [
            {
                "key": "synthetic-adverse",
                "statement": "Synthetic finding for review-trace reproduction.",
            }
        ],
        "created_on": "2026-07-31",
    }
    stdout = json.dumps(
        {
            "text": json.dumps(body),
            "stopReason": "endTurn",
            "sessionId": "repro-review-trace",
        }
    )
    process = SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    task = {
        "id": "TASK-V-%s-P1" % attempt["id"],
        "phase": "review",
        "review_pass": 1,
        "target_attempt_id": attempt["id"],
        "context_revision": CONTEXT_REVISION,
        "packet_id": packet["packet_id"],
        "packet_sha256": packet["packet_sha256"],
        "target": attempt["target"],
        "prover_engine": attempt.get("engine", "codex"),
        "excluded_reviewer_engines": [attempt.get("engine", "codex")],
        "prompt": "prompts/ADVERSARY.md",
        "input_attempt": str(attempt_path.relative_to(ROOT)),
        "input_packet": packet["packet_path"],
        "campaign_id": attempt.get("campaign_id", "C66-001"),
        "campaign_revision": attempt.get(
            "campaign_revision", campaign["campaign_revision"]
        ),
        "subproblem_id": attempt.get("subproblem_id", "C66-FULL"),
        "theorem_statement": body["theorem_statement"],
    }

    with tempfile.TemporaryDirectory(dir=ROOT / "research") as directory, mock.patch(
        "pure_tate.agents.shutil.which", return_value="/usr/bin/grok"
    ), mock.patch(
        "pure_tate.agents.run_captured_process", return_value=process
    ), mock.patch(
        "pure_tate.paired.TRACE_DIR", Path(directory)
    ):
        try:
            run_task(task, "grok", output)
            print("UNEXPECTED_SUCCESS")
        except Exception as exc:
            from pure_tate.paired import ArtifactValidationError

            traces = sorted(Path(directory).glob("TRACE-*.json"))
            print("ERROR_TYPE", type(exc).__name__)
            print("ERROR", str(exc))
            print("OUTPUT_EXISTS", output.exists())
            print("TRACE_COUNT", len(traces))
            if isinstance(exc, ArtifactValidationError):
                print("TRACE_ID", exc.trace_id)
                print("TRACE_PATH", exc.trace_path)
            if traces:
                trace = json.loads(traces[0].read_text(encoding="utf-8"))
                print("TRACE_ID_FILE", trace.get("id"))
                print("TRACE_STDOUT_LEN", len(trace.get("observable_stdout") or ""))
                print("TRACE_VALIDATION", trace.get("validation_error"))
                print("TRACE_CLASSIFICATION", trace.get("classification"))
                print("TRACE_TURN_KIND", trace.get("turn_kind"))
                parsed = trace.get("parsed_artifact") or {}
                print("PARSED_ID", parsed.get("id"))
                print("PARSED_ATTACK_LEN", len(str(parsed.get("strongest_attack") or "")))
            else:
                print("TRACE_MISSING")


if __name__ == "__main__":
    main()
