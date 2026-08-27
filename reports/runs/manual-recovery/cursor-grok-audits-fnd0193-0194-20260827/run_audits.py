#!/usr/bin/env python3
"""Serial Cursor-Grok finding audits for FND-0193 and FND-0194."""
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
ENGINE = "cursor-grok"
FINDING_IDS = ("FND-0193", "FND-0194")
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent


def selected_tasks() -> list[dict]:
    write_campaign_packet(CAMPAIGN_ID)
    available = {item["finding_id"]: item for item in finding_audit_tasks(CAMPAIGN_ID)}
    tasks = []
    for finding_id in FINDING_IDS:
        task = available.get(finding_id)
        if task is None or task.get("status") != "ready":
            raise RuntimeError("%s is not a ready finding-audit" % finding_id)
        if ENGINE in set(task.get("excluded_engines") or []):
            raise RuntimeError("%s is excluded from %s" % (ENGINE, finding_id))
        task = dict(task)
        task["selected_engine"] = ENGINE
        tasks.append(task)
    return tasks


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(
                "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
            )
        tasks = selected_tasks()
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, len(tasks), [ENGINE], [ENGINE], [ENGINE]
        )
        launch = {
            "campaign_id": CAMPAIGN_ID,
            "engine": ENGINE,
            "finding_ids": list(FINDING_IDS),
            "run_id": ledger["run_id"],
            "status": "running",
            "jobs": [],
        }
        events = []
        failures = 0
        for step, task in enumerate(tasks, start=1):
            artifact_id, reservation = reserve_prefixed_artifact(
                ROOT / "research" / "finding-audits", "FAUD", ledger["run_id"]
            )
            output = ROOT / "research" / "finding-audits" / (artifact_id + ".json")
            task["output"] = str(output.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
            event = {
                "step": step,
                "phase": "finding-audit",
                "task_id": task["id"],
                "finding_id": task["finding_id"],
                "engine": ENGINE,
                "output": str(output.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
            }
            job = {
                "artifact_id": artifact_id,
                "finding_id": task["finding_id"],
                "output": event["output"],
                "status": "running",
            }
            events.append(event)
            launch["jobs"].append(job)
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            try:
                artifact = run_task(task, ENGINE, output, timeout=TIMEOUT)
                _apply_finding_audit(artifact)
                event.update({
                    "state": "completed",
                    "completed_at": _timestamp(),
                    "audit_id": artifact.get("id"),
                    "verdict": artifact.get("verdict"),
                    "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                })
                job.update({
                    "status": "done",
                    "audit_id": artifact.get("id"),
                    "verdict": artifact.get("verdict"),
                    "applied": True,
                })
            except Exception as exc:
                failures += 1
                event.update({
                    "state": "failed",
                    "completed_at": _timestamp(),
                    "error": str(exc),
                })
                job.update({"status": "failed", "error": str(exc)})
                if isinstance(exc, ArtifactValidationError):
                    event["trace_id"] = exc.trace_id
                    event["trace_path"] = exc.trace_path
                else:
                    job["traceback"] = traceback.format_exc()
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
                event["notification_delivery"] = notify_campaign_step(
                    CAMPAIGN_ID, event, len(tasks), desktop=True, ntfy=True
                )
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)
                atomic_write_json(VAULT / "LAUNCH.json", launch)
        ledger["status"] = "completed" if failures == 0 else "stopped"
        ledger["stop_reason"] = "step_limit" if failures == 0 else "engine_failure"
        ledger["completed_at"] = _timestamp()
        ledger["executed_steps"] = len(events)
        ledger["run_notification_delivery"] = notify_campaign_run(
            CAMPAIGN_ID,
            len(tasks),
            len(events),
            ledger["status"],
            ledger["stop_reason"],
            desktop=True,
            ntfy=True,
        )
        _write_run_ledger(ledger_path, ledger)
        launch["status"] = ledger["status"]
        launch["stop_reason"] = ledger["stop_reason"]
        atomic_write_json(VAULT / "LAUNCH.json", launch)
        print(json.dumps(launch, indent=2), flush=True)
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
