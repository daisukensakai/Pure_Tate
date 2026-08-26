#!/usr/bin/env python3
"""One corrective Claude TATE-SUPPORT turn after ATT-0124 validation failure.

Injects TRACE-0090 parsed artifact plus validator feedback. Nested mechanical
repair is disabled so this is exactly one Claude call. No model fallback.
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

import pure_tate.validation_repair as validation_repair
from pure_tate.agents import run_task
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.notifications import (
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import ArtifactValidationError, attach_working_context
from pure_tate.routing import high_tier_chain_order, load_routing_config, record_high_tier_dispatch
from pure_tate.run_lifecycle import (
    CampaignAlreadyRunning,
    CampaignRunLock,
    live_run_ledgers,
    recover_stale_run_ledgers,
    release_artifact_reservation,
    spend_artifact_reservation,
    reserve_prefixed_artifact,
)
from pure_tate.store import atomic_write_json
from pure_tate.tasking import campaign_mathematics_tasks

CAMPAIGN_ID = "C66-001"
TASK_ID = "TASK-C66-M-005"
SUBPROBLEM_ID = "C66-TATE-SUPPORT"
ENGINE = "claude"
INTERFACE_ATTEMPT = "ATT-0120"
FAILED_SLOT = "ATT-0124"
FAILED_TRACE = "TRACE-0090"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
PREVIOUS_PATH = VAULT / "PREVIOUS-ATT-0124.json"
CORRECTIVE_PROMPT = VAULT / "CORRECTIVE.md"
VALIDATION_ERROR = (
    "target_interface_reference cites undeclared interface claim(s): "
    "CLM-0120-1, CLM-0120-2, CLM-0120-3, CLM-0120-4, CLM-0120-5, CLM-0120-6"
)

# Exactly one Claude call: do not nest a second mechanical-repair attempt.
validation_repair.validation_repair_settings = lambda *_a, **_k: {
    "enabled": False,
    "retry_limit": 0,
}


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
    packet = write_campaign_packet(CAMPAIGN_ID)
    campaign = load_campaign(CAMPAIGN_ID)
    matches = [
        task for task in campaign_mathematics_tasks(CAMPAIGN_ID) if task.get("id") == TASK_ID
    ]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one %s" % TASK_ID)
    task = matches[0]
    if task.get("status") != "ready" or task.get("subproblem_id") != SUBPROBLEM_ID:
        raise RuntimeError(
            "%s not ready: status=%s subproblem=%s"
            % (TASK_ID, task.get("status"), task.get("subproblem_id"))
        )
    exact_theorem = task.get("exact_theorem")
    if not isinstance(exact_theorem, str) or "T_Z" not in exact_theorem:
        raise RuntimeError("%s missing TATE-SUPPORT exact_theorem" % TASK_ID)
    if task.get("dependency_artifacts", {}).get("C66-SUPPORT-INTERFACE") != INTERFACE_ATTEMPT:
        raise RuntimeError(
            "TATE-SUPPORT is not wired to verified %s" % INTERFACE_ATTEMPT
        )
    contract = task.get("artifact_contract") or {}
    if contract.get("object_field") != "target_interface_reference":
        raise RuntimeError("%s missing target_interface_reference contract" % TASK_ID)
    input_ids = {
        item.get("id")
        for item in (task.get("input_artifacts") or [])
        if isinstance(item, dict)
    }
    required_ids = {INTERFACE_ATTEMPT, "REV-0169", "REV-0170"}
    missing = required_ids - input_ids
    if missing:
        raise RuntimeError("missing injected interface artifacts: %s" % sorted(missing))
    task = attach_working_context(dict(task), campaign)
    wc = task.get("working_context") or {}
    if not (wc.get("primary") or {}).get("path"):
        raise RuntimeError("primary working context was not attached")
    if not PREVIOUS_PATH.is_file() or not CORRECTIVE_PROMPT.is_file():
        raise RuntimeError("missing prior artifact or corrective prompt")
    previous_rel = str(PREVIOUS_PATH.relative_to(ROOT))
    existing = list(task.get("input_artifacts") or [])
    existing.append(
        {
            "path": previous_rel,
            "sha256": hashlib.sha256(PREVIOUS_PATH.read_bytes()).hexdigest(),
            "id": FAILED_SLOT,
            "kind": "prior_rejected_artifact",
        }
    )
    task["input_artifacts"] = existing
    task["prompt"] = str(CORRECTIVE_PROMPT.relative_to(ROOT))
    task["selected_engine"] = ENGINE
    task["packet_sha256"] = packet["packet_sha256"]
    task["exact_theorem"] = exact_theorem
    task["corrective_of"] = FAILED_SLOT
    task["corrective_trace"] = FAILED_TRACE
    task["validation_error"] = VALIDATION_ERROR
    task.setdefault("routing_chain_id", "proof:%s:%s" % (CAMPAIGN_ID, TASK_ID))

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, 1, ["grok"], [ENGINE], ["codex", "grok"]
            )
            artifact_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "proof" / "attempts", "ATT", ledger["run_id"]
            )
            output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
            if output.exists():
                raise RuntimeError("refusing to overwrite %s" % output)
            task["output"] = str(output.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)
            launch = {
                "note": (
                    "corrective Claude TATE-SUPPORT of spent ATT-0124; "
                    "TRACE-0090 prior JSON + validator feedback injected; "
                    "exactly one Claude call; no nested repair; no model fallback"
                ),
                "corrective_of": FAILED_SLOT,
                "corrective_trace": FAILED_TRACE,
                "validation_error": VALIDATION_ERROR,
                "previous_artifact": previous_rel,
                "campaign_id": CAMPAIGN_ID,
                "task_id": TASK_ID,
                "subproblem_id": SUBPROBLEM_ID,
                "engine": ENGINE,
                "artifact_id": artifact_id,
                "output": str(output.relative_to(ROOT)),
                "reservation": str(reservation_path),
                "run_id": ledger["run_id"],
                "packet_sha256": packet["packet_sha256"],
                "packet_binding_sha256": packet.get("packet_binding_sha256"),
                "working_context": task.get("working_context"),
                "routing_chain_id": task.get("routing_chain_id"),
                "exact_theorem": exact_theorem,
                "status": "running",
            }
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            event = {
                "step": 1,
                "phase": "mathematics",
                "task_id": TASK_ID,
                "engine": ENGINE,
                "output": str(output.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
                "working_context": task.get("working_context"),
            }
            ledger["events"] = [event]
            _write_run_ledger(ledger_path, ledger)
            notify(
                "Pure Tate • Claude TATE-SUPPORT corrective starting",
                "%s • repair %s via %s -> %s"
                % (CAMPAIGN_ID, FAILED_SLOT, FAILED_TRACE, artifact_id),
            )
            last = [0.0]

            def record_activity(stream: str, byte_count: int, elapsed: float) -> None:
                event["last_activity_at"] = _timestamp()
                event["last_activity_stream"] = stream
                event["activity_bytes"] = int(event.get("activity_bytes", 0)) + byte_count
                if elapsed - last[0] >= 1.0:
                    last[0] = elapsed
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
                routing = load_routing_config()
                chain_id = task.get("routing_chain_id")
                if (
                    isinstance(chain_id, str)
                    and ENGINE in routing["high_tier_chain_engines"]
                ):
                    high_tier_chain_order(chain_id, persist=True)
                    record_high_tier_dispatch(chain_id, ENGINE)
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
                event["attempt_id"] = artifact.get("id")
                if output.is_file():
                    event["artifact_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                launch["result_status"] = artifact.get("status")
                launch["gap_count"] = len(artifact.get("gap_markers") or [])
                launch["result_type"] = artifact.get("result_type")
            except Exception as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                launch["error"] = str(exc)
                if isinstance(exc, ArtifactValidationError):
                    event["trace_id"] = exc.trace_id
                    event["trace_path"] = exc.trace_path
                else:
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
        notify("Pure Tate • Claude TATE-SUPPORT corrective blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
