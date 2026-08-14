#!/usr/bin/env python3
"""Resume interrupted Claude FND-0142 audit into FAUD--0001."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate')
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream
from pure_tate.campaign_driver import _apply_finding_audit
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import atomic_write_json

META_PATH = Path("/tmp/pure-tate-faud0146-resume-meta.json")

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
    argv = meta["argv"]
    env_updates = meta.get("env_updates") or {}
    task_id = meta["task_id"]
    finding_id = meta["finding_id"]

    if (ROOT / "research/finding-audits/FAUD-0146.json").exists():
        raise SystemExit("refusing: spent slot FAUD-0146 unexpectedly exists")
    if output.exists():
        raise SystemExit("refusing to overwrite existing %s" % output)
    if artifact_id in ("FAUD-0146", "FAUD-0147"):
        raise SystemExit("refusing forbidden slot %s" % artifact_id)

    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    notify(
        "Pure Tate • Claude FND-0142 resume starting",
        "C66-001 • Claude --resume %s\n%s -> %s (FAUD-0146 closed)"
        % (session_id, task_id, artifact_id),
    )
    env = dict(os.environ)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
    env.update({str(k): str(v) for k, v in env_updates.items()})
    with stdout_path.open("w") as out_h, stderr_path.open("w") as err_h:
        proc = subprocess.run(argv, cwd=str(cwd), env=env, stdout=out_h, stderr=err_h, check=False)
    with stderr_path.open("a") as err_h:
        err_h.write("EXIT:%d\n" % proc.returncode)
        err_h.write("OUT_BYTES:%d\n" % stdout_path.stat().st_size)
    raw = stdout_path.read_text(errors="replace")
    if proc.returncode != 0 or not raw.strip():
        spend_artifact_reservation(reservation, reason="resume_agent_failure", task_id=task_id)
        notify("Pure Tate • Claude FND-0142 resume failed", "exit=%s artifact=%s" % (proc.returncode, artifact_id))
        return proc.returncode or 1
    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:
        spend_artifact_reservation(reservation, reason="resume_extract_failure", task_id=task_id)
        notify("Pure Tate • Claude FND-0142 resume extract failed", str(exc))
        raise
    artifact["id"] = artifact_id
    artifact["engine"] = "claude"
    for key in ("adjudicator_engine", "auditor_engine"):
        if key in artifact:
            artifact[key] = "claude"
    artifact["task_id"] = task_id
    artifact["finding_id"] = finding_id
    if output.exists():
        raise SystemExit("output appeared concurrently; abort")
    atomic_write_json(output, artifact)
    release_artifact_reservation(reservation)
    try:
        _apply_finding_audit(artifact)
        applied = True
    except Exception as exc:
        applied = False
        print("apply_finding_audit warning:", exc, flush=True)
    notify(
        "Pure Tate • Claude FND-0142 resume done",
        "C66-001 • %s %s verdict=%s applied=%s" % (artifact_id, finding_id, artifact.get("verdict"), applied),
    )
    result = {
        "artifact_id": artifact_id,
        "finding_id": finding_id,
        "verdict": artifact.get("verdict"),
        "applied": applied,
        "output": str(output),
        "returncode": proc.returncode,
    }
    Path("/tmp/pure-tate-faud0146-resume-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
