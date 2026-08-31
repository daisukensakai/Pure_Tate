#!/usr/bin/env python3
"""Emit one DONE/FAILED line per cell; exit when all three finish."""
from __future__ import annotations

import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNDIR = Path(__file__).resolve().parent
CELLS = [
    ("C66BAR-GRAPH", "ATT-0137"),
    ("C58-OPEN", "ATT-0138"),
    ("C58-BOUNDARY", "ATT-0139"),
]


def status_of(att: str) -> str | None:
    log = RUNDIR / ("%s.codex.console.log" % att)
    output = ROOT / "proof" / "attempts" / ("%s.json" % att)
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
        for cell, att in CELLS:
            if cell in seen:
                continue
            status = status_of(att)
            if status:
                seen[cell] = status
                print("%s %s" % (cell, status), flush=True)
        if len(seen) < len(CELLS):
            time.sleep(15)
    return 0 if all(v == "DONE" for v in seen.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
