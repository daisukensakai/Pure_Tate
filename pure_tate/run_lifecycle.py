"""Crash-safe campaign leases, stale-run recovery, and artifact reservations.

Artifact ID policy (mandatory):
- Every live dispatch reserves a fresh, never-before-used ID.
- Existing on-disk proof artifacts are never rewritten.
- IDs used by files, active reservations, spent markers, run-ledger outputs,
  recoverable traces, or the recovery ledger are never reissued.
- After a paid turn produces a trace, the reserved ID is permanently spent even
  if validation fails and no artifact file is written.
- Reattempts of the same task must reserve a different slot.
- Recover unpaid validation failures from the official trace before paying for
  another run of the same work.
"""

from __future__ import annotations

import datetime
import errno
import fcntl
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .store import ROOT, atomic_write_json


RUN_LEDGER_DIR = ROOT / "reports" / "runs"
LOCK_DIR = RUN_LEDGER_DIR / "locks"
RESERVATION_DIR = RUN_LEDGER_DIR / "reservations"
RECOVERY_LEDGER_PATH = ROOT / "proof" / "paired-recoveries.json"


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


def _prefix_pattern(prefix: str) -> re.Pattern[str]:
    return re.compile(re.escape(prefix) + r"-(\d{4})$")


def _add_prefixed_id(numbers: Set[int], prefix: str, value: Any) -> None:
    if not isinstance(value, str):
        return
    match = _prefix_pattern(prefix).fullmatch(Path(value).stem)
    if match:
        numbers.add(int(match.group(1)))


def claimed_prefixed_numbers(directory: Path, prefix: str) -> Set[int]:
    """Every number that must never be reissued for this prefix."""
    numbers: Set[int] = set()
    pattern = _prefix_pattern(prefix)
    if directory.is_dir():
        for path in directory.glob(prefix + "-*.json"):
            match = pattern.fullmatch(path.stem)
            if match:
                numbers.add(int(match.group(1)))
    if RESERVATION_DIR.is_dir():
        for path in RESERVATION_DIR.glob(prefix + "-*.json"):
            match = pattern.fullmatch(path.stem)
            if match:
                numbers.add(int(match.group(1)))
    if RUN_LEDGER_DIR.is_dir():
        for path in RUN_LEDGER_DIR.glob("RUN-*.json"):
            try:
                ledger = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(ledger, dict):
                continue
            for event in ledger.get("events", []):
                if not isinstance(event, dict):
                    continue
                _add_prefixed_id(numbers, prefix, event.get("output"))
                _add_prefixed_id(numbers, prefix, event.get("attempt_id"))
                _add_prefixed_id(numbers, prefix, event.get("review_id"))
    if RECOVERY_LEDGER_PATH.is_file():
        try:
            ledger = json.loads(RECOVERY_LEDGER_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ledger = {}
        for receipt in ledger.get("recoveries", []) if isinstance(ledger, dict) else []:
            if not isinstance(receipt, dict):
                continue
            _add_prefixed_id(numbers, prefix, receipt.get("artifact_id"))
            _add_prefixed_id(numbers, prefix, receipt.get("artifact_path"))
    return numbers


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
    """Mark ledgers abandoned when their recorded parent no longer exists.

    Active (non-spent) reservations owned by the dead run are released. Spent
    reservations are permanent ID claims and are never deleted.
    """
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
            if not isinstance(record, dict) or record.get("run_id") != run_id:
                continue
            # A paid turn that already produced a trace must keep its slot.
            if record.get("status") == "spent" or record.get("trace_id"):
                if record.get("status") != "spent":
                    spend_artifact_reservation(
                        reservation,
                        reason="parent_process_missing",
                        trace_id=str(record.get("trace_id") or "") or None,
                        task_id=str(record.get("task_id") or "") or None,
                    )
                continue
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
    """Atomically reserve the next never-before-used prefixed artifact ID.

    Reattempts always receive a different slot: numbers already claimed by
    on-disk artifacts, reservations (active or spent), historical run ledgers,
    recovery receipts, or trace-linked artifact IDs are skipped permanently.
    """
    directory.mkdir(parents=True, exist_ok=True)
    RESERVATION_DIR.mkdir(parents=True, exist_ok=True)
    claimed = claimed_prefixed_numbers(directory, prefix)
    number = (max(claimed) if claimed else 0) + 1
    while True:
        while number in claimed:
            number += 1
        artifact_id = "%s-%04d" % (prefix, number)
        reservation = RESERVATION_DIR / (artifact_id + ".json")
        # Refuse to reserve a path that already has durable work on disk.
        if (directory / (artifact_id + ".json")).exists():
            claimed.add(number)
            number += 1
            continue
        try:
            descriptor = os.open(
                str(reservation), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
        except FileExistsError:
            claimed.add(number)
            number += 1
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "artifact_id": artifact_id,
                    "run_id": run_id,
                    "status": "reserved",
                    "reserved_at": _timestamp(),
                    "target_directory": str(directory.relative_to(ROOT)),
                },
                handle,
                sort_keys=True,
            )
            handle.write("\n")
        return artifact_id, reservation


def spend_artifact_reservation(
    path: Optional[Path],
    *,
    reason: str,
    trace_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None:
    """Permanently retire a reserved ID so reattempts cannot reuse the slot."""
    if path is None:
        return
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        record = {"artifact_id": path.stem}
    if not isinstance(record, dict):
        record = {"artifact_id": path.stem}
    record["status"] = "spent"
    record["spent_at"] = _timestamp()
    record["reason"] = reason
    if trace_id:
        record["trace_id"] = trace_id
    if task_id:
        record["task_id"] = task_id
    atomic_write_json(path, record)


def release_artifact_reservation(path: Optional[Path]) -> None:
    """Drop an active reservation after the on-disk artifact owns the ID.

    Spent reservations are permanent claims and are never deleted.
    """
    if path is None:
        return
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, json.JSONDecodeError):
        record = {}
    if isinstance(record, dict) and record.get("status") == "spent":
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
