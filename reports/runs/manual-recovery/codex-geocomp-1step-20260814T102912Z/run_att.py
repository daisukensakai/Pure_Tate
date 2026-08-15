#!/usr/bin/env python3
"""One ordinary C66-GEO-COMP Codex mathematics turn from LAUNCH.json. No forced-proof."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.run_lifecycle import (
    CampaignRunLock,
    live_run_ledgers,
    recover_stale_run_ledgers,
    release_artifact_reservation,
    spend_artifact_reservation,
)
from pure_tate.store import ROOT, atomic_write_json

VAULT = Path(__file__).resolve().parent


def notify(title: str, msg: str) -> None:
    print("desktop", send_desktop_notification(title, msg), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, msg), flush=True)


def main() -> int:
    launch_path = VAULT / "LAUNCH.json"
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    artifact_id = launch["artifact_id"]
    task_id = launch["task_id"]
    engine = launch["engine"]
    output = launch["output"]
    manifest = Path(launch["manifest"])
    reservation = Path(launch["reservation"])
    log = VAULT / ("%s.codex.console.log" % artifact_id)
    outp = ROOT / output

    with CampaignRunLock("C66-001"):
        recover_stale_run_ledgers("C66-001")
        active = live_run_ledgers("C66-001")
        if active:
            print("ERROR: live drive still present: %s" % active, file=sys.stderr)
            return 2
        launch["status"] = "running"
        atomic_write_json(launch_path, launch)
        notify(
            "Pure Tate • Codex GEO-COMP starting",
            "C66-001 • %s C66-GEO-COMP -> %s" % (task_id, artifact_id),
        )
        with log.open("w", encoding="utf-8") as fh:
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
        with log.open("a", encoding="utf-8") as fh:
            fh.write("\nEXIT:%s\n" % proc.returncode)
        if proc.returncode != 0 or not outp.exists():
            spend_artifact_reservation(
                reservation, reason="agent_run_failure", task_id=task_id
            )
            launch["status"] = "failed"
            launch["exit_code"] = proc.returncode
            atomic_write_json(launch_path, launch)
            notify(
                "Pure Tate • Codex GEO-COMP failed",
                "C66-001 • %s exit=%s" % (artifact_id, proc.returncode),
            )
            return proc.returncode or 1
        payload = json.loads(outp.read_text(encoding="utf-8"))
        release_artifact_reservation(reservation)
        launch["status"] = "done"
        launch["result_status"] = payload.get("status")
        launch["gap_count"] = len(payload.get("gap_markers") or [])
        atomic_write_json(launch_path, launch)
        notify(
            "Pure Tate • Codex GEO-COMP done",
            "C66-001 • %s C66-GEO-COMP status=%s"
            % (artifact_id, payload.get("status")),
        )
        print("done", artifact_id, payload.get("status"), flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
