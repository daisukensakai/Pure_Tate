import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .artifacts import load_artifacts
from .store import PACKETS_GENERATED, ROOT, atomic_write_json, atomic_write_text


POLICY_REVISION = 1
LEDGER_PATH = ROOT / "proof" / "paired-turns.json"
TRACE_DIR = ROOT / "research" / "paired-traces"
DIGEST_DIR = ROOT / "research" / "paired-digests"
WORKING_CONTEXT_DIR = PACKETS_GENERATED / "paired-working-context"
RECOVERY_LEDGER_PATH = ROOT / "proof" / "paired-recoveries.json"
FORCED_PROMPT = "prompts/FORCED_FULL_PROOF.md"
MINER_PROMPT = "prompts/TRACE_MINER.md"

INTERNAL_TASK_FIELDS = {
    "paired_attempt_policy_revision",
    "paired_turn_kind",
    "paired_problem_key",
    "paired_theorem_sha256",
    "paired_source_engine",
    "paired_trace_id",
    "paired_trace_path",
    "paired_digest_paths",
    "paired_scheduler_state",
    "selected_engine",
    "status",
    "created_on",
    "output",
}


class SubstantiveAttemptError(ValueError):
    def __init__(
        self, message: str, trace_id: str, trace_path: str
    ) -> None:
        super().__init__(message)
        self.trace_id = trace_id
        self.trace_path = trace_path


class PairedInfrastructureError(RuntimeError):
    def __init__(
        self, message: str, trace_id: str, trace_path: str
    ) -> None:
        super().__init__(message)
        self.trace_id = trace_id
        self.trace_path = trace_path


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def theorem_sha256(campaign: Dict[str, Any]) -> str:
    return _digest_text(str(campaign["paired_attempt_policy"]["exact_theorem"]))


def problem_key(campaign: Dict[str, Any]) -> str:
    from .campaigns import campaign_packet_record

    packet = campaign_packet_record(str(campaign["id"]))
    payload = {
        "campaign_id": campaign["id"],
        "packet_revision": campaign["campaign_revision"],
        "packet_sha256": packet["packet_sha256"],
        "context_revision": campaign["context_revision"],
        "theorem_sha256": theorem_sha256(campaign),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_ledger() -> Dict[str, Any]:
    if not LEDGER_PATH.is_file():
        return {
            "schema_version": 1,
            "paired_attempt_policy_revision": POLICY_REVISION,
            "events": [],
        }
    try:
        value = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("paired-turn ledger is invalid: %s" % exc) from exc
    if (
        not isinstance(value, dict)
        or value.get("paired_attempt_policy_revision") != POLICY_REVISION
        or not isinstance(value.get("events"), list)
    ):
        raise ValueError("paired-turn ledger has the wrong schema")
    return value


def record_event(event: Dict[str, Any]) -> Dict[str, Any]:
    ledger = load_ledger()
    campaign_id = event.get("campaign_id")
    if isinstance(campaign_id, str) and campaign_id:
        from .campaigns import load_campaign

        campaign = load_campaign(campaign_id)
        event = {
            "theorem_sha256": theorem_sha256(campaign),
            "packet_revision": campaign["campaign_revision"],
            **event,
        }
    row = {
        "schema_version": 1,
        "paired_attempt_policy_revision": POLICY_REVISION,
        "recorded_at": _timestamp(),
        **event,
    }
    ledger["events"].append(row)
    atomic_write_json(LEDGER_PATH, ledger)
    return row


def events_for(
    campaign: Dict[str, Any], engine: Optional[str] = None
) -> List[Dict[str, Any]]:
    key = problem_key(campaign)
    return [
        event
        for event in load_ledger()["events"]
        if event.get("problem_key") == key
        and (engine is None or event.get("engine") == engine)
    ]


def model_visible_task(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in task.items()
        if key not in INTERNAL_TASK_FIELDS
    }


def _next_id(directory: Path, prefix: str) -> str:
    numbers = []
    for path in directory.glob(prefix + "-*.json"):
        try:
            numbers.append(int(path.stem.split("-")[-1]))
        except ValueError:
            continue
    return "%s-%04d" % (prefix, (max(numbers) if numbers else 0) + 1)


def write_observable_trace(
    task: Dict[str, Any],
    engine: str,
    stdout: str,
    stderr: str,
    parsed_artifact: Optional[Dict[str, Any]] = None,
    validation_error: Optional[str] = None,
    classification: str = "substantive",
) -> Dict[str, Any]:
    trace_id = _next_id(TRACE_DIR, "TRACE")
    path = TRACE_DIR / (trace_id + ".json")
    record = {
        "schema_version": 1,
        "id": trace_id,
        "created_at": _timestamp(),
        "campaign_id": task.get("campaign_id"),
        "problem_key": task.get("paired_problem_key"),
        "turn_kind": task.get("paired_turn_kind"),
        "task_id": task.get("id"),
        "engine": engine,
        "packet_sha256": task.get("packet_sha256"),
        "observable_stdout": stdout,
        "observable_stderr": stderr,
        "parsed_artifact": parsed_artifact,
        "validation_error": validation_error,
        "classification": classification,
        "source_boundary": (
            "Official subprocess output only; no provider-private session files "
            "or hidden chain-of-thought."
        ),
    }
    atomic_write_json(path, record)
    return {
        "id": trace_id,
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def forced_task(
    campaign: Dict[str, Any],
    packet: Dict[str, Any],
    working_context: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    target = packet["target"]
    return {
        "id": "TASK-%s-FORCED-FULL" % campaign["id"],
        "phase": "mathematics",
        "role": "exact-theorem-prover-or-disprover",
        "campaign_id": campaign["id"],
        "campaign_revision": campaign["campaign_revision"],
        "target_claim_id": campaign["target_claim_id"],
        "target": target,
        "exact_theorem": campaign["paired_attempt_policy"]["exact_theorem"],
        "subproblem_id": "C66-FULL",
        "lane": "full-resolution",
        "context_revision": campaign["context_revision"],
        "packet_id": packet["packet_id"],
        "packet_sha256": packet["packet_sha256"],
        "input_packet": packet["packet_path"],
        "input_artifacts": list(working_context),
        "prompt": FORCED_PROMPT,
        "output": "proof/attempts/ATT-####.json",
        "status": "ready",
        "created_on": datetime.date.today().isoformat(),
        "paired_attempt_policy_revision": POLICY_REVISION,
        "paired_turn_kind": "forced-proof",
        "paired_problem_key": problem_key(campaign),
        "paired_theorem_sha256": theorem_sha256(campaign),
    }


def standard_fallback_task(
    base_task: Dict[str, Any],
    campaign: Dict[str, Any],
    working_context: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    task = dict(base_task)
    task["input_artifacts"] = list(task.get("input_artifacts", [])) + list(
        working_context
    )
    task.update(
        {
            "paired_attempt_policy_revision": POLICY_REVISION,
            "paired_turn_kind": "standard-fallback",
            "paired_problem_key": problem_key(campaign),
            "paired_theorem_sha256": theorem_sha256(campaign),
            "exact_theorem": campaign["paired_attempt_policy"][
                "exact_theorem"
            ],
        }
    )
    return task


def next_digest_id() -> str:
    return _next_id(DIGEST_DIR, "DIGEST")


def _attached_reviews(attempt_id: str) -> List[Dict[str, Any]]:
    return [
        review
        for review in load_artifacts("reviews")
        if review.get("attempt_id") == attempt_id
    ]


def _attempts_for(
    campaign: Dict[str, Any], engine: str, turn_kind: str
) -> List[Dict[str, Any]]:
    key = problem_key(campaign)
    return [
        attempt
        for attempt in load_artifacts("attempts")
        if attempt.get("paired_problem_key") == key
        and attempt.get("engine") == engine
        and attempt.get("paired_turn_kind") == turn_kind
    ]


def _event(
    campaign: Dict[str, Any], engine: str, event_type: str
) -> Optional[Dict[str, Any]]:
    matches = [
        event
        for event in events_for(campaign, engine)
        if event.get("event") == event_type
    ]
    return matches[-1] if matches else None


def _event_for_trace(
    campaign: Dict[str, Any],
    engine: str,
    event_type: str,
    trace_id: str,
) -> Optional[Dict[str, Any]]:
    matches = [
        event
        for event in events_for(campaign, engine)
        if event.get("event") == event_type
        and event.get("trace_id") == trace_id
    ]
    return matches[-1] if matches else None


def _review_state(attempt: Dict[str, Any]) -> str:
    reviews = _attached_reviews(str(attempt.get("id")))
    if any(
        review.get("verdict") in {"incomplete", "refuted"}
        for review in reviews
    ):
        return "rejected"
    confirmations = [
        review
        for review in reviews
        if review.get("verdict") == "confirmed"
        and review.get("independent") is True
        and review.get("reviewer_engine") != attempt.get("engine")
    ]
    if (
        {review.get("review_pass") for review in confirmations}
        >= {1, 2}
        and len({review.get("reviewer_engine") for review in confirmations})
        >= 2
    ):
        return "verified"
    return "under_review"


def pair_state(campaign: Dict[str, Any], engine: str) -> Dict[str, Any]:
    standard_attempts = _attempts_for(
        campaign, engine, "standard-fallback"
    )
    if standard_attempts:
        attempt = standard_attempts[-1]
        state = _review_state(attempt)
        if (
            attempt.get("status") == "proposed"
            and _attached_reviews(str(attempt.get("id")))
        ):
            state = "rejected"
        if state == "verified":
            return {"state": "verified", "attempt": attempt}
        if state == "under_review" and attempt.get("status") in {
            "proposed",
            "claimed_complete",
        }:
            return {"state": "standard_under_review", "attempt": attempt}
        if _event(campaign, engine, "standard_digest_written"):
            return {"state": "pair_exhausted", "attempt": attempt}
        return {
            "state": "standard_trace_mining",
            "attempt": attempt,
            "trace_id": attempt.get("observable_trace_id"),
        }
    invalid_standard = _event(
        campaign, engine, "standard_substantive_rejected"
    )
    if invalid_standard:
        if _event(campaign, engine, "standard_digest_written"):
            return {"state": "pair_exhausted"}
        return {
            "state": "standard_trace_mining",
            "trace_id": invalid_standard.get("trace_id"),
        }
    standard_infrastructure = _event(
        campaign, engine, "standard-fallback_infrastructure_failure"
    )
    standard_infrastructure_trace = (
        standard_infrastructure.get("trace_id")
        if isinstance(standard_infrastructure, dict)
        else None
    )
    if (
        isinstance(standard_infrastructure_trace, str)
        and standard_infrastructure_trace
        and not _event_for_trace(
            campaign,
            engine,
            "infrastructure_digest_written",
            standard_infrastructure_trace,
        )
    ):
        return {
            "state": "infrastructure_trace_mining",
            "retry_turn": "standard-fallback",
            "trace_id": standard_infrastructure_trace,
        }

    forced_attempts = _attempts_for(campaign, engine, "forced-proof")
    if forced_attempts:
        attempt = forced_attempts[-1]
        state = _review_state(attempt)
        if state == "verified":
            return {"state": "verified", "attempt": attempt}
        if state == "under_review":
            return {"state": "forced_under_review", "attempt": attempt}
        if _event(campaign, engine, "forced_digest_written"):
            return {"state": "standard_ready", "attempt": attempt}
        return {
            "state": "forced_trace_mining",
            "attempt": attempt,
            "trace_id": attempt.get("observable_trace_id"),
        }
    invalid_forced = _event(
        campaign, engine, "forced_substantive_rejected"
    )
    if invalid_forced:
        if _event(campaign, engine, "forced_digest_written"):
            return {"state": "standard_ready"}
        return {
            "state": "forced_trace_mining",
            "trace_id": invalid_forced.get("trace_id"),
        }
    infrastructure = _event(
        campaign, engine, "forced-proof_infrastructure_failure"
    )
    infrastructure_trace = (
        infrastructure.get("trace_id")
        if isinstance(infrastructure, dict)
        else None
    )
    if isinstance(infrastructure_trace, str) and infrastructure_trace:
        if not _event_for_trace(
            campaign,
            engine,
            "infrastructure_digest_written",
            infrastructure_trace,
        ):
            return {
                "state": "infrastructure_trace_mining",
                "retry_turn": "forced-proof",
                "trace_id": infrastructure_trace,
            }
    return {"state": "forced_untried"}


def _trace_record(trace_id: str) -> Dict[str, Any]:
    path = TRACE_DIR / (trace_id + ".json")
    if not path.is_file():
        raise ValueError("paired trace is missing: %s" % trace_id)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["_path"] = str(path)
    return value


def annotate_trace(trace_id: str, validation_error: str) -> None:
    path = TRACE_DIR / (trace_id + ".json")
    if not path.is_file():
        raise ValueError("paired trace is missing: %s" % trace_id)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["validation_error"] = validation_error
    atomic_write_json(path, value)


def recover_attempt_from_trace(
    trace_id: str, output: Optional[Path] = None
) -> Dict[str, Any]:
    """Recover a lost paired attempt solely from its official observable trace.

    This is intentionally append-only with respect to scheduling history: the
    original rejected run and ledger event remain intact, and a recovery event
    explains why a proof artifact now exists.
    """
    from .agents import (
        _extract_gemini_stream,
        _extract_grok_stream,
        _extract_json_object,
        _validate_artifact,
        load_engines,
    )
    from .campaigns import campaign_packet_record, load_campaign
    from .tasking import campaign_mathematics_tasks

    trace = _trace_record(trace_id)
    if trace.get("source_boundary") != (
        "Official subprocess output only; no provider-private session files "
        "or hidden chain-of-thought."
    ):
        raise ValueError("trace does not attest the official-output boundary")
    if trace.get("turn_kind") not in {"forced-proof", "standard-fallback"}:
        raise ValueError("trace is not a paired mathematics turn")
    campaign_id = trace.get("campaign_id")
    engine = trace.get("engine")
    if not isinstance(campaign_id, str) or not isinstance(engine, str):
        raise ValueError("trace lacks campaign or engine identity")
    campaign = load_campaign(campaign_id)
    packet = campaign_packet_record(campaign_id)
    if trace.get("packet_sha256") != packet["packet_sha256"]:
        raise ValueError("trace packet is stale; recovery is not safe")
    base_tasks = {
        task["id"]: task for task in campaign_mathematics_tasks(campaign_id)
    }
    base = base_tasks.get(str(trace.get("task_id")))
    if base is None:
        raise ValueError("trace task is not a current campaign task")
    if trace["turn_kind"] == "forced-proof":
        task = forced_task(campaign, packet, [])
    else:
        task = standard_fallback_task(base, campaign, [])
    task["id"] = trace["task_id"]

    stdout = trace.get("observable_stdout")
    if not isinstance(stdout, str) or not stdout:
        raise ValueError("trace has no observable stdout")
    family = load_engines().get(engine, {}).get("family")
    artifact = (
        _extract_gemini_stream(stdout)
        if family == "gemini"
        else (
            _extract_grok_stream(stdout)
            if family == "grok"
            else _extract_json_object(stdout)
        )
    )
    if output is None:
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id.startswith("ATT-"):
            raise ValueError("recovered output has no valid attempt id")
        output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
    if output.exists():
        raise ValueError("refusing to overwrite existing artifact %s" % output)
    _validate_artifact("mathematics", task, artifact, output, engine)

    trace_path = Path(str(trace["_path"]))
    trace_sha256 = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    artifact["observable_trace_id"] = trace_id
    artifact["observable_trace_sha256"] = trace_sha256
    for field in (
        "paired_turn_kind",
        "paired_problem_key",
        "paired_theorem_sha256",
        "paired_attempt_policy_revision",
    ):
        if field in task:
            artifact[field] = task[field]
    atomic_write_json(output, artifact)
    artifact_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()

    if RECOVERY_LEDGER_PATH.is_file():
        ledger = json.loads(RECOVERY_LEDGER_PATH.read_text(encoding="utf-8"))
    else:
        ledger = {"schema_version": 1, "recoveries": []}
    if not isinstance(ledger, dict) or not isinstance(
        ledger.get("recoveries"), list
    ):
        raise ValueError("paired recovery ledger has the wrong schema")
    recovery_id = "REC-%04d" % (len(ledger["recoveries"]) + 1)
    receipt = {
        "schema_version": 1,
        "id": recovery_id,
        "recovered_at": _timestamp(),
        "campaign_id": campaign_id,
        "engine": engine,
        "turn_kind": trace["turn_kind"],
        "trace_id": trace_id,
        "trace_sha256": trace_sha256,
        "artifact_id": artifact["id"],
        "artifact_path": str(output.relative_to(ROOT)),
        "artifact_sha256": artifact_sha256,
        "reason": "PARSER-RECOVERY-0001",
        "source_boundary": trace["source_boundary"],
    }
    ledger["recoveries"].append(receipt)
    atomic_write_json(RECOVERY_LEDGER_PATH, ledger)
    record_event(
        {
            "event": "paired_artifact_recovered",
            "campaign_id": campaign_id,
            "problem_key": task["paired_problem_key"],
            "engine": engine,
            "turn_kind": trace["turn_kind"],
            "packet_sha256": packet["packet_sha256"],
            "classification": "parser_recovery",
            "trace_id": trace_id,
            "trace_path": str(trace_path.relative_to(ROOT)),
            "trace_sha256": trace_sha256,
            "attempt_id": artifact["id"],
            "artifact_sha256": artifact_sha256,
            "recovery_id": recovery_id,
        }
    )
    return receipt


def trace_mining_task(
    campaign: Dict[str, Any],
    packet: Dict[str, Any],
    engine: str,
    source_turn: str,
    trace_id: str,
) -> Dict[str, Any]:
    trace = _trace_record(trace_id)
    path = Path(trace["_path"])
    review_inputs: List[Dict[str, str]] = []
    source_attempt_ids = {
        attempt.get("id")
        for attempt in load_artifacts("attempts")
        if attempt.get("observable_trace_id") == trace_id
    }
    for review in load_artifacts("reviews"):
        if review.get("attempt_id") not in source_attempt_ids:
            continue
        review_path = Path(str(review.get("_path", "")))
        if review_path.is_file():
            review_inputs.append(
                {
                    "path": str(review_path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
                }
            )
    task_id = "TASK-%s-MINE-%s-%s" % (
        campaign["id"],
        engine.upper(),
        source_turn.upper().replace("-", "_"),
    )
    return {
        "id": task_id,
        "phase": "trace-mining",
        "role": "observable-mathematical-trace-miner",
        "campaign_id": campaign["id"],
        "campaign_revision": campaign["campaign_revision"],
        "context_revision": campaign["context_revision"],
        "target": packet["target"],
        "packet_id": packet["packet_id"],
        "packet_sha256": packet["packet_sha256"],
        "input_packet": packet["packet_path"],
        "input_trace": str(path.relative_to(ROOT)),
        "input_artifacts": review_inputs,
        "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_turn": source_turn,
        "prompt": MINER_PROMPT,
        "output": "research/paired-digests/DIGEST-####.json",
        "status": "ready",
        "created_on": datetime.date.today().isoformat(),
        "paired_attempt_policy_revision": POLICY_REVISION,
        "paired_problem_key": problem_key(campaign),
        "problem_key": problem_key(campaign),
        "paired_source_engine": engine,
        "paired_trace_id": trace_id,
    }


def validate_digest(task: Dict[str, Any], artifact: Dict[str, Any]) -> None:
    required = {
        "schema_version",
        "id",
        "task_id",
        "campaign_id",
        "campaign_revision",
        "problem_key",
        "target",
        "packet_sha256",
        "established_facts",
        "candidate_ideas",
        "invalid_steps",
        "reusable_computations",
        "unresolved_dependencies",
        "sanitized",
        "engine",
    }
    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError(
            "trace digest lacks fields: %s" % ", ".join(missing)
        )
    exact = {
        "schema_version": 1,
        "task_id": task["id"],
        "campaign_id": task["campaign_id"],
        "campaign_revision": task["campaign_revision"],
        "problem_key": task["paired_problem_key"],
        "target": task["target"],
        "packet_sha256": task["packet_sha256"],
        "sanitized": True,
    }
    for field, expected in exact.items():
        if artifact.get(field) != expected:
            raise ValueError("trace digest %s does not match task" % field)
    for field in (
        "established_facts",
        "candidate_ideas",
        "invalid_steps",
        "reusable_computations",
        "unresolved_dependencies",
    ):
        values = artifact.get(field)
        if not isinstance(values, list) or any(
            not isinstance(item, dict)
            or not str(item.get("statement", "")).strip()
            for item in values
        ):
            raise ValueError("trace digest %s is not structured" % field)
    if artifact.get("engine") == task.get("paired_source_engine"):
        raise ValueError("trace miner must be cross-engine")
    for row in artifact["established_facts"]:
        if (
            row.get("evidence_class") not in {"source", "mechanical"}
            or not str(row.get("evidence", "")).strip()
        ):
            raise ValueError(
                "established digest facts require source or mechanical evidence"
            )
    if any(
        row.get("requires_reproof") is not True
        for row in artifact["candidate_ideas"]
    ):
        raise ValueError("digest candidates must require independent reproving")
    if any(
        not str(row.get("mathematical_reason", "")).strip()
        for row in artifact["invalid_steps"]
    ):
        raise ValueError("invalid digest steps require a mathematical reason")
    if any(
        not isinstance(row.get("sha256"), str)
        or len(row["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in row["sha256"])
        for row in artifact["reusable_computations"]
    ):
        raise ValueError("reusable digest computations require SHA-256")


def _safe_math_rows(
    rows: Iterable[Dict[str, Any]], category: str = ""
) -> List[str]:
    forbidden = (
        "ATT-",
        "REV-",
        "TRACE-",
        "previous attempt",
        "earlier attempt",
        "failed attempt",
        "the engine",
        "the reviewer",
        "verdict",
    )
    rendered = []
    for row in rows:
        statement = " ".join(str(row.get("statement", "")).split())
        if not statement:
            continue
        if category == "established":
            statement += " [evidence: %s; %s]" % (
                row.get("evidence_class"),
                " ".join(str(row.get("evidence", "")).split()),
            )
        elif category == "invalid":
            statement += " [reason: %s]" % " ".join(
                str(row.get("mathematical_reason", "")).split()
            )
        elif category == "computation":
            statement += " [sha256: %s]" % row.get("sha256")
        lowered = statement.lower()
        if any(term.lower() in lowered for term in forbidden):
            raise ValueError(
                "trace digest leaks provenance into working context"
            )
        rendered.append(statement)
    return rendered


def publish_working_context(
    campaign: Dict[str, Any],
    task: Dict[str, Any],
    digest: Dict[str, Any],
) -> Dict[str, Any]:
    sections = [
        ("Established facts", digest["established_facts"], "established"),
        (
            "Candidate ideas requiring proof",
            digest["candidate_ideas"],
            "candidate",
        ),
        ("Mathematical constraints", digest["invalid_steps"], "invalid"),
        (
            "Reusable computations",
            digest["reusable_computations"],
            "computation",
        ),
        (
            "Dependencies to resolve",
            digest["unresolved_dependencies"],
            "dependency",
        ),
    ]
    lines = [
        "# Mathematical working context",
        "",
        "Treat candidates as unproved. Reprove every fact used in the final argument.",
    ]
    for heading, rows, category in sections:
        lines.extend(["", "## " + heading, ""])
        values = _safe_math_rows(rows, category)
        lines.extend("- " + value for value in values or ["None recorded."])
    text = "\n".join(lines) + "\n"
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path = WORKING_CONTEXT_DIR / ("WORKING-%s.md" % content_hash[:16])
    if not path.exists():
        atomic_write_text(path, text)
    record = {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    source_turn = task["source_turn"]
    record_event(
        {
            "event": (
                "forced_digest_written"
                if source_turn == "forced-proof"
                else (
                    "standard_digest_written"
                    if source_turn == "standard-fallback"
                    else "infrastructure_digest_written"
                )
            ),
            "campaign_id": campaign["id"],
            "problem_key": problem_key(campaign),
            "engine": task["paired_source_engine"],
            "source_turn": source_turn,
            "trace_id": task["paired_trace_id"],
            "digest_id": digest["id"],
            "digest_sha256": hashlib.sha256(
                (DIGEST_DIR / (digest["id"] + ".json")).read_bytes()
            ).hexdigest(),
            "working_context": record,
        }
    )
    return record


def working_context_records(campaign: Dict[str, Any]) -> List[Dict[str, str]]:
    records = []
    seen = set()
    for event in load_ledger()["events"]:
        if event.get("campaign_id") != campaign.get("id"):
            continue
        record = event.get("working_context")
        if not isinstance(record, dict):
            continue
        key = (record.get("path"), record.get("sha256"))
        if key in seen:
            continue
        path = ROOT / str(record.get("path", ""))
        if (
            path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest()
            == record.get("sha256")
        ):
            records.append(
                {"path": str(record["path"]), "sha256": str(record["sha256"])}
            )
            seen.add(key)
    return records


def pair_statuses(
    campaign: Dict[str, Any], engines: Sequence[str]
) -> Dict[str, Dict[str, Any]]:
    return {
        engine: {"state": pair_state(campaign, engine)["state"]}
        for engine in engines
    }


def dry_run_preview(
    campaign: Dict[str, Any],
    packet: Dict[str, Any],
    engines: Sequence[str],
    steps: int,
) -> List[Dict[str, Any]]:
    events = []
    for engine in engines:
        state = pair_state(campaign, engine)["state"]
        if state == "forced_untried":
            events.append(
                {
                    "phase": "forced-proof",
                    "task_id": "TASK-%s-FORCED-FULL" % campaign["id"],
                    "engine": engine,
                    "condition": "always",
                    "packet_sha256": packet["packet_sha256"],
                }
            )
            events.append(
                {
                    "phase": "standard-fallback",
                    "task_id": "TASK-%s-STANDARD-CONDITIONAL" % campaign["id"],
                    "engine": engine,
                    "condition": "only_after_substantive_forced_failure",
                    "packet_sha256": packet["packet_sha256"],
                }
            )
        elif state in {
            "forced_trace_mining",
            "standard_trace_mining",
            "infrastructure_trace_mining",
        }:
            events.append(
                {
                    "phase": "trace-mining",
                    "task_id": "TASK-%s-TRACE-MINING" % campaign["id"],
                    "engine": engine,
                    "condition": "always",
                    "packet_sha256": packet["packet_sha256"],
                }
            )
        else:
            events.append(
                {
                    "phase": state.replace("_", "-"),
                    "task_id": "TASK-%s-PAIRED-STATE" % campaign["id"],
                    "engine": engine,
                    "condition": "current_state",
                    "packet_sha256": packet["packet_sha256"],
                }
            )
    return [
        {"step": index + 1, **event}
        for index, event in enumerate(events[:steps])
    ]


def integrity_errors() -> List[str]:
    errors: List[str] = []
    try:
        ledger = load_ledger()
    except ValueError as exc:
        return [str(exc)]
    for index, event in enumerate(ledger["events"], 1):
        label = "paired ledger event %d" % index
        for field in (
            "event",
            "campaign_id",
            "problem_key",
            "engine",
            "theorem_sha256",
            "packet_revision",
        ):
            if field not in event:
                errors.append("%s lacks %s" % (label, field))
        trace_path = event.get("trace_path")
        trace_hash = event.get("trace_sha256")
        if trace_path or trace_hash:
            path = ROOT / str(trace_path or "")
            if not path.is_file():
                errors.append("%s trace is missing" % label)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != trace_hash:
                errors.append("%s trace hash does not match" % label)
        digest_id = event.get("digest_id")
        digest_hash = event.get("digest_sha256")
        if digest_id or digest_hash:
            path = DIGEST_DIR / ("%s.json" % digest_id)
            if not path.is_file():
                errors.append("%s digest is missing" % label)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest_hash:
                errors.append("%s digest hash does not match" % label)
        context = event.get("working_context")
        if isinstance(context, dict):
            path = ROOT / str(context.get("path", ""))
            if not path.is_file():
                errors.append("%s working context is missing" % label)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != context.get(
                "sha256"
            ):
                errors.append("%s working-context hash does not match" % label)
        artifact_hash = event.get("artifact_sha256")
        attempt_id = event.get("attempt_id")
        if artifact_hash and attempt_id:
            path = ROOT / "proof" / "attempts" / ("%s.json" % attempt_id)
            if not path.is_file():
                errors.append("%s attempt artifact is missing" % label)
            elif hashlib.sha256(path.read_bytes()).hexdigest() != artifact_hash:
                errors.append("%s attempt artifact hash does not match" % label)
    if RECOVERY_LEDGER_PATH.is_file():
        try:
            recoveries = json.loads(
                RECOVERY_LEDGER_PATH.read_text(encoding="utf-8")
            ).get("recoveries", [])
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            errors.append("paired recovery ledger is invalid: %s" % exc)
            recoveries = []
        if not isinstance(recoveries, list):
            errors.append("paired recovery ledger recoveries is not a list")
            recoveries = []
        for index, receipt in enumerate(recoveries, 1):
            label = "paired recovery %d" % index
            if not isinstance(receipt, dict):
                errors.append("%s is not an object" % label)
                continue
            artifact_path = ROOT / str(receipt.get("artifact_path", ""))
            trace_path = TRACE_DIR / ("%s.json" % receipt.get("trace_id"))
            if not artifact_path.is_file():
                errors.append("%s artifact is missing" % label)
            elif hashlib.sha256(artifact_path.read_bytes()).hexdigest() != receipt.get(
                "artifact_sha256"
            ):
                errors.append("%s artifact hash does not match" % label)
            if not trace_path.is_file():
                errors.append("%s trace is missing" % label)
            elif hashlib.sha256(trace_path.read_bytes()).hexdigest() != receipt.get(
                "trace_sha256"
            ):
                errors.append("%s trace hash does not match" % label)
    return errors
