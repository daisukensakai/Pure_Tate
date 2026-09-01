#!/usr/bin/env python3
"""Run Claude's C66BAR boundary-image assembly attempt."""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import run_task
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import campaign_status, load_campaign, write_campaign_packet
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.paired import ArtifactValidationError, attach_working_context
from pure_tate.run_lifecycle import (
    CampaignAlreadyRunning,
    CampaignRunLock,
    live_run_ledgers,
    recover_stale_run_ledgers,
    release_artifact_reservation,
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import atomic_write_json
from pure_tate.tasking import campaign_mathematics_tasks

CAMPAIGN_ID = "C66BAR-001"
SUBPROBLEM_ID = "C66BAR-IMAGE"
ENGINE = "claude"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent


def current_task() -> dict:
    packet = write_campaign_packet(CAMPAIGN_ID)
    if campaign_status(CAMPAIGN_ID).get("structural_integrity") != "ready":
        raise RuntimeError("campaign structural integrity is not ready")
    campaign = load_campaign(CAMPAIGN_ID)
    matches = [
        task for task in campaign_mathematics_tasks(CAMPAIGN_ID)
        if task.get("subproblem_id") == SUBPROBLEM_ID
    ]
    if len(matches) != 1 or matches[0].get("status") != "ready":
        raise RuntimeError("C66BAR-IMAGE is not uniquely ready")
    task = attach_working_context(dict(matches[0]), campaign)
    expected = {
        "C66BAR-GRAPH": "ATT-0140",
        "C66BAR-SEP": "ATT-0143",
        "C58-COMPACT": "ATT-0145",
    }
    if task.get("dependency_artifacts") != expected:
        raise RuntimeError("verified C66BAR dependencies are not the expected artifacts")
    task["selected_engine"] = ENGINE
    task["packet_sha256"] = packet["packet_sha256"]
    return task


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        task = current_task()
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, 1, [ENGINE], [ENGINE], [ENGINE]
        )
        artifact_id, reservation = reserve_prefixed_artifact(
            ROOT / "proof" / "attempts", "ATT", ledger["run_id"]
        )
        output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        atomic_write_json(VAULT / ("manifest-" + artifact_id + ".json"), task)
        launch = {
            "campaign_id": CAMPAIGN_ID,
            "task_id": task["id"],
            "subproblem_id": SUBPROBLEM_ID,
            "engine": ENGINE,
            "artifact_id": artifact_id,
            "output": str(output.relative_to(ROOT)),
            "packet_binding_sha256": task.get("packet_binding_sha256"),
            "working_context": task.get("working_context"),
            "status": "running",
        }
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        event = {
            "step": 1,
            "phase": "mathematics",
            "task_id": task["id"],
            "engine": ENGINE,
            "output": str(output.relative_to(ROOT)),
            "state": "running",
            "started_at": _timestamp(),
            "working_context": task.get("working_context"),
        }
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        try:
            artifact = run_task(task, ENGINE, output, timeout=TIMEOUT)
            event.update({
                "state": "completed",
                "completed_at": _timestamp(),
                "attempt_id": artifact.get("id"),
                "result_status": artifact.get("status"),
                "result_type": artifact.get("result_type"),
                "gap_count": len(artifact.get("gap_markers") or []),
                "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            })
            launch.update({
                "result_status": artifact.get("status"),
                "result_type": artifact.get("result_type"),
                "gap_count": len(artifact.get("gap_markers") or []),
            })
        except Exception as exc:
            event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
            launch["error"] = str(exc)
            if isinstance(exc, ArtifactValidationError):
                event["trace_id"], event["trace_path"] = exc.trace_id, exc.trace_path
            else:
                launch["traceback"] = traceback.format_exc()
        finally:
            if event["state"] == "completed" and output.is_file():
                release_artifact_reservation(reservation)
            else:
                spend_artifact_reservation(
                    reservation,
                    reason=event["state"],
                    trace_id=event.get("trace_id"),
                    task_id=task["id"],
                )
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
