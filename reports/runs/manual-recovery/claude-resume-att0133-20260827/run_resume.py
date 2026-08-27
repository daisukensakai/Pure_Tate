#!/usr/bin/env python3
"""Resume Claude's rejected ATT-0133 session in a new append-only attempt."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import _engine_argv, _extract_claude_stream, _validate_artifact, assemble_prompt, build_isolated_context
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import campaign_status, load_campaign, write_campaign_packet
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.paired import attach_working_context
from pure_tate.run_lifecycle import CampaignAlreadyRunning, CampaignRunLock, live_run_ledgers, recover_stale_run_ledgers, release_artifact_reservation, reserve_prefixed_artifact, spend_artifact_reservation
from pure_tate.store import atomic_write_json
from pure_tate.tasking import campaign_mathematics_tasks

CAMPAIGN_ID = "C66-001"
SESSION_ID = "338c6913-006d-46ea-9561-fbb16e071b92"
PARENT_TRACE = "TRACE-0104"
VAULT = Path(__file__).resolve().parent


def task() -> dict:
    packet = write_campaign_packet(CAMPAIGN_ID)
    if campaign_status(CAMPAIGN_ID)["structural_integrity"] != "ready":
        raise RuntimeError("campaign structural integrity is not ready")
    campaign = load_campaign(CAMPAIGN_ID)
    matches = [x for x in campaign_mathematics_tasks(CAMPAIGN_ID)
               if x.get("subproblem_id") == "C66-TATE-SUPPORT"]
    if len(matches) != 1 or matches[0].get("status") != "ready":
        raise RuntimeError("C66-TATE-SUPPORT is not uniquely ready")
    value = attach_working_context(dict(matches[0]), campaign)
    value["selected_engine"] = "claude"
    value["packet_sha256"] = packet["packet_sha256"]
    return value


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        current = task()
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, 1, ["cursor-grok"], ["claude"], ["cursor-grok"]
        )
        artifact_id, reservation = reserve_prefixed_artifact(
            ROOT / "proof" / "attempts", "ATT", ledger["run_id"]
        )
        output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
        current["output"] = str(output.relative_to(ROOT))
        workspace = VAULT / ("workspace-" + artifact_id)
        workspace.mkdir(parents=True, exist_ok=False)
        files = build_isolated_context(current, workspace)
        for path in workspace.rglob("*"):
            if path.is_file():
                path.chmod(path.stat().st_mode & ~0o222)
        prompt = assemble_prompt(current, files, artifact_id, "claude")
        prompt += (
            "\n\nContinuation after ATT-0133 validation rejection. The prior mathematical "
            "response was received, but its provenance metadata was invalid. Return a new "
            "artifact with the requested ID. Keep the conclusion honest. In addition to "
            "structured proof_dependencies for ATT-0120 and ATT-0130, dependency_claim_ids "
            "must include CLM-0120-2 through CLM-0120-7 and CLM-0130-1 through CLM-0130-5. "
            "Never put ATT-* or REV-* identifiers in source_ids; those are artifacts, not "
            "bibliographic sources. Re-read TASK.json and current working context. Return "
            "one JSON object only."
        )
        atomic_write_json(VAULT / ("manifest-" + artifact_id + ".json"), current)
        event = {
            "step": 1, "phase": "mathematics", "task_id": current["id"],
            "engine": "claude", "output": str(output.relative_to(ROOT)),
            "parent_attempt_id": "ATT-0133", "parent_trace_id": PARENT_TRACE,
            "state": "running", "started_at": _timestamp(),
        }
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        launch = {
            "campaign_id": CAMPAIGN_ID, "artifact_id": artifact_id,
            "parent_attempt_id": "ATT-0133", "parent_trace_id": PARENT_TRACE,
            "session_id": SESSION_ID, "status": "running",
        }
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        try:
            command = _engine_argv("claude", prompt, phase="mathematics")
            command[2:2] = ["--resume", SESSION_ID]
            completed = subprocess.run(
                command, cwd=workspace,
                env=dict(os.environ, CLAUDE_CODE_MAX_OUTPUT_TOKENS="64000"),
                capture_output=True, text=True, timeout=10800, check=False,
            )
            stdout = VAULT / (artifact_id + ".stdout.jsonl")
            stderr = VAULT / (artifact_id + ".stderr.txt")
            stdout.write_text(completed.stdout, encoding="utf-8")
            stderr.write_text(completed.stderr, encoding="utf-8")
            if completed.returncode:
                raise RuntimeError("Claude resume failed: exit=%s bytes=%s" % (completed.returncode, len(completed.stdout)))
            artifact = _extract_claude_stream(completed.stdout)
            _validate_artifact("mathematics", current, artifact, output, "claude")
            artifact["observable_trace_id"] = PARENT_TRACE
            artifact["recovery"] = {
                "classification": "manual_session_resume",
                "parent_attempt_id": "ATT-0133",
                "parent_trace_id": PARENT_TRACE,
                "parent_session_id": SESSION_ID,
                "resume_stdout": str(stdout.relative_to(ROOT)),
            }
            atomic_write_json(output, artifact)
            event.update({
                "state": "completed", "completed_at": _timestamp(),
                "attempt_id": artifact_id, "result_status": artifact.get("status"),
                "result_type": artifact.get("result_type"),
                "gap_count": len(artifact.get("gap_markers") or []),
                "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            })
        except Exception as exc:
            event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
            launch["error"] = str(exc)
            launch["traceback"] = traceback.format_exc()
        finally:
            if event["state"] == "completed" and output.is_file():
                release_artifact_reservation(reservation)
            else:
                spend_artifact_reservation(reservation, reason=event["state"], task_id=current["id"])
            ledger["events"] = [event]
            ledger["status"] = "completed" if event["state"] == "completed" else "stopped"
            ledger["stop_reason"] = "step_limit" if event["state"] == "completed" else event["state"]
            ledger["completed_at"] = _timestamp()
            event["notification_delivery"] = notify_campaign_step(CAMPAIGN_ID, event, 1, desktop=True, ntfy=True)
            ledger["run_notification_delivery"] = notify_campaign_run(CAMPAIGN_ID, 1, 1, ledger["status"], ledger["stop_reason"], desktop=True, ntfy=True)
            _write_run_ledger(ledger_path, ledger)
            launch["status"] = ledger["status"]
            atomic_write_json(launch_path, launch)
        print(json.dumps(launch, indent=2))
        return 0 if event["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
