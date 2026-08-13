#!/usr/bin/env python3
"""Run one reserved job from the three-engine vault; apply audit / publish digest."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pure_tate.campaign_driver import _apply_finding_audit
from pure_tate.campaigns import load_campaign
from pure_tate.notifications import (
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import publish_working_context, stamp_digest_attribution_from_task
from pure_tate.run_lifecycle import (
    release_artifact_reservation,
    spend_artifact_reservation,
)
from pure_tate.store import ROOT, atomic_write_json

META = Path("/tmp/pure-tate-three-engine-meta.json")


def _notify(title: str, msg: str) -> None:
    print("desktop", send_desktop_notification(title, msg), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, msg), flush=True)


def main() -> None:
    artifact_id = sys.argv[1]
    launch = json.loads(META.read_text())
    vault = Path(launch["vault"])
    job = next(j for j in launch["jobs"] if j["artifact_id"] == artifact_id)
    engine = job["engine"]
    task_id = job["task_id"]
    output = job["output"]
    res = Path(job["reservation"])
    run_manifest = vault / f"run-{artifact_id}.json"
    log = vault / f"{artifact_id}.{engine.replace('cursor-','')}.console.log"

    job["status"] = "running"
    _rewrite_job(vault, launch, job)
    _notify(
        f"Pure Tate • {engine} {job['kind']} starting",
        f"C66-001 • {task_id} -> {artifact_id}",
    )

    with log.open("w") as fh:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pure_tate",
                "agent-run",
                "--manifest",
                str(run_manifest),
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
    with log.open("a") as fh:
        fh.write(f"\nEXIT:{proc.returncode}\n")

    outp = ROOT / output
    if proc.returncode != 0 or not outp.exists():
        spend_artifact_reservation(res, reason="agent_run_failure", task_id=task_id)
        job["status"] = "failed"
        job["exit_code"] = proc.returncode
        _rewrite_job(vault, launch, job)
        _notify(
            f"Pure Tate • {engine} {job['kind']} failed",
            f"C66-001 • {artifact_id} exit={proc.returncode}",
        )
        raise SystemExit(proc.returncode or 1)

    payload = json.loads(outp.read_text())
    release_artifact_reservation(res)

    if job["kind"] == "finding-audit":
        try:
            _apply_finding_audit(payload)
            job["applied"] = True
        except Exception as exc:
            job["applied"] = False
            print("apply warning:", exc, flush=True)
        job["result_verdict"] = payload.get("verdict")
        msg = f"C66-001 • {artifact_id} {job['finding_id']} verdict={payload.get('verdict')}"
    else:
        task = json.loads(Path(job["manifest"]).read_text())
        # mutate in place; do NOT replace digest with return value
        stamp_digest_attribution_from_task(payload, task)
        atomic_write_json(outp, payload)
        campaign = load_campaign("C66-001")
        pub = publish_working_context(campaign, task, payload)
        job["publish"] = pub if isinstance(pub, dict) else str(pub)
        msg = f"C66-001 • {artifact_id} TRACE-0035 COMP-RANK WC published"

    job["status"] = "done"
    _rewrite_job(vault, launch, job)
    _notify(f"Pure Tate • {engine} {job['kind']} done", msg)
    print("done", artifact_id, job.get("result_verdict") or "published", flush=True)


def _rewrite_job(vault: Path, launch: dict, job: dict) -> None:
    launch = json.loads((vault / "LAUNCH.json").read_text())
    launch["jobs"] = [
        job if j["artifact_id"] == job["artifact_id"] else j for j in launch["jobs"]
    ]
    atomic_write_json(vault / "LAUNCH.json", launch)
    META.write_text(json.dumps(launch, indent=2) + "\n")


if __name__ == "__main__":
    main()
