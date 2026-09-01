#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNDIR = Path(__file__).resolve().parent
REV = "REV-0195"
CELL = "C66BAR-SEP"


def status_of() -> str | None:
    log = RUNDIR / ("%s.codex.console.log" % REV)
    output = ROOT / "proof" / "reviews" / ("%s.json" % REV)
    if not log.is_file():
        return None
    text = log.read_text(encoding="utf-8", errors="replace")
    if "\nDONE\n" in text or text.endswith("\nDONE"):
        return "DONE"
    if "\nFAILED\n" in text or text.endswith("\nFAILED"):
        return "FAILED"
    if "EXIT:" in text:
        return "FAILED" if not output.is_file() else "DONE"
    return None


def main() -> int:
    while True:
        status = status_of()
        if status:
            print("%s %s" % (CELL, status), flush=True)
            return 0 if status == "DONE" else 1
        time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main())
