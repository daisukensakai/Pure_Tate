#!/usr/bin/env python3
"""Resume interrupted Claude FND-0121 audit into a new FAUD slot."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream
from pure_tate.campaign_driver import _apply_finding_audit
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import atomic_write_json

META_PATH = Path("/tmp/pure-tate-faud0123-resume-meta.json")

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

    protected = ROOT / "research/finding-audits/FAUD-0122.json"
    if not protected.exists():
        raise SystemExit("protected FAUD-0122 missing unexpectedly")
    if (ROOT / "research/finding-audits/FAUD-0123.json").exists():
        raise SystemExit("refusing: spent slot FAUD-0123 unexpectedly exists")
    if output.exists():
        raise SystemExit("refusing to overwrite existing %s" % output)
    if artifact_id == "FAUD-0123":
        raise SystemExit("refusing to write into spent FAUD-0123")

    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    notify(
        "Pure Tate • Claude FND-0121 resume starting",
        "C66-001 • Claude --resume %s\nTASK-F-FND-0121 -> %s (FAUD-0122 protected)"
        % (session_id, artifact_id),
    )
    env = dict(os.environ)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
    argv = [
        "claude", "-p", resume_prompt, "--resume", session_id,
        "--model", "claude-opus-5", "--effort", "high",
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
        spend_artifact_reservation(reservation, reason="resume_agent_failure", task_id="TASK-F-FND-0121")
        notify("Pure Tate • Claude FND-0121 resume failed", "exit=%s artifact=%s" % (proc.returncode, artifact_id))
        return proc.returncode or 1
    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:
        spend_artifact_reservation(reservation, reason="resume_extract_failure", task_id="TASK-F-FND-0121")
        notify("Pure Tate • Claude FND-0121 resume extract failed", str(exc))
        raise
    artifact["id"] = artifact_id
    artifact["engine"] = artifact.get("engine") or "claude"
    if "adjudicator_engine" in artifact or "auditor_engine" in artifact:
        pass
    # Prefer template field names if present; else set common ones.
    for key in ("adjudicator_engine", "auditor_engine", "engine"):
        if key in artifact:
            artifact[key] = "claude"
    artifact["task_id"] = "TASK-F-FND-0121"
    artifact["finding_id"] = "FND-0121"
    atomic_write_json(output, artifact)
    release_artifact_reservation(reservation)
    try:
        _apply_finding_audit(artifact)
    except Exception as exc:
        print("apply_finding_audit warning:", exc, flush=True)
    # Also apply FAUD-0122 if still pending.
    try:
        faud122 = json.loads((ROOT / "research/finding-audits/FAUD-0122.json").read_text())
        _apply_finding_audit(faud122)
    except Exception as exc:
        print("apply FAUD-0122 warning:", exc, flush=True)
    notify(
        "Pure Tate • Claude FND-0121 resume done",
        "C66-001 • %s FND-0121 verdict=%s" % (artifact_id, artifact.get("verdict")),
    )
    print("verdict", artifact.get("verdict"), "engine", artifact.get("engine"), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
