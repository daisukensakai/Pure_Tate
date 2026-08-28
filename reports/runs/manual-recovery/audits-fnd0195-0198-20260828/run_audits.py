#!/usr/bin/env python3
"""Serial independent audits: xAI Grok FND-0195..0197, Codex FND-0198."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
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
PLAN = (("FND-0195", "grok"), ("FND-0196", "grok"), ("FND-0197", "grok"), ("FND-0198", "codex"))
VAULT = Path(__file__).resolve().parent


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        write_campaign_packet(CAMPAIGN_ID)
        available = {x["finding_id"]: x for x in finding_audit_tasks(CAMPAIGN_ID)}
        tasks = []
        for finding_id, engine in PLAN:
            task = available.get(finding_id)
            if task is None or task.get("status") != "ready":
                raise RuntimeError("%s is not ready" % finding_id)
            if engine in set(task.get("excluded_engines") or []):
                raise RuntimeError("%s is excluded from %s" % (engine, finding_id))
            task = dict(task)
            task["selected_engine"] = engine
            tasks.append((finding_id, engine, task))
        ledger, ledger_path = _new_run_ledger(CAMPAIGN_ID, len(tasks), ["grok", "codex"], ["codex"], ["grok", "codex"])
        launch = {"campaign_id": CAMPAIGN_ID, "plan": [{"finding_id": f, "engine": e} for f, e, _ in tasks], "run_id": ledger["run_id"], "jobs": [], "status": "running"}
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        events, failures = [], 0
        for step, (finding_id, engine, task) in enumerate(tasks, start=1):
            artifact_id, reservation = reserve_prefixed_artifact(ROOT / "research" / "finding-audits", "FAUD", ledger["run_id"])
            output = ROOT / "research" / "finding-audits" / (artifact_id + ".json")
            task["output"] = str(output.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-" + artifact_id + ".json"), task)
            event = {"step": step, "phase": "finding-audit", "task_id": task["id"], "finding_id": finding_id, "engine": engine, "output": str(output.relative_to(ROOT)), "state": "running", "started_at": _timestamp()}
            job = {"finding_id": finding_id, "engine": engine, "artifact_id": artifact_id, "status": "running"}
            events.append(event)
            launch["jobs"].append(job)
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)
            atomic_write_json(launch_path, launch)
            old_backend = os.environ.get("GROK_WORKER_BACKEND")
            os.environ["GROK_WORKER_BACKEND"] = "xai"
            try:
                artifact = run_task(task, engine, output, timeout=10800)
                _apply_finding_audit(artifact)
                event.update({"state": "completed", "completed_at": _timestamp(), "audit_id": artifact.get("id"), "verdict": artifact.get("verdict"), "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
                job.update({"status": "done", "audit_id": artifact.get("id"), "verdict": artifact.get("verdict"), "applied": True})
            except Exception as exc:
                failures += 1
                event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
                job.update({"status": "failed", "error": str(exc)})
                if isinstance(exc, ArtifactValidationError):
                    event["trace_id"], event["trace_path"] = exc.trace_id, exc.trace_path
                else:
                    job["traceback"] = traceback.format_exc()
            finally:
                if old_backend is None:
                    os.environ.pop("GROK_WORKER_BACKEND", None)
                else:
                    os.environ["GROK_WORKER_BACKEND"] = old_backend
                if event["state"] == "completed" and output.is_file():
                    release_artifact_reservation(reservation)
                else:
                    spend_artifact_reservation(reservation, reason=event["state"], trace_id=event.get("trace_id"), task_id=task["id"])
                event["notification_delivery"] = notify_campaign_step(CAMPAIGN_ID, event, len(tasks), desktop=True, ntfy=True)
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)
                atomic_write_json(launch_path, launch)
        ledger["status"] = "completed" if failures == 0 else "stopped"
        ledger["stop_reason"] = "step_limit" if failures == 0 else "engine_failure"
        ledger["completed_at"] = _timestamp()
        ledger["executed_steps"] = len(events)
        ledger["run_notification_delivery"] = notify_campaign_run(CAMPAIGN_ID, len(tasks), len(events), ledger["status"], ledger["stop_reason"], desktop=True, ntfy=True)
        _write_run_ledger(ledger_path, ledger)
        launch["status"], launch["stop_reason"] = ledger["status"], ledger["stop_reason"]
        atomic_write_json(launch_path, launch)
        print(json.dumps(launch, indent=2))
        return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
