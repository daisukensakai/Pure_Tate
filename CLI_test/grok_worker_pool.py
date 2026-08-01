#!/usr/bin/env python3
"""Hard-capped Grok 4.5 worker pool for CLI_test (not imported by pure_tate).

Caps (hard):
  - max_concurrent: simultaneous live workers (default 4)
  - max_total: lifetime dispatches per pool session (default 4)

Workers are headless `grok -p` processes with a read-only tool allowlist and
`--no-subagents`. Nothing here mutates user Grok config.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


DEFAULT_MODEL = "grok-4.5"
DEFAULT_MAX_CONCURRENT = 4
DEFAULT_MAX_TOTAL = 4
DEFAULT_MAX_TURNS = 20
DEFAULT_TIMEOUT_SECONDS = 300


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
        }
        if include_result:
            payload["result_text"] = self.result_text
        return payload


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def build_worker_argv(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    allow_web: bool = False,
    cwd: Optional[Path] = None,
) -> List[str]:
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
    if "-p" in out:
        idx = out.index("-p")
        if idx + 1 < len(out):
            out[idx + 1] = marker
    return out


def extract_result_text(stdout: str) -> str:
    """Prefer headless json envelope `.text`; else raw stdout."""
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


class GrokWorkerPool:
    """Thread-safe pool with hard concurrent and total dispatch caps."""

    def __init__(
        self,
        *,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        max_total: int = DEFAULT_MAX_TOTAL,
        model: str = DEFAULT_MODEL,
        max_turns: int = DEFAULT_MAX_TURNS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        allow_web: bool = False,
        work_dir: Optional[Path] = None,
        results_dir: Optional[Path] = None,
        runner: Optional[Callable[..., WorkerRecord]] = None,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        if max_total < 1:
            raise ValueError("max_total must be >= 1")
        self.max_concurrent = max_concurrent
        self.max_total = max_total
        self.model = model
        self.max_turns = max_turns
        self.timeout_seconds = timeout_seconds
        self.allow_web = allow_web
        self.work_dir = work_dir
        self.results_dir = results_dir
        if self.results_dir is not None:
            self.results_dir.mkdir(parents=True, exist_ok=True)
        self._runner = runner
        self._lock = threading.RLock()
        self._workers: Dict[str, WorkerRecord] = {}
        self._dispatched = 0
        self._live = 0
        self._threads: Dict[str, threading.Thread] = {}

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
            return {
                "max_concurrent": self.max_concurrent,
                "max_total": self.max_total,
                "dispatched": self._dispatched,
                "live": self._live,
                "remaining_total": max(0, self.max_total - self._dispatched),
                "remaining_concurrent": max(0, self.max_concurrent - self._live),
                "model": self.model,
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
        with self._lock:
            if self._dispatched >= self.max_total:
                raise PoolError(
                    "budget_exhausted",
                    "worker budget exhausted: max_total=%d already dispatched=%d"
                    % (self.max_total, self._dispatched),
                )
            if self._live >= self.max_concurrent:
                raise PoolError(
                    "pool_full",
                    "worker pool full: max_concurrent=%d live=%d"
                    % (self.max_concurrent, self._live),
                )
            worker_id = "W-%s" % uuid.uuid4().hex[:12]
            record = WorkerRecord(
                worker_id=worker_id,
                description=description,
                prompt_sha256=sha256_text(prompt),
                status="queued",
                created_at=utc_now_iso(),
            )
            self._workers[worker_id] = record
            self._dispatched += 1
            self._live += 1

        if self._runner is not None:
            # Deterministic offline / unit-test path (synchronous).
            try:
                finished = self._runner(
                    prompt=prompt,
                    description=description,
                    worker_id=worker_id,
                    pool=self,
                )
                with self._lock:
                    self._workers[worker_id] = finished
                    self._live = max(0, self._live - 1)
                return finished.public_dict()
            except Exception as exc:  # noqa: BLE001 — surface to caller
                with self._lock:
                    record.status = "failed"
                    record.error = str(exc)
                    record.finished_at = utc_now_iso()
                    self._live = max(0, self._live - 1)
                raise

        thread = threading.Thread(
            target=self._run_worker,
            args=(worker_id, prompt, timeout_seconds),
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
        return record.public_dict(include_result=False)

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
        return self.get_worker(worker_id).public_dict()

    def _run_worker(
        self,
        worker_id: str,
        prompt: str,
        timeout_seconds: Optional[int],
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
        )
        started = time.monotonic()
        with self._lock:
            record = self._workers[worker_id]
            record.status = "running"
            record.started_at = utc_now_iso()
            record.argv_redacted = redact_argv(argv, prompt)

        stdout_path = None
        stderr_path = None
        if self.results_dir is not None:
            stdout_path = self.results_dir / ("%s.stdout.txt" % worker_id)
            stderr_path = self.results_dir / ("%s.stderr.txt" % worker_id)

        try:
            process = subprocess.Popen(
                argv,
                cwd=str(self.work_dir) if self.work_dir else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=os.environ.copy(),
            )
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
                    record.elapsed_seconds = round(time.monotonic() - started, 3)
                    record.finished_at = utc_now_iso()
                    if stdout_path is not None:
                        stdout_path.write_text(stdout or "", encoding="utf-8")
                        record.stdout_path = str(stdout_path)
                    if stderr_path is not None:
                        stderr_path.write_text(stderr or "", encoding="utf-8")
                        record.stderr_path = str(stderr_path)
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
                    record.elapsed_seconds = round(time.monotonic() - started, 3)
                    if stdout_path is not None:
                        record.stdout_path = str(stdout_path)
                    if stderr_path is not None:
                        record.stderr_path = str(stderr_path)
                    return
                record.returncode = process.returncode
                record.result_text = extract_result_text(stdout or "")
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
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                record = self._workers[worker_id]
                record.status = "failed"
                record.error = str(exc)
                record.finished_at = utc_now_iso()
                record.elapsed_seconds = round(time.monotonic() - started, 3)
        finally:
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
