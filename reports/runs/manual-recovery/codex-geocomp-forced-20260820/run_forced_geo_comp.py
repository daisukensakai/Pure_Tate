#!/usr/bin/env python3
"""PI override: Codex forced-prompt C66-GEO-COMP with 2 parallel Grok workers.

Same conditions as the Claude forced GEO-COMP turn: completeness contract
retargeted at GEO-COMP (TASK-C66-M-003), not official C66-FULL forced-proof.
Worker caps: 2 concurrent identities, 256 turns each. Codex controller
max_requests raised to 16 so it can dispatch both identities and continue.
Default engines.json stays 1/4.
"""
from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pure_tate.agents as agents
import pure_tate.grok_workers as grok_workers
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
    attempt_pending_recoveries,
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
MAX_GROK_WORKERS = 2
MAX_WORKER_TURNS = 256
MAX_CONTROLLER_REQUESTS = 16
VAULT = Path(__file__).resolve().parent
FORCED_PROMPT = (
    "reports/runs/manual-recovery/claude-geocomp-forced-20260819/FORCED_GEO_COMP.md"
)
EXACT_THEOREM = (
    "Over a reduced locally Noetherian base carrying a balanced Casnati-Ekedahl "
    "genus-six degree-four family satisfying (CE), (BAL), and (N), determine the "
    "irreducible components, dimensions, deck and component stabilizers, and "
    "finite-cover behavior of the ordered evaluation-failure locus Z. In "
    "particular: compute the exact geometric monodromy image H_alpha of the "
    "finite etale S_6-ordering cover on every balanced component, including "
    "purely type-(ii) components if they exist; decide whether a connected "
    "component of the balanced base can consist entirely of type-(ii) fibres; "
    "give the resulting component count and component-stabilizer formula; and "
    "identify the relevant Aut / inertia groups for the ordered model. This "
    "lemma does not resolve the campaign Hodge/Tate group RED-0001."
)

grok_workers.max_grok_workers_from_config = lambda _cfg: MAX_GROK_WORKERS
grok_workers.max_worker_turns_from_config = lambda _cfg: MAX_WORKER_TURNS


def _controller_settings(_cfg):
    return {
        "enabled": True,
        "max_requests": MAX_CONTROLLER_REQUESTS,
        "retry_limit": 1,
        "max_attempts": 8,
        "max_result_chars": 12000,
    }


agents._codex_controller_settings = _controller_settings


def _notify(title: str, message: str) -> None:
    print("desktop", send_desktop_notification(title, message), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, message), flush=True)


def _save_launch(payload: dict) -> None:
    atomic_write_json(VAULT / "LAUNCH.json", payload)


def main() -> int:
    launch = {
        "note": (
            "PI override: Codex forced-prompt GEO-COMP (not C66-FULL); "
            "2 parallel Grok workers; 256 turns/identity; controller rounds=16; "
            "completeness contract"
        ),
        "stamp": "20260820T080000Z",
        "campaign_id": CAMPAIGN_ID,
        "task_id": TASK_ID,
        "subproblem_id": SUBPROBLEM_ID,
        "engine": ENGINE,
        "timeout": TIMEOUT,
        "forced_prompt": FORCED_PROMPT,
        "paired_turn_kind": None,
        "official_c66_full_forced_proof": False,
        "max_grok_workers": MAX_GROK_WORKERS,
        "max_worker_turns": MAX_WORKER_TURNS,
        "max_controller_requests": MAX_CONTROLLER_REQUESTS,
        "vault": str(VAULT),
        "status": "starting",
    }
    _save_launch(launch)
    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recovered = recover_stale_run_ledgers(CAMPAIGN_ID)
            launch["recovered_stale_runs"] = recovered
            pre_run_recoveries = attempt_pending_recoveries(CAMPAIGN_ID)
            launch["pre_run_recoveries"] = pre_run_recoveries
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
            task["prompt"] = FORCED_PROMPT
            task["exact_theorem"] = EXACT_THEOREM
            task.setdefault("routing_chain_id", "proof:%s:%s" % (CAMPAIGN_ID, TASK_ID))

            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, 1, ["grok"], [ENGINE], ["claude", "grok"]
            )
            run_id = ledger["run_id"]
            if pre_run_recoveries:
                ledger["pre_run_recoveries"] = pre_run_recoveries
                _write_run_ledger(ledger_path, ledger)
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
                    "exact_theorem": EXACT_THEOREM,
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
                "pi_override": {
                    "forced_prompt": FORCED_PROMPT,
                    "max_grok_workers": MAX_GROK_WORKERS,
                    "max_worker_turns": MAX_WORKER_TURNS,
                    "max_controller_requests": MAX_CONTROLLER_REQUESTS,
                },
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
                "Pure Tate • Codex forced GEO-COMP starting",
                "%s • %s %s -> %s • 2 Grok workers / 256 turns"
                % (CAMPAIGN_ID, TASK_ID, SUBPROBLEM_ID, artifact_id),
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
                event["result_status"] = artifact.get("status")
                event["gap_count"] = len(artifact.get("gap_markers") or [])
                if artifact.get("observable_trace_id"):
                    event["trace_path"] = (
                        "research/paired-traces/%s.json"
                        % artifact["observable_trace_id"]
                    )
                    event["trace_sha256"] = artifact.get("observable_trace_sha256")
                if output.is_file():
                    event["artifact_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                launch["result_status"] = artifact.get("status")
                launch["gap_count"] = event["gap_count"]
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
                        "gap_count": launch.get("gap_count"),
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
        _notify("Pure Tate • forced GEO-COMP blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
