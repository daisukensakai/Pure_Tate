#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path

RUNDIR = Path(__file__).resolve().parent


def status_of() -> str | None:
    log = RUNDIR / "CLAUDE-P1.claude.console.log"
    if not log.is_file():
        return None
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
            print("LIU-AUDIT-P1 %s" % status, flush=True)
            return 0 if status == "DONE" else 1
        time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
