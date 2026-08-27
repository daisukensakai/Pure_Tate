#!/usr/bin/env python3
"""Run Claude's independent finding audit of FND-0192."""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pure_tate.agents import run_task
from pure_tate.campaign_driver import _apply_finding_audit, _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import write_campaign_packet
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.paired import ArtifactValidationError
from pure_tate.run_lifecycle import CampaignAlreadyRunning, CampaignRunLock, live_run_ledgers, recover_stale_run_ledgers, release_artifact_reservation, reserve_prefixed_artifact, spend_artifact_reservation
from pure_tate.store import atomic_write_json
from pure_tate.tasking import finding_audit_tasks

CAMPAIGN_ID = "C66-001"
FINDING_ID = "FND-0192"
ENGINE = "claude"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent


def current_task() -> dict:
    write_campaign_packet(CAMPAIGN_ID)
    matches = [task for task in finding_audit_tasks(CAMPAIGN_ID) if task.get("finding_id") == FINDING_ID]
    if len(matches) != 1 or matches[0].get("status") != "ready":
        raise RuntimeError("FND-0192 has no ready finding-audit task")
    task = dict(matches[0])
    if ENGINE in set(task.get("excluded_engines") or []):
        raise RuntimeError("Claude is not independent for FND-0192")
    task["selected_engine"] = ENGINE
    return task


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning("campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active)))
        task = current_task()
        ledger, ledger_path = _new_run_ledger(CAMPAIGN_ID, 1, [ENGINE], ["cursor-grok"], ["qwen"])
        artifact_id, reservation = reserve_prefixed_artifact(ROOT / "research" / "finding-audits", "FAUD", ledger["run_id"])
        output = ROOT / "research" / "finding-audits" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        manifest = VAULT / ("manifest-%s.json" % artifact_id)
        atomic_write_json(manifest, task)
        launch_path = VAULT / "LAUNCH.json"
        launch = {"campaign_id": CAMPAIGN_ID, "finding_id": FINDING_ID, "task_id": task["id"], "engine": ENGINE, "artifact_id": artifact_id, "output": str(output.relative_to(ROOT)), "manifest": str(manifest), "status": "running"}
        atomic_write_json(launch_path, launch)
        event = {"step": 1, "phase": "finding-audit", "task_id": task["id"], "engine": ENGINE, "output": str(output.relative_to(ROOT)), "finding_id": FINDING_ID, "state": "running", "started_at": _timestamp()}
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        try:
            audit = run_task(task, ENGINE, output, timeout=TIMEOUT)
            _apply_finding_audit(audit)
            event.update({"state": "completed", "completed_at": _timestamp(), "audit_id": audit.get("id"), "verdict": audit.get("verdict"), "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
            launch.update({"verdict": audit.get("verdict"), "applied": True})
        except Exception as exc:
            event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
            launch["error"] = str(exc)
            if isinstance(exc, ArtifactValidationError):
                event["trace_id"] = exc.trace_id
                event["trace_path"] = exc.trace_path
            else:
                launch["traceback"] = traceback.format_exc()
        finally:
            if event["state"] == "completed" and output.is_file():
                release_artifact_reservation(reservation)
            else:
                spend_artifact_reservation(reservation, reason=event["state"], trace_id=event.get("trace_id"), task_id=task["id"])
            ledger["events"] = [event]
            ledger["status"] = "completed" if event["state"] == "completed" else "stopped"
            ledger["stop_reason"] = "step_limit" if event["state"] == "completed" else event["state"]
            ledger["completed_at"] = _timestamp()
            event["notification_delivery"] = notify_campaign_step(CAMPAIGN_ID, event, 1, desktop=True, ntfy=True)
            ledger["run_notification_delivery"] = notify_campaign_run(CAMPAIGN_ID, 1, 1, ledger["status"], ledger["stop_reason"], desktop=True, ntfy=True)
            _write_run_ledger(ledger_path, ledger)
            launch["status"] = ledger["status"]
            atomic_write_json(launch_path, launch)
        print(json.dumps(launch, indent=2), flush=True)
        return 0 if event["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
