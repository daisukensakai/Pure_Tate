#!/usr/bin/env python3
"""Run Claude Opus independent P1 review of Liu arXiv:2509.02950v1."""
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
from pure_tate.process_runner import ProcessWatchdogError, run_captured_process
from pure_tate.store import atomic_write_json, atomic_write_text

VAULT = Path(__file__).resolve().parent
STAMP = "20260901T054000Z"
ENGINE = "claude"
TASK_ID = "LIU-AUDIT-P1"
MODEL = "claude-opus-5"
EFFORT = "high"
TIMEOUT = 10800
INACTIVITY = 3600
LIU_SHA = "ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_claude_text(stream: str) -> str:
    results = []
    assistant = []
    error_detail = None
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
        event_type = event.get("type")
        if event_type == "result":
            result = event.get("result")
            if isinstance(result, str) and result.strip():
                results.append(result)
            subtype = str(event.get("subtype", "")).lower()
            if event.get("is_error") is True or subtype in {"error", "failed"}:
                error_detail = str(event.get("error") or result or "Claude stream failed")
        elif event_type == "assistant":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and isinstance(block.get("text"), str)
                    ):
                        assistant.append(block["text"])
    if results:
        return results[-1]
    if assistant:
        return "".join(assistant)
    if error_detail:
        raise RuntimeError(error_detail)
    raise RuntimeError("Claude produced no text result")


def build_workspace() -> Path:
    workspace = VAULT / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    packet = workspace / "tmp" / "liu-audit"
    paper = workspace / "paper"
    packet.mkdir(parents=True)
    paper.mkdir(parents=True)
    names = [
        "CLAUDE-P1-PROMPT.md",
        "SOURCE-HASHES.json",
        "liu-2509.02950v1.pdf",
        "liu-2509.02950v1.txt",
        "canning-larson-2208.02357.pdf",
        "canning-larson-2208.02357.txt",
        "clp-2307.08830.pdf",
        "clp-2307.08830.txt",
        "ionel-math9908060.pdf",
        "ionel-math9908060.txt",
    ]
    src = ROOT / "tmp" / "liu-audit"
    for name in names:
        source = src / name
        if not source.is_file():
            raise FileNotFoundError("missing source packet file %s" % source)
        shutil.copy2(source, packet / name)
    shutil.copy2(
        ROOT / "paper" / "degree16_genus_le7.tex",
        paper / "degree16_genus_le7.tex",
    )
    digest = hashlib_file(packet / "liu-2509.02950v1.pdf")
    if digest != LIU_SHA:
        raise RuntimeError("Liu PDF hash drifted: %s" % digest)
    return workspace


def hashlib_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def notify(title: str, message: str) -> dict:
    return {
        "desktop": send_desktop_notification(title, message),
        "ntfy": send_ntfy_notification_detailed(title, message),
    }


def main() -> int:
    console = VAULT / "CLAUDE-P1.claude.console.log"
    stream_log = VAULT / "CLAUDE-P1.stream.jsonl"
    report_path = VAULT / "CLAUDE-P1-REPORT.md"
    launch_path = VAULT / "LAUNCH.json"
    pid_path = VAULT / "CLAUDE-P1.pid"
    pid_path.write_text(str(os.getpid()) + "\n", encoding="utf-8")

    launch = {
        "note": "Claude P1 independent adversarial review of Liu arXiv:2509.02950v1",
        "stamp": STAMP,
        "run_id": "liu-claude-p1-20260901",
        "engine": ENGINE,
        "model": MODEL,
        "effort": EFFORT,
        "task_id": TASK_ID,
        "review_pass": 1,
        "liu_sha256": LIU_SHA,
        "status": "running",
        "started_at": utc_now(),
    }
    atomic_write_json(launch_path, launch)
    console.write_text(
        "START %s LIU-AUDIT %s %s\n" % (utc_now(), TASK_ID, ENGINE),
        encoding="utf-8",
    )
    notify("Pure Tate Liu P1", "Claude Opus P1 review of Liu 2509.02950v1 started")

    try:
        workspace = build_workspace()
        prompt = (ROOT / "tmp" / "liu-audit" / "CLAUDE-P1-PROMPT.md").read_text(
            encoding="utf-8"
        )
        config = load_engines()[ENGINE]
        binary = shutil.which(str(config.get("binary") or "claude")) or "/Users/ken/.local/bin/claude"
        command = [
            binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--permission-mode",
            "default",
            "--allowedTools",
            "Read",
            "Grep",
            "Glob",
            "--disallowedTools",
            "Edit",
            "Write",
            "Bash",
            "--model",
            MODEL,
            "--effort",
            EFFORT,
        ]
        env = _subprocess_env("claude", config)
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"

        def on_start(meta):
            extra = VAULT / "CLAUDE-P1.engine.pid"
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
            (VAULT / "CLAUDE-P1.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(
                "claude exited %s: %s"
                % (completed.returncode, completed.stderr[-2000:])
            )
        report = extract_claude_text(completed.stdout)
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
        notify("Pure Tate Liu P1", "Claude Opus P1 review completed")
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
        notify("Pure Tate Liu P1 failed", str(exc)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
