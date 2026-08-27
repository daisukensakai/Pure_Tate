#!/usr/bin/env python3
"""PI-authorized C66 full forced proof: Codex plus two unbounded xAI workers."""
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
from pure_tate.campaigns import campaign_status, campaign_packet_record, load_campaign
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.paired import ArtifactValidationError, SubstantiveAttemptError, attach_working_context, forced_task, working_context_records
from pure_tate.run_lifecycle import CampaignAlreadyRunning, CampaignRunLock, live_run_ledgers, recover_stale_run_ledgers, release_artifact_reservation, reserve_prefixed_artifact, spend_artifact_reservation
from pure_tate.store import atomic_write_json

CAMPAIGN_ID = "C66-001"
ENGINE = "codex"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent


def current_task() -> dict:
    if campaign_status(CAMPAIGN_ID)["structural_integrity"] != "ready":
        raise RuntimeError("campaign structural integrity is not ready")
    campaign = load_campaign(CAMPAIGN_ID)
    packet = campaign_packet_record(CAMPAIGN_ID)
    task = attach_working_context(
        forced_task(campaign, packet, working_context_records(campaign)), campaign
    )
    if task.get("paired_turn_kind") != "forced-proof":
        raise RuntimeError("not a formal forced-proof task")
    task["selected_engine"] = ENGINE
    return task


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning("campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active)))
        task = current_task()
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, 1, ["grok"], [ENGINE], ["claude", "grok"]
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
            "subproblem_id": task["subproblem_id"],
            "engine": ENGINE,
            "artifact_id": artifact_id,
            "timeout_seconds": TIMEOUT,
            "worker_backend": "xai",
            "worker_model": "grok-4.6",
            "controller_policy": {
                "parallel_workers": 2,
                "worker_turns": "unbounded_until_task_timeout",
                "controller_rounds": "unbounded_until_task_timeout",
            },
            "status": "running",
        }
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        event = {
            "step": 1,
            "phase": "forced-proof",
            "task_id": task["id"],
            "engine": ENGINE,
            "output": str(output.relative_to(ROOT)),
            "state": "running",
            "started_at": _timestamp(),
            "pi_override": launch["controller_policy"],
            "worker_backend": "xai",
            "working_context": task.get("working_context"),
        }
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        old_backend, old_model = os.environ.get("GROK_WORKER_BACKEND"), os.environ.get("GROK_WORKER_MODEL")
        os.environ["GROK_WORKER_BACKEND"] = "xai"
        os.environ["GROK_WORKER_MODEL"] = "grok-4.6"
        try:
            artifact = run_task(task, ENGINE, output, timeout=TIMEOUT)
            event.update({
                "state": "completed",
                "completed_at": _timestamp(),
                "attempt_id": artifact.get("id"),
                "result_status": artifact.get("status"),
                "result_type": artifact.get("result_type"),
                "trace_id": artifact.get("observable_trace_id"),
                "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            })
            launch.update({"result_status": artifact.get("status"), "result_type": artifact.get("result_type")})
        except SubstantiveAttemptError as exc:
            event.update({"state": "substantive_rejected", "completed_at": _timestamp(), "error": str(exc), "trace_id": exc.trace_id})
            launch["error"] = str(exc)
        except ArtifactValidationError as exc:
            event.update({"state": "validation_rejected", "completed_at": _timestamp(), "error": str(exc), "trace_id": exc.trace_id})
            launch["error"] = str(exc)
        except Exception as exc:
            event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
            launch["error"] = str(exc)
            launch["traceback"] = traceback.format_exc()
        finally:
            if old_backend is None:
                os.environ.pop("GROK_WORKER_BACKEND", None)
            else:
                os.environ["GROK_WORKER_BACKEND"] = old_backend
            if old_model is None:
                os.environ.pop("GROK_WORKER_MODEL", None)
            else:
                os.environ["GROK_WORKER_MODEL"] = old_model
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
