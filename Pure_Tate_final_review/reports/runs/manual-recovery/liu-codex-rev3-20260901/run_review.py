#!/usr/bin/env python3
"""Run Codex adversarial review of Liu M_{5,8} Revision 3."""
from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import _subprocess_env, load_engines
from pure_tate.notifications import (
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.process_runner import run_captured_process
from pure_tate.store import atomic_write_json, atomic_write_text

VAULT = Path(__file__).resolve().parent
STAMP = "20260901T084500Z"
ENGINE = "codex"
TASK_ID = "LIU-REPAIRED-CODEX"
MODEL = "gpt-5.6-sol"
EFFORT = "high"
TIMEOUT = 10800
INACTIVITY = 3600
LIU_SHA = "ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a"

CONTEXT_FILES = [
    "tmp/liu-repaired/PROOF.md",
    "tmp/liu-repaired/claims.json",
    "tmp/liu-repaired/CODEX-P2-PROMPT.md",
    "tmp/liu-audit/SOURCE-HASHES.json",
    "tmp/liu-audit/liu-2509.02950v1.pdf",
    "tmp/liu-audit/liu-2509.02950v1.txt",
    "tmp/liu-audit/canning-larson-2208.02357.pdf",
    "tmp/liu-audit/canning-larson-2208.02357.txt",
    "tmp/liu-audit/clp-2307.08830.pdf",
    "tmp/liu-audit/clp-2307.08830.txt",
    "tmp/liu-audit/ionel-math9908060.pdf",
    "tmp/liu-audit/ionel-math9908060.txt",
    "paper/degree16_genus_le7.tex",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hashlib_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_workspace() -> Path:
    workspace = VAULT / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    for relative in CONTEXT_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError("missing packet file %s" % source)
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    digest = hashlib_file(workspace / "tmp/liu-audit/liu-2509.02950v1.pdf")
    if digest != LIU_SHA:
        raise RuntimeError("Liu PDF hash drifted: %s" % digest)
    return workspace


def notify(title: str, message: str) -> dict:
    return {
        "desktop": send_desktop_notification(title, message),
        "ntfy": send_ntfy_notification_detailed(title, message),
    }


def extract_codex_text(last_message: Path, stream: str) -> str:
    if last_message.is_file():
        text = last_message.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            return text
    chunks = []
    for line in stream.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"agent_message", "message"}:
            item = event.get("item") or event
            content = item.get("text") or item.get("content") or event.get("text")
            if isinstance(content, str) and content.strip():
                chunks.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        chunks.append(block["text"])
                    elif isinstance(block, str):
                        chunks.append(block)
    if chunks:
        return "\n".join(chunks).strip()
    raise RuntimeError("Codex produced no text result")


def main() -> int:
    console = VAULT / "CODEX-P2.codex.console.log"
    stream_log = VAULT / "CODEX-P2.stream.jsonl"
    report_path = VAULT / "CODEX-P2-REPORT.md"
    last_message = VAULT / "CODEX-P2.last.md"
    launch_path = VAULT / "LAUNCH.json"
    (VAULT / "CODEX-P2.pid").write_text(str(os.getpid()) + "\n", encoding="utf-8")

    launch = {
        "note": "Codex adversarial review of Liu M_{5,8} Revision 3 (PROOF.md)",
        "stamp": STAMP,
        "run_id": "liu-codex-rev3-20260901",
        "engine": ENGINE,
        "model": MODEL,
        "effort": EFFORT,
        "task_id": TASK_ID,
        "review_pass": "rev3-adversarial",
        "target": "tmp/liu-repaired/PROOF.md",
        "liu_sha256": LIU_SHA,
        "status": "running",
        "started_at": utc_now(),
    }
    atomic_write_json(launch_path, launch)
    console.write_text(
        "START %s LIU-REPAIRED-REV3 %s %s\n" % (utc_now(), TASK_ID, ENGINE),
        encoding="utf-8",
    )
    notify("Pure Tate Liu Rev3", "Codex adversarial review of Revision 3 started")

    try:
        workspace = build_workspace()
        prompt = (ROOT / "tmp/liu-repaired/CODEX-P2-PROMPT.md").read_text(
            encoding="utf-8"
        )
        config = load_engines()[ENGINE]
        binary = shutil.which(str(config.get("binary") or "codex")) or "codex"
        command = [
            binary,
            "exec",
            "--skip-git-repo-check",
            "-m",
            MODEL,
            "--sandbox",
            "read-only",
            "-c",
            'approval_policy="never"',
            "-c",
            'model_reasoning_effort="%s"' % EFFORT,
            "--json",
            "-o",
            str(last_message),
            prompt,
        ]
        env = _subprocess_env("openai", config)

        def on_start(meta):
            extra = VAULT / "CODEX-P2.engine.pid"
            extra.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        completed = run_captured_process(
            command,
            cwd=workspace,
            env=env,
            timeout=TIMEOUT,
            inactivity_timeout=INACTIVITY,
            on_process_start=on_start,
            abort_stderr_pattern_counts=config.get("abort_stderr_pattern_counts"),
            activity_streams=["stdout"],
        )
        stream_log.write_text(completed.stdout, encoding="utf-8")
        if completed.stderr:
            (VAULT / "CODEX-P2.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(
                "codex exited %s: %s"
                % (completed.returncode, (completed.stderr or completed.stdout)[-2000:])
            )
        report = extract_codex_text(last_message, completed.stdout)
        atomic_write_text(report_path, report if report.endswith("\n") else report + "\n")
        launch.update(
            {
                "status": "completed",
                "completed_at": utc_now(),
                "output": str(report_path.relative_to(ROOT)),
                "returncode": completed.returncode,
            }
        )
        atomic_write_json(launch_path, launch)
        with console.open("a", encoding="utf-8") as handle:
            handle.write("EXIT:%s %s\n" % (completed.returncode, utc_now()))
            handle.write("report %s\n" % report_path)
            handle.write("DONE\n")
        notify("Pure Tate Liu Rev3", "Codex adversarial review of Revision 3 completed")
        worktree = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate-liu-claude-repairs")
        if worktree.is_dir():
            dest = worktree / "reports/runs/manual-recovery/liu-codex-rev3-20260901"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_path, dest / "CODEX-P2-REPORT.md")
            shutil.copy2(launch_path, dest / "LAUNCH.json")
        return 0
    except Exception as exc:
        launch.update(
            {
                "status": "failed",
                "completed_at": utc_now(),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        atomic_write_json(launch_path, launch)
        with console.open("a", encoding="utf-8") as handle:
            handle.write("ERROR %s %s\n" % (utc_now(), exc))
            handle.write(traceback.format_exc())
            handle.write("FAILED\n")
        notify("Pure Tate Liu Rev3 failed", str(exc)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
