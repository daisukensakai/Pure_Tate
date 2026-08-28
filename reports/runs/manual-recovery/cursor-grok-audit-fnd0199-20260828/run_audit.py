#!/usr/bin/env python3
"""Independent Cursor-Grok audit of the promoted FND-0199 obstruction."""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import run_task
from pure_tate.campaign_driver import (
    _apply_finding_audit,
    _new_run_ledger,
    _timestamp,
    _write_run_ledger,
)
from pure_tate.campaigns import write_campaign_packet
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.paired import ArtifactValidationError
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
from pure_tate.tasking import finding_audit_tasks

CAMPAIGN_ID = "C66-001"
FINDING_ID = "FND-0199"
ENGINE = "grok"  # data/engines.json routes Grok workers to Cursor by default.
VAULT = Path(__file__).resolve().parent


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        write_campaign_packet(CAMPAIGN_ID)
        available = {item["finding_id"]: item for item in finding_audit_tasks(CAMPAIGN_ID)}
        task = available.get(FINDING_ID)
        if task is None or task.get("status") != "ready":
            raise RuntimeError("%s is not ready for audit" % FINDING_ID)
        if ENGINE in set(task.get("excluded_engines") or []):
            raise RuntimeError("%s is excluded from %s" % (ENGINE, FINDING_ID))
        task = dict(task)
        task["selected_engine"] = ENGINE
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, 1, [ENGINE], [ENGINE], [ENGINE]
        )
        artifact_id, reservation = reserve_prefixed_artifact(
            ROOT / "research" / "finding-audits", "FAUD", ledger["run_id"]
        )
        output = ROOT / "research" / "finding-audits" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
        launch = {
            "campaign_id": CAMPAIGN_ID,
            "finding_id": FINDING_ID,
            "engine": ENGINE,
            "worker_backend": "cursor",
            "artifact_id": artifact_id,
            "run_id": ledger["run_id"],
            "status": "running",
        }
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        event = {
            "step": 1,
            "phase": "finding-audit",
            "task_id": task["id"],
            "finding_id": FINDING_ID,
            "engine": ENGINE,
            "output": str(output.relative_to(ROOT)),
            "state": "running",
            "started_at": _timestamp(),
        }
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        try:
            artifact = run_task(task, ENGINE, output, timeout=10800)
            _apply_finding_audit(artifact)
            event.update({
                "state": "completed",
                "completed_at": _timestamp(),
                "audit_id": artifact.get("id"),
                "verdict": artifact.get("verdict"),
                "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            })
            launch.update({
                "audit_id": artifact.get("id"),
                "verdict": artifact.get("verdict"),
                "applied": True,
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
            ledger["stop_reason"] = "finding_audit_complete" if event["state"] == "completed" else event["state"]
            ledger["completed_at"] = _timestamp()
            event["notification_delivery"] = notify_campaign_step(CAMPAIGN_ID, event, 1, desktop=True, ntfy=True)
            ledger["run_notification_delivery"] = notify_campaign_run(CAMPAIGN_ID, 1, 1, ledger["status"], ledger["stop_reason"], desktop=True, ntfy=True)
            _write_run_ledger(ledger_path, ledger)
            launch["status"], launch["stop_reason"] = ledger["status"], ledger["stop_reason"]
            atomic_write_json(launch_path, launch)
        print(json.dumps(launch, indent=2))
        return 0 if event["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
