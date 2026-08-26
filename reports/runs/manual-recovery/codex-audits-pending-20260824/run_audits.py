#!/usr/bin/env python3
"""Serial Codex finding-audits of pending Codex-eligible candidates.

FND-0179 excludes Codex. No model fallback.
"""
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
from pure_tate.store import atomic_write_json
from pure_tate.tasking import finding_audit_tasks

CAMPAIGN_ID = "C66-001"
JOBS = (
    {"finding_id": "FND-0190", "engine": "codex"},
    {"finding_id": "FND-0173", "engine": "codex"},
    {"finding_id": "FND-0174", "engine": "codex"},
    {"finding_id": "FND-0175", "engine": "codex"},
)
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
STEPS = len(JOBS)


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
    available = {task["finding_id"]: task for task in finding_audit_tasks(CAMPAIGN_ID)}
    planned = []
    for spec in JOBS:
        task = available.get(spec["finding_id"])
        if task is None:
            raise RuntimeError("%s is not an eligible finding-audit" % spec["finding_id"])
        if spec["engine"] in set(task.get("excluded_engines") or []):
            raise RuntimeError(
                "%s is excluded from %s" % (spec["engine"], spec["finding_id"])
            )
        task = dict(task)
        task["selected_engine"] = spec["engine"]
        planned.append(task)

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, STEPS, ["codex"], ["claude"], ["grok", "claude"]
            )
            launch = {
                "note": "serial Codex FAUD of FND-0190 then 0173, 0174, 0175; FND-0179 excludes Codex; no model fallback",
                "jobs": [],
                "run_id": ledger["run_id"],
                "run_ledger": str(ledger_path.relative_to(ROOT)),
                "status": "running",
            }
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            events = []
            failures = 0

            for index, task in enumerate(planned, start=1):
                engine = task["selected_engine"]
                finding_id = task["finding_id"]
                task_id = task["id"]
                artifact_id, reservation_path = reserve_prefixed_artifact(
                    ROOT / "research" / "finding-audits", "FAUD", ledger["run_id"]
                )
                output = ROOT / "research" / "finding-audits" / (artifact_id + ".json")
                if output.exists():
                    raise RuntimeError("refusing to overwrite %s" % output)
                task["output"] = str(output.relative_to(ROOT))
                atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
                job = {
                    "artifact_id": artifact_id,
                    "engine": engine,
                    "finding_id": finding_id,
                    "task_id": task_id,
                    "output": str(output.relative_to(ROOT)),
                    "reservation": str(reservation_path),
                    "status": "running",
                }
                launch["jobs"].append(job)
                atomic_write_json(VAULT / "LAUNCH.json", launch)
                event = {
                    "step": index,
                    "phase": "finding-audit",
                    "task_id": task_id,
                    "engine": engine,
                    "output": str(output.relative_to(ROOT)),
                    "state": "running",
                    "started_at": _timestamp(),
                    "finding_id": finding_id,
                }
                events.append(event)
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)
                notify(
                    "Pure Tate • Codex finding-audit starting",
                    "%s • %s %s -> %s" % (CAMPAIGN_ID, task_id, finding_id, artifact_id),
                )
                last_ledger_activity = [0.0]

                def record_activity(
                    stream: str,
                    byte_count: int,
                    elapsed: float,
                    event=event,
                    events=events,
                ) -> None:
                    event["last_activity_at"] = _timestamp()
                    event["last_activity_stream"] = stream
                    event["activity_bytes"] = int(event.get("activity_bytes", 0)) + byte_count
                    if elapsed - last_ledger_activity[0] >= 1.0:
                        last_ledger_activity[0] = elapsed
                        ledger["events"] = events
                        _write_run_ledger(ledger_path, ledger)

                def record_process_start(
                    process_meta: dict, event=event, events=events
                ) -> None:
                    record = dict(process_meta)
                    record["started_at"] = _timestamp()
                    event.setdefault("processes", []).append(record)
                    event["engine_pid"] = record.get("engine_pid")
                    event["engine_process_group"] = record.get("engine_process_group")
                    event["supervisor_pid"] = record.get("supervisor_pid")
                    ledger["events"] = events
                    _write_run_ledger(ledger_path, ledger)

                try:
                    artifact = run_task(
                        task,
                        engine,
                        output,
                        timeout=TIMEOUT,
                        progress_callback=record_activity,
                        process_start_callback=record_process_start,
                    )
                    _apply_finding_audit(artifact)
                    event["state"] = "completed"
                    event["completed_at"] = _timestamp()
                    event["audit_id"] = artifact.get("id")
                    event["verdict"] = artifact.get("verdict")
                    if output.is_file():
                        event["artifact_sha256"] = hashlib.sha256(
                            output.read_bytes()
                        ).hexdigest()
                    job["status"] = "done"
                    job["result_verdict"] = artifact.get("verdict")
                    job["applied"] = True
                except Exception as exc:
                    failures += 1
                    event["error"] = str(exc)
                    event["state"] = "failed"
                    event["completed_at"] = _timestamp()
                    job["status"] = "failed"
                    job["error"] = str(exc)
                    if isinstance(exc, ArtifactValidationError):
                        event["trace_id"] = exc.trace_id
                        event["trace_path"] = exc.trace_path
                    else:
                        job["traceback"] = traceback.format_exc()
                finally:
                    if output.is_file() and event.get("state") == "completed":
                        release_artifact_reservation(reservation_path)
                    else:
                        spend_artifact_reservation(
                            reservation_path,
                            reason=str(event.get("state") or "dispatch_consumed"),
                            trace_id=event.get("trace_id"),
                            task_id=task_id,
                        )
                    event["notification_delivery"] = notify_campaign_step(
                        CAMPAIGN_ID, event, STEPS, desktop=True, ntfy=True
                    )
                    ledger["events"] = events
                    _write_run_ledger(ledger_path, ledger)
                    atomic_write_json(VAULT / "LAUNCH.json", launch)

            stop_reason = "step_limit" if failures == 0 else "engine_failure"
            ledger["status"] = "completed" if failures == 0 else "stopped"
            ledger["stop_reason"] = stop_reason
            ledger["completed_at"] = _timestamp()
            ledger["executed_steps"] = len(events)
            ledger["run_notification_delivery"] = notify_campaign_run(
                CAMPAIGN_ID,
                STEPS,
                len(events),
                ledger["status"],
                stop_reason,
                desktop=True,
                ntfy=True,
            )
            _write_run_ledger(ledger_path, ledger)
            launch["status"] = ledger["status"]
            launch["stop_reason"] = stop_reason
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            print(json.dumps(launch, indent=2, default=str), flush=True)
            return 0 if failures == 0 else 1
    except CampaignAlreadyRunning as exc:
        notify("Pure Tate • Codex audits blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
