#!/usr/bin/env python3
"""Run Qwen independent P1 review of the repaired Liu M_{5,8} argument."""
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

from pure_tate.agents import _qwen_stream_events, load_engines
from pure_tate.notifications import (
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.process_runner import run_captured_process
from pure_tate.store import atomic_write_json, atomic_write_text

VAULT = Path(__file__).resolve().parent
STAMP = "20260901T064000Z"
ENGINE = "qwen"
TASK_ID = "LIU-REPAIRED-P1"
MODEL = "qwen3.8-max"
EFFORT = "xhigh"
TIMEOUT = 10800
INACTIVITY = 3600
LIU_SHA = "ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a"

CONTEXT_FILES = [
    "tmp/liu-repaired/PROOF.md",
    "tmp/liu-repaired/claims.json",
    "tmp/liu-repaired/QWEN-P1-PROMPT.md",
    "tmp/liu-audit/SOURCE-HASHES.json",
    "tmp/liu-audit/liu-2509.02950v1.txt",
    "tmp/liu-audit/canning-larson-2208.02357.txt",
    "tmp/liu-audit/clp-2307.08830.txt",
    "tmp/liu-audit/ionel-math9908060.txt",
    "paper/degree16_genus_le7.tex",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_qwen_text(stream: str) -> str:
    events = _qwen_stream_events(stream)
    errors = [
        str(event.get("message") or event.get("error") or "Qwen stream failed")
        for event in events
        if event.get("type") == "error"
    ]
    chunks = [
        str(event.get("data"))
        for event in events
        if event.get("type") == "text" and isinstance(event.get("data"), str)
    ]
    text = "".join(chunks).strip()
    if text:
        return text
    if errors:
        raise RuntimeError(errors[-1])
    raise RuntimeError("Qwen produced no text result")


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
    pdf = ROOT / "tmp/liu-audit/liu-2509.02950v1.pdf"
    if pdf.is_file():
        digest = hashlib_file(pdf)
        if digest != LIU_SHA:
            raise RuntimeError("Liu PDF hash drifted: %s" % digest)
    return workspace


def notify(title: str, message: str) -> dict:
    return {
        "desktop": send_desktop_notification(title, message),
        "ntfy": send_ntfy_notification_detailed(title, message),
    }


def main() -> int:
    console = VAULT / "QWEN-P1.qwen.console.log"
    stream_log = VAULT / "QWEN-P1.stream.jsonl"
    report_path = VAULT / "QWEN-P1-REPORT.md"
    launch_path = VAULT / "LAUNCH.json"
    (VAULT / "QWEN-P1.pid").write_text(str(os.getpid()) + "\n", encoding="utf-8")

    launch = {
        "note": "Qwen P1 independent adversarial review of repaired Liu M_{5,8} argument",
        "stamp": STAMP,
        "run_id": "liu-qwen-p1-20260901",
        "engine": ENGINE,
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "task_id": TASK_ID,
        "review_pass": 1,
        "target": "tmp/liu-repaired/PROOF.md",
        "liu_sha256": LIU_SHA,
        "status": "running",
        "started_at": utc_now(),
    }
    atomic_write_json(launch_path, launch)
    console.write_text(
        "START %s LIU-REPAIRED %s %s\n" % (utc_now(), TASK_ID, ENGINE),
        encoding="utf-8",
    )
    notify("Pure Tate Liu Qwen P1", "Qwen P1 review of repaired Liu argument started")

    try:
        workspace = build_workspace()
        rubric = (ROOT / "tmp/liu-repaired/QWEN-P1-PROMPT.md").read_text(encoding="utf-8")
        proof = (ROOT / "tmp/liu-repaired/PROOF.md").read_text(encoding="utf-8")
        claims = (ROOT / "tmp/liu-repaired/claims.json").read_text(encoding="utf-8")
        prompt = (
            rubric
            + "\n\nThe worker can read only the listed text extracts via read_file "
            "(PDFs are not readable as UTF-8 in this adapter). Prioritize Liu §§2–3, "
            "Canning–Larson Lemmas 3.5, 3.6, 9.9, CLP Lemma 4.3, and Ionel Theorem 0.1.\n\n"
            "# PROOF.md (included so a tool round is not spent on it)\n\n"
            + proof
            + "\n\n# claims.json\n\n"
            + claims
        )
        config = load_engines()[ENGINE]
        command = [
            sys.executable,
            str((ROOT / "pure_tate" / "qwen_worker.py").resolve()),
            "--model",
            MODEL,
            "--prompt",
            prompt,
            "--max-tokens",
            "65536",
            "--thinking-budget",
            "65536",
            "--reasoning-effort",
            EFFORT,
        ]
        for relative in CONTEXT_FILES:
            command.extend(["--context-file", relative])

        def on_start(meta):
            (VAULT / "QWEN-P1.engine.pid").write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8"
            )

        completed = run_captured_process(
            command,
            cwd=workspace,
            env=dict(os.environ),
            timeout=TIMEOUT,
            inactivity_timeout=INACTIVITY,
            on_process_start=on_start,
            activity_streams=["stdout"],
        )
        stream_log.write_text(completed.stdout, encoding="utf-8")
        if completed.stderr:
            (VAULT / "QWEN-P1.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(
                "qwen exited %s: %s"
                % (completed.returncode, (completed.stderr or completed.stdout)[-2000:])
            )
        report = extract_qwen_text(completed.stdout)
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
        notify("Pure Tate Liu Qwen P1", "Qwen P1 review of repaired Liu argument completed")
        # Mirror report into the reserved worktree if present.
        worktree = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate-liu-claude-repairs")
        if worktree.is_dir():
            dest = worktree / "reports/runs/manual-recovery/liu-qwen-p1-20260901"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_path, dest / "QWEN-P1-REPORT.md")
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
        notify("Pure Tate Liu Qwen P1 failed", str(exc)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
