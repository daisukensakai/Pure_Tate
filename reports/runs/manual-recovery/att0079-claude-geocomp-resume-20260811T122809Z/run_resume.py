#!/usr/bin/env python3
"""Resume interrupted Claude GEO-COMP into a new ATT, then notify."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import atomic_write_json

META_PATH = Path("/tmp/pure-tate-att0079-resume-meta.json")

def notify(title, message):
    print("notify", {
        "desktop": send_desktop_notification(title, message),
        "ntfy": send_ntfy_notification_detailed(title, message),
    }, flush=True)

def main() -> int:
    meta = json.loads(META_PATH.read_text())
    vault = Path(meta["vault"])
    cwd = Path(meta["cwd"])
    session_id = meta["session_id"]
    artifact_id = meta["artifact_id"]
    output = Path(meta["output"])
    reservation = Path(meta["reservation"])
    resume_prompt = Path(meta["resume_prompt"]).read_text()

    if (ROOT / "proof/attempts/ATT-0079.json").exists():
        raise SystemExit("refusing: ATT-0079 unexpectedly exists")
    if output.exists():
        raise SystemExit("refusing to overwrite existing %s" % output)
    if artifact_id == "ATT-0079":
        raise SystemExit("refusing to write into spent ATT-0079")

    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    notify(
        "Pure Tate • Claude GEO-COMP resume starting",
        "C66-001 • Claude --resume %s\nTASK-C66-M-003 -> %s (ATT-0079 closed)"
        % (session_id, artifact_id),
    )
    env = dict(os.environ)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
    argv = [
        "claude", "-p", resume_prompt, "--resume", session_id,
        "--model", "claude-opus-5", "--effort", "max",
        "--output-format", "stream-json", "--verbose", "--include-partial-messages",
        "--permission-mode", "bypassPermissions",
        "--allowedTools", "Read", "Grep", "Glob", "WebSearch", "WebFetch",
        "--disallowedTools", "Edit", "Write", "Bash",
    ]
    with stdout_path.open("w") as out_h, stderr_path.open("w") as err_h:
        proc = subprocess.run(argv, cwd=str(cwd), env=env, stdout=out_h, stderr=err_h, check=False)
    with stderr_path.open("a") as err_h:
        err_h.write("EXIT:%d\n" % proc.returncode)
        err_h.write("OUT_BYTES:%d\n" % stdout_path.stat().st_size)
    raw = stdout_path.read_text(errors="replace")
    if proc.returncode != 0 or not raw.strip():
        spend_artifact_reservation(reservation, reason="resume_agent_failure", task_id="TASK-C66-M-003")
        notify("Pure Tate • Claude GEO-COMP resume failed", "exit=%s artifact=%s" % (proc.returncode, artifact_id))
        return proc.returncode or 1
    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:
        spend_artifact_reservation(reservation, reason="resume_extract_failure", task_id="TASK-C66-M-003")
        notify("Pure Tate • Claude GEO-COMP resume extract failed", str(exc))
        raise
    artifact["id"] = artifact_id
    artifact["engine"] = "claude"
    artifact["task_id"] = "TASK-C66-M-003"
    artifact["subproblem_id"] = "C66-GEO-COMP"
    atomic_write_json(output, artifact)
    release_artifact_reservation(reservation)
    notify(
        "Pure Tate • Claude GEO-COMP resume done",
        "C66-001 • %s status=%s" % (artifact_id, artifact.get("status")),
    )
    print("status", artifact.get("status"), "engine", artifact.get("engine"), flush=True)
    Path("/tmp/pure-tate-att0079-resume-result.json").write_text(
        json.dumps({"artifact_id": artifact_id, "status": artifact.get("status"), "output": str(output)}, indent=2) + "\n"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
