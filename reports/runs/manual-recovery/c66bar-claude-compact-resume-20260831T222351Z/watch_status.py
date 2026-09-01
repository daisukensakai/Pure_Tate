#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNDIR = Path(__file__).resolve().parent


def artifact_id() -> str:
    path = RUNDIR / "RESERVATION.json"
    if not path.is_file():
        return "UNKNOWN"
    return str(json.loads(path.read_text(encoding="utf-8")).get("artifact_id") or "UNKNOWN")


def status_of() -> str | None:
    att = artifact_id()
    output = ROOT / "proof" / "attempts" / ("%s.json" % att)
    receipt = RUNDIR / "RECEIPT.json"
    log = RUNDIR / ("%s.resume.console.log" % att)
    if receipt.is_file():
        record = json.loads(receipt.read_text(encoding="utf-8"))
        state = record.get("state")
        if state == "completed" and output.is_file():
            return "DONE"
        if state in {"failed", "completed"}:
            return "FAILED"
    if log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
        if "\nDONE\n" in text or text.endswith("\nDONE"):
            return "DONE"
        if "\nFAILED\n" in text or text.endswith("\nFAILED"):
            return "FAILED"
    return None


def main() -> int:
    while True:
        status = status_of()
        if status:
            print("%s %s" % (artifact_id(), status), flush=True)
            return 0 if status == "DONE" else 1
        time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
