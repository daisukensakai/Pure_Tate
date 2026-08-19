#!/usr/bin/env python3
"""Mine ATT-0103 into GEO-COMP working context, then one Codex mathematics turn.

Serial. No forced-proof. ATT-0103/REV-0152/FAUD-0163 are not rewritten.
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

from pure_tate.agents import run_task
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import (
    load_campaign,
    write_campaign_packet,
    write_campaign_status,
)
from pure_tate.notifications import (
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import (
    ArtifactValidationError,
    attach_working_context,
    publish_working_context,
    stamp_digest_attribution_from_task,
    trace_mining_task,
    write_observable_trace,
)
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
MATH_TASK_ID = "TASK-C66-M-003"
SUBPROBLEM_ID = "C66-GEO-COMP"
MINER_ENGINE = "grok"
PROVER_ENGINE = "codex"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
RESUME_STDOUT = (
    ROOT
    / "reports/runs/manual-recovery/att0102-claude-geocomp-resume-20260818T021800Z"
    / "ATT-0103.resume.stdout.jsonl"
)
RESUME_STDERR = (
    ROOT
    / "reports/runs/manual-recovery/att0102-claude-geocomp-resume-20260818T021800Z"
    / "ATT-0103.resume.stderr.txt"
)


def notify(title: str, message: str) -> None:
    print(
        "notify",
        {
            "desktop": send_desktop_notification(title, message),
            "ntfy": send_ntfy_notification_detailed(title, message),
        },
        flush=True,
    )


def _save_launch(payload: dict) -> None:
    atomic_write_json(VAULT / "LAUNCH.json", payload)


def _run_engine(task, engine, output, event, ledger, ledger_path, events):
    last = [0.0]

    def record_activity(stream: str, byte_count: int, elapsed: float) -> None:
        event["last_activity_at"] = _timestamp()
        event["last_activity_stream"] = stream
        event["activity_bytes"] = int(event.get("activity_bytes", 0)) + byte_count
        if elapsed - last[0] >= 1.0:
            last[0] = elapsed
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

    return run_task(
        task,
        engine,
        output,
        timeout=TIMEOUT,
        progress_callback=record_activity,
        process_start_callback=record_process_start,
    )


def main() -> int:
    if not RESUME_STDOUT.is_file():
        raise SystemExit("missing ATT-0103 official resume stdout")
    packet = write_campaign_packet(CAMPAIGN_ID)
    campaign = load_campaign(CAMPAIGN_ID)
    math_matches = [
        task
        for task in campaign_mathematics_tasks(CAMPAIGN_ID)
        if task.get("id") == MATH_TASK_ID
    ]
    if len(math_matches) != 1:
        raise RuntimeError("expected exactly one %s" % MATH_TASK_ID)
    math_task = math_matches[0]
    if math_task.get("status") != "ready" or math_task.get("subproblem_id") != SUBPROBLEM_ID:
        raise RuntimeError(
            "%s not ready: status=%s subproblem=%s"
            % (MATH_TASK_ID, math_task.get("status"), math_task.get("subproblem_id"))
        )

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID,
                2,
                ["grok"],
                [PROVER_ENGINE],
                ["grok", "claude"],
            )
            events = []
            launch = {
                "note": "mine ATT-0103 into GEO-COMP WC, then Codex ordinary math; no forced-proof",
                "run_id": ledger["run_id"],
                "run_ledger": str(ledger_path.relative_to(ROOT)),
                "status": "running",
                "jobs": [],
            }
            _save_launch(launch)

            trace_task = {
                "id": MATH_TASK_ID,
                "campaign_id": CAMPAIGN_ID,
                "packet_sha256": packet["packet_sha256"],
                "packet_binding_sha256": packet.get("packet_binding_sha256"),
                "paired_turn_kind": "mathematics",
                "paired_problem_key": packet.get("packet_binding_sha256"),
                "subproblem_id": SUBPROBLEM_ID,
            }
            trace = write_observable_trace(
                trace_task,
                "claude",
                RESUME_STDOUT.read_text(encoding="utf-8", errors="replace"),
                RESUME_STDERR.read_text(encoding="utf-8", errors="replace")
                if RESUME_STDERR.is_file()
                else "",
                parsed_artifact=json.loads(
                    (ROOT / "proof/attempts/ATT-0103.json").read_text(encoding="utf-8")
                ),
                classification="substantive",
            )
            launch["trace_id"] = trace["id"]
            launch["trace_path"] = trace["path"]
            _save_launch(launch)

            mine_task = trace_mining_task(
                campaign, packet, MINER_ENGINE, "mathematics", trace["id"]
            )
            rev_path = ROOT / "proof/reviews/REV-0152.json"
            mine_task.setdefault("input_artifacts", []).append(
                {
                    "path": str(rev_path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(rev_path.read_bytes()).hexdigest(),
                }
            )
            mine_task["selected_engine"] = MINER_ENGINE
            mine_task["source_subproblem_id"] = SUBPROBLEM_ID
            digest_id, digest_res = reserve_prefixed_artifact(
                ROOT / "research" / "paired-digests", "DIGEST", ledger["run_id"]
            )
            digest_out = ROOT / "research" / "paired-digests" / (digest_id + ".json")
            mine_task["output"] = str(digest_out.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % digest_id), mine_task)
            job_mine = {
                "kind": "trace-mining",
                "artifact_id": digest_id,
                "engine": MINER_ENGINE,
                "task_id": mine_task["id"],
                "output": str(digest_out.relative_to(ROOT)),
                "reservation": str(digest_res),
                "trace_id": trace["id"],
                "status": "running",
            }
            launch["jobs"].append(job_mine)
            event_mine = {
                "step": 1,
                "phase": "trace-mining",
                "task_id": mine_task["id"],
                "engine": MINER_ENGINE,
                "output": str(digest_out.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
                "trace_id": trace["id"],
            }
            events.append(event_mine)
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)
            _save_launch(launch)
            notify(
                "Pure Tate • Grok trace-mining starting",
                "%s • %s %s -> %s"
                % (CAMPAIGN_ID, mine_task["id"], trace["id"], digest_id),
            )
            try:
                digest = _run_engine(
                    mine_task,
                    MINER_ENGINE,
                    digest_out,
                    event_mine,
                    ledger,
                    ledger_path,
                    events,
                )
                stamp_digest_attribution_from_task(digest, mine_task)
                atomic_write_json(digest_out, digest)
                published = publish_working_context(campaign, mine_task, digest)
                write_campaign_status(CAMPAIGN_ID)
                event_mine["state"] = "completed"
                event_mine["completed_at"] = _timestamp()
                event_mine["digest_id"] = digest.get("id")
                if digest_out.is_file():
                    event_mine["artifact_sha256"] = hashlib.sha256(
                        digest_out.read_bytes()
                    ).hexdigest()
                job_mine["status"] = "done"
                job_mine["publish"] = published
                launch["working_context"] = published.get("primary")
            except Exception as exc:
                event_mine["error"] = str(exc)
                event_mine["state"] = "failed"
                event_mine["completed_at"] = _timestamp()
                job_mine["status"] = "failed"
                job_mine["error"] = str(exc)
                if isinstance(exc, ArtifactValidationError):
                    event_mine["trace_id"] = exc.trace_id
                    event_mine["trace_path"] = exc.trace_path
                else:
                    job_mine["traceback"] = traceback.format_exc()
            finally:
                if digest_out.is_file() and event_mine.get("state") == "completed":
                    release_artifact_reservation(digest_res)
                else:
                    spend_artifact_reservation(
                        digest_res,
                        reason=str(event_mine.get("state") or "dispatch_consumed"),
                        trace_id=event_mine.get("trace_id"),
                        task_id=mine_task["id"],
                    )
                event_mine["notification_delivery"] = notify_campaign_step(
                    CAMPAIGN_ID, event_mine, 2, desktop=True, ntfy=True
                )
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)
                _save_launch(launch)

            # Fresh packet + WC after mining, even if the digest failed.
            packet = write_campaign_packet(CAMPAIGN_ID)
            campaign = load_campaign(CAMPAIGN_ID)
            math_task = attach_working_context(dict(math_matches[0]), campaign)
            math_task["selected_engine"] = PROVER_ENGINE
            math_task["packet_sha256"] = packet["packet_sha256"]
            att_id, att_res = reserve_prefixed_artifact(
                ROOT / "proof" / "attempts", "ATT", ledger["run_id"]
            )
            att_out = ROOT / "proof" / "attempts" / (att_id + ".json")
            math_task["output"] = str(att_out.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % att_id), math_task)
            job_math = {
                "kind": "mathematics",
                "artifact_id": att_id,
                "engine": PROVER_ENGINE,
                "task_id": MATH_TASK_ID,
                "output": str(att_out.relative_to(ROOT)),
                "reservation": str(att_res),
                "status": "running",
                "working_context": math_task.get("working_context"),
            }
            launch["jobs"].append(job_math)
            event_math = {
                "step": 2,
                "phase": "mathematics",
                "task_id": MATH_TASK_ID,
                "engine": PROVER_ENGINE,
                "output": str(att_out.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
                "working_context": math_task.get("working_context"),
            }
            events.append(event_math)
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)
            _save_launch(launch)
            notify(
                "Pure Tate • Codex GEO-COMP starting",
                "%s • %s %s -> %s"
                % (CAMPAIGN_ID, MATH_TASK_ID, SUBPROBLEM_ID, att_id),
            )
            try:
                artifact = _run_engine(
                    math_task,
                    PROVER_ENGINE,
                    att_out,
                    event_math,
                    ledger,
                    ledger_path,
                    events,
                )
                event_math["state"] = "completed"
                event_math["completed_at"] = _timestamp()
                event_math["attempt_id"] = artifact.get("id")
                if att_out.is_file():
                    event_math["artifact_sha256"] = hashlib.sha256(
                        att_out.read_bytes()
                    ).hexdigest()
                job_math["status"] = "done"
                job_math["result_status"] = artifact.get("status")
                job_math["gap_count"] = len(artifact.get("gap_markers") or [])
            except Exception as exc:
                event_math["error"] = str(exc)
                event_math["state"] = "failed"
                event_math["completed_at"] = _timestamp()
                job_math["status"] = "failed"
                job_math["error"] = str(exc)
                if isinstance(exc, ArtifactValidationError):
                    event_math["trace_id"] = exc.trace_id
                    event_math["trace_path"] = exc.trace_path
                else:
                    job_math["traceback"] = traceback.format_exc()
            finally:
                if att_out.is_file() and event_math.get("state") == "completed":
                    release_artifact_reservation(att_res)
                else:
                    spend_artifact_reservation(
                        att_res,
                        reason=str(event_math.get("state") or "dispatch_consumed"),
                        trace_id=event_math.get("trace_id"),
                        task_id=MATH_TASK_ID,
                    )
                event_math["notification_delivery"] = notify_campaign_step(
                    CAMPAIGN_ID, event_math, 2, desktop=True, ntfy=True
                )
                stop_reason = (
                    "step_limit"
                    if event_math.get("state") == "completed"
                    else "engine_failure"
                )
                ledger["events"] = events
                ledger["status"] = (
                    "completed" if event_math.get("state") == "completed" else "stopped"
                )
                ledger["stop_reason"] = stop_reason
                ledger["completed_at"] = _timestamp()
                ledger["executed_steps"] = len(events)
                ledger["run_notification_delivery"] = notify_campaign_run(
                    CAMPAIGN_ID,
                    2,
                    len(events),
                    ledger["status"],
                    stop_reason,
                    desktop=True,
                    ntfy=True,
                )
                _write_run_ledger(ledger_path, ledger)
                launch["status"] = ledger["status"]
                launch["stop_reason"] = stop_reason
                _save_launch(launch)
            print(json.dumps(launch, indent=2, default=str), flush=True)
            return 0 if event_math.get("state") == "completed" else 1
    except CampaignAlreadyRunning as exc:
        notify("Pure Tate • GEO-COMP blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
