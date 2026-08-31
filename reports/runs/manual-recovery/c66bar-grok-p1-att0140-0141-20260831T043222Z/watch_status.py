#!/usr/bin/env python3
"""Emit one DONE/FAILED line per review; exit when both finish."""
from __future__ import annotations

import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNDIR = Path(__file__).resolve().parent
CELLS = [
    ("C66BAR-GRAPH", "REV-0189"),
    ("C58-BOUNDARY", "REV-0190"),
]


def status_of(rev: str) -> str | None:
    log = RUNDIR / ("%s.grok.console.log" % rev)
    output = ROOT / "proof" / "reviews" / ("%s.json" % rev)
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
    seen = {}
    while len(seen) < len(CELLS):
        for cell, rev in CELLS:
            if cell in seen:
                continue
            status = status_of(rev)
            if status:
                seen[cell] = status
                print("%s %s" % (cell, status), flush=True)
        if len(seen) < len(CELLS):
            time.sleep(15)
    return 0 if all(v == "DONE" for v in seen.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
