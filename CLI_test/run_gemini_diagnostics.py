#!/usr/bin/env python3
"""Bounded Gemini API + CLI diagnostics. Isolated from Pure Tate harness."""

from __future__ import annotations

import datetime
import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


LAB = Path(__file__).resolve().parent
RESULTS = LAB / "results" / "gemini"
API_TIMEOUT = 30
CLI_TIMEOUT = 45

MODELS = [
    "gemini-3.5-flash",  # harness default in data/engines.json
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
]


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def probe_api(model: str) -> Dict[str, Any]:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return {
            "path": "api",
            "model": model,
            "ok": False,
            "error": "GEMINI_API_KEY unset",
        }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent?key="
        + key
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": "Reply with exactly: API_WORKING"}]}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            raw = resp.read()
            data = json.loads(raw)
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return {
                "path": "api",
                "model": model,
                "ok": text.strip() == "API_WORKING",
                "http": resp.status,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "text": text[:120],
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            err = json.loads(raw).get("error", {})
        except json.JSONDecodeError:
            err = {"message": raw[:300]}
        return {
            "path": "api",
            "model": model,
            "ok": False,
            "http": exc.code,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "text": None,
            "error": {
                "code": err.get("code"),
                "status": err.get("status"),
                "message": err.get("message"),
            },
        }
    except Exception as exc:  # noqa: BLE001 - diagnostic surface
        return {
            "path": "api",
            "model": model,
            "ok": False,
            "http": None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "text": None,
            "error": {"message": str(exc)},
        }


def _run_cli(
    model: str, output_format: str, prompt: str, timeout: int = CLI_TIMEOUT
) -> Dict[str, Any]:
    argv = [
        "gemini",
        "-m",
        model,
        "-p",
        prompt,
        "-o",
        output_format,
        "--approval-mode",
        "plan",
        "--skip-trust",
    ]
    slug = model.replace(".", "_").replace("-", "_") + "_" + output_format.replace(
        "-", "_"
    )
    stdout_path = RESULTS / (slug + ".stdout.txt")
    stderr_path = RESULTS / (slug + ".stderr.txt")
    started = time.monotonic()
    # Start a new session so timeout can kill the whole gemini process group.
    proc = subprocess.Popen(
        argv,
        cwd=str(LAB),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout_b, stderr_b = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout_b, stderr_b = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout_b, stderr_b = proc.communicate()
    elapsed = round(time.monotonic() - started, 3)
    stdout = (stdout_b or b"").decode("utf-8", "replace")
    stderr = (stderr_b or b"").decode("utf-8", "replace")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    needle = "CLI_WORKING"
    ok = (not timed_out) and proc.returncode == 0 and needle in stdout
    # stream-json: also accept success result event
    if (not ok) and output_format == "stream-json" and not timed_out:
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("type") == "result"
                and event.get("status") == "success"
                and needle in stdout
            ):
                ok = True
                break
    return {
        "path": "cli",
        "model": model,
        "output_format": output_format,
        "ok": ok,
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "stdout_path": str(stdout_path.relative_to(LAB.parent)),
        "stderr_path": str(stderr_path.relative_to(LAB.parent)),
        "stdout_prefix": stdout[:240].replace("\n", "\\n"),
        "stderr_prefix": stderr[:400].replace("\n", "\\n"),
        "error": _cli_error_hint(stdout, stderr, timed_out),
    }


def _cli_error_hint(
    stdout: str, stderr: str, timed_out: bool
) -> Optional[Dict[str, Any]]:
    blob = stdout + "\n" + stderr
    lower = blob.lower()
    if timed_out:
        return {"kind": "timeout", "message": "CLI exceeded timeout"}
    for marker in (
        "high demand",
        "unavailable",
        "503",
        "rate limit",
        "resource_exhausted",
        "fetch failed",
    ):
        if marker in lower:
            # Prefer a stream-json result error if present.
            for line in stdout.splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "result":
                    return {
                        "kind": "cli_result",
                        "status": event.get("status"),
                        "error": event.get("error") or event.get("message"),
                    }
            idx = lower.index(marker)
            return {
                "kind": "text_match",
                "marker": marker,
                "snippet": blob[max(0, idx - 40) : idx + 120].replace("\n", " "),
            }
    return None


def probe_cli_text(model: str) -> Dict[str, Any]:
    return _run_cli(model, "text", "Reply with exactly: CLI_WORKING")


def probe_cli_stream(model: str) -> Dict[str, Any]:
    return _run_cli(
        model,
        "stream-json",
        'Return exactly this JSON object and no other text: {"probe":"basic","ok":true}',
    )


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []

    print("=== API matrix ===", flush=True)
    for model in MODELS:
        row = probe_api(model)
        rows.append(row)
        print(json.dumps(row), flush=True)

    # CLI only for models that are not hard-503 on API, plus the harness default.
    cli_models = ["gemini-3.5-flash"]
    for row in rows:
        if row.get("path") == "api" and row.get("ok") and row["model"] not in cli_models:
            cli_models.append(row["model"])

    print("=== CLI text matrix ===", flush=True)
    for model in cli_models:
        # Short timeout for known-bad default to avoid long retry hangs.
        timeout = 25 if model == "gemini-3.5-flash" else CLI_TIMEOUT
        row = _run_cli(
            model, "text", "Reply with exactly: CLI_WORKING", timeout=timeout
        )
        rows.append(row)
        print(json.dumps(row), flush=True)

    # Stream-json only for first healthy CLI model (or default if none).
    stream_model = next(
        (
            r["model"]
            for r in rows
            if r.get("path") == "cli" and r.get("ok")
        ),
        "gemini-3.5-flash",
    )
    print("=== CLI stream-json (%s) ===" % stream_model, flush=True)
    stream_row = probe_cli_stream(stream_model)
    rows.append(stream_row)
    print(json.dumps(stream_row), flush=True)

    manifest = {
        "schema_version": 1,
        "executed_at": _utc_now(),
        "gemini_cli_version": _gemini_version(),
        "harness_default_model": "gemini-3.5-flash",
        "api_key_present": bool(os.environ.get("GEMINI_API_KEY")),
        "probes": rows,
        "summary": {
            "api_ok_models": [
                r["model"] for r in rows if r.get("path") == "api" and r.get("ok")
            ],
            "api_fail_models": [
                {
                    "model": r["model"],
                    "http": r.get("http"),
                    "error": r.get("error"),
                }
                for r in rows
                if r.get("path") == "api" and not r.get("ok")
            ],
            "cli_ok_models": [
                r["model"] for r in rows if r.get("path") == "cli" and r.get("ok")
            ],
            "cli_fail_models": [
                {
                    "model": r["model"],
                    "timed_out": r.get("timed_out"),
                    "error": r.get("error"),
                }
                for r in rows
                if r.get("path") == "cli" and not r.get("ok")
            ],
        },
    }
    out = RESULTS / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"], indent=2), flush=True)
    print("wrote", out, flush=True)
    # Non-zero if harness default is broken on both paths.
    default_api = next(
        (r for r in rows if r.get("path") == "api" and r["model"] == "gemini-3.5-flash"),
        None,
    )
    default_cli = next(
        (r for r in rows if r.get("path") == "cli" and r["model"] == "gemini-3.5-flash"),
        None,
    )
    if default_api and not default_api.get("ok") and default_cli and not default_cli.get("ok"):
        return 2
    return 0


def _gemini_version() -> str:
    try:
        completed = subprocess.run(
            ["gemini", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        return (completed.stdout or completed.stderr).decode("utf-8", "replace").strip()
    except Exception as exc:  # noqa: BLE001
        return "unknown: %s" % exc


if __name__ == "__main__":
    raise SystemExit(main())
