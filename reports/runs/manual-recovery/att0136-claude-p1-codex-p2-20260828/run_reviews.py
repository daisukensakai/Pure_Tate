#!/usr/bin/env python3
"""Claude P1 then Codex P2 independent reviews of Grok proof ATT-0136."""
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
from pure_tate.campaigns import write_campaign_packet
from pure_tate.findings import record_review_findings
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
from pure_tate.store import atomic_write_json, load_json
from pure_tate.tasking import review_tasks

CAMPAIGN_ID = "C66-001"
ATTEMPT_ID = "ATT-0136"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
STEPS = (
    {"pass": 1, "task_id": "TASK-V-ATT-0136-P1", "engine": "claude"},
    {"pass": 2, "task_id": "TASK-V-ATT-0136-P2", "engine": "codex"},
)


def ready_task(task_id: str, pass_number: int, engine: str) -> dict:
    write_campaign_packet(CAMPAIGN_ID)
    matches = [
        item
        for item in review_tasks(ATTEMPT_ID)
        if item.get("id") == task_id and item.get("review_pass") == pass_number
    ]
    if len(matches) != 1 or matches[0].get("status") != "ready":
        raise RuntimeError("%s has no ready %s" % (ATTEMPT_ID, task_id))
    task = dict(matches[0])
    if engine in set(task.get("excluded_reviewer_engines") or []):
        raise RuntimeError("%s is not independent for %s" % (engine, ATTEMPT_ID))
    task["selected_engine"] = engine
    return task


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        engines = [step["engine"] for step in STEPS]
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, len(STEPS), engines, ["grok"], engines
        )
        launch = {
            "campaign_id": CAMPAIGN_ID,
            "target_attempt_id": ATTEMPT_ID,
            "steps": [],
            "status": "running",
        }
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        events = []
        overall = "completed"
        stop_reason = "step_limit"
        try:
            for index, step in enumerate(STEPS, 1):
                task = ready_task(step["task_id"], step["pass"], step["engine"])
                artifact_id, reservation = reserve_prefixed_artifact(
                    ROOT / "proof" / "reviews", "REV", ledger["run_id"]
                )
                output = ROOT / "proof" / "reviews" / (artifact_id + ".json")
                task["output"] = str(output.relative_to(ROOT))
                atomic_write_json(VAULT / ("manifest-" + artifact_id + ".json"), task)
                event = {
                    "step": index,
                    "phase": "review",
                    "task_id": step["task_id"],
                    "target_attempt_id": ATTEMPT_ID,
                    "review_pass": step["pass"],
                    "engine": step["engine"],
                    "output": str(output.relative_to(ROOT)),
                    "state": "running",
                    "started_at": _timestamp(),
                }
                events.append(event)
                ledger["events"] = list(events)
                _write_run_ledger(ledger_path, ledger)
                step_launch = {
                    "task_id": step["task_id"],
                    "engine": step["engine"],
                    "artifact_id": artifact_id,
                    "status": "running",
                }
                launch["steps"].append(step_launch)
                atomic_write_json(launch_path, launch)
                try:
                    review = run_task(task, step["engine"], output, timeout=TIMEOUT)
                    attempt = load_json(
                        ROOT / "proof" / "attempts" / (ATTEMPT_ID + ".json")
                    )
                    attempt["_path"] = str(
                        ROOT / "proof" / "attempts" / (ATTEMPT_ID + ".json")
                    )
                    ingested = [
                        item.get("id")
                        for item in record_review_findings(review, attempt)
                    ]
                    step_launch["ingested_findings"] = ingested
                    step_launch["verdict"] = review.get("verdict")
                    step_launch["review_id"] = review.get("id")
                    step_launch["status"] = "completed"
                    event.update(
                        {
                            "state": "completed",
                            "completed_at": _timestamp(),
                            "review_id": review.get("id"),
                            "verdict": review.get("verdict"),
                            "artifact_sha256": hashlib.sha256(
                                output.read_bytes()
                            ).hexdigest(),
                        }
                    )
                    release_artifact_reservation(reservation)
                except Exception as exc:
                    event.update(
                        {
                            "state": "failed",
                            "completed_at": _timestamp(),
                            "error": str(exc),
                        }
                    )
                    step_launch["status"] = "failed"
                    step_launch["error"] = str(exc)
                    if isinstance(exc, ArtifactValidationError):
                        event["trace_id"] = exc.trace_id
                        event["trace_path"] = exc.trace_path
                    else:
                        step_launch["traceback"] = traceback.format_exc()
                    spend_artifact_reservation(
                        reservation,
                        reason=event["state"],
                        trace_id=event.get("trace_id"),
                        task_id=step["task_id"],
                    )
                    overall = "stopped"
                    stop_reason = event["state"]
                    break
                finally:
                    event["notification_delivery"] = notify_campaign_step(
                        CAMPAIGN_ID, event, index, desktop=True, ntfy=True
                    )
                    ledger["events"] = list(events)
                    _write_run_ledger(ledger_path, ledger)
                    atomic_write_json(launch_path, launch)
                if event.get("verdict") != "confirmed":
                    overall = "completed"
                    stop_reason = "adverse_review"
                    break
        finally:
            ledger["events"] = list(events)
            ledger["status"] = overall
            ledger["stop_reason"] = stop_reason
            ledger["completed_at"] = _timestamp()
            ledger["run_notification_delivery"] = notify_campaign_run(
                CAMPAIGN_ID,
                len(events),
                len(STEPS),
                ledger["status"],
                ledger["stop_reason"],
                desktop=True,
                ntfy=True,
            )
            _write_run_ledger(ledger_path, ledger)
            launch["status"] = ledger["status"]
            launch["stop_reason"] = ledger["stop_reason"]
            atomic_write_json(launch_path, launch)
        print(json.dumps(launch, indent=2))
        return 0 if overall == "completed" and stop_reason != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
