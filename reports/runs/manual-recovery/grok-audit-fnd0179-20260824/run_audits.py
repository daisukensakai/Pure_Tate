#!/usr/bin/env python3
"""xAI Grok FAUD of remaining candidate FND-0179.

Codex is excluded from FND-0179. No model fallback.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from pure_tate.tasking import finding_audit_tasks

CAMPAIGN_ID = "C66-001"
AUDIT_ENGINE = "grok"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
AUDIT_FINDING_IDS = ("FND-0179",)


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
    audits = []
    for finding_id in AUDIT_FINDING_IDS:
        task = available.get(finding_id)
        if task is None:
            raise RuntimeError("%s is not an eligible finding-audit" % finding_id)
        if AUDIT_ENGINE in set(task.get("excluded_engines") or []):
            raise RuntimeError("%s is excluded from %s" % (AUDIT_ENGINE, finding_id))
        audits.append(task)

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            n_jobs = len(audits)
            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, n_jobs, ["grok"], ["grok"], [AUDIT_ENGINE]
            )
            jobs = []
            events = []
            ledger_lock = threading.Lock()

            def add_job(kind, task, prefix, directory, engine, extra):
                task = dict(task)
                task["selected_engine"] = engine
                artifact_id, reservation_path = reserve_prefixed_artifact(
                    directory, prefix, ledger["run_id"]
                )
                output = directory / (artifact_id + ".json")
                if output.exists():
                    raise RuntimeError("refusing to overwrite %s" % output)
                task["output"] = str(output.relative_to(ROOT))
                atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
                job = {
                    "kind": kind,
                    "artifact_id": artifact_id,
                    "engine": engine,
                    "task_id": task["id"],
                    "output": str(output.relative_to(ROOT)),
                    "reservation": str(reservation_path),
                    "status": "running",
                }
                job.update(extra)
                jobs.append(job)
                event = {
                    "step": len(events) + 1,
                    "phase": task["phase"],
                    "task_id": task["id"],
                    "engine": engine,
                    "output": job["output"],
                    "state": "running",
                    "started_at": _timestamp(),
                }
                event.update(extra)
                events.append(event)
                return task, job, event, output, reservation_path

            audit_specs = []
            for audit in audits:
                spec = add_job(
                    "finding-audit",
                    audit,
                    "FAUD",
                    ROOT / "research" / "finding-audits",
                    AUDIT_ENGINE,
                    {"finding_id": audit["finding_id"]},
                )
                audit_specs.append(spec)

            launch = {
                "note": (
                    "xAI Grok FAUD of remaining FND-0179; Codex excluded; no model fallback"
                ),
                "jobs": jobs,
                "run_id": ledger["run_id"],
                "run_ledger": str(ledger_path.relative_to(ROOT)),
                "status": "running",
            }
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)

            def run_one(task, job, event, output, reservation_path):
                engine = job["engine"]
                last = [0.0]

                def record_activity(stream, byte_count, elapsed):
                    event["last_activity_at"] = _timestamp()
                    event["last_activity_stream"] = stream
                    event["activity_bytes"] = int(event.get("activity_bytes", 0)) + byte_count
                    if elapsed - last[0] >= 2.0:
                        last[0] = elapsed
                        with ledger_lock:
                            ledger["events"] = events
                            _write_run_ledger(ledger_path, ledger)

                def record_process_start(process_meta):
                    record = dict(process_meta)
                    record["started_at"] = _timestamp()
                    event.setdefault("processes", []).append(record)
                    event["engine_pid"] = record.get("engine_pid")
                    event["engine_process_group"] = record.get("engine_process_group")
                    event["supervisor_pid"] = record.get("supervisor_pid")
                    with ledger_lock:
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
                    event["state"] = "completed"
                    event["completed_at"] = _timestamp()
                    if output.is_file():
                        event["artifact_sha256"] = hashlib.sha256(
                            output.read_bytes()
                        ).hexdigest()
                    event["audit_id"] = artifact.get("id")
                    event["verdict"] = artifact.get("verdict")
                    _apply_finding_audit(artifact)
                    job["result_verdict"] = artifact.get("verdict")
                    job["applied"] = True
                    job["status"] = "done"
                except Exception as exc:
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
                            task_id=task["id"],
                        )
                    event["notification_delivery"] = notify_campaign_step(
                        CAMPAIGN_ID, event, n_jobs, desktop=True, ntfy=True
                    )
                    with ledger_lock:
                        ledger["events"] = events
                        _write_run_ledger(ledger_path, ledger)
                        atomic_write_json(VAULT / "LAUNCH.json", launch)
                return event.get("state")

            work = audit_specs
            failures = 0
            with ThreadPoolExecutor(max_workers=n_jobs) as pool:
                futures = [
                    pool.submit(run_one, task, job, event, output, Path(reservation))
                    for task, job, event, output, reservation in work
                ]
                for future in as_completed(futures):
                    try:
                        if future.result() != "completed":
                            failures += 1
                    except Exception:
                        failures += 1
                        traceback.print_exc()

            stop_reason = "step_limit" if failures == 0 else "engine_failure"
            ledger["status"] = "completed" if failures == 0 else "stopped"
            ledger["stop_reason"] = stop_reason
            ledger["completed_at"] = _timestamp()
            ledger["executed_steps"] = len(events)
            ledger["events"] = events
            ledger["run_notification_delivery"] = notify_campaign_run(
                CAMPAIGN_ID,
                n_jobs,
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
        notify("Pure Tate • Grok audits blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
