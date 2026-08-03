#!/usr/bin/env python3
"""Isolated CLI probes: Claude Max effort + Codex Sol Extra High (xhigh).

Nothing here is imported by pure_tate. Results land under
CLI_test/results/effort/<timestamp>/.

Gate for harness integration of:
  claude ... --effort max
  codex exec ... -m gpt-5.6-sol -c model_reasoning_effort="xhigh"
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "CLI_test"
RESULTS_ROOT = LAB / "results" / "effort"
DEFAULT_TIMEOUT = 180

CLAUDE_MODEL = "claude-opus-5"
CLAUDE_EFFORT = "max"
CODEX_MODEL = "gpt-5.6-sol"
CODEX_EFFORT = "xhigh"  # UI label: Extra High

PROMPT = (
    "Reply with exactly one JSON object and no Markdown fences or surrounding "
    "prose. Keys: probe (string), ok (boolean true), answer (integer 2), "
    "effort_hint (string naming the effort level you believe is active, or "
    '"unknown"). Question: what is 1+1?'
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def timestamp_slug() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def redacted_argv(argv: Sequence[str], prompt: str) -> List[str]:
    out = list(argv)
    digest = "<prompt-sha256:%s>" % sha256_text(prompt)
    if "-p" in out:
        idx = out.index("-p")
        if idx + 1 < len(out):
            out[idx + 1] = digest
    if out and out[-1] == prompt:
        out[-1] = digest
    return out


def build_claude_argv(prompt: str) -> List[str]:
    return [
        "claude",
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
        CLAUDE_MODEL,
        "--effort",
        CLAUDE_EFFORT,
    ]


def build_codex_argv(prompt: str, last_message: Path) -> List[str]:
    return [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "-m",
        CODEX_MODEL,
        "--sandbox",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        'model_reasoning_effort="%s"' % CODEX_EFFORT,
        "--json",
        "-o",
        str(last_message),
        prompt,
    ]


def run_command(
    argv: Sequence[str],
    cwd: Path,
    timeout: int,
) -> Dict[str, Any]:
    started = time.time()
    env = dict(os.environ)
    # Prefer not inheriting interactive defaults that could mask flags.
    env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
    try:
        process = subprocess.run(
            list(argv),
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )
        return {
            "returncode": process.returncode,
            "stdout": process.stdout or "",
            "stderr": process.stderr or "",
            "elapsed_seconds": round(time.time() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        # Kill process group if still alive.
        if exc.process is not None and exc.process.pid:
            try:
                os.killpg(exc.process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        return {
            "returncode": None,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            "elapsed_seconds": round(time.time() - started, 3),
            "timed_out": True,
            "error": "timeout after %ss" % timeout,
        }


def _json_objects_from_stream(text: str) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def extract_final_json(text: str) -> Optional[Dict[str, Any]]:
    # Prefer stream-json final text assembly, else last brace object.
    chunks: List[str] = []
    for event in _json_objects_from_stream(text):
        # Claude stream-json partial/final message shapes vary.
        if event.get("type") in {"assistant", "result", "content_block_delta"}:
            message = event.get("message") or event.get("result") or event
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and isinstance(block.get("text"), str):
                            chunks.append(block["text"])
                elif isinstance(content, str):
                    chunks.append(content)
            elif isinstance(message, str):
                chunks.append(message)
        if event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        if isinstance(event.get("text"), str) and event.get("type") in {
            None,
            "message",
            "agent_message",
        }:
            chunks.append(event["text"])
    blob = "".join(chunks) if chunks else text
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def codex_effort_from_events(stdout: str) -> Optional[str]:
    for event in _json_objects_from_stream(stdout):
        # Session / thread config events often carry reasoning_effort.
        for key in ("reasoning_effort", "model_reasoning_effort", "effort"):
            value = event.get(key)
            if isinstance(value, str) and value:
                return value
        payload = event.get("payload") or event.get("item") or event.get("msg")
        if isinstance(payload, dict):
            for key in ("reasoning_effort", "model_reasoning_effort", "effort"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
            # Nested session configuration.
            for nested_key in ("session", "config", "thread"):
                nested = payload.get(nested_key)
                if isinstance(nested, dict):
                    for key in ("reasoning_effort", "model_reasoning_effort", "effort"):
                        value = nested.get(key)
                        if isinstance(value, str) and value:
                            return value
    return None


def probe_claude(run_dir: Path, timeout: int) -> Dict[str, Any]:
    out_dir = run_dir / "claude_max"
    out_dir.mkdir(parents=True, exist_ok=True)
    if shutil.which("claude") is None:
        return {
            "probe": "claude_max",
            "status": "skip",
            "reason": "claude not on PATH",
        }
    argv = build_claude_argv(PROMPT)
    result = run_command(argv, cwd=out_dir, timeout=timeout)
    (out_dir / "stdout.jsonl").write_text(result["stdout"], encoding="utf-8")
    (out_dir / "stderr.txt").write_text(result["stderr"], encoding="utf-8")
    parsed = extract_final_json(result["stdout"])
    effort_in_argv = "--effort" in argv and CLAUDE_EFFORT in argv
    status = "pass"
    reasons: List[str] = []
    if result.get("timed_out"):
        status = "fail"
        reasons.append("timed_out")
    elif result.get("returncode") != 0:
        status = "fail"
        reasons.append("nonzero_returncode=%s" % result.get("returncode"))
    if not effort_in_argv:
        status = "fail"
        reasons.append("effort_flag_missing_from_argv")
    if parsed is None or parsed.get("ok") is not True:
        # Soft: CLI accepted flags even if JSON shape is messy.
        if status == "pass":
            status = "pass_with_parse_warning"
            reasons.append("final_json_not_ok_or_missing")
    summary = {
        "probe": "claude_max",
        "status": status,
        "model": CLAUDE_MODEL,
        "effort": CLAUDE_EFFORT,
        "effort_in_argv": effort_in_argv,
        "returncode": result.get("returncode"),
        "timed_out": result.get("timed_out"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "argv_redacted": redacted_argv(argv, PROMPT),
        "parsed": parsed,
        "reasons": reasons,
        "stdout_sha256": sha256_text(result["stdout"]),
        "stderr_sha256": sha256_text(result["stderr"]),
        "stderr_tail": (result["stderr"] or "")[-800:],
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def probe_codex(run_dir: Path, timeout: int) -> Dict[str, Any]:
    out_dir = run_dir / "codex_sol_xhigh"
    out_dir.mkdir(parents=True, exist_ok=True)
    if shutil.which("codex") is None:
        return {
            "probe": "codex_sol_xhigh",
            "status": "skip",
            "reason": "codex not on PATH",
        }
    last_message = out_dir / "last-message.txt"
    argv = build_codex_argv(PROMPT, last_message)
    result = run_command(argv, cwd=out_dir, timeout=timeout)
    (out_dir / "stdout.jsonl").write_text(result["stdout"], encoding="utf-8")
    (out_dir / "stderr.txt").write_text(result["stderr"], encoding="utf-8")
    last_text = (
        last_message.read_text(encoding="utf-8") if last_message.is_file() else ""
    )
    if last_text:
        (out_dir / "last-message.txt").write_text(last_text, encoding="utf-8")
    observed_effort = codex_effort_from_events(result["stdout"])
    parsed = extract_final_json(last_text or result["stdout"])
    effort_flag = any(
        'model_reasoning_effort="%s"' % CODEX_EFFORT in part for part in argv
    )
    status = "pass"
    reasons: List[str] = []
    if result.get("timed_out"):
        status = "fail"
        reasons.append("timed_out")
    elif result.get("returncode") != 0:
        status = "fail"
        reasons.append("nonzero_returncode=%s" % result.get("returncode"))
    if not effort_flag:
        status = "fail"
        reasons.append("reasoning_effort_flag_missing_from_argv")
    if observed_effort and observed_effort.lower() not in {
        CODEX_EFFORT,
        "extra_high",
        "extra-high",
        "x-high",
    }:
        # Flag mismatch but still may have run.
        reasons.append("observed_effort=%s" % observed_effort)
        if status == "pass":
            status = "pass_with_effort_mismatch"
    if parsed is None or parsed.get("ok") is not True:
        if status == "pass":
            status = "pass_with_parse_warning"
            reasons.append("final_json_not_ok_or_missing")
    summary = {
        "probe": "codex_sol_xhigh",
        "status": status,
        "model": CODEX_MODEL,
        "model_reasoning_effort": CODEX_EFFORT,
        "effort_in_argv": effort_flag,
        "observed_effort": observed_effort,
        "returncode": result.get("returncode"),
        "timed_out": result.get("timed_out"),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "argv_redacted": redacted_argv(argv, PROMPT),
        "parsed": parsed,
        "reasons": reasons,
        "stdout_sha256": sha256_text(result["stdout"]),
        "stderr_sha256": sha256_text(result["stderr"]),
        "stderr_tail": (result["stderr"] or "")[-800:],
        "last_message_sha256": sha256_text(last_text) if last_text else None,
    }
    write_json(out_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--engines",
        default="claude,codex",
        help="Comma-separated: claude,codex",
    )
    args = parser.parse_args()
    run_dir = RESULTS_ROOT / timestamp_slug()
    run_dir.mkdir(parents=True, exist_ok=True)
    (RESULTS_ROOT / "latest.txt").write_text(str(run_dir) + "\n", encoding="utf-8")

    engines = {item.strip() for item in args.engines.split(",") if item.strip()}
    results: List[Dict[str, Any]] = []
    if "claude" in engines:
        print("Running Claude Max effort probe...")
        results.append(probe_claude(run_dir, args.timeout))
        print("  ->", results[-1]["status"], results[-1].get("reasons") or "")
    if "codex" in engines:
        print("Running Codex Sol xhigh (Extra High) probe...")
        results.append(probe_codex(run_dir, args.timeout))
        print("  ->", results[-1]["status"], results[-1].get("reasons") or "")

    manifest = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "run_dir": str(run_dir.relative_to(ROOT)),
        "timeout_seconds": args.timeout,
        "prompt_sha256": sha256_text(PROMPT),
        "targets": {
            "claude": {"model": CLAUDE_MODEL, "effort": CLAUDE_EFFORT},
            "codex": {
                "model": CODEX_MODEL,
                "model_reasoning_effort": CODEX_EFFORT,
                "ui_label": "Extra High",
            },
        },
        "results": results,
    }
    write_json(run_dir / "manifest.json", manifest)

    hard_fail = any(item.get("status") == "fail" for item in results)
    any_skip = any(item.get("status") == "skip" for item in results)
    if hard_fail:
        print("FAIL: one or more effort probes failed. See", run_dir)
        return 1
    if any_skip and not results:
        print("SKIP: no engines runnable")
        return 0
    print("OK: effort probes finished. Results:", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
