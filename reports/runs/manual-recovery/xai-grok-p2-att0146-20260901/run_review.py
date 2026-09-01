#!/usr/bin/env python3
"""Run xAI Grok's independent P2 review of Claude's ATT-0146."""
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
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import write_campaign_packet
from pure_tate.findings import record_review_findings
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.paired import ArtifactValidationError
from pure_tate.run_lifecycle import CampaignAlreadyRunning, CampaignRunLock, live_run_ledgers, recover_stale_run_ledgers, release_artifact_reservation, reserve_prefixed_artifact, spend_artifact_reservation
from pure_tate.store import atomic_write_json, load_json
from pure_tate.tasking import review_tasks

CAMPAIGN_ID = "C66BAR-001"
ATTEMPT_ID = "ATT-0146"
TASK_ID = "TASK-V-ATT-0146-P2"
ENGINE = "grok"
VAULT = Path(__file__).resolve().parent


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        write_campaign_packet(CAMPAIGN_ID)
        matches = [item for item in review_tasks(ATTEMPT_ID) if item.get("id") == TASK_ID]
        if len(matches) != 1 or matches[0].get("status") != "ready":
            raise RuntimeError("ATT-0146 has no ready P2 review")
        task = dict(matches[0])
        if ENGINE in set(task.get("excluded_reviewer_engines") or []):
            raise RuntimeError("xAI Grok is not independent")
        task["selected_engine"] = ENGINE
        ledger, ledger_path = _new_run_ledger(CAMPAIGN_ID, 1, [ENGINE], [ENGINE], [ENGINE])
        artifact_id, reservation = reserve_prefixed_artifact(ROOT / "proof" / "reviews", "REV", ledger["run_id"])
        output = ROOT / "proof" / "reviews" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        atomic_write_json(VAULT / ("manifest-" + artifact_id + ".json"), task)
        launch = {"campaign_id": CAMPAIGN_ID, "target_attempt_id": ATTEMPT_ID, "task_id": TASK_ID, "engine": ENGINE, "worker_backend": "xai", "artifact_id": artifact_id, "status": "running"}
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        event = {"step": 1, "phase": "review", "task_id": TASK_ID, "target_attempt_id": ATTEMPT_ID, "review_pass": 2, "engine": ENGINE, "output": str(output.relative_to(ROOT)), "state": "running", "started_at": _timestamp()}
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        old_backend = os.environ.get("GROK_WORKER_BACKEND")
        os.environ["GROK_WORKER_BACKEND"] = "xai"
        try:
            review = run_task(task, ENGINE, output, timeout=10800)
            attempt = load_json(ROOT / "proof" / "attempts" / (ATTEMPT_ID + ".json"))
            attempt["_path"] = str(ROOT / "proof" / "attempts" / (ATTEMPT_ID + ".json"))
            launch["ingested_findings"] = [item.get("id") for item in record_review_findings(review, attempt)]
            launch["verdict"] = review.get("verdict")
            event.update({"state": "completed", "completed_at": _timestamp(), "review_id": review.get("id"), "verdict": review.get("verdict"), "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest()})
        except Exception as exc:
            event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
            launch["error"] = str(exc)
            if isinstance(exc, ArtifactValidationError):
                event["trace_id"], event["trace_path"] = exc.trace_id, exc.trace_path
            else:
                launch["traceback"] = traceback.format_exc()
        finally:
            if old_backend is None:
                os.environ.pop("GROK_WORKER_BACKEND", None)
            else:
                os.environ["GROK_WORKER_BACKEND"] = old_backend
            if event["state"] == "completed" and output.is_file():
                release_artifact_reservation(reservation)
            else:
                spend_artifact_reservation(reservation, reason=event["state"], trace_id=event.get("trace_id"), task_id=TASK_ID)
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
