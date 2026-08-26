#!/usr/bin/env python3
"""Run Qwen's ordinary P1 review of the validated ATT-0128 artifact."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pure_tate.findings import record_review_findings
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
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
from pure_tate.tasking import review_tasks

CAMPAIGN_ID = "C66-001"
ATTEMPT_ID = "ATT-0128"
TASK_ID = "TASK-V-ATT-0128-P1"
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


def current_task() -> dict:
    matches = [
        task
        for task in review_tasks(ATTEMPT_ID)
        if task.get("id") == TASK_ID and task.get("review_pass") == 1
    ]
    if len(matches) != 1:
        raise RuntimeError("ATT-0128 no longer has exactly one eligible P1 review")
    task = dict(matches[0])
    if "qwen" in task.get("excluded_reviewer_engines", []):
        raise RuntimeError("Qwen is not an independent reviewer for ATT-0128")
    task["selected_engine"] = "qwen"
    return task


def main() -> int:
    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(
                "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
            )
        task = current_task()
        artifact_id, reservation = reserve_prefixed_artifact(
            ROOT / "proof" / "reviews", "REV", "MANUAL-QWEN-P1-ATT-0128"
        )
        output = ROOT / "proof" / "reviews" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        manifest = VAULT / ("manifest-%s.json" % artifact_id)
        log = VAULT / ("%s.qwen.console.log" % artifact_id)
        launch_path = VAULT / "LAUNCH.json"
        launch = {
            "campaign_id": CAMPAIGN_ID,
            "target_attempt_id": ATTEMPT_ID,
            "task_id": TASK_ID,
            "subproblem_id": "C66-TATE-SUPPORT",
            "review_pass": 1,
            "engine": "qwen",
            "artifact_id": artifact_id,
            "output": str(output.relative_to(ROOT)),
            "manifest": str(manifest),
            "reservation": str(reservation),
            "status": "running",
            "note": "Qwen P1 review of Claude ATT-0128 after validation-only provenance repair; no model fallback.",
        }
        atomic_write_json(manifest, task)
        atomic_write_json(launch_path, launch)
        notify("Pure Tate • Qwen ATT-0128 P1 starting", "%s -> %s" % (ATTEMPT_ID, artifact_id))
        with log.open("w", encoding="utf-8") as handle:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pure_tate",
                    "agent-run",
                    "--manifest",
                    str(manifest),
                    "--task-id",
                    TASK_ID,
                    "--engine",
                    "qwen",
                    "--output",
                    str(output.relative_to(ROOT)),
                    "--timeout",
                    "10800",
                ],
                cwd=str(ROOT),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if proc.returncode != 0 or not output.exists():
            spend_artifact_reservation(reservation, reason="agent_run_failure", task_id=TASK_ID)
            launch["status"] = "failed"
            launch["exit_code"] = proc.returncode
            atomic_write_json(launch_path, launch)
            notify("Pure Tate • Qwen ATT-0128 P1 failed", "%s exit=%s" % (artifact_id, proc.returncode))
            return proc.returncode or 1
        review = json.loads(output.read_text(encoding="utf-8"))
        release_artifact_reservation(reservation)
        attempt_path = ROOT / "proof" / "attempts" / (ATTEMPT_ID + ".json")
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        attempt["_path"] = str(attempt_path)
        try:
            launch["ingested_findings"] = [
                item.get("id") for item in record_review_findings(review, attempt)
            ]
        except Exception as exc:
            launch["ingest_warning"] = str(exc)
        launch["status"] = "completed"
        launch["verdict"] = review.get("verdict")
        atomic_write_json(launch_path, launch)
        notify("Pure Tate • Qwen ATT-0128 P1 complete", "%s verdict=%s" % (artifact_id, review.get("verdict")))
        print(json.dumps(launch, indent=2), flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
