import os
import json
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ProcessWatchdogError(RuntimeError):
    def __init__(
        self,
        reason: str,
        elapsed_seconds: float,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__(
            "%s after %.1fs" % (reason, elapsed_seconds)
        )
        self.reason = reason
        self.elapsed_seconds = elapsed_seconds
        self.stdout = stdout
        self.stderr = stderr


def _terminate_process_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        # The supervisor first gives its engine group a graceful termination
        # window, then escalates.  Wait longer than that child-side window so
        # we do not kill the supervisor before it can deliver SIGKILL.
        process.wait(timeout=7)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=3)


def run_captured_process(
    command: List[str],
    cwd: Path,
    env: Dict[str, str],
    timeout: int,
    inactivity_timeout: Optional[int] = None,
    on_activity: Optional[Callable[[str, int, float], None]] = None,
    abort_stderr_pattern_counts: Optional[Dict[str, int]] = None,
    activity_streams: Optional[List[str]] = None,
    on_process_start: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> subprocess.CompletedProcess:
    started = time.monotonic()
    last_activity = started
    stdout_parts: List[bytes] = []
    stderr_parts: List[bytes] = []
    counted_streams = set(activity_streams or ("stdout", "stderr"))
    status_read, status_write = os.pipe()
    supervisor = Path(__file__).with_name("process_supervisor.py").resolve()
    wrapped_command = [
        sys.executable,
        str(supervisor),
        "--parent-pid",
        str(os.getpid()),
        "--status-fd",
        str(status_write),
        "--",
    ] + command
    process = subprocess.Popen(
        wrapped_command,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True,
        pass_fds=(status_write,),
    )
    os.close(status_write)
    process_meta: Dict[str, Any] = {
        "supervisor_pid": process.pid,
        "supervisor_process_group": process.pid,
    }
    status_selector = selectors.DefaultSelector()
    try:
        status_selector.register(status_read, selectors.EVENT_READ)
        if status_selector.select(5.0):
            raw_status = os.read(status_read, 4096).decode("utf-8", "replace")
            try:
                reported = json.loads(raw_status.strip().splitlines()[0])
            except (IndexError, json.JSONDecodeError):
                reported = {}
            if isinstance(reported, dict):
                process_meta.update(reported)
    finally:
        status_selector.close()
        os.close(status_read)
    if on_process_start is not None:
        on_process_start(process_meta)
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    assert process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    streams = {
        process.stdout: stdout_parts,
        process.stderr: stderr_parts,
    }
    try:
        while selector.get_map():
            now = time.monotonic()
            if now - started >= timeout:
                raise ProcessWatchdogError(
                    "total timeout",
                    now - started,
                    b"".join(stdout_parts).decode("utf-8", "replace"),
                    b"".join(stderr_parts).decode("utf-8", "replace"),
                )
            if (
                inactivity_timeout is not None
                and now - last_activity >= inactivity_timeout
            ):
                raise ProcessWatchdogError(
                    "inactivity timeout",
                    now - started,
                    b"".join(stdout_parts).decode("utf-8", "replace"),
                    b"".join(stderr_parts).decode("utf-8", "replace"),
                )
            waits = [1.0, max(0.01, timeout - (now - started))]
            if inactivity_timeout is not None:
                waits.append(
                    max(
                        0.01,
                        inactivity_timeout - (now - last_activity),
                    )
                )
            events = selector.select(min(waits))
            for key, _mask in events:
                stream = key.fileobj
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    selector.unregister(stream)
                    continue
                streams[stream].append(chunk)
                stream_name = str(key.data)
                if stream_name in counted_streams:
                    last_activity = time.monotonic()
                    if on_activity is not None:
                        on_activity(
                            stream_name,
                            len(chunk),
                            last_activity - started,
                        )
                if stream_name == "stderr" and abort_stderr_pattern_counts:
                    stderr_text = b"".join(stderr_parts).decode(
                        "utf-8", "replace"
                    )
                    for pattern, threshold in abort_stderr_pattern_counts.items():
                        if (
                            threshold > 0
                            and stderr_text.count(pattern) >= threshold
                        ):
                            raise ProcessWatchdogError(
                                "repeated stderr pattern %r" % pattern,
                                time.monotonic() - started,
                                b"".join(stdout_parts).decode(
                                    "utf-8", "replace"
                                ),
                                stderr_text,
                            )
        try:
            returncode = process.wait(timeout=3)
        except subprocess.TimeoutExpired as exc:
            raise ProcessWatchdogError(
                "process closed output streams without exiting",
                time.monotonic() - started,
                b"".join(stdout_parts).decode("utf-8", "replace"),
                b"".join(stderr_parts).decode("utf-8", "replace"),
            ) from exc
    except KeyboardInterrupt as exc:
        _terminate_process_group(process)
        raise ProcessWatchdogError(
            "interrupted",
            time.monotonic() - started,
            b"".join(stdout_parts).decode("utf-8", "replace"),
            b"".join(stderr_parts).decode("utf-8", "replace"),
        ) from exc
    except ProcessWatchdogError:
        _terminate_process_group(process)
        raise
    finally:
        selector.close()
        for stream in streams:
            stream.close()
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout=b"".join(stdout_parts).decode("utf-8", "replace"),
        stderr=b"".join(stderr_parts).decode("utf-8", "replace"),
    )
