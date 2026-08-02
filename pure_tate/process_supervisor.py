"""Supervise one engine process and terminate it if the harness parent dies."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from typing import List, Optional


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def supervise(parent_pid: int, status_fd: int, command: List[str]) -> int:
    process = subprocess.Popen(command, start_new_session=True)
    try:
        payload = {
            "engine_pid": process.pid,
            "engine_process_group": process.pid,
            "supervisor_pid": os.getpid(),
            "supervisor_process_group": os.getpgrp(),
        }
        os.write(status_fd, (json.dumps(payload) + "\n").encode("utf-8"))
    finally:
        os.close(status_fd)

    interrupted: List[Optional[int]] = [None]

    def receive_signal(signum: int, _frame: object) -> None:
        interrupted[0] = signum

    previous = {}
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        previous[signum] = signal.signal(signum, receive_signal)
    try:
        while process.poll() is None:
            if interrupted[0] is not None:
                _terminate(process)
                return 128 + int(interrupted[0])
            if os.getppid() != parent_pid or not _alive(parent_pid):
                _terminate(process)
                return 125
            time.sleep(0.25)
        return int(process.returncode or 0)
    finally:
        _terminate(process)
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--status-fd", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("missing supervised command")
    return supervise(args.parent_pid, args.status_fd, command)


if __name__ == "__main__":
    raise SystemExit(main())
