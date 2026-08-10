#!/usr/bin/env python3
"""Official-SDK MCP server for the hard-capped Grok worker pool.

Prefer launching with:
  uv run --with mcp python CLI_test/grok_worker_mcp_sdk.py

Falls back is not attempted here — use grok_worker_mcp.py only for unit
tests of the hand-rolled JSON-RPC framing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

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
    return Path(raw) if raw else None


def build_pool() -> GrokWorkerPool:
    return GrokWorkerPool(
        max_concurrent=_env_int("GROK_WORKER_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT),
        max_total=_env_int("GROK_WORKER_MAX_TOTAL", DEFAULT_MAX_TOTAL),
        model=os.environ.get("GROK_WORKER_MODEL", DEFAULT_MODEL),
        timeout_seconds=_env_int("GROK_WORKER_TIMEOUT", DEFAULT_TIMEOUT_SECONDS),
        allow_web=_env_bool("GROK_WORKER_ALLOW_WEB", False),
        work_dir=_env_path("GROK_WORKER_CWD"),
        results_dir=_env_path("GROK_WORKER_RESULTS_DIR"),
    )


def main() -> int:
    from mcp.server import MCPServer

    pool = build_pool()
    mcp = MCPServer(
        name="grok-workers",
        instructions=(
            "Hard-capped Grok 4.5 worker pool. Max 1 concurrent identity and 4 "
            "conversational turns "
            "dispatches per session."
        ),
    )

    @mcp.tool()
    def dispatch_grok_worker(
        prompt: str,
        description: str = "",
        wait: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """Dispatch a read-only Grok 4.5 worker (hard cap 4 total / 4 concurrent)."""
        try:
            payload = pool.dispatch(
                prompt,
                description,
                wait=wait,
                timeout_seconds=timeout_seconds,
            )
            return json.dumps(payload, indent=2, sort_keys=True)
        except PoolError as exc:
            return json.dumps(exc.as_dict(), indent=2)

    @mcp.tool()
    def await_grok_worker(
        worker_id: str,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """Wait for a dispatched worker to finish."""
        try:
            payload = pool.await_worker(
                worker_id, timeout_seconds=timeout_seconds
            )
            return json.dumps(payload, indent=2, sort_keys=True)
        except PoolError as exc:
            return json.dumps(exc.as_dict(), indent=2)

    @mcp.tool()
    def list_grok_workers() -> str:
        """List workers in this pool session."""
        payload = {
            "ok": True,
            "workers": pool.list_workers(),
            "stats": pool.stats(),
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    @mcp.tool()
    def cancel_grok_worker(worker_id: str) -> str:
        """Cancel a running or queued worker."""
        try:
            payload = pool.cancel_worker(worker_id)
            return json.dumps(payload, indent=2, sort_keys=True)
        except PoolError as exc:
            return json.dumps(exc.as_dict(), indent=2)

    @mcp.tool()
    def worker_pool_stats() -> str:
        """Return hard-cap stats for the pool."""
        return json.dumps({"ok": True, **pool.stats()}, indent=2, sort_keys=True)

    try:
        # run_stdio_async is the supported stdio entry for MCPServer.
        import anyio

        anyio.run(mcp.run_stdio_async)
    finally:
        pool.shutdown(cancel_live=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
