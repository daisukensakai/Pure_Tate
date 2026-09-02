#!/usr/bin/env python3
"""Hard-capped Grok 4.5 worker pool and session-scoped MCP attachment.

Caps (hard):
  - max_concurrent: simultaneous live workers (default 1)
  - max_total: worker identities per pool session (default 1)
  - max_worker_turns: conversational turns on that identity (default 4)

Turn 1 is ``dispatch``; turns 2–4 are ``continue_worker`` resumes that keep
prior worker context so follow-ups stay short (redo / more info / gap-fill /
narrow sub-task) without re-ingesting principal parent context.

Workers are headless ``cursor-agent -p`` / ``grok -p`` processes with a
read-only tool allowlist. Parents attach via MCP (never native
spawn_subagent in Grok ``--tools`` — that collapses the allowlist).

This module is also an MCP server entrypoint::

    uv run --with mcp python pure_tate/grok_workers.py --serve-mcp
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


DEFAULT_MODEL = "grok-4.5"
DEFAULT_CURSOR_MODEL = "cursor-grok-4.5-high"
DEFAULT_WORKER_BACKEND = "cursor"
DEFAULT_MAX_CONCURRENT = 1
DEFAULT_MAX_TOTAL = 1
DEFAULT_MAX_WORKER_TURNS = 4
# Intra-process tool-loop cap for the xAI ``grok -p`` backend (not resume turns).
DEFAULT_MAX_TURNS = 20
DEFAULT_TIMEOUT_SECONDS = 1200

# Repo root (pure_tate/..) — durable logs live under research/worker-dispatches/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DISPATCH_LOG_DIR = _REPO_ROOT / "research" / "worker-dispatches"


class PoolError(RuntimeError):
    """Structured pool failure (cap, unknown id, etc.)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": False, "error_code": self.code, "error": self.message}


@dataclass
class WorkerRecord:
    worker_id: str
    description: str
    prompt_sha256: str
    status: str  # queued | running | completed | failed | cancelled | rejected
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    returncode: Optional[int] = None
    result_text: str = ""
    error: str = ""
    elapsed_seconds: Optional[float] = None
    argv_redacted: List[str] = field(default_factory=list)
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    turn_index: int = 1
    max_turns: int = DEFAULT_MAX_WORKER_TURNS
    cli_session_id: Optional[str] = None
    turns: List[Dict[str, Any]] = field(default_factory=list)
    process: Optional[subprocess.Popen] = field(default=None, repr=False)

    def public_dict(self, include_result: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ok": self.status in {"completed"},
            "worker_id": self.worker_id,
            "description": self.description,
            "prompt_sha256": self.prompt_sha256,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "returncode": self.returncode,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error or None,
            "argv": self.argv_redacted,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "turn_index": self.turn_index,
            "max_turns": self.max_turns,
            "remaining_turns": max(0, self.max_turns - self.turn_index),
            "cli_session_id": self.cli_session_id,
            "turns": list(self.turns),
        }
        if include_result:
            payload["result_text"] = self.result_text
        return payload


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolve_worker_backend(config_root: Optional[Dict[str, Any]] = None) -> str:
    """Return worker backend: ``cursor`` (default) or ``xai``."""
    env = (os.environ.get("GROK_WORKER_BACKEND") or "").strip().lower()
    if env in {"cursor", "xai", "grok"}:
        return "xai" if env == "grok" else env
    if isinstance(config_root, dict):
        raw = str(config_root.get("grok_worker_backend") or "").strip().lower()
        if raw in {"cursor", "xai", "grok"}:
            return "xai" if raw == "grok" else raw
    return DEFAULT_WORKER_BACKEND


def resolve_worker_model(
    config_root: Optional[Dict[str, Any]] = None,
    *,
    backend: Optional[str] = None,
) -> str:
    """Return the worker model slug for the active backend."""
    env_model = (os.environ.get("GROK_WORKER_MODEL") or "").strip()
    if env_model:
        return env_model
    selected = backend or resolve_worker_backend(config_root)
    if isinstance(config_root, dict):
        configured = str(config_root.get("grok_worker_model") or "").strip()
        if configured:
            return configured
        engines = config_root.get("engines")
        if isinstance(engines, dict):
            if selected == "cursor":
                cursor = engines.get("cursor-grok")
                if isinstance(cursor, dict) and cursor.get("model"):
                    return str(cursor["model"])
            grok = engines.get("grok")
            if isinstance(grok, dict) and grok.get("model"):
                return str(grok["model"])
    return DEFAULT_CURSOR_MODEL if selected == "cursor" else DEFAULT_MODEL


def worker_backend_available(backend: str) -> bool:
    """Whether the local machine can run the selected worker backend."""
    if backend == "cursor":
        return (
            shutil.which("cursor-agent") is not None
            and bool(os.environ.get("CURSOR_API_KEY", "").strip())
        )
    return shutil.which("grok") is not None


def build_cursor_worker_argv(
    prompt: str,
    *,
    model: str = DEFAULT_CURSOR_MODEL,
    cwd: Optional[Path] = None,
    allow_web: bool = False,
    resume_session_id: Optional[str] = None,
) -> List[str]:
    # CLI_test/CURSOR_WEB_FINDINGS.md: --mode ask alone rejects WebFetch
    # ("User Rejected"). --force auto-approves permitted tools; keep ask so
    # workers stay write-blocked. Without allow_web, omit --force so network
    # tools remain denied by approval.
    argv = [
        "cursor-agent",
        "-p",
        "--trust",
        "--mode",
        "ask",
    ]
    if allow_web:
        argv.append("--force")
    argv.extend(
        [
            "--output-format",
            "json",
            "--model",
            model,
        ]
    )
    if resume_session_id:
        argv.extend(["--resume", str(resume_session_id)])
    if cwd is not None:
        argv.extend(["--workspace", str(cwd)])
    argv.append(prompt)
    return argv


def build_worker_argv(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    allow_web: bool = False,
    cwd: Optional[Path] = None,
    backend: str = "xai",
    resume_session_id: Optional[str] = None,
) -> List[str]:
    if backend == "cursor":
        return build_cursor_worker_argv(
            prompt,
            model=model,
            cwd=cwd,
            allow_web=allow_web,
            resume_session_id=resume_session_id,
        )
    if resume_session_id:
        raise PoolError(
            "resume_unavailable",
            "xAI grok worker backend does not support resume turns",
        )
    tools = ["read_file", "grep", "list_dir"]
    denied = ["run_terminal_command", "write", "open_page"]
    if allow_web:
        tools.extend(["web_search", "web_fetch"])
    else:
        denied.extend(["web_search", "web_fetch"])
    argv = [
        "grok",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--max-turns",
        str(max_turns),
        "--permission-mode",
        "dontAsk",
        "--always-approve",
        "--no-subagents",
        "--tools",
        ",".join(tools),
        "--disallowed-tools",
        ",".join(denied),
    ]
    if not allow_web:
        argv.append("--disable-web-search")
    argv.extend(["-m", model])
    if cwd is not None:
        argv.extend(["--cwd", str(cwd)])
    return argv


def redact_argv(argv: Sequence[str], prompt: str) -> List[str]:
    out = list(argv)
    marker = "<prompt-sha256:%s>" % sha256_text(prompt)
    for index, value in enumerate(out):
        if value == prompt:
            out[index] = marker
    return out


def extract_result_text(stdout: str) -> str:
    """Prefer headless json envelope `.text` / `.result`; else raw stdout."""
    stripped = stdout.strip()
    if not stripped:
        return ""
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
        result = value.get("result")
        if isinstance(result, str):
            return result
    return stripped


def extract_cli_session_id(stdout: str) -> Optional[str]:
    """Return the Cursor/agent ``session_id`` from a JSON envelope, if any."""
    stripped = (stdout or "").strip()
    if not stripped:
        return None
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    session_id = value.get("session_id")
    if isinstance(session_id, str) and session_id.strip():
        return session_id.strip()
    return None


class DispatchLog:
    """Durable, append-only dispatch log (survives temp agent workspaces)."""

    def __init__(
        self,
        root: Optional[Path] = None,
        *,
        session_id: Optional[str] = None,
        parent: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.root = Path(root) if root is not None else DEFAULT_DISPATCH_LOG_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or (
            "SESS-%s" % uuid.uuid4().hex[:12]
        )
        self.parent = dict(parent or {})
        self.session_dir = self.root / "sessions" / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "workers").mkdir(exist_ok=True)
        self.global_events = self.root / "events.jsonl"
        self.session_events = self.session_dir / "events.jsonl"
        self._lock = threading.Lock()
        # A parent process may reopen this session after it exits to append
        # client-side MCP telemetry. Preserve the original metadata then.
        if not (self.session_dir / "session.json").exists():
            self._write_session_meta()
        self._touch_latest()

    def _write_session_meta(self) -> None:
        meta = {
            "schema_version": 1,
            "session_id": self.session_id,
            "created_at": utc_now_iso(),
            "parent": self.parent,
            "log_dir": str(self.session_dir),
        }
        path = self.session_dir / "session.json"
        path.write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _touch_latest(self) -> None:
        try:
            (self.root / "latest.txt").write_text(
                self.session_id + "\n", encoding="utf-8"
            )
        except OSError:
            pass

    def log(self, event_type: str, **fields: Any) -> Dict[str, Any]:
        event: Dict[str, Any] = {
            "schema_version": 1,
            "event": event_type,
            "session_id": self.session_id,
            "logged_at": utc_now_iso(),
        }
        if self.parent:
            event["parent"] = self.parent
        for key, value in fields.items():
            if value is not None:
                event[key] = value
        line = json.dumps(event, sort_keys=True, default=str) + "\n"
        with self._lock:
            for path in (self.global_events, self.session_events):
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
        return event

    def persist_worker_output(
        self,
        worker_id: str,
        stdout: str,
        stderr: str,
    ) -> Dict[str, str]:
        """Copy worker stdout/stderr into the durable session folder."""
        workers = self.session_dir / "workers"
        workers.mkdir(parents=True, exist_ok=True)
        stdout_path = workers / ("%s.stdout.txt" % worker_id)
        stderr_path = workers / ("%s.stderr.txt" % worker_id)
        stdout_path.write_text(stdout or "", encoding="utf-8")
        stderr_path.write_text(stderr or "", encoding="utf-8")
        return {
            "durable_stdout_path": str(stdout_path.relative_to(self.root)),
            "durable_stderr_path": str(stderr_path.relative_to(self.root)),
        }


def default_dispatch_log_dir() -> Path:
    raw = os.environ.get("GROK_WORKER_LOG_DIR")
    if raw:
        return Path(raw)
    return DEFAULT_DISPATCH_LOG_DIR


def ensure_dispatch_log_dir(path: Optional[Path] = None) -> Path:
    directory = Path(path) if path is not None else default_dispatch_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    readme = directory / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# Grok worker dispatch logs\n\n"
            "Durable logs of optional Grok 4.5 worker dispatches from Pure Tate "
            "agent runs. Temp task workspaces are deleted after each run; this "
            "folder is not.\n\n"
            "- `events.jsonl` — global append-only event stream\n"
            "- `sessions/<SESS-id>/session.json` — parent task metadata\n"
            "- `sessions/<SESS-id>/events.jsonl` — per-parent-session events\n"
            "- `sessions/<SESS-id>/workers/` — durable worker stdout/stderr\n"
            "- `latest.txt` — most recent session id\n",
            encoding="utf-8",
        )
    return directory


class GrokWorkerPool:
    """Thread-safe pool with hard concurrent, identity, and turn caps."""

    def __init__(
        self,
        *,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        max_total: int = DEFAULT_MAX_TOTAL,
        max_worker_turns: int = DEFAULT_MAX_WORKER_TURNS,
        model: str = DEFAULT_MODEL,
        max_turns: int = DEFAULT_MAX_TURNS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        allow_web: bool = False,
        backend: str = DEFAULT_WORKER_BACKEND,
        work_dir: Optional[Path] = None,
        results_dir: Optional[Path] = None,
        dispatch_log: Optional[DispatchLog] = None,
        runner: Optional[Callable[..., WorkerRecord]] = None,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        if max_total < 1:
            raise ValueError("max_total must be >= 1")
        if max_worker_turns < 1:
            raise ValueError("max_worker_turns must be >= 1")
        self.max_concurrent = max_concurrent
        self.max_total = max_total
        self.max_worker_turns = max_worker_turns
        self.model = model
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self.allow_web = allow_web
        self.backend = "cursor" if backend == "cursor" else "xai"
        self.work_dir = work_dir
        self.results_dir = results_dir
        if self.results_dir is not None:
            self.results_dir.mkdir(parents=True, exist_ok=True)
        self.dispatch_log = dispatch_log
        self._runner = runner
        self._lock = threading.RLock()
        self._workers: Dict[str, WorkerRecord] = {}
        self._dispatched = 0
        self._live = 0
        self._threads: Dict[str, threading.Thread] = {}

    def _log(self, event_type: str, **fields: Any) -> None:
        if self.dispatch_log is None:
            return
        try:
            self.dispatch_log.log(event_type, **fields)
        except OSError:
            # Logging must never fail a worker dispatch.
            pass

    @property
    def dispatched_count(self) -> int:
        with self._lock:
            return self._dispatched

    @property
    def live_count(self) -> int:
        with self._lock:
            return self._live

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            active = None
            turns_used = 0
            for record in self._workers.values():
                active = record.worker_id
                turns_used = record.turn_index
            return {
                "max_concurrent": self.max_concurrent,
                "max_total": self.max_total,
                "max_worker_turns": self.max_worker_turns,
                "dispatched": self._dispatched,
                "live": self._live,
                "remaining_total": max(0, self.max_total - self._dispatched),
                "remaining_concurrent": max(0, self.max_concurrent - self._live),
                "active_worker_id": active,
                "turns_used": turns_used,
                "remaining_turns": (
                    max(0, self.max_worker_turns - turns_used) if active else self.max_worker_turns
                ),
                "model": self.model,
                "backend": self.backend,
            }

    def list_workers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                record.public_dict(include_result=False)
                for record in self._workers.values()
            ]

    def get_worker(self, worker_id: str) -> WorkerRecord:
        with self._lock:
            if worker_id not in self._workers:
                raise PoolError("unknown_worker", "unknown worker_id %s" % worker_id)
            return self._workers[worker_id]

    def _reclaim_failed_non_resumable(self) -> None:
        """Drop a sole failed turn-1 worker with no session so dispatch can retry."""
        if self._live > 0 or len(self._workers) != 1:
            return
        worker_id, record = next(iter(self._workers.items()))
        if (
            record.status in {"failed", "cancelled"}
            and not record.cli_session_id
            and record.turn_index <= 1
        ):
            del self._workers[worker_id]
            self._dispatched = 0

    def dispatch(
        self,
        prompt: str,
        description: str = "",
        *,
        wait: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise PoolError("invalid_prompt", "prompt must be a non-empty string")
        description = (description or "").strip() or "grok-worker"
        prompt_digest = sha256_text(prompt)
        with self._lock:
            self._reclaim_failed_non_resumable()
            if self._dispatched >= self.max_total:
                self._log(
                    "dispatch_rejected",
                    error_code="budget_exhausted",
                    description=description,
                    prompt_sha256=prompt_digest,
                    dispatched=self._dispatched,
                    live=self._live,
                    max_total=self.max_total,
                    max_concurrent=self.max_concurrent,
                )
                raise PoolError(
                    "budget_exhausted",
                    "worker budget exhausted: max_total=%d already dispatched=%d"
                    % (self.max_total, self._dispatched),
                )
            if self._live >= self.max_concurrent:
                self._log(
                    "dispatch_rejected",
                    error_code="pool_full",
                    description=description,
                    prompt_sha256=prompt_digest,
                    dispatched=self._dispatched,
                    live=self._live,
                    max_total=self.max_total,
                    max_concurrent=self.max_concurrent,
                )
                raise PoolError(
                    "pool_full",
                    "worker pool full: max_concurrent=%d live=%d"
                    % (self.max_concurrent, self._live),
                )
            worker_id = "W-%s" % uuid.uuid4().hex[:12]
            record = WorkerRecord(
                worker_id=worker_id,
                description=description,
                prompt_sha256=prompt_digest,
                status="queued",
                created_at=utc_now_iso(),
                turn_index=1,
                max_turns=self.max_worker_turns,
                turns=[
                    {
                        "turn": 1,
                        "prompt_sha256": prompt_digest,
                        "description": description,
                        "status": "queued",
                    }
                ],
            )
            self._workers[worker_id] = record
            self._dispatched += 1
            self._live += 1

        self._log(
            "dispatch",
            worker_id=worker_id,
            description=description,
            prompt_sha256=prompt_digest,
            status="queued",
            wait=bool(wait),
            turn=1,
            model=self.model,
            backend=self.backend,
            allow_web=self.allow_web,
            dispatched=self._dispatched,
            live=self._live,
            max_total=self.max_total,
            max_concurrent=self.max_concurrent,
            max_worker_turns=self.max_worker_turns,
        )

        return self._launch_turn(
            worker_id,
            prompt,
            wait=wait,
            timeout_seconds=timeout_seconds,
            resume_session_id=None,
        )

    def continue_worker(
        self,
        worker_id: str,
        prompt: str,
        description: str = "",
        *,
        wait: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resume an existing worker with a short follow-up (turns 2..N)."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise PoolError("invalid_prompt", "prompt must be a non-empty string")
        description = (description or "").strip() or "grok-worker-continue"
        prompt_digest = sha256_text(prompt)
        with self._lock:
            record = self.get_worker(worker_id)
            if record.status in {"queued", "running"}:
                raise PoolError(
                    "pool_full",
                    "worker %s is still live (status=%s)" % (worker_id, record.status),
                )
            if record.turn_index >= record.max_turns:
                self._log(
                    "continue_rejected",
                    error_code="turns_exhausted",
                    worker_id=worker_id,
                    turn_index=record.turn_index,
                    max_turns=record.max_turns,
                )
                raise PoolError(
                    "turns_exhausted",
                    "worker turn budget exhausted: turn_index=%d max_turns=%d"
                    % (record.turn_index, record.max_turns),
                )
            if self.backend != "cursor":
                raise PoolError(
                    "resume_unavailable",
                    "worker backend %s does not support resume turns" % self.backend,
                )
            if not record.cli_session_id:
                raise PoolError(
                    "resume_unavailable",
                    "worker %s has no resumable cli_session_id" % worker_id,
                )
            if self._live >= self.max_concurrent:
                raise PoolError(
                    "pool_full",
                    "worker pool full: max_concurrent=%d live=%d"
                    % (self.max_concurrent, self._live),
                )
            resume_session_id = record.cli_session_id
            next_turn = record.turn_index + 1
            record.turn_index = next_turn
            record.description = description
            record.prompt_sha256 = prompt_digest
            record.status = "queued"
            record.started_at = None
            record.finished_at = None
            record.returncode = None
            record.result_text = ""
            record.error = ""
            record.elapsed_seconds = None
            record.process = None
            record.turns.append(
                {
                    "turn": next_turn,
                    "prompt_sha256": prompt_digest,
                    "description": description,
                    "status": "queued",
                }
            )
            self._live += 1
            turn_for_log = next_turn
            session_for_log = resume_session_id

        self._log(
            "continue",
            worker_id=worker_id,
            description=description,
            prompt_sha256=prompt_digest,
            status="queued",
            wait=bool(wait),
            turn=turn_for_log,
            cli_session_id=session_for_log,
            model=self.model,
            backend=self.backend,
        )
        return self._launch_turn(
            worker_id,
            prompt,
            wait=wait,
            timeout_seconds=timeout_seconds,
            resume_session_id=session_for_log,
        )

    def _launch_turn(
        self,
        worker_id: str,
        prompt: str,
        *,
        wait: bool,
        timeout_seconds: Optional[int],
        resume_session_id: Optional[str],
    ) -> Dict[str, Any]:
        record = self.get_worker(worker_id)
        if self._runner is not None:
            try:
                finished = self._runner(
                    prompt=prompt,
                    description=record.description,
                    worker_id=worker_id,
                    pool=self,
                    turn=record.turn_index,
                    resume_session_id=resume_session_id,
                )
                with self._lock:
                    # Preserve identity/turn metadata the runner may omit.
                    finished.worker_id = worker_id
                    finished.turn_index = record.turn_index
                    finished.max_turns = record.max_turns
                    finished.turns = list(record.turns)
                    if finished.cli_session_id is None:
                        finished.cli_session_id = record.cli_session_id
                    if finished.turns:
                        finished.turns[-1] = {
                            **finished.turns[-1],
                            "status": finished.status,
                            "result_preview": (finished.result_text or "")[:200],
                        }
                    self._workers[worker_id] = finished
                    self._live = max(0, self._live - 1)
                self._log(
                    "worker_finished",
                    worker_id=worker_id,
                    status=finished.status,
                    returncode=finished.returncode,
                    error=finished.error or None,
                    elapsed_seconds=finished.elapsed_seconds,
                    turn=finished.turn_index,
                    cli_session_id=finished.cli_session_id,
                    result_text_preview=(finished.result_text or "")[:500],
                )
                return finished.public_dict()
            except TypeError:
                # Legacy runners used in older tests accept only the original kwargs.
                finished = self._runner(
                    prompt=prompt,
                    description=record.description,
                    worker_id=worker_id,
                    pool=self,
                )
                with self._lock:
                    finished.worker_id = worker_id
                    finished.turn_index = record.turn_index
                    finished.max_turns = record.max_turns
                    finished.turns = list(record.turns)
                    if finished.cli_session_id is None:
                        finished.cli_session_id = record.cli_session_id
                    self._workers[worker_id] = finished
                    self._live = max(0, self._live - 1)
                self._log(
                    "worker_finished",
                    worker_id=worker_id,
                    status=finished.status,
                    returncode=finished.returncode,
                    error=finished.error or None,
                    elapsed_seconds=finished.elapsed_seconds,
                    turn=finished.turn_index,
                    cli_session_id=finished.cli_session_id,
                    result_text_preview=(finished.result_text or "")[:500],
                )
                return finished.public_dict()
            except Exception as exc:  # noqa: BLE001 — surface to caller
                with self._lock:
                    record.status = "failed"
                    record.error = str(exc)
                    record.finished_at = utc_now_iso()
                    if record.turns:
                        record.turns[-1]["status"] = "failed"
                    self._live = max(0, self._live - 1)
                self._log(
                    "worker_finished",
                    worker_id=worker_id,
                    status="failed",
                    error=str(exc),
                    turn=record.turn_index,
                )
                raise

        thread = threading.Thread(
            target=self._run_worker,
            args=(worker_id, prompt, timeout_seconds, resume_session_id),
            name="grok-worker-%s" % worker_id,
            daemon=True,
        )
        with self._lock:
            self._threads[worker_id] = thread
        thread.start()
        if wait:
            return self.await_worker(
                worker_id, timeout_seconds=timeout_seconds
            )
        return self.get_worker(worker_id).public_dict(include_result=False)

    def await_worker(
        self,
        worker_id: str,
        *,
        timeout_seconds: Optional[int] = None,
        poll_interval: float = 0.1,
    ) -> Dict[str, Any]:
        deadline = None
        if timeout_seconds is not None:
            deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while True:
            record = self.get_worker(worker_id)
            if record.status in {"completed", "failed", "cancelled", "rejected"}:
                return record.public_dict()
            if deadline is not None and time.monotonic() >= deadline:
                raise PoolError(
                    "await_timeout",
                    "timed out waiting for worker %s (status=%s)"
                    % (worker_id, record.status),
                )
            time.sleep(poll_interval)

    def cancel_worker(self, worker_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self.get_worker(worker_id)
            if record.status in {"completed", "failed", "cancelled", "rejected"}:
                return record.public_dict()
            process = record.process
            record.status = "cancelled"
            record.error = "cancelled by parent"
            record.finished_at = utc_now_iso()
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    process.terminate()
                except OSError:
                    pass
        with self._lock:
            if self._live > 0 and worker_id in self._workers:
                # Only decrement if still counted live.
                if self._workers[worker_id].status == "cancelled":
                    # Idempotent: live may already be reduced by runner finish.
                    pass
            # Recompute live from statuses for safety.
            self._live = sum(
                1
                for item in self._workers.values()
                if item.status in {"queued", "running"}
            )
        self._log(
            "worker_finished",
            worker_id=worker_id,
            status="cancelled",
            error="cancelled by parent",
        )
        return self.get_worker(worker_id).public_dict()

    def _finalize_worker_log(
        self,
        worker_id: str,
        *,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        record = self.get_worker(worker_id)
        durable_paths: Dict[str, str] = {}
        if self.dispatch_log is not None:
            try:
                durable_paths = self.dispatch_log.persist_worker_output(
                    worker_id, stdout, stderr
                )
            except OSError:
                durable_paths = {}
        self._log(
            "worker_finished",
            worker_id=worker_id,
            description=record.description,
            prompt_sha256=record.prompt_sha256,
            status=record.status,
            returncode=record.returncode,
            error=record.error or None,
            elapsed_seconds=record.elapsed_seconds,
            argv=record.argv_redacted,
            turn=record.turn_index,
            cli_session_id=record.cli_session_id,
            result_text_preview=(record.result_text or "")[:500],
            **durable_paths,
        )

    def _run_worker(
        self,
        worker_id: str,
        prompt: str,
        timeout_seconds: Optional[int],
        resume_session_id: Optional[str] = None,
    ) -> None:
        timeout = (
            self.timeout_seconds
            if timeout_seconds is None
            else int(timeout_seconds)
        )
        argv = build_worker_argv(
            prompt,
            model=self.model,
            max_turns=self.max_turns,
            allow_web=self.allow_web,
            cwd=self.work_dir,
            backend=self.backend,
            resume_session_id=resume_session_id,
        )
        started = time.monotonic()
        with self._lock:
            record = self._workers[worker_id]
            record.status = "running"
            record.started_at = utc_now_iso()
            record.argv_redacted = redact_argv(argv, prompt)
            if record.turns:
                record.turns[-1]["status"] = "running"
        self._log(
            "worker_started",
            worker_id=worker_id,
            description=record.description,
            prompt_sha256=record.prompt_sha256,
            status="running",
            argv=record.argv_redacted,
            turn=record.turn_index,
            cli_session_id=resume_session_id or record.cli_session_id,
            model=self.model,
            backend=self.backend,
        )

        stdout_path = None
        stderr_path = None
        if self.results_dir is not None:
            # Unique per turn so continues do not overwrite prior stdout.
            turn_tag = "t%d" % record.turn_index
            stdout_path = self.results_dir / (
                "%s.%s.stdout.txt" % (worker_id, turn_tag)
            )
            stderr_path = self.results_dir / (
                "%s.%s.stderr.txt" % (worker_id, turn_tag)
            )

        stdout = ""
        stderr = ""
        supervisor_status_fd: Optional[int] = None
        try:
            supervisor = Path(__file__).with_name("process_supervisor.py").resolve()
            supervisor_status_fd = os.open(os.devnull, os.O_WRONLY)
            supervised_argv = [
                sys.executable,
                str(supervisor),
                "--parent-pid",
                str(os.getpid()),
                "--status-fd",
                str(supervisor_status_fd),
                "--",
            ] + argv
            process = subprocess.Popen(
                supervised_argv,
                cwd=str(self.work_dir) if self.work_dir else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=os.environ.copy(),
                pass_fds=(supervisor_status_fd,),
            )
            os.close(supervisor_status_fd)
            supervisor_status_fd = None
            with self._lock:
                self._workers[worker_id].process = process
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    process.kill()
                stdout, stderr = process.communicate(timeout=5)
                with self._lock:
                    record = self._workers[worker_id]
                    record.status = "failed"
                    record.returncode = process.returncode
                    record.error = "worker timed out after %ss" % timeout
                    record.result_text = extract_result_text(stdout or "")
                    session_id = extract_cli_session_id(stdout or "")
                    if session_id:
                        record.cli_session_id = session_id
                    record.elapsed_seconds = round(time.monotonic() - started, 3)
                    record.finished_at = utc_now_iso()
                    if record.turns:
                        record.turns[-1]["status"] = "failed"
                    if stdout_path is not None:
                        stdout_path.write_text(stdout or "", encoding="utf-8")
                        record.stdout_path = str(stdout_path)
                    if stderr_path is not None:
                        stderr_path.write_text(stderr or "", encoding="utf-8")
                        record.stderr_path = str(stderr_path)
                self._finalize_worker_log(
                    worker_id, stdout=stdout or "", stderr=stderr or ""
                )
                return

            if stdout_path is not None:
                stdout_path.write_text(stdout or "", encoding="utf-8")
            if stderr_path is not None:
                stderr_path.write_text(stderr or "", encoding="utf-8")

            with self._lock:
                record = self._workers[worker_id]
                if record.status == "cancelled":
                    record.returncode = process.returncode
                    record.result_text = extract_result_text(stdout or "")
                    session_id = extract_cli_session_id(stdout or "")
                    if session_id:
                        record.cli_session_id = session_id
                    record.elapsed_seconds = round(time.monotonic() - started, 3)
                    if stdout_path is not None:
                        record.stdout_path = str(stdout_path)
                    if stderr_path is not None:
                        record.stderr_path = str(stderr_path)
                    # cancel_worker already logged finished; still persist output.
                    if self.dispatch_log is not None:
                        try:
                            self.dispatch_log.persist_worker_output(
                                worker_id, stdout or "", stderr or ""
                            )
                        except OSError:
                            pass
                    return
                record.returncode = process.returncode
                record.result_text = extract_result_text(stdout or "")
                session_id = extract_cli_session_id(stdout or "")
                if session_id:
                    record.cli_session_id = session_id
                record.elapsed_seconds = round(time.monotonic() - started, 3)
                record.finished_at = utc_now_iso()
                if stdout_path is not None:
                    record.stdout_path = str(stdout_path)
                if stderr_path is not None:
                    record.stderr_path = str(stderr_path)
                if process.returncode == 0:
                    record.status = "completed"
                    record.error = ""
                else:
                    record.status = "failed"
                    record.error = (stderr or stdout or "worker failed")[:1000]
                if record.turns:
                    record.turns[-1] = {
                        **record.turns[-1],
                        "status": record.status,
                        "result_preview": (record.result_text or "")[:200],
                        "cli_session_id": record.cli_session_id,
                    }
            self._finalize_worker_log(
                worker_id, stdout=stdout or "", stderr=stderr or ""
            )
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                record = self._workers[worker_id]
                record.status = "failed"
                record.error = str(exc)
                record.finished_at = utc_now_iso()
                record.elapsed_seconds = round(time.monotonic() - started, 3)
                if record.turns:
                    record.turns[-1]["status"] = "failed"
            self._finalize_worker_log(
                worker_id, stdout=stdout or "", stderr=stderr or ""
            )
        finally:
            if supervisor_status_fd is not None:
                os.close(supervisor_status_fd)
            with self._lock:
                self._live = sum(
                    1
                    for item in self._workers.values()
                    if item.status in {"queued", "running"}
                )
                self._threads.pop(worker_id, None)

    def shutdown(self, *, cancel_live: bool = True) -> None:
        with self._lock:
            ids = [
                wid
                for wid, rec in self._workers.items()
                if rec.status in {"queued", "running"}
            ]
        if cancel_live:
            for worker_id in ids:
                try:
                    self.cancel_worker(worker_id)
                except PoolError:
                    pass
        threads = []
        with self._lock:
            threads = list(self._threads.values())
        for thread in threads:
            thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# Harness session attachment
# ---------------------------------------------------------------------------

WORKER_FAMILIES = frozenset({"claude", "grok", "cursor", "openai", "qwen"})
MCP_SERVER_NAME = "grok-workers"
CLAUDE_MCP_TOOLS = [
    "mcp__grok-workers__dispatch_grok_worker",
    "mcp__grok-workers__continue_grok_worker",
    "mcp__grok-workers__await_grok_worker",
    "mcp__grok-workers__list_grok_workers",
    "mcp__grok-workers__cancel_grok_worker",
    "mcp__grok-workers__worker_pool_stats",
]


@dataclass
class WorkerSession:
    """Session-scoped Grok worker MCP attachment for one parent agent run."""

    enabled: bool
    max_workers: int
    allow_web: bool
    family: str
    results_dir: Path
    mcp_config_path: Optional[Path] = None
    grok_home: Optional[Path] = None
    env_updates: Dict[str, str] = field(default_factory=dict)
    server_command: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    max_worker_turns: int = DEFAULT_MAX_WORKER_TURNS
    dispatch_log: Optional[DispatchLog] = field(default=None, repr=False)

    def prompt_contract(self) -> str:
        return worker_dispatch_parent_policy(
            self.max_workers, max_worker_turns=self.max_worker_turns
        )


def worker_dispatch_parent_policy(
    max_workers: int,
    max_worker_turns: int = DEFAULT_MAX_WORKER_TURNS,
) -> str:
    """Shared parent/controller policy for all Grok worker dispatches.

    The parent is the mastermind (thinking, analysis, critical decisions).
    One worker identity may be continued for short follow-ups; re-reading
    sources a worker already covered is forbidden token waste.
    """
    if max_workers <= 1:
        identity = (
            "That single worker may run up to %d conversational turns "
            "(turn 1 = dispatch; turns 2–%d = continue_grok_worker). "
            "A second worker identity is rejected. "
            % (max_worker_turns, max_worker_turns)
        )
        noun = "worker"
    else:
        identity = (
            "Each worker may run up to %d conversational turns "
            "(turn 1 = dispatch; turns 2–%d = continue_grok_worker). "
            "Those %d worker identities may run in parallel. "
            "A further worker identity is rejected. "
            % (max_worker_turns, max_worker_turns, max_workers)
        )
        noun = "workers"
    return (
        "Optional Grok helpers: you may dispatch at most %d read-only Grok "
        "%s via the grok-workers MCP tools "
        "(dispatch_grok_worker, continue_grok_worker, await_grok_worker, "
        "list_grok_workers, worker_pool_stats). %sWorkers "
        "share this isolated workspace and cannot write files or run shell "
        "commands. Do not nest further workers inside workers.\n\n"
        "Worker-dispatch policy (you are the mastermind):\n"
        "- Keep strategic thinking, analysis, critical choices, and the "
        "final artifact on the parent.\n"
        "- First dispatch: one narrow task plus path/ID pointers — not a dump "
        "of the packet or working context you already hold.\n"
        "- Continues: keep them short and easy — a redo with clearer "
        "constraints, ask-for-more / missing locator, gap-fill critique, or "
        "one new narrow sub-task. One ask per continue. Do not use continues "
        "for complex or open-ended proof work; do that yourself.\n"
        "- Do not re-read or re-fetch sources a worker already covered just "
        "to re-skim the raw text — that wastes tokens. Treat worker reports "
        "as your reading layer; analyze, critique, select, and decide from "
        "them. Spot-check only when a load-bearing claim is contested or "
        "the worker report is incomplete or incoherent.\n"
        "- Workers are assistive only — you must still return exactly one "
        "final JSON artifact yourself and remain responsible for every "
        "load-bearing step."
        % (max_workers, noun, identity)
    )


def max_grok_workers_from_config(config_root: Dict[str, Any]) -> int:
    """Return hard worker-identity budget from engines.json (default 1)."""
    if config_root.get("grok_workers_enabled") is False:
        return 0
    raw = config_root.get("max_grok_workers", DEFAULT_MAX_TOTAL)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_TOTAL
    return max(0, min(value, DEFAULT_MAX_TOTAL))


def max_worker_turns_from_config(config_root: Dict[str, Any]) -> int:
    """Return conversational turn budget per worker identity (default 4)."""
    raw = config_root.get("max_worker_turns", DEFAULT_MAX_WORKER_TURNS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_WORKER_TURNS
    return max(1, min(value, 8))


def mcp_server_command() -> List[str]:
    """Command vector to launch this module as an MCP stdio server."""
    script = str(Path(__file__).resolve())
    uv = shutil.which("uv")
    if uv:
        # Keep MCP startup independent of the repository project and of uv's
        # user cache.  The latter can be inaccessible inside an engine's
        # sandbox (notably when it contains uv's internal .git marker).
        return [
            uv,
            "run",
            "--no-project",
            "--with",
            "mcp",
            "python",
            script,
            "--serve-mcp",
        ]
    return [sys.executable, script, "--serve-mcp"]


def _link_or_copy(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(src, dest)
    except OSError:
        if src.is_file():
            shutil.copy2(src, dest)


def prepare_worker_session(
    context: Path,
    *,
    family: str,
    max_workers: int,
    allow_web: bool = False,
    worker_model: str = DEFAULT_MODEL,
    worker_timeout: int = DEFAULT_TIMEOUT_SECONDS,
    worker_backend: Optional[str] = None,
    parent_meta: Optional[Dict[str, Any]] = None,
    dispatch_log_dir: Optional[Path] = None,
    session_id: Optional[str] = None,
    attach_mcp: bool = True,
    max_worker_turns: int = DEFAULT_MAX_WORKER_TURNS,
) -> Optional[WorkerSession]:
    """Build session-scoped MCP config for a parent engine family.

    Returns None when workers are disabled or the family is unsupported.
    Never mutates the user's ~/.grok/config.toml.

    Durable dispatch logs are written under ``research/worker-dispatches/``
    (or ``dispatch_log_dir`` / ``GROK_WORKER_LOG_DIR``).
    """
    family = str(family or "")
    if max_workers <= 0 or family not in WORKER_FAMILIES:
        return None
    backend = worker_backend or resolve_worker_backend()
    if backend not in {"cursor", "xai"}:
        backend = DEFAULT_WORKER_BACKEND
    if not worker_backend_available(backend):
        return None

    results_dir = context / "grok-workers"
    results_dir.mkdir(parents=True, exist_ok=True)
    log_root = ensure_dispatch_log_dir(dispatch_log_dir)
    sid = session_id or ("SESS-%s" % uuid.uuid4().hex[:12])
    parent = dict(parent_meta or {})
    # Write session shell immediately so the folder exists even if no worker is
    # ever dispatched (useful when auditing "available but unused").
    session_log = DispatchLog(log_root, session_id=sid, parent=parent)
    turns = max(1, int(max_worker_turns))
    session_log.log(
        "session_open",
        family=family,
        max_workers=max_workers,
        max_worker_turns=turns,
        allow_web=allow_web,
        worker_model=worker_model,
        worker_backend=backend,
    )

    server_cmd = mcp_server_command()
    worker_env = {
        "GROK_WORKER_RESULTS_DIR": str(results_dir),
        "GROK_WORKER_CWD": str(context),
        "GROK_WORKER_MAX_CONCURRENT": str(max_workers),
        "GROK_WORKER_MAX_TOTAL": str(max_workers),
        "GROK_WORKER_MAX_TURNS": str(turns),
        "GROK_WORKER_TIMEOUT": str(worker_timeout),
        "GROK_WORKER_MODEL": worker_model,
        "GROK_WORKER_BACKEND": backend,
        "GROK_WORKER_ALLOW_WEB": "1" if allow_web else "0",
        "GROK_WORKER_LOG_DIR": str(log_root),
        "GROK_WORKER_SESSION_ID": sid,
        "GROK_WORKER_PARENT_JSON": json.dumps(parent, sort_keys=True),
        # MCP startup may run inside a stricter sandbox than the parent.  Use
        # a writable, non-user cache for uv rather than ~/.cache/uv.
        "UV_CACHE_DIR": str(
            Path(tempfile.gettempdir()) / "pure-tate-mcp-uv-cache"
        ),
    }
    cursor_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if backend == "cursor" and cursor_key:
        worker_env["CURSOR_API_KEY"] = cursor_key
    session = WorkerSession(
        enabled=True,
        max_workers=max_workers,
        allow_web=allow_web,
        family=family,
        results_dir=results_dir,
        server_command=server_cmd,
        env_updates=dict(worker_env),
        session_id=sid,
        max_worker_turns=turns,
        dispatch_log=session_log,
    )

    # Controller-mediated Codex workers run directly from the trusted harness,
    # so Codex never needs an approval-gated MCP attachment.
    if not attach_mcp:
        return session

    # Qwen is driven through the local API adapter rather than an MCP client.
    # The adapter consumes this session's environment and calls the same
    # hard-capped worker pool directly when the model selects ask_grok.
    if family == "qwen":
        return session

    if family == "claude":
        mcp_path = context / "grok-workers.mcp.json"
        mcp_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        MCP_SERVER_NAME: {
                            "command": server_cmd[0],
                            "args": server_cmd[1:],
                            "env": worker_env,
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        session.mcp_config_path = mcp_path
        return session

    if family == "cursor":
        # Cursor Agent loads MCP from <workspace>/.cursor/mcp.json.
        cursor_dir = context / ".cursor"
        cursor_dir.mkdir(parents=True, exist_ok=True)
        mcp_path = cursor_dir / "mcp.json"
        mcp_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        MCP_SERVER_NAME: {
                            "command": server_cmd[0],
                            "args": server_cmd[1:],
                            "env": worker_env,
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        session.mcp_config_path = mcp_path
        return session

    if family == "grok":
        real_home = Path(
            os.environ.get("GROK_HOME", Path.home() / ".grok")
        ).expanduser()
        grok_home = context / "grok-home"
        grok_home.mkdir(parents=True, exist_ok=True)
        for name in ("auth.json", "auth.json.lock", "models_cache.json"):
            _link_or_copy(real_home / name, grok_home / name)

        def esc(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', '\\"')

        args_toml = ", ".join('"%s"' % esc(part) for part in server_cmd[1:])
        env_items = ", ".join(
            '%s = "%s"' % (key, esc(val)) for key, val in worker_env.items()
        )
        config = (
            "# ephemeral pure-tate agent session — do not copy to user home\n"
            "[mcp_servers.grok_workers]\n"
            'command = "%s"\n'
            "args = [%s]\n"
            "enabled = true\n"
            "startup_timeout_sec = 90\n"
            "tool_timeout_sec = 1200\n"
            "env = { %s }\n"
            % (esc(server_cmd[0]), args_toml, env_items)
        )
        (grok_home / "config.toml").write_text(config, encoding="utf-8")
        session.grok_home = grok_home
        session.env_updates["GROK_HOME"] = str(grok_home)
        return session

    if family == "openai":
        # Best-effort: codex accepts -c mcp_servers.* overrides.
        mcp_path = context / "grok-workers.mcp.json"
        mcp_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "grok_workers": {
                            "command": server_cmd[0],
                            "args": server_cmd[1:],
                            "env": worker_env,
                        }
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        session.mcp_config_path = mcp_path
        return session

    return None


def apply_workers_to_argv(
    command: List[str],
    family: str,
    session: Optional[WorkerSession],
) -> List[str]:
    """Return a new argv with worker MCP attachment for supported families."""
    if session is None or not session.enabled:
        return list(command)
    out = list(command)
    if family == "claude":
        # Prefer bypassPermissions so MCP tools run headlessly; write/shell stay
        # disallowed via --disallowedTools.
        if "--permission-mode" in out:
            idx = out.index("--permission-mode")
            if idx + 1 < len(out):
                out[idx + 1] = "bypassPermissions"
        else:
            out.extend(["--permission-mode", "bypassPermissions"])
        # Insert MCP tools into the allowedTools list (variadic until next --).
        if "--allowedTools" in out:
            start = out.index("--allowedTools") + 1
            end = start
            while end < len(out) and not out[end].startswith("--"):
                end += 1
            allowed = out[start:end]
            for tool in CLAUDE_MCP_TOOLS:
                if tool not in allowed:
                    allowed.append(tool)
            out = out[:start] + allowed + out[end:]
        if session.mcp_config_path is not None:
            out.extend(
                [
                    "--mcp-config",
                    str(session.mcp_config_path),
                    "--strict-mcp-config",
                ]
            )
        return out

    if family == "grok":
        # MCP use_tool fails under dontAsk; keep strict read-only allowlist.
        if "--permission-mode" in out:
            idx = out.index("--permission-mode")
            if idx + 1 < len(out):
                out[idx + 1] = "bypassPermissions"
        if "--tools" in out:
            idx = out.index("--tools")
            tools = out[idx + 1].split(",") if idx + 1 < len(out) else []
            for extra in ("search_tool", "use_tool"):
                if extra not in tools:
                    tools.append(extra)
            out[idx + 1] = ",".join(tools)
        return out

    if family == "cursor":
        # Approve the ephemeral workspace MCP servers without prompting.
        if "--approve-mcps" not in out:
            # Insert before the trailing prompt positional when present.
            insert_at = len(out)
            if out and not out[-1].startswith("-"):
                insert_at = len(out) - 1
            out = out[:insert_at] + ["--approve-mcps"] + out[insert_at:]
        return out

    if family == "openai" and session.server_command:
        # Best-effort Codex MCP override (may no-op on some versions).
        cmd_json = json.dumps(session.server_command[0])
        args_json = json.dumps(session.server_command[1:])
        # Codex does not reliably inherit the parent's environment when it
        # starts an MCP stdio child.  Put the session-scoped worker values in
        # the MCP definition itself so results and durable lifecycle logs stay
        # attached to the parent task.
        env_toml = "{" + ", ".join(
            "%s=%s" % (key, json.dumps(value))
            for key, value in sorted(session.env_updates.items())
        ) + "}"
        # Insert before the trailing prompt positional when present.
        override = (
            "{command=%s, args=%s, env=%s, enabled=true}"
            % (cmd_json, args_json, env_toml)
        )
        insert_at = len(out)
        # Prefer inserting before final prompt if last arg does not look like a flag.
        if out and not out[-1].startswith("-") and out[-1] != str(
            session.mcp_config_path or ""
        ):
            # Find -o last-message path pattern: prompt is last.
            insert_at = len(out) - 1
        out[insert_at:insert_at] = [
            "-c",
            "mcp_servers.grok_workers=%s" % override,
        ]
        return out

    return out


def merge_worker_env(
    base: Dict[str, str], session: Optional[WorkerSession]
) -> Dict[str, str]:
    env = dict(base)
    if session is not None and session.env_updates:
        env.update(session.env_updates)
    return env


def record_parent_mcp_events(session: Optional[WorkerSession], stdout: str) -> int:
    """Record engine-observed MCP calls that may never reach the server.

    Codex can cancel an MCP invocation in its approval layer before the server
    starts. The server-side log alone would mistake that for an unused tool.
    Prompts and complete model output are deliberately not retained here.
    """
    if session is None or not session.enabled or not stdout.strip():
        return 0
    log_dir = session.env_updates.get("GROK_WORKER_LOG_DIR")
    session_id = session.env_updates.get("GROK_WORKER_SESSION_ID")
    if not log_dir or not session_id:
        return 0
    try:
        log = DispatchLog(Path(log_dir), session_id=session_id)
    except OSError:
        return 0

    recorded = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if session.family == "openai":
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            if (
                item.get("type") != "mcp_tool_call"
                or item.get("server") not in {"grok_workers", MCP_SERVER_NAME}
            ):
                continue
            tool = str(item.get("tool") or "")
            if not tool.endswith("grok_worker") and tool != "worker_pool_stats":
                continue
            error = item.get("error")
            log.log(
                "parent_mcp_attempt",
                family=session.family,
                tool=tool,
                client_status=str(item.get("status") or event.get("type") or "unknown"),
                client_error=(
                    str(error.get("message") or error)
                    if isinstance(error, dict)
                    else (str(error) if error else None)
                ),
                client_result_present=item.get("result") is not None,
            )
            recorded += 1
        elif session.family == "claude":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = str(block.get("name") or "")
                if not name.startswith("mcp__grok-workers__"):
                    continue
                log.log(
                    "parent_mcp_attempt",
                    family=session.family,
                    tool=name.rsplit("__", 1)[-1],
                    client_status="started",
                )
                recorded += 1
    return recorded


# ---------------------------------------------------------------------------
# MCP server entry (stdlib pool + official mcp SDK)
# ---------------------------------------------------------------------------


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


def build_pool_from_env() -> GrokWorkerPool:
    parent: Dict[str, Any] = {}
    raw_parent = os.environ.get("GROK_WORKER_PARENT_JSON")
    if raw_parent:
        try:
            value = json.loads(raw_parent)
            if isinstance(value, dict):
                parent = value
        except json.JSONDecodeError:
            parent = {"parent_json_error": "invalid JSON in GROK_WORKER_PARENT_JSON"}
    # Individual env keys override / fill gaps.
    for env_key, field in (
        ("GROK_WORKER_PARENT_ENGINE", "engine"),
        ("GROK_WORKER_PARENT_PHASE", "phase"),
        ("GROK_WORKER_PARENT_TASK_ID", "task_id"),
        ("GROK_WORKER_PARENT_OUTPUT", "output"),
    ):
        raw = os.environ.get(env_key)
        if raw and field not in parent:
            parent[field] = raw

    log_dir = ensure_dispatch_log_dir(default_dispatch_log_dir())
    session_id = os.environ.get("GROK_WORKER_SESSION_ID") or None
    dispatch_log = DispatchLog(
        log_dir,
        session_id=session_id,
        parent=parent,
    )
    return GrokWorkerPool(
        max_concurrent=_env_int(
            "GROK_WORKER_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT
        ),
        max_total=_env_int("GROK_WORKER_MAX_TOTAL", DEFAULT_MAX_TOTAL),
        max_worker_turns=_env_int(
            "GROK_WORKER_MAX_TURNS", DEFAULT_MAX_WORKER_TURNS
        ),
        model=resolve_worker_model(backend=resolve_worker_backend()),
        timeout_seconds=_env_int(
            "GROK_WORKER_TIMEOUT", DEFAULT_TIMEOUT_SECONDS
        ),
        allow_web=_env_bool("GROK_WORKER_ALLOW_WEB", False),
        backend=resolve_worker_backend(),
        work_dir=_env_path("GROK_WORKER_CWD"),
        results_dir=_env_path("GROK_WORKER_RESULTS_DIR"),
        dispatch_log=dispatch_log,
    )


def serve_mcp() -> int:
    """Run the official MCP SDK stdio server for the worker pool."""
    from mcp.server import MCPServer
    import anyio

    pool = build_pool_from_env()
    mcp = MCPServer(
        name=MCP_SERVER_NAME,
        instructions=(
            "Hard-capped Grok worker pool. At most %d worker %s and %d "
            "conversational turns on each identity (dispatch + continue). "
            "Parents are masterminds; workers do targeted reading/extraction. "
            "Follow-ups must stay short (redo / more info / gap-fill / narrow "
            "sub-task) without re-dumping principal context."
            % (
                pool.max_total,
                "identity" if pool.max_total == 1 else "identities",
                pool.max_worker_turns,
            )
        ),
    )

    @mcp.tool()
    def dispatch_grok_worker(
        prompt: str,
        description: str = "",
        wait: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """Dispatch a read-only Grok worker (turn 1; pool-capped).

        Parent remains the mastermind. Give a narrow task with path/ID
        pointers — not a dump of packet/working context you already hold.
        Use continue_grok_worker for short follow-ups on the same worker.
        Parallel identities are allowed up to the pool's max_total.
        """
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
    def continue_grok_worker(
        worker_id: str,
        prompt: str,
        description: str = "",
        wait: bool = False,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """Continue the existing worker with a short follow-up (turns 2–N).

        Allowed: redo, ask-for-more, gap-fill critique, or one narrow new
        sub-task. Do not re-send principal packet/working context.
        """
        try:
            payload = pool.continue_worker(
                worker_id,
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
        anyio.run(mcp.run_stdio_async)
    finally:
        pool.shutdown(cancel_live=True)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--serve-mcp":
        return serve_mcp()
    print(
        "usage: python pure_tate/grok_workers.py --serve-mcp",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
