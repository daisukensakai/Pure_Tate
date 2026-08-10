#!/usr/bin/env python3
"""Serial cursor-grok finding audits (noforced) with Mac+iPhone notify."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pure_tate.notifications import (  # noqa: E402
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.run_lifecycle import (  # noqa: E402
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import ROOT as PT_ROOT  # noqa: E402
from pure_tate.tasking import finding_audit_tasks  # noqa: E402
from pure_tate.capabilities import capability_is_attested  # noqa: E402


ENGINE = "cursor-grok"
STEP_TASKS = ["TASK-F-FND-0116", "TASK-F-FND-0117"]


def notify(title: str, message: str) -> None:
    desktop = send_desktop_notification(title, message)
    ntfy = send_ntfy_notification_detailed(title, message)
    print("notify", {"desktop": desktop, "ntfy": ntfy}, flush=True)


def ensure_attestation(rundir: Path) -> None:
    if capability_is_attested(ENGINE, "finding-audit"):
        print("attestation already present for", ENGINE, flush=True)
        return
    notify(
        "Pure Tate • cursor-grok attest starting",
        "C66-001 • live capability-audit for cursor-grok (prerequisite)",
    )
    log = rundir / "capability-audit.console.log"
    with log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pure_tate",
                "capability-audit",
                "--engines",
                ENGINE,
                "--live",
                "--timeout",
                "300",
            ],
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    print("capability-audit exit", proc.returncode, flush=True)
    if proc.returncode != 0 or not capability_is_attested(ENGINE, "finding-audit"):
        notify(
            "Pure Tate • cursor-grok attest failed",
            "C66-001 • capability-audit failed; cannot run finding audits",
        )
        raise SystemExit(proc.returncode or 1)
    notify(
        "Pure Tate • cursor-grok attest done",
        "C66-001 • cursor-grok finding-audit attestation pass",
    )


def main() -> int:
    stamp = os.environ.get("PURE_TATE_STAMP") or __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")
    run_id = "cursor-grok-audits-%s" % stamp
    rundir = ROOT / "reports" / "runs" / "manual-recovery" / run_id
    rundir.mkdir(parents=True, exist_ok=True)

    ensure_attestation(rundir)

    tasks = finding_audit_tasks("C66-001")
    manifest_path = ROOT / "tasks" / "generated" / "campaign-C66-001-finding-audit.json"
    manifest_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    ready = {t["id"]: t for t in tasks if t.get("status") == "ready"}

    # Reuse existing reserved IDs if still reserved for prior aborted launch.
    preferred = ["FAUD-0118", "FAUD-0119"]
    launches = []
    for index, tid in enumerate(STEP_TASKS):
        if tid not in ready:
            raise SystemExit("task not ready: %s" % tid)
        preferred_id = preferred[index] if index < len(preferred) else None
        reservation = None
        artifact_id = None
        if preferred_id:
            res_path = (
                ROOT / "reports" / "runs" / "reservations" / (preferred_id + ".json")
            )
            if res_path.exists():
                record = json.loads(res_path.read_text(encoding="utf-8"))
                if record.get("status") == "reserved" and not (
                    ROOT / "research" / "finding-audits" / (preferred_id + ".json")
                ).exists():
                    artifact_id = preferred_id
                    reservation = res_path
                    record["run_id"] = run_id
                    res_path.write_text(
                        json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
        if artifact_id is None:
            artifact_id, reservation = reserve_prefixed_artifact(
                PT_ROOT / "research" / "finding-audits", "FAUD", run_id
            )
        task = dict(ready[tid])
        output = "research/finding-audits/%s.json" % artifact_id
        task["selected_engine"] = ENGINE
        task["output"] = output
        (rundir / ("manifest-%s.json" % artifact_id)).write_text(
            json.dumps(task, indent=2) + "\n", encoding="utf-8"
        )
        launches.append(
            {
                "step": index + 1,
                "kind": "finding-audit",
                "task_id": tid,
                "finding_id": task["finding_id"],
                "engine": ENGINE,
                "artifact_id": artifact_id,
                "output": output,
                "reservation": str(reservation),
            }
        )

    (rundir / "LAUNCH.json").write_text(
        json.dumps(
            {
                "note": (
                    "two serial finding audits; cursor-grok only; no forced; "
                    "Mac+iPhone notify; Claude deferred"
                ),
                "stamp": stamp,
                "engine": ENGINE,
                "launches": launches,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("RUNDIR", rundir, flush=True)

    for item in launches:
        step = item["step"]
        title_start = "Pure Tate • grok step %d/2 starting" % step
        msg_start = "C66-001 • finding-audit via %s\n%s (%s)" % (
            ENGINE,
            item["task_id"],
            item["artifact_id"],
        )
        notify(title_start, msg_start)
        log_path = rundir / ("%s.cursor-grok.console.log" % item["artifact_id"])
        with log_path.open("w", encoding="utf-8") as handle:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pure_tate",
                    "agent-run",
                    "--manifest",
                    str(manifest_path.relative_to(ROOT)),
                    "--task-id",
                    item["task_id"],
                    "--engine",
                    ENGINE,
                    "--output",
                    item["output"],
                    "--timeout",
                    "10800",
                ],
                cwd=ROOT,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        handle_txt = "EXIT:%d\n" % proc.returncode
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(handle_txt)
        artifact = ROOT / item["output"]
        if proc.returncode != 0 or not artifact.exists():
            spend_artifact_reservation(
                Path(item["reservation"]),
                reason="agent_run_failure",
                task_id=item["task_id"],
            )
            notify(
                "Pure Tate • grok step %d/2 failed" % step,
                "C66-001 • %s FAILED exit=%s" % (item["task_id"], proc.returncode),
            )
            return proc.returncode or 1
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        spend_artifact_reservation(
            Path(item["reservation"]),
            reason="agent_run_success",
            task_id=item["task_id"],
        )
        notify(
            "Pure Tate • grok step %d/2 done" % step,
            "C66-001 • %s (%s) verdict=%s"
            % (item["task_id"], item["artifact_id"], payload.get("verdict")),
        )
        print(
            "completed",
            item["artifact_id"],
            payload.get("finding_id"),
            payload.get("verdict"),
            flush=True,
        )
    notify(
        "Pure Tate • run completed",
        "C66-001: 2/2 cursor-grok finding-audit steps",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
