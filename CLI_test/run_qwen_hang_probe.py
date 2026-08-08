#!/usr/bin/env python3
"""Diagnose Qwen hangs: timed probes with heartbeats and hard wall clocks.

Isolated from the Pure Tate harness.  Reproduces the request shapes that
campaign steps use (Chat Completions + thinking, Responses + web tools)
while emitting progress so a silent urlopen cannot look like a dead process.

Run:
    python3 CLI_test/run_qwen_hang_probe.py
    python3 CLI_test/run_qwen_hang_probe.py --suite all --wall 180

Results land under CLI_test/results/qwen_hang/<timestamp>/.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RESULTS = ROOT / "results" / "qwen_hang"
QWEN_WORKER = REPO / "pure_tate" / "qwen_worker.py"

DEFAULT_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-max"
KEY_ENVIRONMENTS = ("DASHSCOPE_API_KEY", "QWEN_API_KEY")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _credential() -> Tuple[Optional[str], Optional[str]]:
    for name in KEY_ENVIRONMENTS:
        value = os.environ.get(name)
        if value:
            return name, value
    return None, None


def _base_url() -> str:
    return (
        os.environ.get("QWEN_BASE_URL")
        or os.environ.get("DASHSCOPE_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


class Heartbeat:
    """Emit timed heartbeats while a blocking request is in flight."""

    def __init__(
        self,
        label: str,
        log: Callable[[str], None],
        interval: float = 5.0,
    ) -> None:
        self.label = label
        self.log = log
        self.interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.started = 0.0

    def __enter__(self) -> "Heartbeat":
        self.started = time.monotonic()
        self.log("[%s] BEGIN t=0.0s" % self.label)
        self._thread = threading.Thread(target=self._run, name="hb-" + self.label, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        elapsed = time.monotonic() - self.started
        if exc is None:
            self.log("[%s] END ok t=%.1fs" % (self.label, elapsed))
        else:
            self.log(
                "[%s] END error t=%.1fs %s: %s"
                % (self.label, elapsed, type(exc).__name__, exc)
            )

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            elapsed = time.monotonic() - self.started
            self.log("[%s] HEARTBEAT still waiting t=%.1fs" % (self.label, elapsed))


def _post_json(
    url: str,
    body: Dict[str, Any],
    api_key: str,
    timeout: float,
    extra_headers: Optional[Dict[str, str]] = None,
    stream: bool = False,
) -> Tuple[int, Any, Dict[str, Any]]:
    """POST JSON. Returns (http_status, payload_or_error, meta)."""
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "User-Agent": "pure-tate-cli-test-qwen-hang-probe/1.0",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    meta: Dict[str, Any] = {
        "url": url,
        "body_bytes": len(data),
        "timeout": timeout,
        "stream": stream,
        "started_at": _now(),
    }
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            meta["ttfb_seconds"] = round(time.monotonic() - t0, 3)
            meta["http_status"] = response.status
            meta["response_headers"] = {
                k.lower(): v
                for k, v in response.headers.items()
                if k.lower()
                in (
                    "content-type",
                    "content-length",
                    "transfer-encoding",
                    "x-request-id",
                    "request-id",
                    "x-dashscope-call-id",
                    "x-dashscope-trace-id",
                )
            }
            if stream:
                chunks: List[bytes] = []
                first_chunk_at: Optional[float] = None
                chunk_count = 0
                while True:
                    piece = response.read(4096)
                    if not piece:
                        break
                    if first_chunk_at is None:
                        first_chunk_at = time.monotonic() - t0
                    chunks.append(piece)
                    chunk_count += 1
                raw = b"".join(chunks)
                meta["first_chunk_seconds"] = (
                    round(first_chunk_at, 3) if first_chunk_at is not None else None
                )
                meta["chunk_count"] = chunk_count
                meta["raw_bytes"] = len(raw)
            else:
                raw = response.read()
                meta["raw_bytes"] = len(raw)
            meta["elapsed_seconds"] = round(time.monotonic() - t0, 3)
            try:
                payload = json.loads(raw.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                payload = {"_raw_text": raw.decode("utf-8", "replace")[:2000]}
            return response.status, payload, meta
    except urllib.error.HTTPError as exc:
        meta["elapsed_seconds"] = round(time.monotonic() - t0, 3)
        meta["http_status"] = exc.code
        raw = exc.read()
        meta["raw_bytes"] = len(raw)
        try:
            payload = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            payload = {"message": raw.decode("utf-8", "replace")[:1000]}
        return exc.code, payload, meta
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary
        meta["elapsed_seconds"] = round(time.monotonic() - t0, 3)
        meta["exception_type"] = type(exc).__name__
        meta["exception"] = str(exc)
        # socket.timeout subclasses TimeoutError / OSError depending on version
        return -1, {"error": str(exc), "type": type(exc).__name__}, meta


def _summarize_chat(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"kind": "non_object"}
    choices = payload.get("choices")
    message = {}
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    reasoning = message.get("reasoning_content") if isinstance(message, dict) else None
    return {
        "kind": "chat",
        "model": payload.get("model"),
        "id": payload.get("id"),
        "content_preview": (content or "")[:200] if isinstance(content, str) else None,
        "content_len": len(content) if isinstance(content, str) else 0,
        "reasoning_len": len(reasoning) if isinstance(reasoning, str) else 0,
        "finish_reason": (
            choices[0].get("finish_reason")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict)
            else None
        ),
        "usage": payload.get("usage"),
        "tool_calls": bool(
            isinstance(message, dict) and message.get("tool_calls")
        ),
    }


def _responses_message_text(payload: Dict[str, Any]) -> str:
    """Mirror pure_tate.qwen_worker._responses_text extraction."""
    text = payload.get("output_text")
    if isinstance(text, str) and text:
        return text
    parts: List[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
            # Some Model Studio builds nest under output_text / value.
            elif isinstance(content, dict):
                for key in ("output_text", "value", "content"):
                    val = content.get(key)
                    if isinstance(val, str) and val:
                        parts.append(val)
        # Fallback: message-level text fields
        for key in ("text", "content"):
            val = item.get(key)
            if isinstance(val, str) and val:
                parts.append(val)
    return "\n".join(parts)


def _summarize_responses(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"kind": "non_object"}
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    types = sorted(
        {
            str(item.get("type"))
            for item in output
            if isinstance(item, dict) and item.get("type") is not None
        }
    )
    text = _responses_message_text(payload)
    # Capture structure when text extraction fails (hang/empty-artifact diagnosis).
    message_shapes: List[Dict[str, Any]] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        shape: Dict[str, Any] = {
            "content_type": type(content).__name__,
            "keys": sorted(item.keys()),
        }
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                shape["first_content_keys"] = sorted(first.keys())
                shape["first_content_type"] = first.get("type")
                for key in ("text", "output_text", "value"):
                    if isinstance(first.get(key), str):
                        shape["sample_%s" % key] = first[key][:120]
        message_shapes.append(shape)
    return {
        "kind": "responses",
        "model": payload.get("model"),
        "id": payload.get("id"),
        "status": payload.get("status"),
        "output_types": types,
        "output_text_preview": text[:300],
        "output_text_len": len(text),
        "top_level_output_text_len": (
            len(payload["output_text"])
            if isinstance(payload.get("output_text"), str)
            else 0
        ),
        "message_shapes": message_shapes,
        "usage": payload.get("usage"),
        "error": payload.get("error"),
    }


def probe_chat_no_thinking(
    api_key: str, model: str, timeout: float, log: Callable[[str], None]
) -> Dict[str, Any]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply exactly: HANG_PROBE_OK"}],
        "temperature": 0,
        "max_tokens": 16,
        "enable_thinking": False,
    }
    with Heartbeat("chat_no_thinking", log):
        status, payload, meta = _post_json(
            _base_url() + "/chat/completions", body, api_key, timeout
        )
    summary = _summarize_chat(payload) if status == 200 else {"error_payload": payload}
    ok = (
        status == 200
        and isinstance(summary.get("content_preview"), str)
        and "HANG_PROBE_OK" in (summary.get("content_preview") or "")
    )
    return {"name": "chat_no_thinking", "ok": ok, "http_status": status, "meta": meta, "summary": summary}


def probe_chat_thinking(
    api_key: str, model: str, timeout: float, log: Callable[[str], None]
) -> Dict[str, Any]:
    """Mirrors harness default thinking_budget=16384 on a tiny prompt."""
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Think briefly then reply with exactly JSON "
                    '{"probe":"thinking_ok"} and nothing else.'
                ),
            }
        ],
        "temperature": 0,
        "max_tokens": 256,
        "enable_thinking": True,
        "thinking_budget": 2048,
    }
    with Heartbeat("chat_thinking", log):
        status, payload, meta = _post_json(
            _base_url() + "/chat/completions", body, api_key, timeout
        )
    summary = _summarize_chat(payload) if status == 200 else {"error_payload": payload}
    ok = status == 200 and bool(summary.get("content_len") or summary.get("reasoning_len"))
    return {"name": "chat_thinking", "ok": ok, "http_status": status, "meta": meta, "summary": summary}


def probe_chat_thinking_high_budget(
    api_key: str, model: str, timeout: float, log: Callable[[str], None]
) -> Dict[str, Any]:
    """Same as harness math turns: thinking_budget=16384, larger max_tokens."""
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a read-only Pure Tate task agent. Return the "
                    "required final JSON artifact as plain text."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Return exactly this JSON object and nothing else:\n"
                    '{"schema_version":1,"probe":"high_budget_ok","status":"pass"}'
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 1024,
        "enable_thinking": True,
        "thinking_budget": 16384,
    }
    with Heartbeat("chat_thinking_high_budget", log, interval=10.0):
        status, payload, meta = _post_json(
            _base_url() + "/chat/completions", body, api_key, timeout
        )
    summary = _summarize_chat(payload) if status == 200 else {"error_payload": payload}
    ok = status == 200 and "high_budget_ok" in (summary.get("content_preview") or "")
    return {
        "name": "chat_thinking_high_budget",
        "ok": ok,
        "http_status": status,
        "meta": meta,
        "summary": summary,
    }


def probe_responses_simple(
    api_key: str, model: str, timeout: float, log: Callable[[str], None]
) -> Dict[str, Any]:
    body = {
        "model": model,
        "input": "Reply exactly: RESPONSES_OK",
        "store": False,
        "max_output_tokens": 32,
        "enable_thinking": False,
    }
    with Heartbeat("responses_simple", log):
        status, payload, meta = _post_json(
            _base_url() + "/responses",
            body,
            api_key,
            timeout,
            extra_headers={"x-dashscope-session-cache": "enable"},
        )
    summary = (
        _summarize_responses(payload) if status == 200 else {"error_payload": payload}
    )
    text = summary.get("output_text_preview") or ""
    # Accept either extracted text match or a completed message with tokens
    # (Model Studio sometimes omits top-level output_text).
    ok = status == 200 and (
        "RESPONSES_OK" in text
        or (
            summary.get("status") == "completed"
            and "message" in (summary.get("output_types") or [])
            and (summary.get("output_text_len") or 0) > 0
        )
    )
    if status == 200 and not ok:
        summary["empty_text_anomaly"] = True
    return {
        "name": "responses_simple",
        "ok": ok,
        "http_status": status,
        "meta": meta,
        "summary": summary,
        # Keep a redacted raw slice for structure diagnosis only.
        "raw_output_slice": (
            json.dumps(payload.get("output"), ensure_ascii=False)[:1500]
            if isinstance(payload, dict)
            else None
        ),
    }


def probe_responses_web(
    api_key: str, model: str, timeout: float, log: Callable[[str], None]
) -> Dict[str, Any]:
    """Mirrors stage-1 web evidence: tools + thinking (required with web_extractor)."""
    body = {
        "model": model,
        "input": (
            "Use web_search once to look up the current year. Then reply with "
            'exactly JSON {"probe":"web_ok","year":YYYY} and nothing else. '
            "Do not write a long report."
        ),
        "instructions": (
            "Build a compact evidence answer. Prefer one search. Return promptly."
        ),
        "tools": [{"type": "web_search"}, {"type": "web_extractor"}],
        "tool_choice": "auto",
        "store": True,
        "max_output_tokens": 1024,
        "enable_thinking": True,
        "thinking": {"budget_tokens": 2048},
    }
    with Heartbeat("responses_web", log, interval=10.0):
        status, payload, meta = _post_json(
            _base_url() + "/responses",
            body,
            api_key,
            timeout,
            extra_headers={"x-dashscope-session-cache": "enable"},
        )
    summary = (
        _summarize_responses(payload) if status == 200 else {"error_payload": payload}
    )
    text = summary.get("output_text_preview") or ""
    has_web = "web_search_call" in (summary.get("output_types") or [])
    has_text = bool(text) or (summary.get("output_text_len") or 0) > 0
    # Harness needs final text after tools; tool-only success is a partial pass.
    ok = status == 200 and (has_web or "web_ok" in text)
    if status == 200 and has_web and not has_text:
        summary["empty_text_after_web"] = True
        summary["harness_would"] = (
            "qwen_worker._run_web_evidence raises 'no final text' when "
            "function_calls is empty and _responses_text is empty, then "
            "falls forward to the chat stage with a failure docket."
        )
    return {
        "name": "responses_web",
        "ok": ok,
        "http_status": status,
        "meta": meta,
        "summary": summary,
        "raw_output_slice": (
            json.dumps(payload.get("output"), ensure_ascii=False)[:2000]
            if isinstance(payload, dict)
            else None
        ),
    }


def probe_responses_web_stream(
    api_key: str, model: str, timeout: float, log: Callable[[str], None]
) -> Dict[str, Any]:
    """Same web probe with stream=true to see if bytes arrive before completion."""
    body = {
        "model": model,
        "input": (
            "Use web_search once for the current year. Reply compactly with "
            'JSON {"probe":"web_stream_ok","year":YYYY}.'
        ),
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "store": False,
        "max_output_tokens": 512,
        "enable_thinking": True,
        "thinking": {"budget_tokens": 1024},
        "stream": True,
    }
    with Heartbeat("responses_web_stream", log, interval=5.0):
        status, payload, meta = _post_json(
            _base_url() + "/responses",
            body,
            api_key,
            timeout,
            extra_headers={"x-dashscope-session-cache": "enable"},
            stream=True,
        )
    # Streaming may return SSE text rather than a single JSON object.
    if isinstance(payload, dict) and "_raw_text" in payload:
        raw = payload["_raw_text"]
        summary = {
            "kind": "sse_or_text",
            "raw_preview": raw[:500],
            "raw_len": len(raw),
            "event_lines": raw.count("\n"),
        }
        ok = status == 200 and len(raw) > 0
    else:
        summary = (
            _summarize_responses(payload)
            if status == 200
            else {"error_payload": payload}
        )
        ok = status == 200
    return {
        "name": "responses_web_stream",
        "ok": ok,
        "http_status": status,
        "meta": meta,
        "summary": summary,
    }


def probe_worker_subprocess(
    api_key: str,
    model: str,
    timeout: float,
    log: Callable[[str], None],
    *,
    allow_web: bool,
    wall: float,
) -> Dict[str, Any]:
    """Run the real qwen_worker.py the way the harness does, with activity watch.

    This reproduces the campaign hang shape: a single silent process until the
    final artifact is written to stdout. Heartbeats report process liveness and
    whether any stdout/stderr bytes arrived.
    """
    name = "worker_web" if allow_web else "worker_no_web"
    fixture = ROOT / "read_fixture.txt"
    if not fixture.is_file():
        fixture.write_text("bounded-qwen-read\n", encoding="utf-8")
    prompt = (
        "Read the allowed workspace file if needed. Return exactly this JSON "
        'object and nothing else: {"schema_version":1,"probe":"%s","status":"pass"}'
        % name
    )
    cmd = [
        sys.executable,
        str(QWEN_WORKER),
        "--model",
        model,
        "--prompt",
        prompt,
        "--max-tokens",
        "1024",
        "--thinking-budget",
        "2048",
        "--context-file",
        "read_fixture.txt",
    ]
    if allow_web:
        cmd.append("--allow-web")
    env = os.environ.copy()
    env["DASHSCOPE_API_KEY"] = api_key
    # Cap urllib waits so this probe cannot sit for 3 hours like production.
    env["QWEN_RESPONSES_TIMEOUT"] = str(max(30, int(wall)))
    log("[%s] spawn argv_len=%d cwd=%s wall=%.0fs" % (name, len(cmd), ROOT, wall))
    t0 = time.monotonic()
    last_activity = t0
    stdout_parts: List[bytes] = []
    stderr_parts: List[bytes] = []
    activity_events: List[Dict[str, Any]] = []
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.stdout is not None and proc.stderr is not None
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
    sel.register(proc.stderr, selectors.EVENT_READ, "stderr")
    streams = {proc.stdout: stdout_parts, proc.stderr: stderr_parts}
    stop_hb = threading.Event()

    def _hb() -> None:
        while not stop_hb.wait(10.0):
            elapsed = time.monotonic() - t0
            silent = time.monotonic() - last_activity
            alive = proc.poll() is None
            log(
                "[%s] HEARTBEAT alive=%s t=%.1fs silent=%.1fs out=%d err=%d"
                % (
                    name,
                    alive,
                    elapsed,
                    silent,
                    sum(len(p) for p in stdout_parts),
                    sum(len(p) for p in stderr_parts),
                )
            )

    hb = threading.Thread(target=_hb, name="hb-" + name, daemon=True)
    hb.start()
    timed_out = False
    try:
        while sel.get_map():
            now = time.monotonic()
            if now - t0 > wall:
                timed_out = True
                log("[%s] WALL timeout at %.1fs; killing worker" % (name, now - t0))
                proc.kill()
                break
            events = sel.select(timeout=1.0)
            if not events:
                if proc.poll() is not None:
                    # Drain remaining
                    for fileobj in list(streams):
                        data = fileobj.read()
                        if data:
                            streams[fileobj].append(data)
                            last_activity = time.monotonic()
                    break
                continue
            for key, _ in events:
                chunk = key.fileobj.read1(65536) if hasattr(key.fileobj, "read1") else key.fileobj.read(65536)  # type: ignore[union-attr]
                if chunk:
                    streams[key.fileobj].append(chunk)
                    last_activity = time.monotonic()
                    activity_events.append(
                        {
                            "t": round(last_activity - t0, 3),
                            "stream": key.data,
                            "bytes": len(chunk),
                        }
                    )
                    log(
                        "[%s] activity %s +%dB t=%.1fs"
                        % (name, key.data, len(chunk), last_activity - t0)
                    )
                else:
                    sel.unregister(key.fileobj)
        proc.wait(timeout=10)
    finally:
        stop_hb.set()
        hb.join(timeout=2)
        sel.close()

    elapsed = round(time.monotonic() - t0, 3)
    stdout = b"".join(stdout_parts).decode("utf-8", "replace")
    stderr = b"".join(stderr_parts).decode("utf-8", "replace")
    silent_total = round(
        (activity_events[0]["t"] if activity_events else elapsed), 3
    )
    # Prefer stream extraction (JSONL text events); fall back to raw substring.
    artifact_ok = False
    try:
        from pure_tate.agents import _extract_qwen_stream

        artifact = _extract_qwen_stream(stdout)
        artifact_ok = (
            isinstance(artifact, dict)
            and artifact.get("probe") == name
            and artifact.get("status") == "pass"
        )
    except Exception:
        artifact_ok = name in stdout and "pass" in stdout
    event_count = sum(
        1 for line in stdout.splitlines() if line.strip().startswith("{")
    )
    ok = (
        not timed_out
        and proc.returncode == 0
        and artifact_ok
        and event_count >= 2  # streaming must emit progressive JSONL
    )
    log(
        "[%s] END rc=%s timed_out=%s t=%.1fs first_activity=%.1fs"
        % (name, proc.returncode, timed_out, elapsed, silent_total)
    )
    return {
        "name": name,
        "ok": ok,
        "http_status": None,
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "first_activity_seconds": silent_total if activity_events else None,
        "activity_events": activity_events,
        "stdout_preview": stdout[:500],
        "stderr_preview": stderr[:500],
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "meta": {
            "elapsed_seconds": elapsed,
            "allow_web": allow_web,
            "wall": wall,
            "command": cmd[:4] + ["--prompt", "<redacted>"] + cmd[6:],
        },
        "summary": {
            "silent_until_first_byte": silent_total if activity_events else elapsed,
            "jsonl_event_lines": event_count,
            "artifact_ok": artifact_ok,
            "note": (
                "Harness inactivity watchdog only sees stdout/stderr. "
                "Streaming workers emit JSONL stage/text events so silence "
                "is near zero while the provider is producing tokens."
            ),
        },
    }


def probe_dns_and_tcp(log: Callable[[str], None]) -> Dict[str, Any]:
    """Cheap network path check for the token-plan host."""
    host = "token-plan.ap-southeast-1.maas.aliyuncs.com"
    port = 443
    t0 = time.monotonic()
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        dns_s = round(time.monotonic() - t0, 3)
        addrs = sorted({item[4][0] for item in infos})
        log("[dns_tcp] resolved %s -> %s in %.3fs" % (host, addrs[:4], dns_s))
    except OSError as exc:
        return {
            "name": "dns_tcp",
            "ok": False,
            "error": "dns: %s" % exc,
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        }
    t1 = time.monotonic()
    try:
        sock = socket.create_connection((addrs[0], port), timeout=10)
        sock.close()
        tcp_s = round(time.monotonic() - t1, 3)
        log("[dns_tcp] tcp connect %s:%s ok in %.3fs" % (addrs[0], port, tcp_s))
        return {
            "name": "dns_tcp",
            "ok": True,
            "host": host,
            "addrs": addrs[:8],
            "dns_seconds": dns_s,
            "tcp_seconds": tcp_s,
        }
    except OSError as exc:
        return {
            "name": "dns_tcp",
            "ok": False,
            "host": host,
            "addrs": addrs[:8],
            "dns_seconds": dns_s,
            "error": "tcp: %s" % exc,
            "elapsed_seconds": round(time.monotonic() - t1, 3),
        }


SUITES: Dict[str, List[str]] = {
    "quick": [
        "dns_tcp",
        "chat_no_thinking",
        "chat_thinking",
        "responses_simple",
    ],
    "hang": [
        "dns_tcp",
        "chat_no_thinking",
        "chat_thinking",
        "chat_thinking_high_budget",
        "responses_simple",
        "responses_web",
        "worker_no_web",
        "worker_web",
    ],
    "worker": [
        "dns_tcp",
        "worker_no_web",
        "worker_web",
    ],
    "all": [
        "dns_tcp",
        "chat_no_thinking",
        "chat_thinking",
        "chat_thinking_high_budget",
        "responses_simple",
        "responses_web",
        "responses_web_stream",
        "worker_no_web",
        "worker_web",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        choices=sorted(SUITES),
        default="hang",
        help="Which probe set to run (default: hang)",
    )
    parser.add_argument(
        "--wall",
        type=float,
        default=180.0,
        help="Per-request urllib timeout / wall clock seconds (default 180)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only named probe(s); can be repeated",
    )
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out_dir = RESULTS / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "live.log"
    events_path = out_dir / "events.jsonl"
    summary_path = out_dir / "summary.json"

    log_lock = threading.Lock()

    def log(msg: str) -> None:
        line = "%s %s" % (_now(), msg)
        with log_lock:
            print(line, flush=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    key_name, api_key = _credential()
    if not api_key:
        result = {
            "ok": False,
            "error": "No Qwen credential",
            "checked": list(KEY_ENVIRONMENTS),
        }
        summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        return 2

    selected = args.only or SUITES[args.suite]
    log(
        "start suite=%s probes=%s wall=%.0fs base=%s model=%s key=%s"
        % (args.suite, selected, args.wall, _base_url(), args.model, key_name)
    )

    probes: Dict[str, Callable[[], Dict[str, Any]]] = {
        "dns_tcp": lambda: probe_dns_and_tcp(log),
        "chat_no_thinking": lambda: probe_chat_no_thinking(
            api_key, args.model, args.wall, log
        ),
        "chat_thinking": lambda: probe_chat_thinking(
            api_key, args.model, args.wall, log
        ),
        "chat_thinking_high_budget": lambda: probe_chat_thinking_high_budget(
            api_key, args.model, args.wall, log
        ),
        "responses_simple": lambda: probe_responses_simple(
            api_key, args.model, args.wall, log
        ),
        "responses_web": lambda: probe_responses_web(
            api_key, args.model, args.wall, log
        ),
        "responses_web_stream": lambda: probe_responses_web_stream(
            api_key, args.model, args.wall, log
        ),
        "worker_no_web": lambda: probe_worker_subprocess(
            api_key, args.model, args.wall, log, allow_web=False, wall=args.wall
        ),
        "worker_web": lambda: probe_worker_subprocess(
            api_key, args.model, args.wall, log, allow_web=True, wall=args.wall
        ),
    }

    results: List[Dict[str, Any]] = []
    overall_t0 = time.monotonic()
    for name in selected:
        if name not in probes:
            log("skip unknown probe %s" % name)
            continue
        log("--- probe %s ---" % name)
        try:
            result = probes[name]()
        except Exception as exc:  # noqa: BLE001
            result = {
                "name": name,
                "ok": False,
                "exception": str(exc),
                "traceback": traceback.format_exc()[-1500:],
            }
            log("[%s] CRASH %s" % (name, exc))
        results.append(result)
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
        log(
            "[%s] RESULT ok=%s http=%s elapsed=%s"
            % (
                name,
                result.get("ok"),
                result.get("http_status"),
                (result.get("meta") or {}).get("elapsed_seconds")
                or result.get("elapsed_seconds"),
            )
        )

    diagnosis = _diagnose(results)
    summary = {
        "ok": all(r.get("ok") for r in results) if results else False,
        "suite": args.suite,
        "probes": selected,
        "wall_seconds": args.wall,
        "base_url": _base_url(),
        "model": args.model,
        "credential_environment": key_name,
        "total_elapsed_seconds": round(time.monotonic() - overall_t0, 3),
        "started_at": stamp,
        "results": results,
        "diagnosis": diagnosis,
        "out_dir": str(out_dir.relative_to(ROOT.parent)),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    (RESULTS / "latest.txt").write_text(stamp + "\n", encoding="utf-8")
    log("DONE overall_ok=%s" % summary["ok"])
    log("diagnosis: %s" % diagnosis["headline"])
    for bullet in diagnosis.get("bullets", []):
        log("  - %s" % bullet)
    log("wrote %s" % summary_path)
    # Compact machine-readable line for scripts
    print(
        json.dumps(
            {
                "ok": summary["ok"],
                "out_dir": summary["out_dir"],
                "diagnosis": diagnosis["headline"],
                "probe_ok": {r["name"]: r.get("ok") for r in results},
            }
        ),
        flush=True,
    )
    return 0 if summary["ok"] else 1


def _diagnose(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_name = {r["name"]: r for r in results if "name" in r}
    bullets: List[str] = []
    causes: List[str] = []

    dns = by_name.get("dns_tcp")
    if dns and not dns.get("ok"):
        causes.append("network_path")
        bullets.append("DNS/TCP to token-plan host failed: %s" % dns.get("error"))

    chat = by_name.get("chat_no_thinking")
    if chat and chat.get("ok"):
        bullets.append(
            "Basic Chat Completions works (%.1fs)."
            % ((chat.get("meta") or {}).get("elapsed_seconds") or 0)
        )
    elif chat:
        causes.append("auth_or_endpoint")
        bullets.append(
            "Basic chat failed http=%s meta=%s"
            % (chat.get("http_status"), chat.get("meta"))
        )

    thinking = by_name.get("chat_thinking") or by_name.get("chat_thinking_high_budget")
    high = by_name.get("chat_thinking_high_budget")
    if high and not high.get("ok"):
        elapsed = (high.get("meta") or {}).get("elapsed_seconds")
        exc = (high.get("meta") or {}).get("exception") or ""
        if high.get("http_status") == 504 or "ResponseTimeout" in str(high):
            causes.append("provider_stream_timeout_thinking")
            bullets.append(
                "High-budget thinking hit provider/stream timeout at t=%.1fs."
                % (elapsed or 0)
            )
        elif "timed out" in exc.lower() or high.get("http_status") == -1:
            causes.append("client_read_timeout_thinking")
            bullets.append(
                "High-budget thinking hit client read timeout (wall) at t=%.1fs: %s"
                % (elapsed or 0, exc)
            )
        else:
            causes.append("thinking_path_failure")
            bullets.append(
                "High-budget thinking failed http=%s summary=%s"
                % (high.get("http_status"), high.get("summary"))
            )
    elif high and high.get("ok"):
        bullets.append(
            "High-budget thinking completed in %.1fs (silent until done)."
            % ((high.get("meta") or {}).get("elapsed_seconds") or 0)
        )

    web = by_name.get("responses_web")
    if web and not web.get("ok"):
        elapsed = (web.get("meta") or {}).get("elapsed_seconds")
        payload = str(web.get("summary") or web.get("meta") or "")
        if web.get("http_status") == 504 or "ResponseTimeout" in payload:
            causes.append("provider_stream_timeout_web")
            bullets.append(
                "Responses+web hit provider ResponseTimeout (~300s server-side) "
                "after %.1fs. This matches campaign 504 hangs."
                % (elapsed or 0)
            )
        elif "timed out" in payload.lower() or (web.get("meta") or {}).get("exception"):
            causes.append("client_read_timeout_web")
            bullets.append(
                "Responses+web blocked until client wall timeout (%.1fs). "
                "urlopen emits no bytes until completion → harness inactivity "
                "looks identical to a hang."
                % (elapsed or 0)
            )
        elif web.get("http_status") == 429:
            causes.append("quota")
            bullets.append("Responses+web throttled (429 quota).")
        else:
            causes.append("web_path_failure")
            bullets.append(
                "Responses+web failed http=%s summary=%s"
                % (web.get("http_status"), web.get("summary"))
            )
    elif web and web.get("ok"):
        bullets.append(
            "Responses+web completed in %.1fs."
            % ((web.get("meta") or {}).get("elapsed_seconds") or 0)
        )

    stream = by_name.get("responses_web_stream")
    if stream and stream.get("ok"):
        meta = stream.get("meta") or {}
        bullets.append(
            "Streaming web path returned %s bytes, first_chunk=%ss, chunks=%s."
            % (
                meta.get("raw_bytes"),
                meta.get("first_chunk_seconds"),
                meta.get("chunk_count"),
            )
        )
        if meta.get("first_chunk_seconds") and meta.get("first_chunk_seconds") > 60:
            causes.append("late_first_byte_stream")
            bullets.append(
                "Even with stream=true, first byte took >60s — provider holds "
                "the connection quiet during tool/thinking work."
            )
    elif stream and not stream.get("ok"):
        bullets.append(
            "Streaming web probe failed http=%s (stream may be unsupported)."
            % stream.get("http_status")
        )

    for wname in ("worker_no_web", "worker_web"):
        w = by_name.get(wname)
        if not w:
            continue
        silent = (w.get("summary") or {}).get("silent_until_first_byte")
        if w.get("timed_out"):
            causes.append("worker_wall_timeout")
            bullets.append(
                "%s hit probe wall with zero/partial I/O (silent≈%ss). "
                "Same shape as campaign inactivity kill."
                % (wname, silent)
            )
        elif w.get("ok"):
            bullets.append(
                "%s finished in %ss; first stdout/stderr only after %ss of silence."
                % (wname, w.get("elapsed_seconds"), silent)
            )
            if isinstance(silent, (int, float)) and silent >= 30:
                causes.append("worker_long_silence")
                bullets.append(
                    "%s was silent for %.1fs — under production "
                    "inactivity_timeout_seconds=3600 this is indistinguishable "
                    "from a hang until the watchdog fires."
                    % (wname, silent)
                )
        else:
            causes.append("worker_failure")
            bullets.append(
                "%s failed rc=%s stderr=%r stdout=%r"
                % (
                    wname,
                    w.get("returncode"),
                    (w.get("stderr_preview") or "")[:200],
                    (w.get("stdout_preview") or "")[:200],
                )
            )

    empty_text = any(
        (r.get("summary") or {}).get("empty_text_anomaly")
        or (r.get("summary") or {}).get("empty_text_after_web")
        for r in results
    )
    if empty_text:
        causes.append("empty_responses_text")
        bullets.append(
            "Responses API returned completed status with empty extractable "
            "text (top-level output_text empty; check message_shapes). "
            "Web evidence stage can raise 'no final text' and fall forward."
        )

    # Streaming status from real worker subprocesses
    streaming_workers = [
        r
        for r in results
        if r.get("name") in {"worker_no_web", "worker_web"}
        and isinstance((r.get("summary") or {}).get("jsonl_event_lines"), int)
        and (r.get("summary") or {}).get("jsonl_event_lines", 0) >= 2
        and isinstance((r.get("summary") or {}).get("silent_until_first_byte"), (int, float))
        and (r.get("summary") or {}).get("silent_until_first_byte", 999) < 5
    ]
    if streaming_workers:
        bullets.append(
            "STREAMING: worker emitted progressive JSONL with first activity "
            "under 5s (events: %s)."
            % ", ".join(
                "%s=%s"
                % (
                    r["name"],
                    (r.get("summary") or {}).get("jsonl_event_lines"),
                )
                for r in streaming_workers
            )
        )
    else:
        bullets.append(
            "NOTE: historical hang mode was silent blocking urllib + "
            "inactivity_timeout 3600s. Current code streams SSE and emits "
            "JSONL stage/text heartbeats; re-check workers if first activity "
            "is still delayed."
        )

    structural_only = {
        "worker_long_silence",
        "empty_responses_text",
    }
    non_structural = [c for c in causes if c not in structural_only]
    all_ok = bool(results) and all(r.get("ok") for r in results)

    if "worker_wall_timeout" in causes:
        headline = (
            "Worker subprocess hit the probe wall — still a hang/stall shape."
        )
    elif "provider_stream_timeout_web" in causes or "provider_stream_timeout_thinking" in causes:
        headline = (
            "Provider-side ResponseTimeout (often 300s stream timeout) on the "
            "thinking/web path."
        )
    elif "client_read_timeout_web" in causes or "client_read_timeout_thinking" in causes:
        headline = "Client wall-clock timeout while waiting on the API."
    elif "quota" in causes:
        headline = "Token-plan quota exhausted (429); not a hang."
    elif "auth_or_endpoint" in causes or "network_path" in causes:
        headline = "Connectivity/auth path is broken before long work starts."
    elif all_ok and streaming_workers:
        headline = (
            "Live probes passed with progressive JSONL streaming; "
            "inactivity false-hangs should no longer apply while tokens flow."
        )
    elif streaming_workers and not non_structural:
        headline = (
            "Streaming activity confirmed; remaining issues are content/parse "
            "checks rather than silent hangs."
        )
    elif "empty_responses_text" in causes and not non_structural:
        headline = (
            "Chat path is healthy; Responses text extraction is empty on some "
            "completed payloads."
        )
    else:
        headline = "Partial failure; see bullets."

    return {"headline": headline, "causes": causes, "bullets": bullets}


if __name__ == "__main__":
    raise SystemExit(main())
