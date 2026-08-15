#!/usr/bin/env python3
"""Run one context job from this vault's LAUNCH.json. No forced-proof."""
from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from pathlib import Path

from pure_tate.campaign_driver import _apply_finding_audit
from pure_tate.campaigns import load_campaign
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.paired import publish_working_context, stamp_digest_attribution_from_task
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import ROOT, atomic_write_json

VAULT = Path(__file__).resolve().parent


def notify(title: str, msg: str) -> None:
    print("desktop", send_desktop_notification(title, msg), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, msg), flush=True)


def _save(job: dict) -> None:
    path = VAULT / "LAUNCH.json"
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        launch = json.loads(handle.read())
        launch["jobs"] = [
            job if item.get("artifact_id") == job["artifact_id"] else item
            for item in launch.get("jobs", [])
        ]
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(launch, indent=2, sort_keys=True) + "\n")
        handle.flush()


def main() -> int:
    artifact_id = sys.argv[1]
    launch = json.loads((VAULT / "LAUNCH.json").read_text(encoding="utf-8"))
    job = next(item for item in launch["jobs"] if item["artifact_id"] == artifact_id)
    engine = job["engine"]
    task_id = job["task_id"]
    output = job["output"]
    reservation = Path(job["reservation"])
    log = VAULT / ("%s.%s.console.log" % (artifact_id, engine))
    outp = ROOT / output
    job["status"] = "running"
    _save(job)
    notify(
        "Pure Tate • %s %s starting" % (engine, job["kind"]),
        "C66-001 • %s -> %s" % (task_id, artifact_id),
    )
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pure_tate",
                "agent-run",
                "--manifest",
                str(VAULT / ("manifest-%s.json" % artifact_id)),
                "--task-id",
                task_id,
                "--engine",
                engine,
                "--output",
                output,
                "--timeout",
                "10800",
            ],
            cwd=str(ROOT),
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    with log.open("a", encoding="utf-8") as fh:
        fh.write("\nEXIT:%s\n" % proc.returncode)
    if proc.returncode != 0 or not outp.exists():
        spend_artifact_reservation(
            reservation, reason="agent_run_failure", task_id=task_id
        )
        job["status"] = "failed"
        job["exit_code"] = proc.returncode
        _save(job)
        notify(
            "Pure Tate • %s %s failed" % (engine, job["kind"]),
            "C66-001 • %s exit=%s" % (artifact_id, proc.returncode),
        )
        return proc.returncode or 1
    payload = json.loads(outp.read_text(encoding="utf-8"))
    release_artifact_reservation(reservation)
    if job["kind"] == "finding-audit":
        try:
            _apply_finding_audit(payload)
            job["applied"] = True
        except Exception as exc:
            job["applied"] = False
            print("apply warning:", exc, flush=True)
        job["result_verdict"] = payload.get("verdict")
        msg = "C66-001 • %s %s verdict=%s" % (
            artifact_id,
            job["finding_id"],
            payload.get("verdict"),
        )
    else:
        task = json.loads(
            (VAULT / ("manifest-%s.json" % artifact_id)).read_text(encoding="utf-8")
        )
        stamp_digest_attribution_from_task(payload, task)
        atomic_write_json(outp, payload)
        pub = publish_working_context(load_campaign("C66-001"), task, payload)
        job["publish"] = pub if isinstance(pub, dict) else str(pub)
        msg = "C66-001 • %s %s GEO-COMP WC published" % (
            artifact_id,
            job.get("trace_id"),
        )
    job["status"] = "done"
    _save(job)
    notify("Pure Tate • %s %s done" % (engine, job["kind"]), msg)
    print("done", artifact_id, job.get("result_verdict") or "published", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
