#!/usr/bin/env python3
"""After REV-0130: run Codex DIGEST-0025 (COMP-COMP) then FAUD on FND-0122."""

from __future__ import annotations

import json
import subprocess
import sys
import time
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
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import ROOT, atomic_write_json
from pure_tate.tasking import finding_audit_tasks

REV_VAULT = ROOT / "reports/runs/manual-recovery/att0079-claude-geocomp-resume-20260811T122809Z"
COMP_VAULT = ROOT / "reports/runs/manual-recovery/comp-trace-context-20260811T123500Z"
META = Path("/tmp/pure-tate-att0080-codex-review-meta.json")


def _notify(title: str, msg: str) -> None:
    print("desktop", send_desktop_notification(title, msg))
    print("ntfy", send_ntfy_notification_detailed(title, msg))


def wait_for_rev() -> dict:
    meta = json.loads(META.read_text())
    rid = meta["rev_id"]
    out = Path(meta["output"])
    log = REV_VAULT / f"{rid}.codex.console.log"
    print(f"waiting for {rid} ...", flush=True)
    while True:
        if log.exists() and "EXIT2:" in log.read_text(errors="replace") and out.exists():
            break
        # also stop if spent without output
        res = Path(meta["reservation"])
        if res.exists():
            st = json.loads(res.read_text()).get("status")
            if st == "spent" and not out.exists():
                raise SystemExit(f"{rid} spent without output")
        time.sleep(5)
    # give post-hook a moment
    for _ in range(60):
        launch = json.loads((REV_VAULT / "LAUNCH.json").read_text())
        if launch.get("codex_review", {}).get("status") == "done":
            break
        time.sleep(2)
    launch = json.loads((REV_VAULT / "LAUNCH.json").read_text())
    print("rev done", launch.get("codex_review"), flush=True)
    return launch


def run_agent(manifest: Path, task_id: str, engine: str, output: str, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as fh:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pure_tate",
                "agent-run",
                "--manifest",
                str(manifest),
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
    return proc.returncode


def run_digest_0025() -> None:
    launch = json.loads((COMP_VAULT / "LAUNCH.json").read_text())
    job = next(j for j in launch["digest_jobs"] if j["digest_id"] == "DIGEST-0025")
    manifest = COMP_VAULT / f"manifest-{job['digest_id']}.json"
    task = json.loads(manifest.read_text())
    # ensure selected engine codex
    task["selected_engine"] = "codex"
    manifest.write_text(json.dumps(task, indent=2) + "\n")
    (COMP_VAULT / "digest25-manifest.json").write_text(json.dumps([task], indent=2) + "\n")
    _notify(
        "Pure Tate • Codex COMP-COMP mine starting",
        f"C66-001 • {job['task_id']} {job['trace_id']} -> {job['digest_id']}",
    )
    ec = run_agent(
        COMP_VAULT / "digest25-manifest.json",
        job["task_id"],
        "codex",
        job["output"],
        COMP_VAULT / f"{job['digest_id']}.codex.console.log",
    )
    out = ROOT / job["output"]
    res = Path(job["reservation"])
    if ec != 0 or not out.exists():
        spend_artifact_reservation(res, reason="agent_run_failure", task_id=job["task_id"])
        _notify(
            "Pure Tate • Codex COMP-COMP mine failed",
            f"C66-001 • {job['digest_id']} exit={ec}",
        )
        raise SystemExit(ec or 1)
    digest = json.loads(out.read_text())
    digest = stamp_digest_attribution_from_task(digest, task)
    atomic_write_json(out, digest)
    release_artifact_reservation(res)
    campaign = load_campaign("C66-001")
    pub = publish_working_context(campaign, task, digest)
    job["status"] = "done"
    job["publish"] = {k: pub.get(k) for k in ("paths", "sha256", "subproblem_id") if k in pub} if isinstance(pub, dict) else str(pub)
    launch["digest_jobs"] = [
        job if j["digest_id"] == "DIGEST-0025" else j for j in launch["digest_jobs"]
    ]
    atomic_write_json(COMP_VAULT / "LAUNCH.json", launch)
    _notify(
        "Pure Tate • Codex COMP-COMP mine done",
        f"C66-001 • {job['digest_id']} published WC",
    )
    print("DIGEST-0025 done", job.get("publish"), flush=True)


def run_faud_0122() -> None:
    tasks = finding_audit_tasks("C66-001")
    task = next(
        (
            t
            for t in tasks
            if t.get("finding_id") == "FND-0122" and "codex" not in (t.get("excluded_engines") or [])
        ),
        None,
    )
    if task is None:
        print("no Codex-eligible FAUD for FND-0122", flush=True)
        return
    faud_id, res = reserve_prefixed_artifact(
        ROOT / "research" / "finding-audits", "FAUD", COMP_VAULT.name
    )
    out = f"research/finding-audits/{faud_id}.json"
    task = dict(task)
    task["selected_engine"] = "codex"
    task["output"] = out
    (COMP_VAULT / f"manifest-{faud_id}.json").write_text(json.dumps(task, indent=2) + "\n")
    (COMP_VAULT / "faud-manifest.json").write_text(json.dumps([task], indent=2) + "\n")
    _notify(
        "Pure Tate • Codex COMP-RANK audit starting",
        f"C66-001 • {task['id']} FND-0122 -> {faud_id}",
    )
    ec = run_agent(
        COMP_VAULT / "faud-manifest.json",
        task["id"],
        "codex",
        out,
        COMP_VAULT / f"{faud_id}.codex.console.log",
    )
    outp = ROOT / out
    if ec != 0 or not outp.exists():
        spend_artifact_reservation(res, reason="agent_run_failure", task_id=task["id"])
        _notify(
            "Pure Tate • Codex COMP-RANK audit failed",
            f"C66-001 • {faud_id} exit={ec}",
        )
        raise SystemExit(ec or 1)
    audit = json.loads(outp.read_text())
    release_artifact_reservation(res)
    try:
        _apply_finding_audit(audit)
    except Exception as exc:
        print("_apply_finding_audit warning:", exc, flush=True)
    launch = json.loads((COMP_VAULT / "LAUNCH.json").read_text())
    launch["faud_job"] = {
        "faud_id": faud_id,
        "finding_id": "FND-0122",
        "verdict": audit.get("verdict"),
        "status": "done",
    }
    atomic_write_json(COMP_VAULT / "LAUNCH.json", launch)
    _notify(
        "Pure Tate • Codex COMP-RANK audit done",
        f"C66-001 • {faud_id} FND-0122 verdict={audit.get('verdict')}",
    )
    print("FAUD done", faud_id, audit.get("verdict"), flush=True)


def main() -> None:
    wait_for_rev()
    run_digest_0025()
    run_faud_0122()
    _notify(
        "Pure Tate • COMP Codex queue complete",
        "C66-001 • DIGEST-0025 + FND-0122 audit finished after REV-0130",
    )


if __name__ == "__main__":
    main()
