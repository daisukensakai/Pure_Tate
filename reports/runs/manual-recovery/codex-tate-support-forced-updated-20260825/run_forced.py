#!/usr/bin/env python3
"""Forced Codex TATE-SUPPORT turn with REV-0178 as fresh evidence."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pure_tate.agents import run_task
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.paired import (
    ArtifactValidationError,
    SubstantiveAttemptError,
    attach_working_context,
)
from pure_tate.routing import high_tier_chain_order, load_routing_config, record_high_tier_dispatch
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
from pure_tate.tasking import campaign_mathematics_tasks

CAMPAIGN_ID = "C66-001"
TASK_ID = "TASK-C66-M-005"
ENGINE = "codex"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
PROMPT = str((VAULT / "FORCED_UPDATED_TATE_SUPPORT.md").relative_to(ROOT))
FRESH_INPUTS = [
    ROOT / "proof" / "attempts" / "ATT-0128.json",
    ROOT / "proof" / "reviews" / "REV-0178.json",
]


def input_record(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError("required fresh input missing: %s" % path)
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def save_launch(payload: dict) -> None:
    atomic_write_json(VAULT / "LAUNCH.json", payload)


def main() -> int:
    launch = {
        "campaign_id": CAMPAIGN_ID,
        "task_id": TASK_ID,
        "subproblem_id": "C66-TATE-SUPPORT",
        "engine": ENGINE,
        "timeout": TIMEOUT,
        "forced_prompt": PROMPT,
        "worker_backend": "cursor",
        "worker_model": "cursor-grok-4.6-high",
        "controller_caps": {
            "parallel_workers": 2,
            "worker_turns": "unbounded_until_task_timeout",
            "controller_rounds": "unbounded_until_task_timeout",
            "retry_limit": 1,
        },
        "fresh_required_inputs": [str(path.relative_to(ROOT)) for path in FRESH_INPUTS],
        "status": "starting",
    }
    save_launch(launch)
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(
                "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
            )
        packet = write_campaign_packet(CAMPAIGN_ID)
        campaign = load_campaign(CAMPAIGN_ID)
        tasks = [task for task in campaign_mathematics_tasks(CAMPAIGN_ID) if task.get("id") == TASK_ID]
        if len(tasks) != 1 or tasks[0].get("status") != "ready":
            raise RuntimeError("C66-TATE-SUPPORT is not ready for the forced turn")
        task = attach_working_context(dict(tasks[0]), campaign)
        existing = {item.get("path") for item in task.get("input_artifacts", []) if isinstance(item, dict)}
        for path in FRESH_INPUTS:
            record = input_record(path)
            if record["path"] not in existing:
                task.setdefault("input_artifacts", []).append(record)
        task["selected_engine"] = ENGINE
        task["prompt"] = PROMPT
        task["forced_resolution"] = True
        task["forced_context_note"] = "ATT-0128 and REV-0178 are mandatory fresh input evidence."
        task.setdefault("routing_chain_id", "proof:%s:%s" % (CAMPAIGN_ID, TASK_ID))
        ledger, ledger_path = _new_run_ledger(CAMPAIGN_ID, 1, ["cursor-grok"], [ENGINE], ["claude", "grok"])
        artifact_id, reservation = reserve_prefixed_artifact(ROOT / "proof" / "attempts", "ATT", ledger["run_id"])
        output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
        event = {
            "step": 1,
            "phase": "mathematics",
            "task_id": TASK_ID,
            "engine": ENGINE,
            "output": str(output.relative_to(ROOT)),
            "state": "running",
            "started_at": _timestamp(),
            "worker_backend": "cursor",
            "fresh_inputs": [str(path.relative_to(ROOT)) for path in FRESH_INPUTS],
        }
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        launch.update({
            "status": "running", "artifact_id": artifact_id,
            "output": str(output.relative_to(ROOT)),
            "run_id": ledger["run_id"], "run_ledger": str(ledger_path.relative_to(ROOT)),
            "packet_sha256": packet["packet_sha256"], "working_context": task.get("working_context"),
        })
        save_launch(launch)
        old_backend = os.environ.get("GROK_WORKER_BACKEND")
        old_model = os.environ.get("GROK_WORKER_MODEL")
        os.environ["GROK_WORKER_BACKEND"] = "cursor"
        os.environ["GROK_WORKER_MODEL"] = "cursor-grok-4.6-high"
        try:
            routing = load_routing_config()
            chain_id = str(task["routing_chain_id"])
            if ENGINE in routing["high_tier_chain_engines"]:
                high_tier_chain_order(chain_id, persist=True)
                record_high_tier_dispatch(chain_id, ENGINE)
            artifact = run_task(task, ENGINE, output, timeout=TIMEOUT)
            event.update({
                "state": "completed", "completed_at": _timestamp(),
                "attempt_id": artifact.get("id"), "trace_id": artifact.get("observable_trace_id"),
                "result_status": artifact.get("status"),
                "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest() if output.is_file() else None,
            })
            launch["result_status"] = artifact.get("status")
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
                spend_artifact_reservation(reservation, reason=event["state"], trace_id=event.get("trace_id"), task_id=TASK_ID)
            ledger["events"] = [event]
            ledger["status"] = "completed" if event["state"] == "completed" else "stopped"
            ledger["stop_reason"] = "step_limit" if event["state"] == "completed" else event["state"]
            ledger["completed_at"] = _timestamp()
            _write_run_ledger(ledger_path, ledger)
            launch["status"] = ledger["status"]
            save_launch(launch)
        print(json.dumps(launch, indent=2), flush=True)
        return 0 if event["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
