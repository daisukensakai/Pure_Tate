#!/usr/bin/env python3
"""Resume interrupted Claude finding-audit session into a new FAUD slot."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import _extract_claude_stream  # noqa: E402
from pure_tate.notifications import (  # noqa: E402
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.run_lifecycle import (  # noqa: E402
    release_artifact_reservation,
    spend_artifact_reservation,
)
from pure_tate.store import atomic_write_json  # noqa: E402


META_PATH = Path("/tmp/pure-tate-claude-resume-meta.json")


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
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    vault = Path(meta["vault"])
    cwd = Path(meta["cwd"])
    session_id = meta["session_id"]
    artifact_id = meta["artifact_id"]
    output = Path(meta["output"])
    reservation = Path(meta["reservation"])
    resume_prompt = Path(meta["resume_prompt"]).read_text(encoding="utf-8")

    # Safety: never overwrite sibling or failed slots.
    protected = [
        ROOT / "research/finding-audits/FAUD-0118.json",
        ROOT / "research/finding-audits/FAUD-0116.json",
    ]
    for path in protected:
        if path.name == "FAUD-0118.json":
            if not path.exists():
                raise SystemExit("protected sibling FAUD-0118 missing unexpectedly")
        if path.name == "FAUD-0116.json" and path.exists():
            raise SystemExit("refusing to proceed: failed slot FAUD-0116 unexpectedly exists")
    if output.exists():
        raise SystemExit("refusing to overwrite existing %s" % output)

    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    notify(
        "Pure Tate • Claude resume starting",
        "C66-001 • Claude --resume %s\nTASK-F-FND-0116 -> %s (FAUD-0118 protected)"
        % (session_id, artifact_id),
    )

    env = dict(os.environ)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
    argv = [
        "claude",
        "-p",
        resume_prompt,
        "--resume",
        session_id,
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
    with stdout_path.open("w", encoding="utf-8") as out_h, stderr_path.open(
        "w", encoding="utf-8"
    ) as err_h:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            stdout=out_h,
            stderr=err_h,
            check=False,
        )
    with stderr_path.open("a", encoding="utf-8") as err_h:
        err_h.write("EXIT:%d\n" % proc.returncode)
        err_h.write("OUT_BYTES:%d\n" % stdout_path.stat().st_size)

    raw = stdout_path.read_text(encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not raw.strip():
        spend_artifact_reservation(
            reservation, reason="resume_agent_failure", task_id="TASK-F-FND-0116"
        )
        notify(
            "Pure Tate • Claude resume failed",
            "C66-001 • %s exit=%s bytes=%s"
            % (artifact_id, proc.returncode, stdout_path.stat().st_size),
        )
        return proc.returncode or 1

    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:  # noqa: BLE001
        spend_artifact_reservation(
            reservation, reason="resume_extract_failure", task_id="TASK-F-FND-0116"
        )
        notify(
            "Pure Tate • Claude resume extract failed",
            "C66-001 • %s extract error: %s" % (artifact_id, exc),
        )
        return 2

    # Force identity onto the reserved new slot.
    if isinstance(artifact, dict):
        artifact["id"] = artifact_id
        if "engine" in artifact:
            artifact["engine"] = "claude"
        if "adjudicator_engine" in artifact:
            artifact["adjudicator_engine"] = "claude"
        if "auditor_engine" in artifact:
            artifact["auditor_engine"] = "claude"
        if "finding_id" in artifact:
            artifact["finding_id"] = "FND-0116"

    # Final overwrite guards
    if (ROOT / "research/finding-audits/FAUD-0118.json").exists():
        pass
    else:
        raise SystemExit("FAUD-0118 vanished during resume; abort write")
    if output.exists():
        raise SystemExit("output appeared concurrently; abort")

    atomic_write_json(output, artifact)
    # Drop active reservation only after durable write owns the id.
    release_artifact_reservation(reservation)
    notify(
        "Pure Tate • Claude resume done",
        "C66-001 • %s verdict=%s (FAUD-0118 untouched)"
        % (artifact_id, artifact.get("verdict") if isinstance(artifact, dict) else "?"),
    )
    print(
        json.dumps(
            {
                "artifact_id": artifact_id,
                "output": str(output),
                "verdict": artifact.get("verdict") if isinstance(artifact, dict) else None,
                "returncode": proc.returncode,
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
