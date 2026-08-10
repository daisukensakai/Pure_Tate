#!/usr/bin/env python3
"""Two serial noforced math steps: Claude GEO-COMP, then Codex COMP-RANK."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pure_tate.notifications import (  # noqa: E402
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.run_lifecycle import (  # noqa: E402
    release_artifact_reservation,
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import ROOT as PT_ROOT  # noqa: E402
from pure_tate.tasking import campaign_mathematics_tasks  # noqa: E402


STEPS = [
    {
        "task_id": "TASK-C66-M-003",
        "subproblem_id": "C66-GEO-COMP",
        "engine": "claude",
    },
    {
        "task_id": "TASK-C66-M-008",
        "subproblem_id": "C66-COMP-RANK",
        "engine": "codex",
    },
]


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
    stamp = os.environ.get("PURE_TATE_STAMP") or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    run_id = "claude-codex-math-2step-%s" % stamp
    rundir = ROOT / "reports" / "runs" / "manual-recovery" / run_id
    rundir.mkdir(parents=True, exist_ok=True)

    tasks = campaign_mathematics_tasks("C66-001")
    manifest_path = (
        ROOT / "tasks" / "generated" / "campaign-C66-001-mathematics.json"
    )
    manifest_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    by_id = {t["id"]: t for t in tasks}

    launches = []
    for index, step in enumerate(STEPS, 1):
        task = dict(by_id[step["task_id"]])
        if task.get("status") != "ready":
            raise SystemExit("task not ready: %s status=%s" % (step["task_id"], task.get("status")))
        if task.get("subproblem_id") != step["subproblem_id"]:
            raise SystemExit("subproblem mismatch for %s" % step["task_id"])
        artifact_id, reservation = reserve_prefixed_artifact(
            PT_ROOT / "proof" / "attempts", "ATT", run_id
        )
        output = "proof/attempts/%s.json" % artifact_id
        if (ROOT / output).exists():
            raise SystemExit("refusing to overwrite %s" % output)
        task["selected_engine"] = step["engine"]
        task["output"] = output
        (rundir / ("manifest-%s.json" % artifact_id)).write_text(
            json.dumps(task, indent=2) + "\n", encoding="utf-8"
        )
        launches.append(
            {
                "step": index,
                "kind": "mathematics",
                "task_id": step["task_id"],
                "subproblem_id": step["subproblem_id"],
                "engine": step["engine"],
                "artifact_id": artifact_id,
                "output": output,
                "reservation": str(reservation),
            }
        )

    (rundir / "LAUNCH.json").write_text(
        json.dumps(
            {
                "note": (
                    "two serial ordinary math steps; no forced; Claude GEO-COMP "
                    "then Codex COMP-RANK; Mac+iPhone notify"
                ),
                "stamp": stamp,
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
        notify(
            "Pure Tate • math step %d/2 starting" % step,
            "C66-001 • mathematics via %s\n%s %s (%s)"
            % (
                item["engine"],
                item["task_id"],
                item["subproblem_id"],
                item["artifact_id"],
            ),
        )
        log_path = rundir / (
            "%s.%s.console.log" % (item["artifact_id"], item["engine"])
        )
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
                    item["engine"],
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
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("EXIT:%d\n" % proc.returncode)

        artifact = ROOT / item["output"]
        reservation = Path(item["reservation"])
        if proc.returncode != 0 or not artifact.exists():
            spend_artifact_reservation(
                reservation,
                reason="agent_run_failure",
                task_id=item["task_id"],
            )
            notify(
                "Pure Tate • math step %d/2 failed" % step,
                "C66-001 • %s FAILED exit=%s"
                % (item["artifact_id"], proc.returncode),
            )
            return proc.returncode or 1

        payload = json.loads(artifact.read_text(encoding="utf-8"))
        # Drop reservation after durable write owns the id.
        release_artifact_reservation(reservation)
        notify(
            "Pure Tate • math step %d/2 done" % step,
            "C66-001 • %s (%s) status=%s"
            % (
                item["artifact_id"],
                item["subproblem_id"],
                payload.get("status"),
            ),
        )
        print(
            "completed",
            item["artifact_id"],
            item["subproblem_id"],
            item["engine"],
            payload.get("status"),
            flush=True,
        )

    notify(
        "Pure Tate • run completed",
        "C66-001: 2/2 ordinary math steps (Claude GEO-COMP, Codex COMP-RANK)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
