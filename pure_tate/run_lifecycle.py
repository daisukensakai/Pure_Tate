"""Crash-safe campaign leases, stale-run recovery, and artifact reservations."""

from __future__ import annotations

import datetime
import errno
import fcntl
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .store import ROOT, atomic_write_json


RUN_LEDGER_DIR = ROOT / "reports" / "runs"
LOCK_DIR = RUN_LEDGER_DIR / "locks"
RESERVATION_DIR = RUN_LEDGER_DIR / "reservations"


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _safe_campaign_name(campaign_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", campaign_id)


def _pid_is_alive(pid: Optional[int]) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _ledger_parent_pid(ledger: Dict[str, Any], path: Path) -> Optional[int]:
    value = ledger.get("parent_pid")
    if isinstance(value, int) and value > 0:
        return value
    match = re.search(r"-(\d+)\.json$", path.name)
    return int(match.group(1)) if match else None


class CampaignAlreadyRunning(RuntimeError):
    pass


class CampaignRunLock:
    """An OS-released exclusive lease for one campaign drive."""

    def __init__(self, campaign_id: str) -> None:
        self.campaign_id = campaign_id
        self.path = LOCK_DIR / (_safe_campaign_name(campaign_id) + ".lock")
        self._handle: Optional[Any] = None

    def __enter__(self) -> "CampaignRunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.seek(0)
            detail = handle.read().strip()
            handle.close()
            if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                raise
            suffix = ": " + detail if detail else ""
            raise CampaignAlreadyRunning(
                "campaign %s already has an active drive%s"
                % (self.campaign_id, suffix)
            ) from exc
        metadata = {
            "campaign_id": self.campaign_id,
            "parent_pid": os.getpid(),
            "parent_process_group": os.getpgrp(),
            "acquired_at": _timestamp(),
        }
        handle.seek(0)
        handle.truncate()
        json.dump(metadata, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            self._handle.truncate()
            json.dump(
                {
                    "campaign_id": self.campaign_id,
                    "parent_pid": os.getpid(),
                    "released_at": _timestamp(),
                },
                self._handle,
                sort_keys=True,
            )
            self._handle.write("\n")
            self._handle.flush()
            os.fsync(self._handle.fileno())
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


def recover_stale_run_ledgers(campaign_id: str) -> List[str]:
    """Mark ledgers abandoned when their recorded parent no longer exists."""
    recovered: List[str] = []
    for path in sorted(RUN_LEDGER_DIR.glob("RUN-%s-*.json" % campaign_id)):
        try:
            ledger = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(ledger, dict) or ledger.get("status") != "running":
            continue
        parent_pid = _ledger_parent_pid(ledger, path)
        if _pid_is_alive(parent_pid):
            continue
        completed_at = _timestamp()
        for event in ledger.get("events", []):
            if isinstance(event, dict) and event.get("state") == "running":
                event["state"] = "abandoned"
                event["completed_at"] = completed_at
                event["error"] = "campaign parent process disappeared"
        ledger["status"] = "abandoned"
        ledger["stop_reason"] = "parent_process_missing"
        ledger["completed_at"] = completed_at
        ledger["executed_steps"] = len(ledger.get("events", []))
        atomic_write_json(path, ledger)
        run_id = str(ledger.get("run_id") or path.stem)
        recovered.append(run_id)
        for reservation in RESERVATION_DIR.glob("*.json"):
            try:
                record = json.loads(reservation.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(record, dict) and record.get("run_id") == run_id:
                try:
                    reservation.unlink()
                except FileNotFoundError:
                    pass
    return recovered


def live_run_ledgers(campaign_id: str) -> List[str]:
    """Return running ledgers whose recorded campaign parent still exists."""
    active: List[str] = []
    for path in sorted(RUN_LEDGER_DIR.glob("RUN-%s-*.json" % campaign_id)):
        try:
            ledger = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(ledger, dict) or ledger.get("status") != "running":
            continue
        if _pid_is_alive(_ledger_parent_pid(ledger, path)):
            active.append(str(ledger.get("run_id") or path.stem))
    return active


def reserve_prefixed_artifact(
    directory: Path, prefix: str, run_id: str
) -> Tuple[str, Path]:
    """Atomically reserve the next globally unique prefixed artifact ID."""
    directory.mkdir(parents=True, exist_ok=True)
    RESERVATION_DIR.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(re.escape(prefix) + r"-(\d{4})$")
    numbers: List[int] = []
    for path in directory.glob(prefix + "-*.json"):
        match = pattern.fullmatch(path.stem)
        if match:
            numbers.append(int(match.group(1)))
    for path in RESERVATION_DIR.glob(prefix + "-*.json"):
        match = pattern.fullmatch(path.stem)
        if match:
            numbers.append(int(match.group(1)))
    number = (max(numbers) if numbers else 0) + 1
    while True:
        artifact_id = "%s-%04d" % (prefix, number)
        reservation = RESERVATION_DIR / (artifact_id + ".json")
        try:
            descriptor = os.open(
                str(reservation), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
        except FileExistsError:
            number += 1
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "artifact_id": artifact_id,
                    "run_id": run_id,
                    "reserved_at": _timestamp(),
                    "target_directory": str(directory.relative_to(ROOT)),
                },
                handle,
                sort_keys=True,
            )
            handle.write("\n")
        return artifact_id, reservation


def release_artifact_reservation(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
