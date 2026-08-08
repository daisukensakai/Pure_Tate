#!/usr/bin/env python3
import json, os, sys, time, datetime
from pathlib import Path
ROOT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate')
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream, _validate_artifact
from pure_tate.run_lifecycle import spend_artifact_reservation
from pure_tate.store import atomic_write_json
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.paired import attach_working_context
from pure_tate.tasking import campaign_mathematics_tasks

VAULT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/ATT-0059-to-comprank-20260808T110954Z')
ARTIFACT_ID = 'ATT-0062'
SESSION_ID = '9c7fef16-de07-40cf-adc7-3e1f99cdd347'
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
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except Exception: continue
    t=o.get("type") or "?"
    types[t]=types.get(t,0)+1
    if t=="result":
        has_result=True; is_error=bool(o.get("is_error"))
log(f"types {types}")
should_ingest = has_result and not is_error
atomic_write_json(decision_path, {"has_result": has_result, "is_error": is_error, "should_ingest": should_ingest})
reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
if not should_ingest:
    log("SKIP_INGEST")
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_no_successful_result", task_id='TASK-C66-M-008')
    sys.exit(2)
try:
    artifact = _extract_claude_stream(raw)
except Exception as exc:
    log(f"EXTRACT_FAIL {exc}")
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_extract_failed", task_id='TASK-C66-M-008')
    atomic_write_json(receipt_path, {"status":"extract_failed","error":str(exc),"ingested_at":ts()})
    sys.exit(3)
if artifact.get("id") in ('ATT-0059', None, ""):
    artifact["id"] = ARTIFACT_ID
if artifact.get("id") != ARTIFACT_ID:
    log(f"ID_MISMATCH {artifact.get('id')}")
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_id_mismatch", task_id='TASK-C66-M-008')
    atomic_write_json(receipt_path, {"status":"id_mismatch","raw_id":artifact.get("id"),"ingested_at":ts()})
    atomic_write_json(VAULT / f"{ARTIFACT_ID}.extracted.raw.json", artifact)
    sys.exit(4)
artifact["engine"] = "claude"
write_campaign_packet("C66-001")
campaign = load_campaign("C66-001")
task = next(t for t in campaign_mathematics_tasks("C66-001") if t["id"] == 'TASK-C66-M-008')
task = attach_working_context(task, campaign)
task["output"] = f"proof/attempts/{ARTIFACT_ID}.json"
output = ROOT / "proof/attempts" / f"{ARTIFACT_ID}.json"
if output.exists():
    log("REFUSE overwrite"); sys.exit(5)
try:
    _validate_artifact("mathematics", task, artifact, output, "claude")
except Exception as exc:
    log(f"VALIDATION_FAIL {exc}")
    atomic_write_json(VAULT / f"{ARTIFACT_ID}.extracted.invalid.json", artifact)
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_validation_failed", task_id='TASK-C66-M-008')
    atomic_write_json(receipt_path, {"status":"validation_failed","error":str(exc),"ingested_at":ts()})
    sys.exit(6)
if reservation.exists():
    spend_artifact_reservation(reservation, reason="wrapup_success_manual_ingest", task_id='TASK-C66-M-008')
atomic_write_json(receipt_path, {
    "status":"success","artifact_id":ARTIFACT_ID,"session_id":SESSION_ID,
    "output":str(output.relative_to(ROOT)),"ingested_at":ts(),
    "attempt_status":artifact.get("status"),"result_type":artifact.get("result_type"),
})
log(f"INGESTED {output}")
print(f"INGESTED\t{ARTIFACT_ID}\t{output}")
