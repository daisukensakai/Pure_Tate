#!/usr/bin/env python3
"""One xAI Grok P1 review of ATT-0115. Official first is cursor-grok; PI selects grok CLI."""
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
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import write_campaign_packet
from pure_tate.findings import record_review_findings
from pure_tate.notifications import (
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
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
TASK_ID = "TASK-V-ATT-0115-P1"
TARGET_ATTEMPT = "ATT-0115"
ENGINE = "grok"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent


def notify(title: str, message: str) -> None:
    print(
        "notify",
        {
            "desktop": send_desktop_notification(title, message),
            "ntfy": send_ntfy_notification_detailed(title, message),
        },
        flush=True,
    )


def main() -> int:
    write_campaign_packet(CAMPAIGN_ID)
    matches = [task for task in review_tasks() if task.get("id") == TASK_ID]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one %s" % TASK_ID)
    task = matches[0]
    if task.get("target_attempt_id") != TARGET_ATTEMPT:
        raise RuntimeError("task target mismatch: %s" % task.get("target_attempt_id"))
    if ENGINE in set(task.get("excluded_reviewer_engines") or []):
        raise RuntimeError("engine %s is excluded from %s" % (ENGINE, TASK_ID))
    if task.get("status") != "ready":
        raise RuntimeError("%s is not ready: %s" % (TASK_ID, task.get("status")))
    task["selected_engine"] = ENGINE

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, 1, ["grok"], ["codex"], [ENGINE, "claude"]
            )
            run_id = ledger["run_id"]
            artifact_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "proof" / "reviews", "REV", run_id
            )
            output = ROOT / "proof" / "reviews" / (artifact_id + ".json")
            if output.exists():
                raise RuntimeError("refusing to overwrite %s" % output)
            task["output"] = str(output.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
            launch = {
                "note": "xAI Grok P1 of ATT-0115 Codex TATE-SUPPORT; official first is cursor-grok; no model fallback",
                "campaign_id": CAMPAIGN_ID,
                "task_id": TASK_ID,
                "target_attempt_id": TARGET_ATTEMPT,
                "review_pass": 1,
                "engine": ENGINE,
                "artifact_id": artifact_id,
                "output": str(output.relative_to(ROOT)),
                "reservation": str(reservation_path),
                "run_id": run_id,
                "run_ledger": str(ledger_path.relative_to(ROOT)),
                "status": "running",
            }
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            event = {
                "step": 1,
                "phase": "review",
                "task_id": TASK_ID,
                "engine": ENGINE,
                "output": str(output.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
                "target_attempt_id": TARGET_ATTEMPT,
                "review_pass": 1,
            }
            ledger["events"] = [event]
            _write_run_ledger(ledger_path, ledger)
            notify(
                "Pure Tate • Grok ATT-0115 P1 starting",
                "%s • %s %s -> %s" % (CAMPAIGN_ID, TASK_ID, TARGET_ATTEMPT, artifact_id),
            )
            last_ledger_activity = [0.0]

            def record_activity(stream: str, byte_count: int, elapsed: float) -> None:
                event["last_activity_at"] = _timestamp()
                event["last_activity_stream"] = stream
                event["activity_bytes"] = int(event.get("activity_bytes", 0)) + byte_count
                if elapsed - last_ledger_activity[0] >= 1.0:
                    last_ledger_activity[0] = elapsed
                    ledger["events"] = [event]
                    _write_run_ledger(ledger_path, ledger)

            def record_process_start(process_meta: dict) -> None:
                record = dict(process_meta)
                record["started_at"] = _timestamp()
                event.setdefault("processes", []).append(record)
                event["engine_pid"] = record.get("engine_pid")
                event["engine_process_group"] = record.get("engine_process_group")
                event["supervisor_pid"] = record.get("supervisor_pid")
                ledger["events"] = [event]
                _write_run_ledger(ledger_path, ledger)

            try:
                artifact = run_task(
                    task,
                    ENGINE,
                    output,
                    timeout=TIMEOUT,
                    progress_callback=record_activity,
                    process_start_callback=record_process_start,
                )
                event["state"] = "completed"
                event["completed_at"] = _timestamp()
                event["review_id"] = artifact.get("id")
                event["verdict"] = artifact.get("verdict")
                if output.is_file():
                    event["artifact_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                attempt = load_json(ROOT / "proof" / "attempts" / (TARGET_ATTEMPT + ".json"))
                attempt["_path"] = str(
                    ROOT / "proof" / "attempts" / (TARGET_ATTEMPT + ".json")
                )
                touched = record_review_findings(artifact, attempt)
                launch["ingested_findings"] = [item.get("id") for item in touched]
                launch["result_verdict"] = artifact.get("verdict")
            except ArtifactValidationError as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                event["trace_id"] = exc.trace_id
                event["trace_path"] = exc.trace_path
                launch["error"] = str(exc)
            except Exception as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                launch["error"] = str(exc)
                launch["traceback"] = traceback.format_exc()
            finally:
                if output.is_file() and event.get("state") == "completed":
                    release_artifact_reservation(reservation_path)
                else:
                    spend_artifact_reservation(
                        reservation_path,
                        reason=str(event.get("state") or "dispatch_consumed"),
                        trace_id=event.get("trace_id"),
                        task_id=TASK_ID,
                    )
                event["notification_delivery"] = notify_campaign_step(
                    CAMPAIGN_ID, event, 1, desktop=True, ntfy=True
                )
                stop_reason = (
                    "step_limit" if event.get("state") == "completed" else "engine_failure"
                )
                ledger["events"] = [event]
                ledger["status"] = (
                    "completed" if event.get("state") == "completed" else "stopped"
                )
                ledger["stop_reason"] = stop_reason
                ledger["completed_at"] = _timestamp()
                ledger["executed_steps"] = 1
                ledger["run_notification_delivery"] = notify_campaign_run(
                    CAMPAIGN_ID,
                    1,
                    1,
                    ledger["status"],
                    stop_reason,
                    desktop=True,
                    ntfy=True,
                )
                _write_run_ledger(ledger_path, ledger)
                launch["status"] = ledger["status"]
                launch["event_state"] = event.get("state")
                launch["stop_reason"] = stop_reason
                atomic_write_json(VAULT / "LAUNCH.json", launch)
            print(json.dumps(launch, indent=2, default=str), flush=True)
            return 0 if event.get("state") == "completed" else 1
    except CampaignAlreadyRunning as exc:
        notify("Pure Tate • Grok ATT-0115 P1 blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
