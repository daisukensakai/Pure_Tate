#!/usr/bin/env python3
import json, os, sys, time, datetime
from pathlib import Path
ROOT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate')
sys.path.insert(0, str(ROOT))
from pure_tate.agents import _extract_claude_stream, _validate_artifact
from pure_tate.run_lifecycle import spend_artifact_reservation
from pure_tate.store import atomic_write_json
from pure_tate.campaigns import campaign_packet_record, load_campaign
from pure_tate.paired import standard_fallback_task, attach_working_context, working_context_records

VAULT = Path('/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/ATT-0053-wrapup-20260808')
ARTIFACT_ID = 'ATT-0054'
SESSION_ID = '0ed298f0-69cd-4513-92da-00f4c5bffa01'
PID = 47934
stdout_path = VAULT / f"{ARTIFACT_ID}.resume.stdout.jsonl"
decision_path = VAULT / f"{ARTIFACT_ID}.finish.decision.json"
receipt_path = VAULT / "RECEIPT.json"
log_path = VAULT / f"{ARTIFACT_ID}.finish.waiter.log"

def log(msg):
    with log_path.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()

def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

log(f"WAIT_START pid={PID} {ts()}")
# wait for process
while True:
    try:
        os.kill(PID, 0)
        time.sleep(2)
    except ProcessLookupError:
        break
    except PermissionError:
        time.sleep(2)

bytes_ = stdout_path.stat().st_size if stdout_path.is_file() else 0
log(f"DONE pid={PID} stdout_bytes={bytes_} {ts()}")

raw = stdout_path.read_text(encoding="utf-8", errors="replace") if bytes_ else ""
# classify result event
has_result = False
is_error = True
types = {}
last_result = None
for line in raw.splitlines():
    line=line.strip()
    if not line: continue
    try:
        o=json.loads(line)
    except Exception:
        continue
    t=o.get("type") or "?"
    types[t]=types.get(t,0)+1
    if t=="result":
        has_result=True
        last_result=o
        is_error=bool(o.get("is_error"))
log(f"types {types}")
if last_result:
    log(f"last_result { {k:last_result.get(k) for k in ('is_error','subtype','stop_reason','session_id') if k in last_result} }")

should_ingest = has_result and not is_error
decision = {"has_result": has_result, "is_error": is_error, "should_ingest": should_ingest}
atomic_write_json(decision_path, decision)

if not should_ingest:
    log("SKIP_INGEST no successful result event — reservation left for manual spend")
    # still spend to free ID discipline if stream empty/error after paid turn
    reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_no_successful_result", task_id="TASK-C66-M-001")
    sys.exit(2)

try:
    artifact = _extract_claude_stream(raw)
except Exception as exc:
    log(f"EXTRACT_FAIL {exc}")
    reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_extract_failed", task_id="TASK-C66-M-001")
    atomic_write_json(receipt_path, {"status":"extract_failed","error":str(exc),"ingested_at":ts()})
    sys.exit(3)

if artifact.get("id") == 'ATT-0053':
    artifact["id"] = ARTIFACT_ID
if artifact.get("id") != ARTIFACT_ID:
    log(f"ID_MISMATCH {artifact.get('id')}")
    reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_id_mismatch", task_id="TASK-C66-M-001")
    atomic_write_json(receipt_path, {"status":"id_mismatch","raw_id":artifact.get("id"),"ingested_at":ts()})
    atomic_write_json(VAULT / f"{ARTIFACT_ID}.extracted.raw.json", artifact)
    sys.exit(4)

if artifact.get("engine") != "claude":
    artifact["engine"] = "claude"

# build minimal task for validation
campaign = load_campaign("C66-001")
packet = campaign_packet_record("C66-001")
task = standard_fallback_task(campaign, packet, working_context_records(campaign), [])
task = attach_working_context(task, campaign)
output = ROOT / "proof/attempts" / f"{ARTIFACT_ID}.json"
if output.exists():
    log("REFUSE overwrite existing attempt")
    sys.exit(5)

try:
    _validate_artifact("mathematics", task, artifact, output, "claude")
except Exception as exc:
    log(f"VALIDATION_FAIL {exc}")
    atomic_write_json(VAULT / f"{ARTIFACT_ID}.extracted.invalid.json", artifact)
    reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
    if reservation.exists():
        spend_artifact_reservation(reservation, reason="wrapup_validation_failed", task_id="TASK-C66-M-001")
    atomic_write_json(receipt_path, {"status":"validation_failed","error":str(exc),"ingested_at":ts()})
    sys.exit(6)

artifact["recovery"] = {
    "classification": "manual_session_wrapup_prompt_inject",
    "principal_override": True,
    "parent_attempt_id": 'ATT-0053',
    "parent_session_id": SESSION_ID,
    "parent_run_id": "RUN-C66-001-20260807T233937839509Z-47462",
    "resume_stdout": str(stdout_path.relative_to(ROOT)),
    "recovered_at": ts(),
    "protect_from_overwrite": True,
    "reason": "Principal wrap-up inject after standard-fallback thinking-token burn; new slot.",
}
for field in (
    "paired_turn_kind",
    "paired_problem_key",
    "paired_theorem_sha256",
    "paired_attempt_policy_revision",
):
    if field in task:
        artifact[field] = task[field]

atomic_write_json(output, artifact)
reservation = ROOT / "reports/runs/reservations" / f"{ARTIFACT_ID}.json"
if reservation.exists():
    spend_artifact_reservation(reservation, reason="wrapup_success", task_id="TASK-C66-M-001")
receipt = {
    "status": "success",
    "artifact_id": ARTIFACT_ID,
    "output": str(output.relative_to(ROOT)),
    "ingested_at": ts(),
    "session_id": SESSION_ID,
    "result_type": artifact.get("result_type"),
    "attempt_status": artifact.get("status"),
}
atomic_write_json(receipt_path, receipt)
log(f"INGEST_OK {output}")
sys.exit(0)
