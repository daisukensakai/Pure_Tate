#!/usr/bin/env python3
"""Run the authorized read-only Claude P2 review of LATT-0005."""
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
from pure_tate.process_runner import run_captured_process
from pure_tate.store import atomic_write_json, atomic_write_text

RUN_DIR = Path(__file__).resolve().parent
PROMPT = ROOT / "formal/dispatch/LREV-0009-claude-p2-latt0005.md"
MODEL = "claude-opus-5"
EFFORT = "high"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_claude_text(stream: str) -> str:
    results: list[str] = []
    assistant: list[str] = []
    error_detail: str | None = None
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result":
            result = event.get("result")
            if isinstance(result, str) and result.strip():
                results.append(result)
            if event.get("is_error") is True:
                error_detail = str(event.get("error") or result or "Claude failed")
        elif event.get("type") == "assistant":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        value = block.get("text")
                        if isinstance(value, str):
                            assistant.append(value)
    if results:
        return results[-1]
    if assistant:
        return "".join(assistant)
    raise RuntimeError(error_detail or "Claude produced no text result")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    launch_path = RUN_DIR / "LAUNCH.json"
    stream_path = RUN_DIR / "LREV-0009.stream.jsonl"
    report_path = RUN_DIR / "LREV-0009.raw.json"
    console_path = RUN_DIR / "LREV-0009.claude.console.log"
    atomic_write_json(
        launch_path,
        {
            "run_id": "RUN-LG7D16-002-LATT-0005-CLAUDE-P2",
            "status": "running",
            "engine": "claude",
            "model": MODEL,
            "effort": EFFORT,
            "review_id": "LREV-0009",
            "attempt_id": "LATT-0005",
            "started_at": utc_now(),
        },
    )
    console_path.write_text(f"START {utc_now()} LREV-0009\n", encoding="utf-8")
    try:
        config = load_engines()["claude"]
        binary = shutil.which(str(config.get("binary") or "claude")) or "/Users/ken/.local/bin/claude"
        command = [
            binary,
            "-p",
            PROMPT.read_text(encoding="utf-8"),
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
            "Bash(shasum:*)",
            "Bash(diff:*)",
            "--disallowedTools",
            "Edit",
            "Write",
            "--model",
            MODEL,
            "--effort",
            EFFORT,
        ]
        env = _subprocess_env("claude", config)
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"

        def on_start(meta: dict) -> None:
            atomic_write_json(RUN_DIR / "LREV-0009.engine.json", meta)

        completed = run_captured_process(
            command,
            cwd=ROOT,
            env=env,
            timeout=10800,
            inactivity_timeout=3600,
            on_process_start=on_start,
            abort_stderr_pattern_counts=config.get("abort_stderr_pattern_counts"),
            activity_streams=["stdout"],
        )
        atomic_write_text(stream_path, completed.stdout)
        if completed.stderr:
            atomic_write_text(RUN_DIR / "LREV-0009.stderr.log", completed.stderr)
        if completed.returncode != 0:
            raise RuntimeError(f"Claude exited {completed.returncode}: {(completed.stderr or completed.stdout)[-2000:]}")
        report = extract_claude_text(completed.stdout)
        atomic_write_text(report_path, report if report.endswith("\n") else report + "\n")
        atomic_write_json(
            launch_path,
            {
                "run_id": "RUN-LG7D16-002-LATT-0005-CLAUDE-P2",
                "status": "completed",
                "engine": "claude",
                "model": MODEL,
                "effort": EFFORT,
                "review_id": "LREV-0009",
                "attempt_id": "LATT-0005",
                "completed_at": utc_now(),
                "returncode": completed.returncode,
                "raw_output": str(report_path.relative_to(ROOT)),
            },
        )
        with console_path.open("a", encoding="utf-8") as handle:
            handle.write(f"EXIT:0 {utc_now()}\nDONE\n")
        return 0
    except Exception as exc:
        atomic_write_json(
            launch_path,
            {
                "run_id": "RUN-LG7D16-002-LATT-0005-CLAUDE-P2",
                "status": "failed",
                "engine": "claude",
                "model": MODEL,
                "effort": EFFORT,
                "review_id": "LREV-0009",
                "attempt_id": "LATT-0005",
                "completed_at": utc_now(),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        with console_path.open("a", encoding="utf-8") as handle:
            handle.write(f"ERROR {utc_now()} {exc}\nFAILED\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
