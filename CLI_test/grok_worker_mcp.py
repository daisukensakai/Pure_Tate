#!/usr/bin/env python3
"""Minimal stdio MCP server exposing the hard-capped Grok worker pool.

Protocol: JSON-RPC 2.0 with Content-Length framing (MCP stdio transport).
No third-party MCP SDK required. Not imported by pure_tate.

Tools:
  - dispatch_grok_worker(prompt, description?)
  - await_grok_worker(worker_id, timeout_seconds?)
  - list_grok_workers()
  - cancel_grok_worker(worker_id)
  - worker_pool_stats()

Environment:
  GROK_WORKER_MAX_CONCURRENT  default 4
  GROK_WORKER_MAX_TOTAL       default 4
  GROK_WORKER_MODEL           default grok-4.6
  GROK_WORKER_ALLOW_WEB       1/true to enable web tools for workers
  GROK_WORKER_RESULTS_DIR     directory for worker stdout/stderr
  GROK_WORKER_CWD             working directory for workers
  GROK_WORKER_TIMEOUT         seconds per worker (default 300)
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

# Allow `python CLI_test/grok_worker_mcp.py` from repo root or lab dir.
_LAB = Path(__file__).resolve().parent
if str(_LAB) not in sys.path:
    sys.path.insert(0, str(_LAB))

from grok_worker_pool import (  # noqa: E402
    DEFAULT_MAX_CONCURRENT,
    DEFAULT_MAX_TOTAL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    GrokWorkerPool,
    PoolError,
)


SERVER_NAME = "grok-workers"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str) -> Optional[Path]:
    raw = os.environ.get(name)
    if not raw:
        return None
    return Path(raw)


def build_pool() -> GrokWorkerPool:
    results = _env_path("GROK_WORKER_RESULTS_DIR")
    cwd = _env_path("GROK_WORKER_CWD")
    return GrokWorkerPool(
        max_concurrent=_env_int("GROK_WORKER_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT),
        max_total=_env_int("GROK_WORKER_MAX_TOTAL", DEFAULT_MAX_TOTAL),
        model=os.environ.get("GROK_WORKER_MODEL", DEFAULT_MODEL),
        timeout_seconds=_env_int("GROK_WORKER_TIMEOUT", DEFAULT_TIMEOUT_SECONDS),
        allow_web=_env_bool("GROK_WORKER_ALLOW_WEB", False),
        work_dir=cwd,
        results_dir=results,
    )


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": "dispatch_grok_worker",
            "description": (
                "Dispatch the single read-only Grok worker (turn 1). Hard caps: "
                "1 identity and 4 conversational turns. Prefer continue_grok_worker "
                "for short follow-ups."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Full task prompt for the worker.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Short 3-5 word label.",
                    },
                    "wait": {
                        "type": "boolean",
                        "description": "If true, block until the worker finishes.",
                        "default": False,
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "description": "Optional per-worker timeout override.",
                    },
                },
                "required": ["prompt"],
            },
        },
        {
            "name": "continue_grok_worker",
            "description": (
                "Continue the existing worker with a short follow-up "
                "(redo / more info / gap-fill / narrow sub-task)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "worker_id": {"type": "string"},
                    "prompt": {
                        "type": "string",
                        "description": "Short delta prompt; do not re-dump principal context.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Short 3-5 word label.",
                    },
                    "wait": {
                        "type": "boolean",
                        "default": False,
                    },
                    "timeout_seconds": {"type": "number"},
                },
                "required": ["worker_id", "prompt"],
            },
        },
        {
            "name": "await_grok_worker",
            "description": "Wait for a dispatched Grok worker to finish.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "worker_id": {"type": "string"},
                    "timeout_seconds": {"type": "number"},
                },
                "required": ["worker_id"],
            },
        },
        {
            "name": "list_grok_workers",
            "description": "List all workers in this pool session.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "cancel_grok_worker",
            "description": "Cancel a running or queued worker.",
            "inputSchema": {
                "type": "object",
                "properties": {"worker_id": {"type": "string"}},
                "required": ["worker_id"],
            },
        },
        {
            "name": "worker_pool_stats",
            "description": "Return hard-cap stats for the Grok worker pool.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


class McpServer:
    def __init__(self, pool: GrokWorkerPool) -> None:
        self.pool = pool
        self._initialized = False

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "method" not in message:
            return self._error(message.get("id"), -32600, "Invalid Request")
        method = message["method"]
        msg_id = message.get("id")
        params = message.get("params") or {}
        # Notifications have no id and expect no response.
        is_notification = msg_id is None and method.startswith("notifications/")

        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method == "notifications/initialized":
                self._initialized = True
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": tool_schemas()}
            elif method == "tools/call":
                result = self._tools_call(params)
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "prompts/list":
                result = {"prompts": []}
            else:
                if is_notification:
                    return None
                return self._error(msg_id, -32601, "Method not found: %s" % method)
        except PoolError as exc:
            if is_notification:
                return None
            # Tool-level soft failure as successful tool result with isError.
            if method == "tools/call":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(exc.as_dict(), indent=2),
                            }
                        ],
                        "isError": True,
                    },
                }
            return self._error(msg_id, -32000, exc.message)
        except Exception as exc:  # noqa: BLE001
            if is_notification:
                return None
            return self._error(
                msg_id,
                -32603,
                "Internal error: %s" % exc,
                data=traceback.format_exc()[-2000:],
            )

        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Echo the client's negotiated protocol version when present.
        client_version = params.get("protocolVersion") or PROTOCOL_VERSION
        _debug("initialize params=%s" % json.dumps(params)[:1000])
        return {
            "protocolVersion": client_version,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
            # Some clients expect instructions on the initialize result.
            "instructions": (
                "Hard-capped Grok worker pool. Max 1 worker identity and 4 "
                "conversational turns per session. Tools: dispatch_grok_worker, "
                "await_grok_worker, list_grok_workers, cancel_grok_worker, "
                "worker_pool_stats."
            ),
        }

    def _tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        if name == "dispatch_grok_worker":
            payload = self.pool.dispatch(
                str(arguments.get("prompt") or ""),
                str(arguments.get("description") or ""),
                wait=bool(arguments.get("wait") or False),
                timeout_seconds=(
                    float(arguments["timeout_seconds"])
                    if arguments.get("timeout_seconds") is not None
                    else None
                ),
            )
        elif name == "continue_grok_worker":
            payload = self.pool.continue_worker(
                str(arguments.get("worker_id") or ""),
                str(arguments.get("prompt") or ""),
                str(arguments.get("description") or ""),
                wait=bool(arguments.get("wait") or False),
                timeout_seconds=(
                    float(arguments["timeout_seconds"])
                    if arguments.get("timeout_seconds") is not None
                    else None
                ),
            )
        elif name == "await_grok_worker":
            payload = self.pool.await_worker(
                str(arguments.get("worker_id") or ""),
                timeout_seconds=(
                    float(arguments["timeout_seconds"])
                    if arguments.get("timeout_seconds") is not None
                    else None
                ),
            )
        elif name == "list_grok_workers":
            payload = {
                "ok": True,
                "workers": self.pool.list_workers(),
                "stats": self.pool.stats(),
            }
        elif name == "cancel_grok_worker":
            payload = self.pool.cancel_worker(str(arguments.get("worker_id") or ""))
        elif name == "worker_pool_stats":
            payload = {"ok": True, **self.pool.stats()}
        else:
            raise PoolError("unknown_tool", "unknown tool %s" % name)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, indent=2, sort_keys=True),
                }
            ],
            "isError": False,
        }

    @staticmethod
    def _error(
        msg_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> Dict[str, Any]:
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": msg_id, "error": error}


def _debug(msg: str) -> None:
    path = os.environ.get("GROK_WORKER_MCP_DEBUG_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(msg.rstrip() + "\n")
    except OSError:
        pass


def read_message(stdin_buffer) -> Optional[Dict[str, Any]]:
    """Read one MCP stdio message (Content-Length or newline-delimited JSON)."""
    first = stdin_buffer.readline()
    if not first:
        return None
    # Newline-delimited JSON (some clients).
    stripped = first.strip()
    if stripped.startswith(b"{"):
        try:
            return json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _debug("failed NDJSON parse: %r" % first[:200])
            return None
    # Content-Length framing.
    headers: Dict[str, str] = {}
    line = first
    while True:
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            line = stdin_buffer.readline()
            continue
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip()
        line = stdin_buffer.readline()
    if "content-length" not in headers:
        _debug("missing content-length; headers=%s first=%r" % (headers, first[:120]))
        return None
    length = int(headers["content-length"])
    body = stdin_buffer.read(length)
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _debug("failed body parse: %s body=%r" % (exc, body[:200]))
        return None


def write_message(stdout_buffer, message: Dict[str, Any]) -> None:
    raw = json.dumps(message, separators=(",", ":")).encode("utf-8")
    header = (
        "Content-Length: %d\r\n"
        "Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n"
        "\r\n" % len(raw)
    )
    stdout_buffer.write(header.encode("ascii"))
    stdout_buffer.write(raw)
    stdout_buffer.flush()


def serve(pool: Optional[GrokWorkerPool] = None) -> int:
    pool = pool or build_pool()
    server = McpServer(pool)
    stdin_buffer = sys.stdin.buffer
    stdout_buffer = sys.stdout.buffer
    _debug("mcp server start pid=%s" % os.getpid())
    try:
        while True:
            message = read_message(stdin_buffer)
            if message is None:
                _debug("stdin closed or unreadable message")
                break
            _debug("in method=%s id=%s" % (message.get("method"), message.get("id")))
            response = server.handle(message)
            if response is not None:
                _debug(
                    "out id=%s keys=%s"
                    % (response.get("id"), list(response.keys()))
                )
                write_message(stdout_buffer, response)
    finally:
        pool.shutdown(cancel_live=True)
        _debug("mcp server stop")
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
