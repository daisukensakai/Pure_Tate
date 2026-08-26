#!/usr/bin/env python3
"""Resume Claude once to correct ATT-0127's validation-only provenance error."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pure_tate.agents import _extract_claude_stream, _validate_artifact
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.notifications import (
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import ArtifactValidationError, attach_working_context, write_observable_trace
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
TRACE_ID = "TRACE-0091"
SOURCE_ATTEMPT = "ATT-0127"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
CLAIMS = [
    "CLM-0120-2",
    "CLM-0120-3",
    "CLM-0120-4",
    "CLM-0120-5",
    "CLM-0120-6",
    "CLM-0120-7",
]


def notify(title: str, message: str) -> None:
    print(
        "notify",
        {
            "desktop": send_desktop_notification(title, message),
            "ntfy": send_ntfy_notification_detailed(title, message),
        },
        flush=True,
    )


def source_session_id(trace: dict) -> str:
    stream = str(trace.get("observable_stdout") or "")
    match = re.search(r'"session_id":"([^"]+)"', stream)
    if not match:
        raise RuntimeError("official trace has no Claude session ID")
    return match.group(1)


def current_task() -> dict:
    packet = write_campaign_packet(CAMPAIGN_ID)
    campaign = load_campaign(CAMPAIGN_ID)
    matches = [
        task
        for task in campaign_mathematics_tasks(CAMPAIGN_ID)
        if task.get("id") == TASK_ID
    ]
    if len(matches) != 1 or matches[0].get("status") != "ready":
        raise RuntimeError("C66-TATE-SUPPORT is not ready for repair")
    task = attach_working_context(dict(matches[0]), campaign)
    task["selected_engine"] = "claude"
    task["packet_sha256"] = packet["packet_sha256"]
    return task


def repair_prompt(artifact_id: str) -> str:
    return """# HARNESS VALIDATION-REPAIR CONTINUATION

Your immediately preceding C66-TATE-SUPPORT artifact %s was rejected only for
declared-provenance metadata. Do not restart the mathematics, do not dispatch a
worker, do not read additional files, and do not alter the argument, claims,
gaps, result type, or status.

The exact validation error was:

target_interface_reference cites undeclared interface claim(s): %s

Your previous JSON named these exact ATT-0120 claims in
`target_interface_reference.interface_claim_ids`, but its top-level
`dependency_claim_ids` was an empty list. The direct dependency ATT-0120 was
already correctly declared in `proof_dependencies`.

Return the same complete JSON artifact, with these minimal changes only:

- set `id` to %s;
- set `engine` to `claude`;
- set top-level `dependency_claim_ids` exactly to %s;
- retain ATT-0120 as the declared direct proof dependency and retain the same
  target_interface_reference claims;
- preserve every substantive field from the prior JSON.

Return exactly one full JSON object and no prose or Markdown fences.
""" % (SOURCE_ATTEMPT, ", ".join(CLAIMS), artifact_id, json.dumps(CLAIMS))


def main() -> int:
    trace_path = ROOT / "research" / "paired-traces" / (TRACE_ID + ".json")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if trace.get("validation_error") != (
        "target_interface_reference cites undeclared interface claim(s): "
        + ", ".join(CLAIMS)
    ):
        raise RuntimeError("TRACE-0091 is not the expected ATT-0127 repair trace")
    session_id = source_session_id(trace)
    task = current_task()

    with CampaignRunLock(CAMPAIGN_ID):
        recover_stale_run_ledgers(CAMPAIGN_ID)
        active = live_run_ledgers(CAMPAIGN_ID)
        if active:
            raise CampaignAlreadyRunning(
                "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
            )
        ledger, ledger_path = _new_run_ledger(
            CAMPAIGN_ID, 1, ["grok"], ["claude"], ["codex", "grok"]
        )
        artifact_id, reservation = reserve_prefixed_artifact(
            ROOT / "proof" / "attempts", "ATT", ledger["run_id"]
        )
        output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
        task["output"] = str(output.relative_to(ROOT))
        task["repair_of_trace_id"] = TRACE_ID
        task["repair_of_attempt_id"] = SOURCE_ATTEMPT
        atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
        event = {
            "step": 1,
            "phase": "mathematics",
            "task_id": TASK_ID,
            "engine": "claude",
            "output": str(output.relative_to(ROOT)),
            "state": "running",
            "started_at": _timestamp(),
            "repair_of_trace_id": TRACE_ID,
        }
        ledger["events"] = [event]
        _write_run_ledger(ledger_path, ledger)
        launch = {
            "campaign_id": CAMPAIGN_ID,
            "task_id": TASK_ID,
            "engine": "claude",
            "artifact_id": artifact_id,
            "output": str(output.relative_to(ROOT)),
            "parent_trace_id": TRACE_ID,
            "session_id_source": "official_observable_trace",
            "status": "running",
        }
        atomic_write_json(VAULT / "REPAIR-LAUNCH.json", launch)
        notify(
            "Pure Tate • Claude metadata repair starting",
            "%s -> %s from %s" % (SOURCE_ATTEMPT, artifact_id, TRACE_ID),
        )
        stdout_path = VAULT / (artifact_id + ".repair.stdout.jsonl")
        stderr_path = VAULT / (artifact_id + ".repair.stderr.txt")
        command = [
            "claude",
            "-p",
            repair_prompt(artifact_id),
            "--resume",
            session_id,
            "--model",
            "claude-opus-5",
            "--effort",
            "high",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--permission-mode",
            "dontAsk",
            "--disallowedTools",
            "Edit,Write,Bash",
        ]
        env = dict(os.environ)
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
        try:
            with stdout_path.open("w", encoding="utf-8") as out_h, stderr_path.open(
                "w", encoding="utf-8"
            ) as err_h:
                process = subprocess.run(
                    command,
                    cwd=str(ROOT),
                    env=env,
                    stdout=out_h,
                    stderr=err_h,
                    timeout=TIMEOUT,
                    check=False,
                )
            raw = stdout_path.read_text(encoding="utf-8", errors="replace")
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
            if process.returncode != 0:
                raise RuntimeError("Claude repair exited %d: %s" % (process.returncode, stderr[-800:]))
            artifact = _extract_claude_stream(raw)
            _validate_artifact("mathematics", task, artifact, output, "claude")
            artifact["validation_repair"] = {
                "classification": "provider_session_metadata_repair",
                "parent_trace_id": TRACE_ID,
                "parent_attempt_id": SOURCE_ATTEMPT,
                "errors": [trace["validation_error"]],
                "repaired": True,
            }
            atomic_write_json(output, artifact)
            release_artifact_reservation(reservation)
            event["state"] = "completed"
            event["attempt_id"] = artifact_id
            event["artifact_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
            launch["result_status"] = artifact.get("status")
        except Exception as exc:
            event["state"] = "failed"
            event["error"] = str(exc)
            raw = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
            trace_record = write_observable_trace(
                task,
                "claude",
                raw,
                stderr,
                validation_error=str(exc),
                classification="validation_repair_failure",
            )
            event["trace_id"] = trace_record["id"]
            launch["error"] = str(exc)
            launch["traceback"] = traceback.format_exc()
            spend_artifact_reservation(
                reservation,
                reason="validation_repair_failed",
                trace_id=trace_record["id"],
                task_id=TASK_ID,
            )
        event["completed_at"] = _timestamp()
        ledger["events"] = [event]
        ledger["status"] = "completed" if event["state"] == "completed" else "stopped"
        ledger["stop_reason"] = "step_limit" if event["state"] == "completed" else "engine_failure"
        ledger["completed_at"] = _timestamp()
        ledger["executed_steps"] = 1
        event["notification_delivery"] = notify_campaign_step(CAMPAIGN_ID, event, 1, desktop=True, ntfy=True)
        ledger["run_notification_delivery"] = notify_campaign_run(
            CAMPAIGN_ID, 1, 1, ledger["status"], ledger["stop_reason"], desktop=True, ntfy=True
        )
        _write_run_ledger(ledger_path, ledger)
        launch["status"] = ledger["status"]
        atomic_write_json(VAULT / "REPAIR-LAUNCH.json", launch)
        print(json.dumps(launch, indent=2), flush=True)
        return 0 if event["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
