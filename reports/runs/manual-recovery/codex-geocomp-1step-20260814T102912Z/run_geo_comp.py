#!/usr/bin/env python3
"""One ordinary C66-GEO-COMP mathematics turn on Codex. No forced-proof."""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

from pure_tate.agents import run_task
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.notifications import (
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import (
    ArtifactValidationError,
    SubstantiveAttemptError,
    attach_working_context,
    recover_attempt_from_trace,
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
from pure_tate.store import ROOT, atomic_write_json
from pure_tate.tasking import campaign_mathematics_tasks

CAMPAIGN_ID = "C66-001"
TASK_ID = "TASK-C66-M-003"
SUBPROBLEM_ID = "C66-GEO-COMP"
ENGINE = "codex"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent


def _notify(title: str, message: str) -> None:
    print("desktop", send_desktop_notification(title, message), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, message), flush=True)


def _save_launch(payload: dict) -> None:
    atomic_write_json(VAULT / "LAUNCH.json", payload)


def main() -> int:
    launch = {
        "note": "one ordinary GEO-COMP mathematics step; Codex/sol; no forced-proof",
        "stamp": "20260814T102912Z",
        "campaign_id": CAMPAIGN_ID,
        "task_id": TASK_ID,
        "subproblem_id": SUBPROBLEM_ID,
        "engine": ENGINE,
        "timeout": TIMEOUT,
        "vault": str(VAULT),
        "status": "starting",
    }
    _save_launch(launch)
    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recovered = recover_stale_run_ledgers(CAMPAIGN_ID)
            launch["recovered_stale_runs"] = recovered
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            packet = write_campaign_packet(CAMPAIGN_ID)
            campaign = load_campaign(CAMPAIGN_ID)
            tasks = campaign_mathematics_tasks(CAMPAIGN_ID)
            matches = [task for task in tasks if task.get("id") == TASK_ID]
            if len(matches) != 1:
                raise RuntimeError("expected exactly one %s task" % TASK_ID)
            task = matches[0]
            if task.get("status") != "ready":
                raise RuntimeError(
                    "%s is not ready: status=%s blocked=%s"
                    % (TASK_ID, task.get("status"), task.get("blocked_dependencies"))
                )
            if task.get("subproblem_id") != SUBPROBLEM_ID:
                raise RuntimeError("task subproblem mismatch: %s" % task.get("subproblem_id"))
            task = attach_working_context(task, campaign)
            task["selected_engine"] = ENGINE
            task.setdefault("routing_chain_id", "proof:%s:%s" % (CAMPAIGN_ID, TASK_ID))

            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, 1, ["claude", "grok"], [ENGINE], ["codex", "claude"]
            )
            run_id = ledger["run_id"]
            artifact_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "proof" / "attempts", "ATT", run_id
            )
            output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
            task["output"] = str(output.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)

            launch.update(
                {
                    "status": "running",
                    "run_id": run_id,
                    "run_ledger": str(ledger_path.relative_to(ROOT)),
                    "artifact_id": artifact_id,
                    "output": str(output.relative_to(ROOT)),
                    "reservation": str(reservation_path),
                    "packet_id": packet.get("packet_id"),
                    "packet_sha256": packet.get("packet_sha256"),
                    "working_context": task.get("working_context"),
                    "routing_chain_id": task.get("routing_chain_id"),
                }
            )
            _save_launch(launch)

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
            events = [event]
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)

            last_ledger_activity = [0.0]

            def record_activity(stream: str, byte_count: int, elapsed: float) -> None:
                event["last_activity_at"] = _timestamp()
                event["last_activity_stream"] = stream
                event["activity_bytes"] = int(event.get("activity_bytes", 0)) + byte_count
                if elapsed - last_ledger_activity[0] >= 1.0:
                    last_ledger_activity[0] = elapsed
                    ledger["events"] = events
                    _write_run_ledger(ledger_path, ledger)

            def record_process_start(process_meta: dict) -> None:
                record = dict(process_meta)
                record["started_at"] = _timestamp()
                event.setdefault("processes", []).append(record)
                event["engine_pid"] = record.get("engine_pid")
                event["engine_process_group"] = record.get("engine_process_group")
                event["supervisor_pid"] = record.get("supervisor_pid")
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)

            _notify(
                "Pure Tate • Codex GEO-COMP starting",
                "%s • %s %s -> %s" % (CAMPAIGN_ID, TASK_ID, SUBPROBLEM_ID, artifact_id),
            )
            routing = load_routing_config()
            chain_id = task.get("routing_chain_id")
            try:
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
                event["trace_id"] = artifact.get("observable_trace_id")
                if artifact.get("observable_trace_id"):
                    event["trace_path"] = (
                        "research/paired-traces/%s.json"
                        % artifact["observable_trace_id"]
                    )
                    event["trace_sha256"] = artifact.get("observable_trace_sha256")
                if output.is_file():
                    event["artifact_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                launch["result_status"] = artifact.get("status")
                launch["gap_count"] = len(artifact.get("gap_markers") or [])
            except SubstantiveAttemptError as exc:
                event["error"] = str(exc)
                event["state"] = "substantive_rejected"
                event["completed_at"] = _timestamp()
                event["trace_id"] = exc.trace_id
                event["trace_path"] = exc.trace_path
                launch["error"] = str(exc)
            except ArtifactValidationError as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                event["trace_id"] = exc.trace_id
                event["trace_path"] = exc.trace_path
                if not output.exists():
                    try:
                        receipt = recover_attempt_from_trace(exc.trace_id, output)
                        event["state"] = "completed"
                        event["recovery"] = receipt
                        event["classification"] = "parser_recovery"
                        event.pop("error", None)
                        if output.is_file():
                            event["artifact_sha256"] = hashlib.sha256(
                                output.read_bytes()
                            ).hexdigest()
                        event["completed_at"] = _timestamp()
                    except (OSError, RuntimeError, ValueError) as recovery_exc:
                        event["recovery_attempt"] = {
                            "status": "recovery_failed",
                            "error": str(recovery_exc),
                            "trace_id": exc.trace_id,
                        }
                launch["error"] = event.get("error")
            except Exception as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                launch["error"] = str(exc)
                launch["traceback"] = traceback.format_exc()
            finally:
                if output.is_file() and event.get("state") == "completed":
                    release_artifact_reservation(reservation_path)
                elif event.get("trace_id") or event.get("state") in {
                    "failed",
                    "abandoned",
                    "substantive_rejected",
                }:
                    spend_artifact_reservation(
                        reservation_path,
                        reason=str(event.get("state") or event.get("error") or "dispatch_consumed"),
                        trace_id=(
                            str(event["trace_id"]) if event.get("trace_id") else None
                        ),
                        task_id=TASK_ID,
                    )
                else:
                    spend_artifact_reservation(
                        reservation_path,
                        reason="dispatch_consumed",
                        task_id=TASK_ID,
                    )
                event["notification_delivery"] = notify_campaign_step(
                    CAMPAIGN_ID, event, 1, desktop=True, ntfy=True
                )
                stop_reason = (
                    "step_limit" if event.get("state") == "completed" else "engine_failure"
                )
                if event.get("state") == "substantive_rejected":
                    stop_reason = "substantive_rejected"
                ledger["events"] = events
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
                _save_launch(launch)

            print(
                json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "state": event.get("state"),
                        "output": str(output.relative_to(ROOT)),
                        "result_status": launch.get("result_status"),
                    },
                    indent=2,
                ),
                flush=True,
            )
            return 0 if event.get("state") == "completed" else 1
    except CampaignAlreadyRunning as exc:
        launch["status"] = "blocked"
        launch["error"] = str(exc)
        _save_launch(launch)
        _notify("Pure Tate • GEO-COMP blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
