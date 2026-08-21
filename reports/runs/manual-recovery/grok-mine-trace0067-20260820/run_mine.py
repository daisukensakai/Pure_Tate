#!/usr/bin/env python3
"""Grok-mine Claude TRACE-0067 (interrupted forced GEO-COMP). Cross-engine.

REV-0155 minted no new candidate finding, so there is no FAUD. Ordinary
successful reviews/attempts do not write traces; TRACE-0067 is the official
Claude stream with the two Grok worker reports.
paired_source_engine=claude; selected_engine=grok.
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
from pure_tate.campaigns import load_campaign, write_campaign_packet, write_campaign_status
from pure_tate.notifications import (
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import (
    ArtifactValidationError,
    publish_working_context,
    stamp_digest_attribution_from_task,
    trace_mining_task,
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

CAMPAIGN_ID = "C66-001"
SOURCE_ENGINE = "claude"
MINER_ENGINE = "grok"
TRACE_ID = "TRACE-0067"
SOURCE_TURN = "mathematics"
TIMEOUT = 10800
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


def main() -> int:
    packet = write_campaign_packet(CAMPAIGN_ID)
    campaign = load_campaign(CAMPAIGN_ID)
    task = trace_mining_task(
        campaign, packet, SOURCE_ENGINE, SOURCE_TURN, TRACE_ID
    )
    if task.get("paired_source_engine") != SOURCE_ENGINE:
        raise RuntimeError(
            "refusing mislabeled source engine %s" % task.get("paired_source_engine")
        )
    task["selected_engine"] = MINER_ENGINE
    if MINER_ENGINE == task["paired_source_engine"]:
        raise RuntimeError("miner must differ from paired_source_engine")

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )
            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, 1, [MINER_ENGINE], ["claude"], ["codex", "claude"]
            )
            run_id = ledger["run_id"]
            digest_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "research" / "paired-digests", "DIGEST", run_id
            )
            output = ROOT / "research" / "paired-digests" / (digest_id + ".json")
            if output.exists():
                raise RuntimeError("refusing to overwrite %s" % output)
            task["output"] = str(output.relative_to(ROOT))
            atomic_write_json(VAULT / ("manifest-%s.json" % digest_id), task)
            launch = {
                "note": (
                    "Grok mine of Claude TRACE-0067; no FAUD from REV-0155; "
                    "source=claude miner=grok"
                ),
                "campaign_id": CAMPAIGN_ID,
                "task_id": task["id"],
                "trace_id": TRACE_ID,
                "source_engine": SOURCE_ENGINE,
                "miner_engine": MINER_ENGINE,
                "paired_source_engine": task["paired_source_engine"],
                "artifact_id": digest_id,
                "output": str(output.relative_to(ROOT)),
                "reservation": str(reservation_path),
                "run_id": run_id,
                "run_ledger": str(ledger_path.relative_to(ROOT)),
                "status": "running",
            }
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            event = {
                "step": 1,
                "phase": "trace-mining",
                "task_id": task["id"],
                "engine": MINER_ENGINE,
                "output": str(output.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
                "trace_id": TRACE_ID,
            }
            ledger["events"] = [event]
            _write_run_ledger(ledger_path, ledger)
            notify(
                "Pure Tate • Grok TRACE-0067 mine starting",
                "%s • %s %s -> %s"
                % (CAMPAIGN_ID, task["id"], TRACE_ID, digest_id),
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
                digest = run_task(
                    task,
                    MINER_ENGINE,
                    output,
                    timeout=TIMEOUT,
                    progress_callback=record_activity,
                    process_start_callback=record_process_start,
                )
                stamp_digest_attribution_from_task(digest, task)
                atomic_write_json(output, digest)
                published = publish_working_context(campaign, task, digest)
                write_campaign_status(CAMPAIGN_ID)
                event["state"] = "completed"
                event["completed_at"] = _timestamp()
                event["digest_id"] = digest.get("id")
                if output.is_file():
                    event["artifact_sha256"] = hashlib.sha256(
                        output.read_bytes()
                    ).hexdigest()
                launch["working_context"] = published.get("primary")
                launch["publish"] = published
            except ArtifactValidationError as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                event["trace_id"] = exc.trace_id
                event["trace_path"] = exc.trace_path
                launch["error"] = str(exc)
            except Exception as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                launch["error"] = str(exc)
                launch["traceback"] = traceback.format_exc()
            finally:
                if output.is_file() and event.get("state") == "completed":
                    release_artifact_reservation(reservation_path)
                else:
                    spend_artifact_reservation(
                        reservation_path,
                        reason=str(event.get("state") or "dispatch_consumed"),
                        trace_id=event.get("trace_id"),
                        task_id=task["id"],
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
        notify("Pure Tate • TRACE-0067 mine blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
