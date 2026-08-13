#!/usr/bin/env python3
"""CLI_test probes for hard-capped Grok 4.6 workers (MCP + native spawn).

Not imported by pure_tate. Does not edit ~/.grok/config.toml or the harness.

Usage:
  python3 CLI_test/run_grok_worker_probes.py              # offline unit + live smokes
  python3 CLI_test/run_grok_worker_probes.py --offline     # unit only
  python3 CLI_test/run_grok_worker_probes.py --live        # include live API probes
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grok_worker_mcp import (  # noqa: E402
    McpServer,
    build_pool,
    read_message,
    write_message,
)
from grok_worker_pool import (  # noqa: E402
    DEFAULT_MODEL,
    GrokWorkerPool,
    PoolError,
    WorkerRecord,
    build_worker_argv,
    extract_result_text,
    redact_argv,
    sha256_text,
    utc_now_iso,
)
from pure_tate.agents import _run_codex_controller  # noqa: E402
from pure_tate.grok_workers import prepare_worker_session  # noqa: E402


RESULTS_ROOT = LAB / "results" / "grok_workers"
MODEL = DEFAULT_MODEL
LIVE_TIMEOUT = 300


def timestamp_slug() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# Offline unit probes
# ---------------------------------------------------------------------------


def _fake_runner_factory(delay: float = 0.05, fail_ids: Optional[set] = None):
    fail_ids = fail_ids or set()

    def runner(
        *,
        prompt: str,
        description: str,
        worker_id: str,
        pool: GrokWorkerPool,
        turn: int = 1,
        resume_session_id: Optional[str] = None,
    ) -> WorkerRecord:
        time.sleep(delay)
        status = "failed" if worker_id in fail_ids else "completed"
        return WorkerRecord(
            worker_id=worker_id,
            description=description,
            prompt_sha256=sha256_text(prompt),
            status=status,
            created_at=utc_now_iso(),
            started_at=utc_now_iso(),
            finished_at=utc_now_iso(),
            returncode=0 if status == "completed" else 1,
            result_text='{"probe":"fake","ok":true,"turn":%d}' % turn,
            elapsed_seconds=delay,
            argv_redacted=["fake-runner"],
            turn_index=turn,
            cli_session_id=resume_session_id or "sess-fake",
        )

    return runner


def probe_pool_unit_cap() -> Dict[str, Any]:
    """Hard identity + concurrent caps without calling Grok."""
    pool = GrokWorkerPool(
        max_concurrent=1, max_total=1, max_worker_turns=4, runner=_fake_runner_factory()
    )
    result = pool.dispatch("prompt-0", "t0")
    assert result["status"] == "completed", result
    try:
        pool.dispatch("prompt-1", "t1")
        second_total = {"raised": False}
    except PoolError as exc:
        second_total = {"raised": True, "code": exc.code, "message": exc.message}
    assert second_total.get("raised") and second_total.get("code") == "budget_exhausted"

    pool3 = GrokWorkerPool(max_concurrent=1, max_total=1, max_worker_turns=4)
    gate_entered = threading.Event()
    gate_release = threading.Event()

    def gated_run(
        worker_id: str,
        prompt: str,
        timeout_seconds: Optional[int],
        resume_session_id: Optional[str] = None,
    ) -> None:
        gate_entered.set()
        gate_release.wait(timeout=15)
        with pool3._lock:
            rec = pool3._workers[worker_id]
            rec.status = "completed"
            rec.finished_at = utc_now_iso()
            rec.result_text = "done"
            rec.returncode = 0
            rec.cli_session_id = "sess-live"
            pool3._live = sum(
                1
                for item in pool3._workers.values()
                if item.status in {"queued", "running"}
            )

    pool3._run_worker = gated_run  # type: ignore[method-assign]
    meta = pool3.dispatch("p-0", "c0", wait=False)
    assert gate_entered.wait(timeout=5), "worker did not become live"
    fifth_concurrent: Dict[str, Any]
    try:
        pool3.dispatch("p-1", "c1", wait=False)
        fifth_concurrent = {"raised": False}
    except PoolError as exc:
        fifth_concurrent = {"raised": True, "code": exc.code, "message": exc.message}
    gate_release.set()
    pool3.await_worker(meta["worker_id"], timeout_seconds=5)
    assert fifth_concurrent.get("raised") and fifth_concurrent.get("code") in {
        "pool_full",
        "budget_exhausted",
    }, fifth_concurrent

    return {
        "probe": "pool_unit_cap",
        "status": "pass",
        "second_total": second_total,
        "second_while_live": fifth_concurrent,
        "stats_after_total_test": pool.stats(),
    }


def probe_mcp_unit_roundtrip() -> Dict[str, Any]:
    """In-process MCP initialize + tools/call against fake pool."""
    pool = GrokWorkerPool(
        max_concurrent=1, max_total=1, max_worker_turns=4, runner=_fake_runner_factory()
    )
    server = McpServer(pool)
    init = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
        }
    )
    assert init and "result" in init
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in listed["result"]["tools"]]
    assert "dispatch_grok_worker" in names
    called = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "dispatch_grok_worker",
                "arguments": {
                    "prompt": "return ok",
                    "description": "unit",
                    "wait": True,
                },
            },
        }
    )
    body = json.loads(called["result"]["content"][0]["text"])
    assert body["status"] == "completed", body
    # Exhaust budget
    for i in range(3):
        server.handle(
            {
                "jsonrpc": "2.0",
                "id": 10 + i,
                "method": "tools/call",
                "params": {
                    "name": "dispatch_grok_worker",
                    "arguments": {"prompt": "x%d" % i, "wait": True},
                },
            }
        )
    fifth = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "dispatch_grok_worker",
                "arguments": {"prompt": "overflow", "wait": True},
            },
        }
    )
    assert fifth["result"].get("isError") is True
    err_body = json.loads(fifth["result"]["content"][0]["text"])
    assert err_body.get("error_code") == "budget_exhausted", err_body
    return {
        "probe": "mcp_unit_roundtrip",
        "status": "pass",
        "tools": names,
        "fifth_error": err_body,
    }


def probe_worker_argv_shape() -> Dict[str, Any]:
    argv = build_worker_argv("hello", model=MODEL, allow_web=False)
    tools = argv[argv.index("--tools") + 1].split(",")
    denied = argv[argv.index("--disallowed-tools") + 1].split(",")
    ok = (
        "read_file" in tools
        and "write" in denied
        and "run_terminal_command" in denied
        and "--no-subagents" in argv
        and argv[argv.index("-m") + 1] == MODEL
    )
    return {
        "probe": "worker_argv_shape",
        "status": "pass" if ok else "fail",
        "argv_redacted": redact_argv(argv, "hello"),
        "tools": tools,
        "denied": denied,
    }


# ---------------------------------------------------------------------------
# Live probes
# ---------------------------------------------------------------------------


def run_subprocess(
    argv: List[str],
    *,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    timeout: int = LIVE_TIMEOUT,
) -> Tuple[int, str, str, float]:
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env=env or os.environ.copy(),
    )
    elapsed = round(time.monotonic() - started, 3)
    return (
        completed.returncode,
        completed.stdout.decode("utf-8", "replace"),
        completed.stderr.decode("utf-8", "replace"),
        elapsed,
    )


def probe_worker_smoke(run_dir: Path) -> Dict[str, Any]:
    """One real Grok worker via the pool using the selected model."""
    results = run_dir / "worker_smoke"
    results.mkdir(parents=True, exist_ok=True)
    pool = GrokWorkerPool(
        max_concurrent=4,
        max_total=4,
        model=MODEL,
        results_dir=results,
        work_dir=ROOT,
        timeout_seconds=LIVE_TIMEOUT,
    )
    prompt = (
        "Return exactly one JSON object and no Markdown: "
        '{"probe":"worker_smoke","ok":true,"marker":"PT-WORKER-OK"}.'
    )
    try:
        result = pool.dispatch(prompt, "smoke", wait=True, timeout_seconds=LIVE_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        return {
            "probe": "worker_smoke",
            "status": "fail",
            "error": str(exc),
        }
    text = result.get("result_text") or ""
    ok = (
        result.get("status") == "completed"
        and "PT-WORKER-OK" in text
        and result.get("returncode") == 0
    )
    return {
        "probe": "worker_smoke",
        "status": "pass" if ok else "fail",
        "worker": result,
        "marker_found": "PT-WORKER-OK" in text,
    }


def probe_worker_single_cap(run_dir: Path) -> Dict[str, Any]:
    """Live: one worker identity; second dispatch must hard-fail."""
    results = run_dir / "worker_single_cap"
    results.mkdir(parents=True, exist_ok=True)
    pool = GrokWorkerPool(
        max_concurrent=1,
        max_total=1,
        max_worker_turns=4,
        results_dir=results,
        work_dir=ROOT,
        timeout_seconds=LIVE_TIMEOUT,
        backend="cursor",
    )
    prompt = (
        "Return exactly one JSON object and no Markdown: "
        '{"probe":"worker_single_cap","ok":true}.'
    )
    first = pool.dispatch(prompt, "p0", wait=True)
    second: Dict[str, Any]
    try:
        pool.dispatch(
            'Return JSON {"probe":"overflow","ok":false}.',
            "overflow",
            wait=False,
        )
        second = {"raised": False}
    except PoolError as exc:
        second = {"raised": True, "code": exc.code, "message": exc.message}
    ok = (
        first.get("status") == "completed"
        and second.get("raised") is True
        and second.get("code") == "budget_exhausted"
    )
    return {
        "probe": "worker_single_cap",
        "status": "pass" if ok else "fail",
        "first": first,
        "second": second,
        "stats": pool.stats(),
    }


def probe_worker_continue_turns(run_dir: Path) -> Dict[str, Any]:
    """Unit/mocked: one identity can continue up to 4 turns then exhausts."""
    results = run_dir / "worker_continue_turns"
    results.mkdir(parents=True, exist_ok=True)
    pool = GrokWorkerPool(
        max_concurrent=1,
        max_total=1,
        max_worker_turns=4,
        backend="cursor",
        runner=_fake_runner_factory(delay=0.0),
        results_dir=results,
    )
    first = pool.dispatch("start", "t1")
    worker_id = first["worker_id"]
    turns = [first]
    for index in range(2, 5):
        turns.append(
            pool.continue_worker(worker_id, "follow-%d" % index, "c%d" % index)
        )
    exhausted: Dict[str, Any]
    try:
        pool.continue_worker(worker_id, "too-many", "x")
        exhausted = {"raised": False}
    except PoolError as exc:
        exhausted = {"raised": True, "code": exc.code, "message": exc.message}
    ok = (
        all(item.get("status") == "completed" for item in turns)
        and [item.get("turn_index") for item in turns] == [1, 2, 3, 4]
        and exhausted.get("code") == "turns_exhausted"
    )
    return {
        "probe": "worker_continue_turns",
        "status": "pass" if ok else "fail",
        "turns": [{"turn": t.get("turn_index"), "status": t.get("status")} for t in turns],
        "exhausted": exhausted,
        "stats": pool.stats(),
    }


def probe_worker_parallel_4(run_dir: Path) -> Dict[str, Any]:
    """Deprecated alias — parallel workers are no longer supported."""
    return probe_worker_single_cap(run_dir)


def _available_tools_from_stream(stdout: str) -> List[str]:
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
            and event.get("type") == "available_commands"
            and isinstance(event.get("tools"), list)
        ):
            return [str(t) for t in event["tools"]]
    return []


def probe_allowlist_safety(run_dir: Path) -> Dict[str, Any]:
    """Prove harness-safe allowlist stays strict; spawn-in-tools is unsafe.

    Gate:
      1) `--tools read_file,grep,list_dir` must NOT expose shell/write/spawn.
      2) Adding `spawn_subagent` to `--tools` must be treated as UNSAFE
         (observed: allowlist collapses and shell reappears). Pass when that
         regression is detected so harness never enables native spawn via
         --tools; MCP workers are the hard-cap path instead.
    """
    out_dir = run_dir / "allowlist_safety"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = (
        'Return exactly JSON {"probe":"allowlist_safety","ok":true}. '
        "Do not call tools."
    )
    baseline_argv = [
        "grok",
        "-p",
        prompt,
        "--output-format",
        "streaming-json",
        "--max-turns",
        "2",
        "--permission-mode",
        "dontAsk",
        "--always-approve",
        "--tools",
        "read_file,grep,list_dir",
        "--disallowed-tools",
        "run_terminal_command,write,open_page,web_search,web_fetch",
        "--disable-web-search",
        "-m",
        MODEL,
    ]
    spawn_argv = list(baseline_argv)
    spawn_argv[spawn_argv.index("--tools") + 1] = (
        "read_file,grep,list_dir,spawn_subagent"
    )

    b_code, b_stdout, b_stderr, b_elapsed = run_subprocess(
        baseline_argv, cwd=ROOT, timeout=LIVE_TIMEOUT
    )
    s_code, s_stdout, s_stderr, s_elapsed = run_subprocess(
        spawn_argv, cwd=ROOT, timeout=LIVE_TIMEOUT
    )
    (out_dir / "baseline.stdout.jsonl").write_text(b_stdout, encoding="utf-8")
    (out_dir / "baseline.stderr.txt").write_text(b_stderr, encoding="utf-8")
    (out_dir / "spawn_tools.stdout.jsonl").write_text(s_stdout, encoding="utf-8")
    (out_dir / "spawn_tools.stderr.txt").write_text(s_stderr, encoding="utf-8")

    baseline_tools = _available_tools_from_stream(b_stdout)
    spawn_tools = _available_tools_from_stream(s_stdout)
    dangerous = {
        "run_terminal_command",
        "run_terminal_cmd",
        "write",
        "search_replace",
    }
    baseline_ok = b_code == 0 and not (set(baseline_tools) & dangerous)
    # MCP meta-tools may remain; that is fine.
    baseline_has_mcp_meta = "search_tool" in baseline_tools and "use_tool" in baseline_tools
    spawn_broke_allowlist = bool(set(spawn_tools) & dangerous) or (
        "run_terminal_command" in spawn_tools
    )
    # Pass criteria for harness design:
    # - baseline allowlist is safe
    # - AND we correctly detect that spawn_subagent-in-tools is unsafe
    #   (so harness must not do that)
    ok = baseline_ok and spawn_broke_allowlist
    return {
        "probe": "allowlist_safety",
        "status": "pass" if ok else "fail",
        "baseline": {
            "returncode": b_code,
            "elapsed_seconds": b_elapsed,
            "tools": baseline_tools,
            "safe": baseline_ok,
            "mcp_meta_present": baseline_has_mcp_meta,
        },
        "spawn_in_tools": {
            "returncode": s_code,
            "elapsed_seconds": s_elapsed,
            "tools": spawn_tools,
            "broke_allowlist": spawn_broke_allowlist,
            "spawn_present": "spawn_subagent" in spawn_tools,
        },
        "recommendation": (
            "Do not put spawn_subagent in Grok --tools; it collapses the "
            "allowlist and reintroduces shell. Use MCP worker pool instead. "
            "Baseline allowlist already exposes search_tool/use_tool for MCP."
        ),
        "argv_baseline": redact_argv(baseline_argv, prompt),
        "argv_spawn": redact_argv(spawn_argv, prompt),
    }


def probe_native_spawn_optional(run_dir: Path) -> Dict[str, Any]:
    """Document that native spawn via --tools is unsafe for headless allowlists.

    Earlier matrix showed adding spawn_subagent to --tools collapses the
    allowlist and reintroduces shell without reliably exposing spawn_subagent.
    Hard-capped workers therefore go through the MCP pool, not native spawn.
    """
    out_dir = run_dir / "native_spawn"
    out_dir.mkdir(parents=True, exist_ok=True)
    note = {
        "probe": "native_spawn_optional",
        "status": "skip",
        "reason": (
            "Native spawn_subagent cannot be enabled via Grok --tools without "
            "collapsing the read-only allowlist (shell reappears). Hard-cap "
            "path is the MCP worker pool. See allowlist_safety probe."
        ),
        "harness_recommendation": "mcp_worker_pool",
    }
    write_json(out_dir / "note.json", note)
    return note


def mcp_server_command() -> List[str]:
    """Launch official-SDK MCP server (protocol-compatible with Grok/Claude)."""
    uv = shutil.which("uv")
    script = str(LAB / "grok_worker_mcp_sdk.py")
    if uv:
        return [uv, "run", "--with", "mcp", "python", script]
    # Fallback: hope mcp is importable on PATH python.
    return [sys.executable, script]


def _claude_mcp_config(
    server_command: List[str], env: Dict[str, str]
) -> Dict[str, Any]:
    return {
        "mcpServers": {
            "grok-workers": {
                "command": server_command[0],
                "args": server_command[1:],
                "env": env,
            }
        }
    }


def probe_mcp_claude(run_dir: Path) -> Dict[str, Any]:
    """Claude headless with session --mcp-config dispatches one worker."""
    if shutil.which("claude") is None:
        return {"probe": "mcp_claude", "status": "skip", "reason": "claude not on PATH"}
    out_dir = run_dir / "mcp_claude"
    out_dir.mkdir(parents=True, exist_ok=True)
    worker_results = out_dir / "workers"
    worker_results.mkdir(exist_ok=True)
    worker_env = {
        "GROK_WORKER_RESULTS_DIR": str(worker_results),
        "GROK_WORKER_CWD": str(ROOT),
        "GROK_WORKER_MAX_CONCURRENT": "4",
        "GROK_WORKER_MAX_TOTAL": "4",
        "GROK_WORKER_TIMEOUT": str(LIVE_TIMEOUT),
    }
    server_cmd = mcp_server_command()
    mcp_path = out_dir / "mcp.json"
    write_json(mcp_path, _claude_mcp_config(server_cmd, worker_env))
    prompt = (
        "Use the MCP tool dispatch_grok_worker exactly once with wait=true and "
        'prompt: Return exactly JSON {"probe":"from_worker","ok":true,"marker":"CLAUDE-MCP"} '
        "with no markdown fences. Then return exactly one JSON object: "
        '{"probe":"mcp_claude","ok":true,"marker":"CLAUDE-MCP"} '
        "after the worker finishes. Do not edit files."
    )
    argv = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools",
        "mcp__grok-workers__dispatch_grok_worker",
        "mcp__grok-workers__await_grok_worker",
        "mcp__grok-workers__list_grok_workers",
        "mcp__grok-workers__worker_pool_stats",
        "Read",
        "--disallowedTools",
        "Edit",
        "Write",
        "Bash",
        "--mcp-config",
        str(mcp_path),
        "--strict-mcp-config",
        "--model",
        "claude-opus-5",
    ]
    code, stdout, stderr, elapsed = run_subprocess(
        argv, cwd=ROOT, timeout=LIVE_TIMEOUT + 90
    )
    (out_dir / "stdout.json").write_text(stdout, encoding="utf-8")
    (out_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    result_text = stdout
    try:
        envelope = json.loads(stdout)
        if isinstance(envelope, dict) and isinstance(envelope.get("result"), str):
            result_text = envelope["result"]
    except json.JSONDecodeError:
        pass
    worker_files = sorted(p.name for p in worker_results.iterdir())
    # Hard gate: a worker must actually have run.
    ok = bool(worker_files) and "CLAUDE-MCP" in result_text
    return {
        "probe": "mcp_claude",
        "status": "pass" if ok else "fail",
        "returncode": code,
        "elapsed_seconds": elapsed,
        "result_prefix": result_text[:500],
        "worker_files": worker_files,
        "server_cmd": server_cmd,
        "stderr_prefix": stderr[:500],
    }


def probe_mcp_grok(run_dir: Path) -> Dict[str, Any]:
    """Grok headless with session-scoped GROK_HOME MCP (no user config write).

    dontAsk rejects MCP use_tool (failed→cancelled). Use bypassPermissions with
    a strict --tools allowlist so write/shell stay unavailable.
    """
    out_dir = run_dir / "mcp_grok"
    out_dir.mkdir(parents=True, exist_ok=True)
    worker_results = out_dir / "workers"
    worker_results.mkdir(exist_ok=True)
    real_home = Path(os.environ.get("GROK_HOME", Path.home() / ".grok")).expanduser()
    server_cmd = mcp_server_command()

    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    with tempfile.TemporaryDirectory(prefix="grok-home-probe-") as tmp:
        home = Path(tmp)
        for name in ("auth.json", "auth.json.lock", "models_cache.json"):
            src = real_home / name
            if src.exists():
                try:
                    os.symlink(src, home / name)
                except OSError:
                    if src.is_file():
                        shutil.copy2(src, home / name)
        args_toml = ", ".join('"%s"' % esc(part) for part in server_cmd[1:])
        config = (
            "# ephemeral CLI_test probe config — do not copy to user home\n"
            "[mcp_servers.grok_workers]\n"
            'command = "%s"\n'
            "args = [%s]\n"
            "enabled = true\n"
            "startup_timeout_sec = 90\n"
            "tool_timeout_sec = 300\n"
            'env = { GROK_WORKER_RESULTS_DIR = "%s", GROK_WORKER_CWD = "%s", '
            'GROK_WORKER_MAX_TOTAL = "4", GROK_WORKER_MAX_CONCURRENT = "4", '
            'GROK_WORKER_TIMEOUT = "%s" }\n'
            % (
                esc(server_cmd[0]),
                args_toml,
                esc(str(worker_results)),
                esc(str(ROOT)),
                LIVE_TIMEOUT,
            )
        )
        (home / "config.toml").write_text(config, encoding="utf-8")
        env = os.environ.copy()
        env["GROK_HOME"] = str(home)
        prompt = (
            "Use search_tool then use_tool to call dispatch_grok_worker once with "
            "wait=true and prompt: Return exactly JSON "
            '{"probe":"from_worker","ok":true,"marker":"GROK-MCP"} with no markdown. '
            "Then return exactly JSON "
            '{"probe":"mcp_grok","ok":true,"marker":"GROK-MCP"}.'
        )
        argv = [
            "grok",
            "-p",
            prompt,
            "--output-format",
            "streaming-json",
            "--max-turns",
            "25",
            "--permission-mode",
            "bypassPermissions",
            "--always-approve",
            "--tools",
            "read_file,grep,list_dir,search_tool,use_tool",
            "--disallowed-tools",
            "run_terminal_command,write,open_page,web_search,web_fetch",
            "--disable-web-search",
            "-m",
            MODEL,
        ]
        code, stdout, stderr, elapsed = run_subprocess(
            argv, cwd=ROOT, env=env, timeout=LIVE_TIMEOUT + 120
        )
        (out_dir / "stdout.jsonl").write_text(stdout, encoding="utf-8")
        (out_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        (out_dir / "config.toml").write_text(config, encoding="utf-8")
        text_parts: List[str] = []
        tool_names: List[str] = []
        available = _available_tools_from_stream(stdout)
        use_tool_failed = False
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "text" and isinstance(event.get("data"), str):
                text_parts.append(event["data"])
            if event.get("type") == "tool_call" and event.get("toolName"):
                tool_names.append(str(event["toolName"]))
            if (
                event.get("type") == "tool_call_update"
                and event.get("status") == "failed"
            ):
                use_tool_failed = True
        combined = "".join(text_parts)
        worker_files = sorted(p.name for p in worker_results.iterdir())
        allowlist_safe = "run_terminal_command" not in available
        ok = (
            allowlist_safe
            and bool(worker_files)
            and not use_tool_failed
        )
        return {
            "probe": "mcp_grok",
            "status": "pass" if ok else "fail",
            "returncode": code,
            "elapsed_seconds": elapsed,
            "available_tools": available,
            "allowlist_safe": allowlist_safe,
            "tool_names": tool_names,
            "use_tool_failed": use_tool_failed,
            "text_prefix": combined[:500],
            "worker_files": worker_files,
            "server_cmd": server_cmd,
            "permission_mode": "bypassPermissions",
            "stderr_prefix": stderr[:500],
            "note": (
                "session GROK_HOME only; user config not modified; "
                "dontAsk cannot call MCP use_tool"
            ),
        }


def probe_mcp_codex(
    run_dir: Path,
    *,
    bypass_approvals_and_sandbox: bool = True,
    approval_policy: str = "never",
) -> Dict[str, Any]:
    if shutil.which("codex") is None:
        return {"probe": "mcp_codex", "status": "skip", "reason": "codex not on PATH"}
    # The green gate is deliberately the externally-contained, headless mode
    # recommended by Codex for automation.  The paired restricted probe below
    # retains the approval-cancellation diagnosis as a regression check.
    probe_name = "mcp_codex" if bypass_approvals_and_sandbox else "mcp_codex_restricted"
    if approval_policy != "never" and not bypass_approvals_and_sandbox:
        probe_name += "_" + approval_policy.replace("-", "_")
    out_dir = run_dir / probe_name
    out_dir.mkdir(parents=True, exist_ok=True)
    worker_results = out_dir / "workers"
    worker_results.mkdir(exist_ok=True)
    server_cmd = mcp_server_command()
    env = os.environ.copy()
    env["GROK_WORKER_RESULTS_DIR"] = str(worker_results)
    env["GROK_WORKER_CWD"] = str(ROOT)
    env["GROK_WORKER_MAX_TOTAL"] = "4"
    prompt = (
        "Use the MCP tool dispatch_grok_worker exactly once with wait=true "
        'and prompt Return JSON {"probe":"from_worker","ok":true,"marker":"CODEX-MCP"}. '
        "Final answer: one JSON object "
        '{"probe":"mcp_codex","ok":true|false}.'
    )
    # Session-scoped MCP via -c; format is version-sensitive.
    cmd_json = json.dumps(server_cmd[0])
    args_json = json.dumps(server_cmd[1:])
    env_toml = "{" + ", ".join(
        "%s=%s" % (key, json.dumps(value)) for key, value in sorted(env.items())
        if key.startswith("GROK_WORKER_")
    ) + "}"
    mcp_toml = (
        "{command=%s, args=%s, env=%s, enabled=true}"
        % (cmd_json, args_json, env_toml)
    )
    argv = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "-m",
        "gpt-5.6-sol",
    ]
    if bypass_approvals_and_sandbox:
        # Codex currently couples noninteractive MCP approval to this bypass
        # flag. This probe is confined by its exact prompt and a session-only
        # MCP server; the dispatched Grok worker itself is strictly read-only.
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        argv.extend(
            ["--sandbox", "read-only", "-c", 'approval_policy="%s"' % approval_policy]
        )
    argv.extend(
        [
            "-c",
            "mcp_servers.grok_workers=%s" % mcp_toml,
            "--json",
            prompt,
        ]
    )
    try:
        code, stdout, stderr, elapsed = run_subprocess(
            argv, cwd=ROOT, env=env, timeout=LIVE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return {
            "probe": probe_name,
            "status": "fail",
            "reason": "timeout",
        }
    (out_dir / "stdout.jsonl").write_text(stdout, encoding="utf-8")
    (out_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    worker_files = sorted(p.name for p in worker_results.iterdir())
    dispatch_events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if (
            isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
            and item.get("server") == "grok_workers"
            and item.get("tool") == "dispatch_grok_worker"
        ):
            dispatch_events.append(item)
    completed_dispatches = [
        item
        for item in dispatch_events
        if item.get("status") == "completed" and item.get("error") is None
    ]
    # Require an accepted client call *and* two persisted worker streams. This
    # rejects false greens where Codex merely proposed or cancelled the tool.
    ok = len(completed_dispatches) == 1 and len(worker_files) >= 2
    return {
        "probe": probe_name,
        "status": "pass" if ok else "fail",
        "returncode": code,
        "elapsed_seconds": elapsed,
        "worker_files": worker_files,
        "dispatch_event_count": len(dispatch_events),
        "completed_dispatch_count": len(completed_dispatches),
        "server_cmd": server_cmd,
        "bypass_approvals_and_sandbox": bypass_approvals_and_sandbox,
        "approval_policy": approval_policy,
        "stderr_prefix": stderr[:500],
        "stdout_prefix": stdout[:500],
        "note": "hard gate requires one accepted MCP dispatch and worker artifacts",
    }


def probe_controller_codex(run_dir: Path) -> Dict[str, Any]:
    """Live safe-controller acceptance: two Codex decisions, two workers."""
    if shutil.which("codex") is None or shutil.which("grok") is None:
        return {
            "probe": "controller_codex",
            "status": "skip",
            "reason": "codex or grok not on PATH",
        }
    out_dir = run_dir / "controller_codex"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pure-tate-controller-probe-") as directory:
        context = Path(directory)
        write_json(context / "TASK.json", {"phase": "research", "id": "CONTROLLER-SMOKE"})
        session = prepare_worker_session(
            context,
            family="openai",
            max_workers=4,
            allow_web=False,
            worker_timeout=LIVE_TIMEOUT,
            parent_meta={"engine": "codex", "task_id": "CONTROLLER-SMOKE", "worker_mode": "controller"},
            dispatch_log_dir=out_dir / "dispatch-log",
            session_id="SESS-controller-smoke",
            attach_mcp=False,
        )
        if session is None:
            return {"probe": "controller_codex", "status": "skip", "reason": "worker session unavailable"}
        task = {"id": "CONTROLLER-SMOKE", "phase": "research", "prompt": "CLI_test/CODEX_CONTROLLER_SMOKE.md"}
        try:
            _run_codex_controller(
                task=task,
                context=context,
                context_files=["TASK.json"],
                expected_artifact_id="CONTROLLER-SMOKE",
                phase="research",
                workers=session,
                settings={
                    "max_requests": 3,
                    "retry_limit": 1,
                    "max_attempts": 4,
                    "max_result_chars": 12000,
                },
                task_timeout=LIVE_TIMEOUT,
                inactivity=None,
                abort_patterns=None,
                activity_streams=["stdout"],
                progress_callback=None,
            )
            final = (context / "last-message.txt").read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return {"probe": "controller_codex", "status": "fail", "error": str(exc)}
        events_path = out_dir / "dispatch-log" / "sessions" / "SESS-controller-smoke" / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        completed = [
            event for event in events
            if event.get("event") == "controller_worker_finished" and event.get("status") == "completed"
        ]
        worker_files = sorted(path.name for path in session.results_dir.iterdir())
        try:
            final_value = json.loads(final)
        except json.JSONDecodeError:
            final_value = {}
        ok = (
            len(completed) == 2
            and len(worker_files) >= 4
            and final_value.get("id") == "CONTROLLER-SMOKE"
            and final_value.get("controller_smoke") is True
        )
        return {
            "probe": "controller_codex",
            "status": "pass" if ok else "fail",
            "completed_workers": len(completed),
            "worker_files": worker_files,
            "events_path": str(events_path),
            "final": final,
            "note": "Codex has no MCP attachment; harness dispatches workers directly.",
        }


def probe_mcp_gemini(run_dir: Path) -> Dict[str, Any]:
    if shutil.which("gemini") is None:
        return {"probe": "mcp_gemini", "status": "skip", "reason": "gemini not on PATH"}
    out_dir = run_dir / "mcp_gemini"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Gemini MCP is usually project/user configured. Avoid writing global settings.
    # Document best-effort: skip if no session flag for ephemeral MCP.
    return {
        "probe": "mcp_gemini",
        "status": "skip",
        "reason": (
            "no safe session-scoped MCP inject without writing user/project "
            "gemini settings; document for harness follow-up"
        ),
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    global MODEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=MODEL,
        help="Grok model slug for argv and live probes (default: %s)" % MODEL,
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run only offline unit probes (no Grok API).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live API probes (default unless --offline).",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only named probes (repeatable).",
    )
    args = parser.parse_args(argv)
    MODEL = args.model
    run_live = args.live or not args.offline
    if args.offline:
        run_live = False

    run_id = timestamp_slug()
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (RESULTS_ROOT / "latest.txt").write_text(run_id + "\n", encoding="utf-8")

    offline_probes = [
        ("pool_unit_cap", probe_pool_unit_cap),
        ("mcp_unit_roundtrip", probe_mcp_unit_roundtrip),
        ("worker_argv_shape", probe_worker_argv_shape),
        ("worker_continue_turns", lambda: probe_worker_continue_turns(run_dir)),
    ]
    live_probes = [
        ("worker_smoke", lambda: probe_worker_smoke(run_dir)),
        ("worker_single_cap", lambda: probe_worker_single_cap(run_dir)),
        ("allowlist_safety", lambda: probe_allowlist_safety(run_dir)),
        ("native_spawn_optional", lambda: probe_native_spawn_optional(run_dir)),
        ("mcp_claude", lambda: probe_mcp_claude(run_dir)),
        ("mcp_grok", lambda: probe_mcp_grok(run_dir)),
        ("mcp_codex", lambda: probe_mcp_codex(run_dir)),
        ("controller_codex", lambda: probe_controller_codex(run_dir)),
        (
            "mcp_codex_restricted",
            lambda: probe_mcp_codex(run_dir, bypass_approvals_and_sandbox=False),
        ),
        (
            "mcp_codex_on_failure",
            lambda: probe_mcp_codex(run_dir, approval_policy="on-failure"),
        ),
        ("mcp_gemini", lambda: probe_mcp_gemini(run_dir)),
    ]

    selected = set(args.only)
    results: List[Dict[str, Any]] = []

    def want(name: str) -> bool:
        return not selected or name in selected

    print("run_id=%s" % run_id)
    for name, fn in offline_probes:
        if not want(name):
            continue
        print(">> %s" % name, flush=True)
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            result = {"probe": name, "status": "fail", "error": str(exc)}
        results.append(result)
        write_json(run_dir / ("%s.json" % name), result)
        print("   %s" % result.get("status"), flush=True)

    if run_live:
        for name, fn in live_probes:
            if not want(name):
                continue
            print(">> %s" % name, flush=True)
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                result = {"probe": name, "status": "fail", "error": str(exc)}
            results.append(result)
            write_json(run_dir / ("%s.json" % name), result)
            print("   %s" % result.get("status"), flush=True)

    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "model": MODEL,
        "executed_at": utc_now_iso(),
        "live": run_live,
        "results": [
            {"probe": r.get("probe"), "status": r.get("status")} for r in results
        ],
        "pass_count": sum(1 for r in results if r.get("status") == "pass"),
        "fail_count": sum(1 for r in results if r.get("status") == "fail"),
        "skip_count": sum(1 for r in results if r.get("status") == "skip"),
    }
    write_json(run_dir / "manifest.json", summary)
    print(json.dumps(summary, indent=2))
    # Gate offline always must pass.
    offline_failed = [
        r
        for r in results
        if r.get("probe")
        in {"pool_unit_cap", "mcp_unit_roundtrip", "worker_argv_shape"}
        and r.get("status") != "pass"
    ]
    return 1 if offline_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
