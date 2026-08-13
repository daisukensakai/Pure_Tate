#!/usr/bin/env python3
"""Prep safe Claude --resume of spent ATT-0081 COMP-RANK into a new ATT slot."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pure_tate.agents import build_isolated_context
from pure_tate.campaigns import load_campaign
from pure_tate.notifications import (
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import attach_working_context
from pure_tate.run_lifecycle import reserve_prefixed_artifact
from pure_tate.store import ROOT, atomic_write_json
from pure_tate.tasking import campaign_mathematics_tasks

SESSION_ID = "cd155554-0ee2-46f0-812c-a83e1bff5f36"
ORIG_CWD = Path(
    "/private/var/folders/r_/40tyr0nj6zn_yqb74rw_351c0000gn/T/pure-tate-agent-jmofto8l"
)
CLAUDE_PROJ = (
    Path.home()
    / ".claude/projects/-private-var-folders-r--40tyr0nj6zn-yqb74rw-351c0000gn-T-pure-tate-agent-jmofto8l"
)
SESSION_JSONL = CLAUDE_PROJ / f"{SESSION_ID}.jsonl"
FAILED_SLOT = "ATT-0081"
TASK_ID = "TASK-C66-M-008"
SUBPROBLEM = "C66-COMP-RANK"


def main() -> None:
    assert SESSION_JSONL.is_file(), SESSION_JSONL
    assert not (ROOT / f"proof/attempts/{FAILED_SLOT}.json").exists()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    vault = ROOT / "reports/runs/manual-recovery" / f"att0081-claude-comprank-resume-{stamp}"
    vault.mkdir(parents=True, exist_ok=True)

    campaign = load_campaign("C66-001")
    math = campaign_mathematics_tasks("C66-001")
    base = next(t for t in math if t["id"] == TASK_ID)
    assert base.get("status") == "ready", base.get("status")
    task = attach_working_context(dict(base), campaign)

    aid, res = reserve_prefixed_artifact(ROOT / "proof" / "attempts", "ATT", vault.name)
    assert aid != FAILED_SLOT
    out = f"proof/attempts/{aid}.json"
    assert not (ROOT / out).exists()
    task["selected_engine"] = "claude"
    task["output"] = out

    # Archive session before resume
    session_archive = vault / "session.pre-resume.jsonl"
    shutil.copy2(SESSION_JSONL, session_archive)
    proj_copy = vault / "claude-project-copy"
    if CLAUDE_PROJ.exists():
        shutil.copytree(CLAUDE_PROJ, proj_copy, dirs_exist_ok=True)

    # Rebuild original cwd (Claude project path is keyed to it)
    if ORIG_CWD.exists():
        shutil.rmtree(ORIG_CWD)
    ORIG_CWD.mkdir(parents=True, exist_ok=True)
    copied = build_isolated_context(task, ORIG_CWD)
    # TASK.json with retargeted output
    (ORIG_CWD / "TASK.json").write_text(json.dumps(task, indent=2) + "\n")

    workspace_copy = vault / "workspace-copy"
    if workspace_copy.exists():
        shutil.rmtree(workspace_copy)
    shutil.copytree(ORIG_CWD, workspace_copy, symlinks=True)

    resume_prompt = vault / "RESUME_PROMPT.txt"
    resume_prompt.write_text(
        f"""PRINCIPAL OVERRIDE — CONTINUE AND FINISH YOUR INTERRUPTED COMP-RANK PROOF.

Context:
- Your previous Claude turn for {TASK_ID} / {SUBPROBLEM} was interrupted by the Claude session limit (resets were at 12:50pm Asia/Tokyo). No attempt artifact was written to the original slot.
- The spent/failed slot {FAILED_SLOT} is closed. Do NOT reopen or overwrite it.
- Do NOT modify or overwrite other attempts (especially ATT-0076 / ATT-0080 / ATT-0082 / ATT-0083).
- Finish into the NEW append-only slot: {aid}.
- Same Claude session is resumed; do not restart the proof from zero.
- Prefer finishing from what you already loaded in this session.
- Updated COMP-RANK working context / DIGEST-0026 are available if needed; prefer session memory first.

Token discipline (mandatory):
1. Prefer finishing from session memory and already-read context.
2. At most a small number of Read/Grep/Glob/WebFetch calls if a load-bearing lemma is still missing.
3. Do NOT re-read the entire packet end-to-end. Do NOT burn a long exploratory monologue.
4. Grok workers are optional; prefer not to dispatch unless a single concrete lookup remains.
5. Emit the final JSON in this turn.

Hard contract:
- Final message: exactly one JSON object matching proof/CAMPAIGN_ATTEMPT_TEMPLATE.json
- No Markdown fences, no prose before or after the JSON
- id must be exactly: {aid}
- engine must be exactly: claude
- task_id must be exactly: {TASK_ID}
- subproblem_id must be exactly: {SUBPROBLEM}
- Keep the artifact schema-faithful

Final message: exactly one JSON object.

Supplied files in this workspace:
- TASK.json (output retargeted to {aid})
- prompts / packet / templates / working-context via curated copies and repo/
"""
    )

    (vault / f"manifest-{aid}.json").write_text(json.dumps(task, indent=2) + "\n")

    run_resume = vault / "run_resume.py"
    run_resume.write_text(
        f'''#!/usr/bin/env python3
"""Resume interrupted Claude COMP-RANK into {aid}."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path({str(ROOT)!r})
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import atomic_write_json

META_PATH = Path("/tmp/pure-tate-att0081-resume-meta.json")

def notify(title, message):
    print("notify", {{
        "desktop": send_desktop_notification(title, message),
        "ntfy": send_ntfy_notification_detailed(title, message),
    }}, flush=True)

def main() -> int:
    meta = json.loads(META_PATH.read_text())
    vault = Path(meta["vault"])
    cwd = Path(meta["cwd"])
    session_id = meta["session_id"]
    artifact_id = meta["artifact_id"]
    output = Path(meta["output"])
    reservation = Path(meta["reservation"])
    resume_prompt = Path(meta["resume_prompt"]).read_text()

    if (ROOT / "proof/attempts/{FAILED_SLOT}.json").exists():
        raise SystemExit("refusing: {FAILED_SLOT} unexpectedly exists")
    if output.exists():
        raise SystemExit("refusing to overwrite existing %s" % output)
    if artifact_id == "{FAILED_SLOT}":
        raise SystemExit("refusing to write into spent {FAILED_SLOT}")

    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    notify(
        "Pure Tate • Claude COMP-RANK resume starting",
        "C66-001 • Claude --resume %s\\n{TASK_ID} -> %s ({FAILED_SLOT} closed)"
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
        err_h.write("EXIT:%d\\n" % proc.returncode)
        err_h.write("OUT_BYTES:%d\\n" % stdout_path.stat().st_size)
    raw = stdout_path.read_text(errors="replace")
    if proc.returncode != 0 or not raw.strip():
        spend_artifact_reservation(reservation, reason="resume_agent_failure", task_id="{TASK_ID}")
        notify("Pure Tate • Claude COMP-RANK resume failed", "exit=%s artifact=%s" % (proc.returncode, artifact_id))
        return proc.returncode or 1
    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:
        spend_artifact_reservation(reservation, reason="resume_extract_failure", task_id="{TASK_ID}")
        notify("Pure Tate • Claude COMP-RANK resume extract failed", str(exc))
        raise
    artifact["id"] = artifact_id
    artifact["engine"] = "claude"
    artifact["task_id"] = "{TASK_ID}"
    artifact["subproblem_id"] = "{SUBPROBLEM}"
    atomic_write_json(output, artifact)
    release_artifact_reservation(reservation)
    notify(
        "Pure Tate • Claude COMP-RANK resume done",
        "C66-001 • %s status=%s" % (artifact_id, artifact.get("status")),
    )
    print("status", artifact.get("status"), "engine", artifact.get("engine"), flush=True)
    Path("/tmp/pure-tate-att0081-resume-result.json").write_text(
        json.dumps({{"artifact_id": artifact_id, "status": artifact.get("status"), "output": str(output)}}, indent=2) + "\\n"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''
    )
    run_resume.chmod(0o755)

    launch = {
        "stamp": stamp,
        "vault": str(vault),
        "failed_slot": FAILED_SLOT,
        "artifact_id": aid,
        "output": str(ROOT / out),
        "output_rel": out,
        "reservation": str(res),
        "session_id": SESSION_ID,
        "cwd": str(ORIG_CWD),
        "resume_prompt": str(resume_prompt),
        "session_archive": str(session_archive),
        "task_id": TASK_ID,
        "subproblem_id": SUBPROBLEM,
        "files": copied,
        "note": f"Safe Claude --resume of COMP-RANK after session limit; {FAILED_SLOT} closed",
    }
    atomic_write_json(vault / "LAUNCH.json", launch)
    atomic_write_json(
        vault / "WORKSPACE.json",
        {
            "artifact_id": aid,
            "failed_slot": FAILED_SLOT,
            "new_slot": aid,
            "cwd": str(ORIG_CWD),
            "session_id": SESSION_ID,
            "session_archive": str(session_archive),
            "claude_project_copy": str(proj_copy),
            "workspace_copy": str(workspace_copy),
            "protect_from_overwrite": [
                f"proof/attempts/{FAILED_SLOT}.json",
                "proof/attempts/ATT-0076.json",
                "proof/attempts/ATT-0080.json",
                "proof/attempts/ATT-0082.json",
                "proof/attempts/ATT-0083.json",
            ],
        },
    )
    meta = {
        "vault": str(vault),
        "cwd": str(ORIG_CWD),
        "session_id": SESSION_ID,
        "artifact_id": aid,
        "output": str(ROOT / out),
        "reservation": str(res),
        "resume_prompt": str(resume_prompt),
        "task_id": TASK_ID,
    }
    Path("/tmp/pure-tate-att0081-resume-meta.json").write_text(
        json.dumps(meta, indent=2) + "\n"
    )

    msg = (
        f"C66-001 • Claude --resume {SESSION_ID}\n"
        f"{TASK_ID} {SUBPROBLEM} -> {aid} ({FAILED_SLOT} closed)"
    )
    print("desktop", send_desktop_notification("Pure Tate • Claude COMP-RANK resume prepped", msg))
    print("ntfy", send_ntfy_notification_detailed("Pure Tate • Claude COMP-RANK resume prepped", msg))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
