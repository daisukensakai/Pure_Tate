#!/usr/bin/env python3
"""Prep COMP-RANK/COMP-COMP context: ingest REV-0127, write TRACEs for mining."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pure_tate.campaigns import campaign_packet_record, load_campaign
from pure_tate.findings import record_review_findings
from pure_tate.notifications import (
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import write_observable_trace
from pure_tate.run_lifecycle import reserve_prefixed_artifact
from pure_tate.store import ROOT, atomic_write_json
from pure_tate.paired import trace_mining_task

STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
VAULT = ROOT / "reports" / "runs" / "manual-recovery" / f"comp-trace-context-{STAMP}"
VAULT.mkdir(parents=True, exist_ok=True)


def _attach_trace(attempt_id: str, trace: dict) -> None:
    path = ROOT / "proof" / "attempts" / f"{attempt_id}.json"
    attempt = json.loads(path.read_text())
    attempt["observable_trace_id"] = trace["id"]
    attempt["observable_trace_sha256"] = trace["sha256"]
    atomic_write_json(path, attempt)


def _stdout_for_attempt(attempt: dict, reviews: list[dict]) -> str:
    """Build mineable stdout from attempt + attached reviews (console stubs are empty)."""
    payload = {
        "attempt": attempt,
        "reviews": reviews,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    campaign = load_campaign("C66-001")
    packet = campaign_packet_record("C66-001")
    packet.pop("_text", None)

    # --- ingest REV-0127 (COMP-RANK P1) ---
    rev127 = json.loads((ROOT / "proof" / "reviews" / "REV-0127.json").read_text())
    att76 = json.loads((ROOT / "proof" / "attempts" / "ATT-0076.json").read_text())
    att76["_path"] = str(ROOT / "proof" / "attempts" / "ATT-0076.json")
    touched = record_review_findings(rev127, att76)
    ingested = [t.get("id") for t in touched]
    print("ingested_REV-0127", ingested)

    # --- TRACE ATT-0074 (COMP-COMP) ---
    att74 = json.loads((ROOT / "proof" / "attempts" / "ATT-0074.json").read_text())
    revs74 = []
    for rid in ("REV-0125", "REV-0126"):
        revs74.append(json.loads((ROOT / "proof" / "reviews" / f"{rid}.json").read_text()))
    task74 = {
        "id": att74.get("task_id") or "TASK-C66-M-009",
        "campaign_id": "C66-001",
        "packet_sha256": att74.get("packet_sha256") or packet.get("packet_sha256"),
        "packet_binding_sha256": att74.get("packet_binding_sha256")
        or packet.get("packet_binding_sha256"),
        "paired_problem_key": None,
        "paired_turn_kind": "standard-fallback",
    }
    stdout74 = _stdout_for_attempt(att74, revs74)
    # Prefer resume/console if ever recovered; stubs are tiny.
    for stub in (
        ROOT
        / "reports"
        / "runs"
        / "manual-recovery"
        / "ordinary-3step-noforced-20260809T235455Z"
        / "ATT-0074.grok.console.log",
    ):
        if stub.is_file() and stub.stat().st_size > 1000:
            stdout74 = stub.read_text(errors="replace")
            break
    tr74 = write_observable_trace(
        task74,
        engine=str(att74.get("engine") or "grok"),
        stdout=stdout74,
        stderr="operator-attached: reconstructed from attempt+reviews (console stub empty)\n",
        parsed_artifact=att74,
        classification="substantive",
    )
    _attach_trace("ATT-0074", tr74)
    print("TRACE ATT-0074", tr74)

    # --- TRACE ATT-0076 (COMP-RANK) ---
    att76 = json.loads((ROOT / "proof" / "attempts" / "ATT-0076.json").read_text())
    revs76 = [json.loads((ROOT / "proof" / "reviews" / "REV-0127.json").read_text())]
    task76 = {
        "id": att76.get("task_id") or "TASK-C66-M-008",
        "campaign_id": "C66-001",
        "packet_sha256": att76.get("packet_sha256") or packet.get("packet_sha256"),
        "packet_binding_sha256": att76.get("packet_binding_sha256")
        or packet.get("packet_binding_sha256"),
        "paired_problem_key": None,
        "paired_turn_kind": "standard-fallback",
    }
    stdout76 = _stdout_for_attempt(att76, revs76)
    for stub in (
        ROOT
        / "reports"
        / "runs"
        / "manual-recovery"
        / "codex-comprank-1step-20260810T082422Z"
        / "ATT-0076.codex.console.log",
    ):
        if stub.is_file() and stub.stat().st_size > 1000:
            stdout76 = stub.read_text(errors="replace")
            break
    tr76 = write_observable_trace(
        task76,
        engine=str(att76.get("engine") or "codex"),
        stdout=stdout76,
        stderr="operator-attached: reconstructed from attempt+reviews (console stub empty)\n",
        parsed_artifact=att76,
        classification="substantive",
    )
    _attach_trace("ATT-0076", tr76)
    print("TRACE ATT-0076", tr76)

    # --- reserve two DIGEST slots for Codex (run after REV-0129) ---
    digest_jobs = []
    for attempt_id, source_engine, trace in (
        ("ATT-0074", "grok", tr74),
        ("ATT-0076", "codex", tr76),
    ):
        dig_id, dig_res = reserve_prefixed_artifact(
            ROOT / "research" / "paired-digests", "DIGEST", VAULT.name
        )
        mine_task = trace_mining_task(
            campaign,
            packet,
            source_engine,
            "standard-fallback",
            trace["id"],
        )
        mine_task["selected_engine"] = "codex"
        mine_task["output"] = f"research/paired-digests/{dig_id}.json"
        # source engine in task id is the attempt engine; miner is codex
        (VAULT / f"manifest-{dig_id}.json").write_text(
            json.dumps(mine_task, indent=2) + "\n"
        )
        digest_jobs.append(
            {
                "attempt_id": attempt_id,
                "trace_id": trace["id"],
                "digest_id": dig_id,
                "output": mine_task["output"],
                "reservation": str(dig_res),
                "task_id": mine_task["id"],
                "source_engine": source_engine,
                "status": "reserved",
            }
        )

    launch = {
        "stamp": STAMP,
        "vault": str(VAULT),
        "note": (
            "COMP context: ingest REV-0127; TRACE ATT-0074/0076; "
            "Codex DIGEST queue after GEO-COMP REV-0129"
        ),
        "ingested_from_REV-0127": ingested,
        "traces": {"ATT-0074": tr74, "ATT-0076": tr76},
        "digest_jobs": digest_jobs,
        "blocked_on": "REV-0129 Codex P1 (ATT-0080)",
    }
    atomic_write_json(VAULT / "LAUNCH.json", launch)
    Path("/tmp/pure-tate-comp-trace-context.json").write_text(
        json.dumps(launch, indent=2) + "\n"
    )

    msg = (
        "C66-001 • COMP context prepped\n"
        "TRACE %s / %s; DIGEST reserved %s / %s; ingest %s"
        % (
            tr74["id"],
            tr76["id"],
            digest_jobs[0]["digest_id"],
            digest_jobs[1]["digest_id"],
            ",".join(ingested) or "(none)",
        )
    )
    print("desktop", send_desktop_notification("Pure Tate • COMP context ready", msg))
    print("ntfy", send_ntfy_notification_detailed("Pure Tate • COMP context ready", msg))
    print(json.dumps(launch, indent=2))


if __name__ == "__main__":
    main()
