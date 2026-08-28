#!/usr/bin/env python3
"""Quarantined Codex P3 self-review of ATT-0135; never campaign evidence."""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import run_task
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import campaign_packet_record, load_campaign
from pure_tate.notifications import notify_campaign_run, notify_campaign_step
from pure_tate.run_lifecycle import CampaignAlreadyRunning, CampaignRunLock, live_run_ledgers, recover_stale_run_ledgers
from pure_tate.store import atomic_write_json, load_json

CAMPAIGN_ID = "C66-001"
ATTEMPT_ID = "ATT-0135"
ENGINE = "codex"
VAULT = Path(__file__).resolve().parent


def task() -> dict:
    attempt = load_json(ROOT / "proof" / "attempts" / (ATTEMPT_ID + ".json"))
    packet = campaign_packet_record(CAMPAIGN_ID)
    campaign = load_campaign(CAMPAIGN_ID)
    return {
        "id": "TASK-SELF-ATT-0135-P3",
        "phase": "review",
        "role": "quarantined-self-reviewer",
        "target_attempt_id": ATTEMPT_ID,
        "target_task_id": attempt["task_id"],
        "review_pass": 3,
        "context_revision": campaign["context_revision"],
        "packet_id": packet["packet_id"],
        "packet_sha256": packet["packet_sha256"],
        "packet_binding_sha256": packet["packet_binding_sha256"],
        "target": packet["target"],
        "prover_engine": "self-review-override",
        "excluded_reviewer_engines": [],
        "prompt": str((VAULT / "P3_SELF_REVIEW.md").relative_to(ROOT)),
        "input_attempt": "proof/attempts/ATT-0135.json",
        "input_packet": packet["packet_path"],
        # `run_task` deliberately permits review artifacts only in this
        # directory.  The post-processing below makes this particular record
        # non-independent and non-evidentiary before it is left on disk.
        "output": "proof/reviews/REV-0186.json",
        "input_artifacts": [],
        "campaign_id": CAMPAIGN_ID,
        "campaign_revision": campaign["campaign_revision"],
        "subproblem_id": "C66-FULL",
        "lane": "full-resolution",
        "theorem_statement": attempt["theorem_statement"],
        "artifact_contract": None,
        "status": "ready",
        "self_review_override": True,
    }


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(", ".join(active))
        current = task()
        ledger, ledger_path = _new_run_ledger(CAMPAIGN_ID, 1, [ENGINE], [ENGINE], [ENGINE])
        output = ROOT / "proof" / "reviews" / "REV-0186.json"
        if output.exists():
            raise RuntimeError("self-review output already exists")
        current["output"] = str(output.relative_to(ROOT))
        atomic_write_json(VAULT / "TASK.json", current)
        launch = {"campaign_id": CAMPAIGN_ID, "attempt_id": ATTEMPT_ID, "engine": ENGINE, "review_pass": 3, "quarantined": True, "status": "running"}
        launch_path = VAULT / "LAUNCH.json"
        atomic_write_json(launch_path, launch)
        event = {"step": 1, "phase": "self-review-override", "task_id": current["id"], "engine": ENGINE, "output": current["output"], "state": "running", "started_at": _timestamp()}
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        try:
            review = run_task(current, ENGINE, output, timeout=10800)
            review["independent"] = False
            review["self_review_override"] = {
                "authorized_by": "principal_investigator",
                "quarantined": True,
                "not_counted_for_verification": True,
                "finding_candidates_ingested": False,
            }
            review["finding_candidates"] = []
            atomic_write_json(output, review)
            event.update({"state": "completed", "completed_at": _timestamp(), "verdict": review.get("verdict")})
            launch["verdict"] = review.get("verdict")
        except Exception as exc:
            event.update({"state": "failed", "completed_at": _timestamp(), "error": str(exc)})
            launch["error"] = str(exc)
            launch["traceback"] = traceback.format_exc()
        finally:
            ledger["events"] = [event]
            ledger["status"] = "completed" if event["state"] == "completed" else "stopped"
            ledger["stop_reason"] = "self_review_complete" if event["state"] == "completed" else event["state"]
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
