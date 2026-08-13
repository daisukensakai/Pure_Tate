#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from pure_tate.findings import record_review_findings
from pure_tate.campaigns import load_campaign
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.paired import publish_working_context, stamp_digest_attribution_from_task
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import ROOT, atomic_write_json

META = Path("/tmp/pure-tate-context-2step-meta.json")

def notify(title, msg):
    print("desktop", send_desktop_notification(title, msg), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, msg), flush=True)

def main():
    aid = sys.argv[1]
    launch = json.loads(META.read_text())
    vault = Path(launch["vault"])
    job = next(j for j in launch["jobs"] if j["artifact_id"] == aid)
    engine, task_id, output = job["engine"], job["task_id"], job["output"]
    res = Path(job["reservation"])
    log = vault / f"{aid}.{engine}.console.log"
    job["status"] = "running"; _save(vault, job)
    notify(f"Pure Tate • {engine} {job['kind']} starting", f"C66-001 • {task_id} -> {aid}")
    with log.open("w") as fh:
        proc = subprocess.run(
            [sys.executable, "-m", "pure_tate", "agent-run",
             "--manifest", str(vault / f"run-{aid}.json"),
             "--task-id", task_id, "--engine", engine,
             "--output", output, "--timeout", "10800"],
            cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT,
        )
    with log.open("a") as fh:
        fh.write(f"\nEXIT:{proc.returncode}\n")
    outp = ROOT / output
    if proc.returncode != 0 or not outp.exists():
        spend_artifact_reservation(res, reason="agent_run_failure", task_id=task_id)
        job["status"] = "failed"; job["exit_code"] = proc.returncode; _save(vault, job)
        notify(f"Pure Tate • {engine} {job['kind']} failed", f"C66-001 • {aid} exit={proc.returncode}")
        raise SystemExit(proc.returncode or 1)
    payload = json.loads(outp.read_text())
    release_artifact_reservation(res)
    if job["kind"] == "review":
        attempt = json.loads((ROOT / f"proof/attempts/{job['target_attempt_id']}.json").read_text())
        attempt["_path"] = str(ROOT / f"proof/attempts/{job['target_attempt_id']}.json")
        try:
            touched = record_review_findings(payload, attempt)
            job["ingested_findings"] = [t.get("id") for t in touched]
        except Exception as exc:
            print("ingest warning:", exc, flush=True)
        job["result_verdict"] = payload.get("verdict")
        msg = f"C66-001 • {aid} {job['target_attempt_id']} P{job['review_pass']} verdict={payload.get('verdict')}"
    else:
        task = json.loads(Path(job["manifest"]).read_text())
        stamp_digest_attribution_from_task(payload, task)  # in-place; ignore return
        atomic_write_json(outp, payload)
        pub = publish_working_context(load_campaign("C66-001"), task, payload)
        job["publish"] = pub if isinstance(pub, dict) else str(pub)
        msg = f"C66-001 • {aid} {job.get('trace_id')} WC published"
    job["status"] = "done"; _save(vault, job)
    notify(f"Pure Tate • {engine} {job['kind']} done", msg)
    print("done", aid, job.get("result_verdict") or "published", flush=True)

def _save(vault, job):
    launch = json.loads((vault / "LAUNCH.json").read_text())
    launch["jobs"] = [job if j["artifact_id"] == job["artifact_id"] else j for j in launch["jobs"]]
    atomic_write_json(vault / "LAUNCH.json", launch)
    META.write_text(json.dumps(launch, indent=2) + "\n")

if __name__ == "__main__":
    main()
