#!/usr/bin/env python3
"""Focused, bounded Gemini 503 probe; never touches the Pure Tate harness."""

from __future__ import annotations

import datetime as dt
import json
import os
import queue
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import IO, Any

from run_gemini_diagnostics import probe_api


LAB = Path(__file__).resolve().parent
RUN_ID = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
RUN_DIR = LAB / "results" / "gemini_503" / RUN_ID
MODELS = ("gemini-3.5-flash", "gemini-3-flash-preview")
CLI_TIMEOUT_SECONDS = 55
MAX_503_ATTEMPTS = 3


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def reader(name: str, pipe: IO[bytes], events: queue.Queue[dict[str, Any]]) -> None:
    while True:
        chunk = pipe.readline()
        if not chunk:
            break
        events.put(
            {
                "at": utc_now(),
                "stream": name,
                "text": chunk.decode("utf-8", "replace"),
            }
        )
    events.put({"at": utc_now(), "stream": name, "eof": True})


def cli_probe(model: str) -> dict[str, Any]:
    argv = [
        "gemini",
        "-m",
        model,
        "-p",
        "Reply with exactly: CLI_WORKING",
        "-o",
        "stream-json",
        "--approval-mode",
        "plan",
        "--skip-trust",
    ]
    model_dir = RUN_DIR / model
    model_dir.mkdir(parents=True, exist_ok=True)
    event_path = model_dir / "events.jsonl"
    stdout_path = model_dir / "stdout.txt"
    stderr_path = model_dir / "stderr.txt"
    started_at = utc_now()
    started = time.monotonic()
    proc = subprocess.Popen(
        argv,
        cwd=LAB,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert proc.stdout is not None and proc.stderr is not None
    pending: queue.Queue[dict[str, Any]] = queue.Queue()
    threads = [
        threading.Thread(target=reader, args=("stdout", proc.stdout, pending)),
        threading.Thread(target=reader, args=("stderr", proc.stderr, pending)),
    ]
    for thread in threads:
        thread.start()

    records: list[dict[str, Any]] = []
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    eof = set()
    timed_out = False
    abort_reason = None
    retry_503_attempts = 0
    while len(eof) < 2:
        remaining = CLI_TIMEOUT_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            timed_out = True
            break
        try:
            record = pending.get(timeout=min(0.5, remaining))
        except queue.Empty:
            if proc.poll() is not None and not any(t.is_alive() for t in threads):
                break
            continue
        records.append(record)
        if record.get("eof"):
            eof.add(record["stream"])
        elif record["stream"] == "stdout":
            stdout_chunks.append(record["text"])
        else:
            stderr_chunks.append(record["text"])

        text = record.get("text", "")
        if (
            record.get("stream") == "stderr"
            and text.startswith("Attempt ")
            and "status 503" in text
        ):
            retry_503_attempts += 1
            if retry_503_attempts >= MAX_503_ATTEMPTS:
                abort_reason = "503_retry_threshold"
                break

    if timed_out or abort_reason:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
    else:
        proc.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=2)
    while True:
        try:
            record = pending.get_nowait()
        except queue.Empty:
            break
        records.append(record)
        if not record.get("eof"):
            (stdout_chunks if record["stream"] == "stdout" else stderr_chunks).append(
                record["text"]
            )

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    with event_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    blob = (stdout + "\n" + stderr).lower()
    result_events = []
    assistant_messages = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            result_events.append(event)
        if (
            isinstance(event, dict)
            and event.get("type") == "message"
            and event.get("role") == "assistant"
        ):
            assistant_messages.append(str(event.get("content", "")))
    terminal_success = any(
        event.get("status") == "success" for event in result_events
    )
    expected_answer = any(
        message.strip() == "CLI_WORKING" for message in assistant_messages
    )
    return {
        "model": model,
        "argv": [x if x != "Reply with exactly: CLI_WORKING" else "<PROMPT>" for x in argv],
        "started_at": started_at,
        "finished_at": utc_now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "abort_reason": abort_reason,
        "retry_503_attempts": retry_503_attempts,
        "stdout_bytes": len(stdout.encode()),
        "stderr_bytes": len(stderr.encode()),
        "saw_503": "503" in blob,
        "saw_unavailable": "unavailable" in blob or "high demand" in blob,
        "success": (
            (not timed_out)
            and abort_reason is None
            and proc.returncode == 0
            and terminal_success
            and expected_answer
        ),
        "assistant_messages": assistant_messages,
        "result_events": result_events,
        "events": str(event_path.relative_to(LAB)),
        "stdout": str(stdout_path.relative_to(LAB)),
        "stderr": str(stderr_path.relative_to(LAB)),
    }


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "executed_at": utc_now(),
        "gemini_cli_version": subprocess.run(
            ["gemini", "--version"], capture_output=True, text=True, timeout=10
        ).stdout.strip(),
        "api_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "api": [],
        "cli": [],
    }
    for model in MODELS:
        result = probe_api(model)
        manifest["api"].append(result)
        print("API", json.dumps(result), flush=True)
    for model in MODELS:
        result = cli_probe(model)
        manifest["cli"].append(result)
        print("CLI", json.dumps(result), flush=True)
    manifest_path = RUN_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    latest_path = RUN_DIR.parent / "latest.txt"
    latest_path.write_text(RUN_ID + "\n")
    print("MANIFEST", manifest_path.relative_to(LAB), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
