#!/usr/bin/env python3
import datetime
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate')
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream, _validate_artifact
from pure_tate.run_lifecycle import spend_artifact_reservation
from pure_tate.store import atomic_write_json
from pure_tate.tasking import review_tasks
from pure_tate.campaigns import (
    campaign_packet_path,
    campaign_packet_snapshot_path,
    write_campaign_packet,
)

VAULT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/att0066-claude-p2-resume-20260809T104217Z')
ARTIFACT_ID = 'REV-0116'
SESSION_ID = 'a9eeac7a-46c4-4add-826a-8748171973ac'
TASK_ID = 'TASK-V-ATT-0066-P2'
PARENT_REV = 'REV-0114'
PID = int(os.environ["CLAUDE_RESUME_PID"])
stdout_path = VAULT / f"{ARTIFACT_ID}.resume.stdout.jsonl"
decision_path = VAULT / f"{ARTIFACT_ID}.finish.decision.json"
receipt_path = VAULT / "RECEIPT.json"
log_path = VAULT / f"{ARTIFACT_ID}.finish.waiter.log"

def log(msg):
    with log_path.open("a", encoding="utf-8") as f:
        f.write(msg + "\n"); f.flush()

def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

log(f"WAIT_START pid={PID} {ts()}")
while True:
    try:
        os.kill(PID, 0); time.sleep(2)
    except ProcessLookupError:
        break
    except PermissionError:
        time.sleep(2)

bytes_ = stdout_path.stat().st_size if stdout_path.is_file() else 0
log(f"DONE pid={PID} stdout_bytes={bytes_} {ts()}")
raw = stdout_path.read_text(encoding="utf-8", errors="replace") if bytes_ else ""
has_result = False; is_error = True; types = {}
for line in raw.splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except Exception:
        continue
    t = o.get("type") or "?"
    types[t] = types.get(t, 0) + 1
    if t == "result":
        has_result = True
        is_error = bool(o.get("is_error"))
log(f"types {types}")
should_ingest = has_result and not is_error
atomic_write_json(decision_path, {"has_result": has_result, "is_error": is_error, "should_ingest": should_ingest})
reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
parent_path = ROOT / "proof/reviews" / f"{PARENT_REV}.json"
if parent_path.exists():
    log("REFUSE: parent REV unexpectedly exists; abort")
    sys.exit(9)
if not should_ingest:
    log("SKIP_INGEST")
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_no_successful_result", task_id=TASK_ID)
    sys.exit(2)
try:
    artifact = _extract_claude_stream(raw)
except Exception as exc:
    log(f"EXTRACT_FAIL {exc}")
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_extract_failed", task_id=TASK_ID)
    atomic_write_json(receipt_path, {"status": "extract_failed", "error": str(exc), "ingested_at": ts()})
    sys.exit(3)
# Repair id if model echoed the spent parent slot
if artifact.get("id") in (PARENT_REV, None, ""):
    artifact["id"] = ARTIFACT_ID
if artifact.get("id") != ARTIFACT_ID:
    log(f"ID_MISMATCH {artifact.get('id')}")
    atomic_write_json(VAULT / f"{ARTIFACT_ID}.extracted.raw.json", artifact)
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_id_mismatch", task_id=TASK_ID)
    atomic_write_json(receipt_path, {"status": "id_mismatch", "raw_id": artifact.get("id"), "ingested_at": ts()})
    sys.exit(4)
artifact["reviewer_engine"] = "claude"
artifact["review_pass"] = 2
artifact["attempt_id"] = "ATT-0066"
write_campaign_packet("C66-001")
task = dict(next(t for t in review_tasks() if t["id"] == TASK_ID))
att = json.loads((ROOT / "proof/attempts/ATT-0066.json").read_text())
snap = campaign_packet_snapshot_path(campaign_packet_path("C66-001"), att["packet_sha256"])
if snap.is_file():
    task["input_packet"] = str(snap.relative_to(ROOT))
task["output"] = f"proof/reviews/{ARTIFACT_ID}.json"
output = ROOT / "proof/reviews" / f"{ARTIFACT_ID}.json"
if output.exists():
    log("REFUSE overwrite existing review")
    sys.exit(5)
if parent_path.exists():
    log("REFUSE parent appeared")
    sys.exit(9)
try:
    _validate_artifact("review", task, artifact, output, "claude")
except Exception as exc:
    log(f"VALIDATION_FAIL {exc}")
    atomic_write_json(VAULT / f"{ARTIFACT_ID}.extracted.invalid.json", artifact)
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_validation_failed", task_id=TASK_ID)
    atomic_write_json(receipt_path, {"status": "validation_failed", "error": str(exc), "ingested_at": ts()})
    sys.exit(6)
# validate may not persist; write only after validate, never overwrite
if output.exists():
    log("REFUSE race overwrite")
    sys.exit(5)
atomic_write_json(output, artifact)
if reservation.exists():
    spend_artifact_reservation(reservation, reason="wrapup_success_manual_ingest", task_id=TASK_ID)
atomic_write_json(receipt_path, {
    "status": "success",
    "artifact_id": ARTIFACT_ID,
    "session_id": SESSION_ID,
    "output": str(output.relative_to(ROOT)),
    "ingested_at": ts(),
    "verdict": artifact.get("verdict"),
    "review_pass": artifact.get("review_pass"),
    "parent_rev_id": PARENT_REV,
})
log(f"INGESTED {output}")
print(f"INGESTED\t{ARTIFACT_ID}\t{output}")
