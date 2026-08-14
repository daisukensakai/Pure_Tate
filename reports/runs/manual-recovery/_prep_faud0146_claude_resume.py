#!/usr/bin/env python3
"""Prepare safe Claude --resume of FAUD-0146 / FND-0142 into a new FAUD slot."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pure_tate.agents import build_isolated_context, load_engines_config
from pure_tate.capabilities import phase_allows_web
from pure_tate.grok_workers import (
    apply_workers_to_argv,
    max_grok_workers_from_config,
    max_worker_turns_from_config,
    prepare_worker_session,
    resolve_worker_backend,
    resolve_worker_model,
)
from pure_tate.run_lifecycle import reserve_prefixed_artifact
from pure_tate.store import ROOT, atomic_write_json
from pure_tate.tasking import finding_audit_tasks

SESSION_ID = "6e6bb5a6-9798-4aa6-b728-da7774a10c0f"
ORIG_CWD = Path(
    "/private/var/folders/r_/40tyr0nj6zn_yqb74rw_351c0000gn/T/pure-tate-agent-wq80i_od"
)
CLAUDE_PROJ = (
    Path.home()
    / ".claude/projects/-private-var-folders-r--40tyr0nj6zn-yqb74rw-351c0000gn-T-pure-tate-agent-wq80i-od"
)
SESSION_SRC = CLAUDE_PROJ / f"{SESSION_ID}.jsonl"
WORKER_SESS = ROOT / "research/worker-dispatches/sessions/SESS-b29f88768188"
FAILED_SLOT = "FAUD-0146"
TASK_ID = "TASK-F-FND-0142"
FINDING_ID = "FND-0142"
META_PATH = Path("/tmp/pure-tate-faud0146-resume-meta.json")


def main() -> int:
    if not SESSION_SRC.exists():
        raise SystemExit(f"missing session {SESSION_SRC}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"faud0146-claude-resume-{stamp}"
    vault = ROOT / "reports/runs/manual-recovery" / run_id
    vault.mkdir(parents=True, exist_ok=True)

    session_archive = vault / "session.pre-resume.jsonl"
    shutil.copy2(SESSION_SRC, session_archive)
    claude_copy = vault / "claude-project-copy"
    claude_copy.mkdir(exist_ok=True)
    shutil.copy2(SESSION_SRC, claude_copy / SESSION_SRC.name)
    tool_dir = CLAUDE_PROJ / SESSION_ID
    if tool_dir.exists():
        shutil.copytree(tool_dir, claude_copy / SESSION_ID, dirs_exist_ok=True)
    if WORKER_SESS.exists():
        shutil.copytree(
            WORKER_SESS, vault / "worker-session-SESS-b29f88768188", dirs_exist_ok=True
        )

    artifact_id, res_path = reserve_prefixed_artifact(
        ROOT / "research/finding-audits", "FAUD", run_id
    )
    if artifact_id in (FAILED_SLOT, "FAUD-0147"):
        raise SystemExit(f"refusing forbidden slot {artifact_id}")
    output_rel = f"research/finding-audits/{artifact_id}.json"
    output = ROOT / output_rel
    if output.exists():
        raise SystemExit(f"output already exists {output}")

    tasks = [
        t for t in finding_audit_tasks("C66-001") if t.get("finding_id") == FINDING_ID
    ]
    if not tasks:
        raise SystemExit(f"{FINDING_ID} not in ready finding_audit_tasks")
    task = dict(tasks[0])
    task["selected_engine"] = "claude"
    task["output"] = output_rel

    ORIG_CWD.mkdir(parents=True, exist_ok=True)
    for child in list(ORIG_CWD.iterdir()):
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)

    files = build_isolated_context(task, ORIG_CWD)

    workspace_copy = vault / "workspace-copy"
    if workspace_copy.exists():
        shutil.rmtree(workspace_copy)
    shutil.copytree(
        ORIG_CWD,
        workspace_copy,
        ignore=shutil.ignore_patterns("repo", "grok-workers", ".cursor"),
        dirs_exist_ok=True,
    )

    engines_root = load_engines_config()
    max_workers = max_grok_workers_from_config(engines_root)
    max_worker_turns = max_worker_turns_from_config(engines_root)
    worker_backend = resolve_worker_backend(engines_root)
    worker_model = resolve_worker_model(engines_root, backend=worker_backend)
    workers = prepare_worker_session(
        ORIG_CWD,
        family="claude",
        max_workers=max_workers,
        allow_web=phase_allows_web("finding-audit"),
        worker_model=str(worker_model),
        worker_timeout=3600,
        worker_backend=worker_backend,
        max_worker_turns=max_worker_turns,
        parent_meta={
            "engine": "claude",
            "family": "claude",
            "phase": "finding-audit",
            "task_id": TASK_ID,
            "output": str(output),
            "campaign_id": "C66-001",
            "worker_mode": "mcp",
            "worker_backend": worker_backend,
            "resume_of": FAILED_SLOT,
            "resume_session": SESSION_ID,
        },
        attach_mcp=True,
    )

    resume_prompt = vault / "RESUME_PROMPT.txt"
    resume_prompt.write_text(
        f"""PRINCIPAL OVERRIDE — CONTINUE AND FINISH YOUR INTERRUPTED FINDING AUDIT.

Context:
- Your previous Claude turn for {TASK_ID} / {FINDING_ID} was interrupted by a Claude session limit. No audit artifact was written to the original slot.
- The spent/failed slot {FAILED_SLOT} is closed. Do NOT reopen or overwrite it.
- FAUD-0147 is a paused Codex attempt on the same finding; leave it alone. Do NOT write FAUD-0147.
- Finish into the NEW append-only slot: {artifact_id}.
- Same Claude session is resumed; do not restart the finding audit from zero.
- Your prior Grok worker W-acf94cc193e4 (SESS-b29f88768188) is dead with the old temp workspace. Do NOT await or continue that worker. If you still need one narrow lookup, dispatch a fresh worker; otherwise finish from what you already loaded.

Token discipline (mandatory):
1. Prefer finishing from what you already loaded in this session.
2. At most a small number of Read/WebFetch calls if a load-bearing locator is still missing.
3. Do NOT re-read the entire packet. Do NOT burn a long exploratory monologue.
4. Grok workers are optional; prefer not to dispatch unless a single concrete lookup remains.
5. Emit the final JSON in this turn.

Hard contract:
- Final message: exactly one JSON object matching research/finding-audits/FINDING_AUDIT_TEMPLATE.json
- No Markdown fences, no prose before or after the JSON
- id must be exactly: {artifact_id}
- adjudicator/auditor engine field must be exactly: claude (match the template field name)
- finding_id must be exactly: {FINDING_ID}
- Keep the artifact schema-faithful and compact

Final message: exactly one JSON object.

Supplied files in this workspace:
- TASK.json (output retargeted to {artifact_id})
- prompts/FINDING_AUDIT.md
- proof/packets/generated/C66-001-v4.md (or pinned snapshot)
- proof/findings.jsonl
- data/claims.jsonl
- data/sources.jsonl
- research/finding-audits/FINDING_AUDIT_TEMPLATE.json
""",
        encoding="utf-8",
    )

    base_argv = [
        "claude",
        "-p",
        resume_prompt.read_text(encoding="utf-8"),
        "--resume",
        SESSION_ID,
        "--model",
        "claude-opus-5",
        "--effort",
        "high",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools",
        "Read",
        "Grep",
        "Glob",
        "WebSearch",
        "WebFetch",
        "--disallowedTools",
        "Edit",
        "Write",
        "Bash",
    ]
    argv = apply_workers_to_argv(base_argv, "claude", workers)

    run_resume = vault / "run_resume.py"
    run_resume.write_text(
        f'''#!/usr/bin/env python3
"""Resume interrupted Claude {FINDING_ID} audit into {artifact_id}."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path({str(ROOT)!r})
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream
from pure_tate.campaign_driver import _apply_finding_audit
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.run_lifecycle import release_artifact_reservation, spend_artifact_reservation
from pure_tate.store import atomic_write_json

META_PATH = Path("/tmp/pure-tate-faud0146-resume-meta.json")

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
    argv = meta["argv"]
    env_updates = meta.get("env_updates") or {{}}
    task_id = meta["task_id"]
    finding_id = meta["finding_id"]

    if (ROOT / "research/finding-audits/{FAILED_SLOT}.json").exists():
        raise SystemExit("refusing: spent slot {FAILED_SLOT} unexpectedly exists")
    if output.exists():
        raise SystemExit("refusing to overwrite existing %s" % output)
    if artifact_id in ("{FAILED_SLOT}", "FAUD-0147"):
        raise SystemExit("refusing forbidden slot %s" % artifact_id)

    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    notify(
        "Pure Tate • Claude {FINDING_ID} resume starting",
        "C66-001 • Claude --resume %s\\n%s -> %s ({FAILED_SLOT} closed)"
        % (session_id, task_id, artifact_id),
    )
    env = dict(os.environ)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
    env.update({{str(k): str(v) for k, v in env_updates.items()}})
    with stdout_path.open("w") as out_h, stderr_path.open("w") as err_h:
        proc = subprocess.run(argv, cwd=str(cwd), env=env, stdout=out_h, stderr=err_h, check=False)
    with stderr_path.open("a") as err_h:
        err_h.write("EXIT:%d\\n" % proc.returncode)
        err_h.write("OUT_BYTES:%d\\n" % stdout_path.stat().st_size)
    raw = stdout_path.read_text(errors="replace")
    if proc.returncode != 0 or not raw.strip():
        spend_artifact_reservation(reservation, reason="resume_agent_failure", task_id=task_id)
        notify("Pure Tate • Claude {FINDING_ID} resume failed", "exit=%s artifact=%s" % (proc.returncode, artifact_id))
        return proc.returncode or 1
    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:
        spend_artifact_reservation(reservation, reason="resume_extract_failure", task_id=task_id)
        notify("Pure Tate • Claude {FINDING_ID} resume extract failed", str(exc))
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
        "Pure Tate • Claude {FINDING_ID} resume done",
        "C66-001 • %s %s verdict=%s applied=%s" % (artifact_id, finding_id, artifact.get("verdict"), applied),
    )
    result = {{
        "artifact_id": artifact_id,
        "finding_id": finding_id,
        "verdict": artifact.get("verdict"),
        "applied": applied,
        "output": str(output),
        "returncode": proc.returncode,
    }}
    Path("/tmp/pure-tate-faud0146-resume-result.json").write_text(json.dumps(result, indent=2) + "\\n")
    print(json.dumps(result, indent=2), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )
    os.chmod(run_resume, 0o755)

    meta = {
        "artifact_id": artifact_id,
        "failed_slot": FAILED_SLOT,
        "task_id": TASK_ID,
        "finding_id": FINDING_ID,
        "session_id": SESSION_ID,
        "cwd": str(ORIG_CWD),
        "vault": str(vault),
        "output": str(output),
        "reservation": str(res_path),
        "resume_prompt": str(resume_prompt),
        "run_resume": str(run_resume),
        "argv": argv,
        "env_updates": dict(workers.env_updates) if workers else {},
        "worker_session_id": workers.session_id if workers else None,
        "mcp_config_path": (
            str(workers.mcp_config_path)
            if workers and workers.mcp_config_path
            else None
        ),
        "files": files,
        "stamp": stamp,
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n")
    atomic_write_json(
        vault / "LAUNCH.json",
        {
            **meta,
            "note": (
                "Safe Claude --resume of FND-0142 after session limit; "
                "FAUD-0146 closed; FAUD-0147 left alone"
            ),
            "status": "prepared",
        },
    )
    atomic_write_json(
        vault / "WORKSPACE.json",
        {
            "artifact_id": artifact_id,
            "cwd": str(ORIG_CWD),
            "failed_slot": FAILED_SLOT,
            "new_slot": artifact_id,
            "session_id": SESSION_ID,
            "session_archive": str(session_archive),
            "claude_project_copy": str(claude_copy),
            "workspace_copy": str(workspace_copy),
            "protect_from_overwrite": [
                f"reports/runs/reservations/{FAILED_SLOT}.json",
                "reports/runs/reservations/FAUD-0147.json",
            ],
        },
    )
    shutil.copy2(ORIG_CWD / "TASK.json", vault / "TASK.json")
    print(
        json.dumps(
            {
                "vault": str(vault),
                "artifact_id": artifact_id,
                "reservation": str(res_path),
                "cwd": str(ORIG_CWD),
                "worker_session_id": meta["worker_session_id"],
                "mcp": meta["mcp_config_path"],
                "files": files,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
