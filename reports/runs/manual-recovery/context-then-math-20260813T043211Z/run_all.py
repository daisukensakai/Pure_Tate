#!/usr/bin/env python3
"""Context 3 parallel, then math 3 parallel. Fail-soft: math still runs if some context fails."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from pure_tate.notifications import send_desktop_notification, send_ntfy_notification_detailed
from pure_tate.store import ROOT

META = Path("/tmp/pure-tate-context-then-math-meta.json")

def notify(title, msg):
    print("desktop", send_desktop_notification(title, msg), flush=True)
    print("ntfy", send_ntfy_notification_detailed(title, msg), flush=True)

def run_phase(vault: Path, jobs):
    procs = []
    for job in jobs:
        aid = job["artifact_id"]
        p = subprocess.Popen(
            [sys.executable, str(vault / "run_one.py"), aid],
            cwd=str(ROOT),
        )
        procs.append((aid, p))
    results = {}
    for aid, p in procs:
        rc = p.wait()
        results[aid] = rc
        print(f"phase_item {aid} exit={rc}", flush=True)
    return results

def main():
    launch = json.loads(META.read_text())
    vault = Path(launch["vault"])
    ctx = [j for j in launch["jobs"] if j["phase"] == "context"]
    math = [j for j in launch["jobs"] if j["phase"] == "math"]
    notify("Pure Tate • context phase starting",
           "C66-001\n" + "\n".join(f"{j['engine']}: {j['artifact_id']} ({j['kind']})" for j in ctx))
    ctx_res = run_phase(vault, ctx)
    notify("Pure Tate • context phase done",
           "C66-001\n" + "\n".join(f"{aid} exit={rc}" for aid, rc in ctx_res.items()))
    notify("Pure Tate • math phase starting",
           "C66-001\n" + "\n".join(f"{j['engine']}: {j['artifact_id']} {j['subproblem_id']}" for j in math))
    math_res = run_phase(vault, math)
    notify("Pure Tate • math phase done",
           "C66-001\n" + "\n".join(f"{aid} exit={rc}" for aid, rc in math_res.items()))
    bad = {**{k:v for k,v in ctx_res.items() if v}, **{k:v for k,v in math_res.items() if v}}
    print("ALL_DONE", json.dumps({"context": ctx_res, "math": math_res}), flush=True)
    raise SystemExit(1 if bad else 0)

if __name__ == "__main__":
    main()
