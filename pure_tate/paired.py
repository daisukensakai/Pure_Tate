import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .artifacts import load_artifacts
from .store import PACKETS_GENERATED, ROOT, atomic_write_json, atomic_write_text


POLICY_REVISION = 2
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
    "routing_chain_id",
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


class ArtifactValidationError(ValueError):
    """Validation failure that preserved the raw observable agent output."""

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


def _problem_key_for(campaign: Dict[str, Any], packet_sha256: str) -> str:
    payload = {
        "campaign_id": campaign["id"],
        "packet_revision": campaign["campaign_revision"],
        "packet_sha256": packet_sha256,
        "context_revision": campaign["context_revision"],
        "theorem_sha256": theorem_sha256(campaign),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def problem_key(campaign: Dict[str, Any]) -> str:
    """Identify the problem a paired turn is working on.

    Keyed on packet identity rather than packet content. Keying it on content
    meant every finding adjudication minted a new problem key, orphaning the
    ledger and resetting each engine's pair state to "untried" -- which spent a
    fresh forced full proof on a problem that was already in progress.
    """
    from .campaigns import campaign_packet_binding_sha256

    return _problem_key_for(
        campaign, campaign_packet_binding_sha256(str(campaign["id"]))
    )


def problem_key_aliases(campaign: Dict[str, Any]) -> Set[str]:
    """Return the current problem key plus its superseded content-keyed forms.

    Historical events and artifacts were keyed on packet content. The content
    hashes attested as binding-equivalent are recorded in the binding migration,
    so their keys are recomputed exactly rather than guessed.
    """
    from .campaigns import _binding_migration

    keys = {problem_key(campaign)}
    migration = _binding_migration(str(campaign["id"]))
    if migration.get("campaign_revision") == campaign["campaign_revision"]:
        for packet_sha256 in migration.get("equivalent_packet_sha256", {}):
            keys.add(_problem_key_for(campaign, packet_sha256))
    return keys


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
        or value.get("paired_attempt_policy_revision") not in {1, POLICY_REVISION}
        or not isinstance(value.get("events"), list)
    ):
        raise ValueError("paired-turn ledger has the wrong schema")
    # Preserve the append-only historical ledger while all newly recorded
    # events carry the current forced-proof policy revision.
    value["paired_attempt_policy_revision"] = POLICY_REVISION
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
    keys = problem_key_aliases(campaign)
    return [
        event
        for event in load_ledger()["events"]
        if event.get("problem_key") in keys
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
        "packet_binding_sha256": task.get("packet_binding_sha256"),
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
        "packet_binding_sha256": packet.get("packet_binding_sha256"),
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
    keys = problem_key_aliases(campaign)
    return [
        attempt
        for attempt in load_artifacts("attempts")
        if attempt.get("paired_problem_key") in keys
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
    if attempt.get("campaign_id"):
        from .campaigns import campaign_route_policy_errors, load_campaign

        campaign = load_campaign(str(attempt["campaign_id"]))
        if campaign_route_policy_errors(campaign, attempt):
            return "rejected"
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
        from .proofs import attempt_is_complete

        state = _review_state(attempt)
        # An incomplete attempt that has already drawn a review is spent. A
        # complete one is not: it still has a second pass to earn, so the pair
        # must stay open rather than being retired into trace mining.
        if not attempt_is_complete(attempt) and _attached_reviews(
            str(attempt.get("id"))
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
    path = TRACE_DIR / ("%s.json" % trace_id)
    if not path.is_file():
        raise ValueError("trace %s is missing" % trace_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("trace %s is invalid: %s" % (trace_id, exc)) from exc
    if not isinstance(value, dict):
        raise ValueError("trace %s is not a JSON object" % trace_id)
    value["_path"] = str(path)
    return value


def annotate_trace(trace_id: str, validation_error: str) -> None:
    path = TRACE_DIR / (trace_id + ".json")
    if not path.is_file():
        raise ValueError("paired trace is missing: %s" % trace_id)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["validation_error"] = validation_error
    atomic_write_json(path, value)


def _recovered_trace_ids() -> set:
    if not RECOVERY_LEDGER_PATH.is_file():
        return set()
    try:
        ledger = json.loads(RECOVERY_LEDGER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    recoveries = ledger.get("recoveries") if isinstance(ledger, dict) else None
    if not isinstance(recoveries, list):
        return set()
    ids = set()
    for receipt in recoveries:
        if isinstance(receipt, dict) and isinstance(receipt.get("trace_id"), str):
            ids.add(receipt["trace_id"])
    return ids


def unrecovered_validation_traces(
    campaign_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Official traces that failed validation and still lack a recovered artifact.

    Recovery must be attempted for these before paying for a re-run of the same
    task. Existing recovered artifacts are never rewritten.
    """
    recovered_traces = _recovered_trace_ids()
    pending: List[Dict[str, Any]] = []
    if not TRACE_DIR.is_dir():
        return pending
    for path in sorted(TRACE_DIR.glob("TRACE-*.json")):
        try:
            trace = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(trace, dict):
            continue
        if campaign_id and trace.get("campaign_id") != campaign_id:
            continue
        if task_id and str(trace.get("task_id")) != task_id:
            continue
        if trace.get("classification") not in {
            "validation_failure",
            "parse_failure",
        }:
            continue
        if trace.get("turn_kind") not in {
            "forced-proof",
            "standard-fallback",
            "mathematics",
        }:
            continue
        trace_id = str(trace.get("id") or path.stem)
        if trace_id in recovered_traces:
            continue
        parsed = trace.get("parsed_artifact")
        artifact_id = None
        if isinstance(parsed, dict) and isinstance(parsed.get("id"), str):
            artifact_id = parsed["id"]
        if artifact_id:
            existing = ROOT / "proof" / "attempts" / (artifact_id + ".json")
            if existing.is_file():
                # On-disk work already owns the slot; do not re-run recovery
                # against it and never overwrite.
                continue
        if not (
            isinstance(trace.get("observable_stdout"), str)
            and trace.get("observable_stdout").strip()
        ) and not isinstance(parsed, dict):
            continue
        pending.append(
            {
                "trace_id": trace_id,
                "trace_path": str(path.relative_to(ROOT)),
                "campaign_id": trace.get("campaign_id"),
                "task_id": trace.get("task_id"),
                "engine": trace.get("engine"),
                "turn_kind": trace.get("turn_kind"),
                "classification": trace.get("classification"),
                "artifact_id": artifact_id,
                "validation_error": trace.get("validation_error"),
            }
        )
    return pending


def recover_attempt_from_trace(
    trace_id: str, output: Optional[Path] = None
) -> Dict[str, Any]:
    """Recover a lost mathematics attempt solely from its official observable trace.

    Supports campaign mathematics turns as well as paired forced-proof /
    standard-fallback turns. This is intentionally append-only with respect to
    scheduling history: the original rejected run and ledger event remain
    intact, a recovery event explains why a proof artifact now exists, and an
    existing on-disk artifact is never rewritten.
    """
    from .agents import (
        _extract_claude_stream,
        _extract_grok_stream,
        _extract_json_object,
        _extract_qwen_stream,
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
    turn_kind = trace.get("turn_kind")
    if turn_kind not in {"forced-proof", "standard-fallback", "mathematics"}:
        raise ValueError("trace is not a recoverable mathematics turn")
    campaign_id = trace.get("campaign_id")
    engine = trace.get("engine")
    if not isinstance(campaign_id, str) or not isinstance(engine, str):
        raise ValueError("trace lacks campaign or engine identity")
    campaign = load_campaign(campaign_id)
    packet = campaign_packet_record(campaign_id)
    from .campaigns import packet_binding_matches

    if not packet_binding_matches(trace, campaign_id):
        raise ValueError("trace packet is stale; recovery is not safe")
    base_tasks = {
        task["id"]: task for task in campaign_mathematics_tasks(campaign_id)
    }
    base = base_tasks.get(str(trace.get("task_id")))
    if base is None and turn_kind != "forced-proof":
        raise ValueError("trace task is not a current campaign task")
    if turn_kind == "forced-proof":
        task = forced_task(campaign, packet, [])
    elif turn_kind == "standard-fallback":
        if base is None:
            raise ValueError("trace task is not a current campaign task")
        task = standard_fallback_task(base, campaign, [])
    else:
        if base is None:
            raise ValueError("trace task is not a current campaign task")
        task = dict(base)
    if isinstance(trace.get("task_id"), str):
        task["id"] = trace["task_id"]

    parsed = trace.get("parsed_artifact")
    if isinstance(parsed, dict) and parsed:
        artifact = dict(parsed)
    else:
        stdout = trace.get("observable_stdout")
        if not isinstance(stdout, str) or not stdout:
            raise ValueError("trace has no observable stdout")
        family = load_engines().get(engine, {}).get("family")
        if family == "claude":
            artifact = _extract_claude_stream(stdout)
        elif family == "grok":
            artifact = _extract_grok_stream(stdout)
        elif family == "qwen":
            artifact = _extract_qwen_stream(stdout)
        else:
            artifact = _extract_json_object(stdout)
    if output is None:
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id.startswith("ATT-"):
            raise ValueError("recovered output has no valid attempt id")
        output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
    if output.exists():
        raise ValueError("refusing to overwrite existing artifact %s" % output)
    # Align the artifact id with the chosen exclusive output path.
    artifact["id"] = output.stem
    _validate_artifact("mathematics", task, artifact, output, engine)

    trace_path = Path(str(trace["_path"]))
    trace_sha256 = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    artifact["observable_trace_id"] = trace_id
    artifact["observable_trace_sha256"] = trace_sha256
    artifact["recovery"] = {
        "classification": "parser_recovery",
        "recovered_from_trace": trace_id,
        "recovered_at": _timestamp(),
        "reason": (
            "Recovered from official observable trace after validation/parser "
            "failure; existing work was never rewritten."
        ),
        "protect_from_overwrite": True,
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
        "turn_kind": turn_kind,
        "task_id": task.get("id"),
        "trace_id": trace_id,
        "trace_path": str(trace_path.relative_to(ROOT)),
        "trace_sha256": trace_sha256,
        "artifact_id": artifact["id"],
        "artifact_path": str(output.relative_to(ROOT)),
        "artifact_sha256": artifact_sha256,
        "classification": "parser_recovery",
        "protect_from_overwrite": True,
        "reason": "PARSER-RECOVERY-0001",
        "source_boundary": trace["source_boundary"],
    }
    ledger["recoveries"].append(receipt)
    atomic_write_json(RECOVERY_LEDGER_PATH, ledger)
    event = {
        "event": "paired_artifact_recovered",
        "campaign_id": campaign_id,
        "engine": engine,
        "turn_kind": turn_kind,
        "packet_sha256": packet["packet_sha256"],
        "classification": "parser_recovery",
        "trace_id": trace_id,
        "trace_path": str(trace_path.relative_to(ROOT)),
        "trace_sha256": trace_sha256,
        "attempt_id": artifact["id"],
        "artifact_sha256": artifact_sha256,
        "recovery_id": recovery_id,
        "task_id": task.get("id"),
    }
    if task.get("paired_problem_key"):
        event["problem_key"] = task["paired_problem_key"]
    record_event(event)
    return receipt


def attempt_pending_recoveries(
    campaign_id: str, task_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Try to recover every pending validation-failure trace before re-running.

    Failures are reported per-trace and do not abort the batch: a human or
    another engine may still recover manually, but the harness must attempt
    recovery before spending another paid turn on the same task.
    """
    results: List[Dict[str, Any]] = []
    for item in unrecovered_validation_traces(campaign_id, task_id=task_id):
        entry = dict(item)
        entry["attempted_at"] = _timestamp()
        try:
            receipt = recover_attempt_from_trace(str(item["trace_id"]))
            entry["status"] = "recovered"
            entry["receipt"] = receipt
        except (OSError, RuntimeError, ValueError) as exc:
            entry["status"] = "recovery_failed"
            entry["error"] = str(exc)
        results.append(entry)
    return results


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
        "packet_binding_sha256": packet.get("packet_binding_sha256"),
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
    # Stamped by the harness, not echoed by the miner: the digest records both
    # the packet content it was mined against and that packet's identity, so
    # working-context assembly can tell genuine staleness from findings churn.
    artifact["packet_binding_sha256"] = task.get("packet_binding_sha256")
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


# Canonical section ids → default headings (value-ordered for injection).
SECTIONS = [
    ("dependency", "Dependencies to resolve"),
    ("invalid", "Mathematical constraints"),
    ("computation", "Reusable computations"),
    ("established", "Established facts"),
    ("candidate", "Candidate ideas requiring proof"),
]
SECTION_HEADINGS = dict(SECTIONS)
PRIMARY_SECTION_HEADINGS = {
    "dependency": "Frontier obligations",
    "invalid": "Mathematical constraints",
    "computation": "Reusable computations",
    "established": "Established facts",
    "candidate": "Candidate ideas requiring proof",
}
# Rank order for eviction. Constraints and mechanically-checkable facts are the
# rows a later prover cannot cheaply rederive; unresolved dependencies are the
# most restateable and go first.
CATEGORY_RANK = {
    "computation": 0,
    "established_mechanical": 0,
    "invalid": 1,
    "established_source": 2,
    "candidate": 3,
    "dependency": 4,
}
PRIMARY_BUDGET_BYTES = 60 * 1000
EXTENDED_BUDGET_BYTES = 30 * 1000
# Primary floors guarantee high-value diversity before global rank fill.
PRIMARY_FLOOR_INVALID = 0.22
PRIMARY_FLOOR_MECH_COMP = 0.18
PRIMARY_FLOOR_SOURCE = 0.05
# Tiny frontier floor so open obligations are not starved by established bulk.
PRIMARY_FLOOR_DEPENDENCY = 0.06
# Hard caps keep low-value sections from crowding primary.
PRIMARY_CAP_DEPENDENCY_ROWS = 8
PRIMARY_CAP_DEPENDENCY_SHARE = 0.06
PRIMARY_CAP_CANDIDATE_ROWS = 12
PRIMARY_CAP_CANDIDATE_SHARE = 0.12
# Extended may keep a thin frontier of fresh dependencies; older ones archive.
EXTENDED_CAP_DEPENDENCY_ROWS = 6
# Only the last N digests contribute dependencies to injected tiers.
DEPENDENCY_DIGEST_WINDOW = 2


def _render_row(row: Dict[str, Any], category: str) -> str:
    """Render one digest row, or return "" when it leaks provenance.

    ``_safe_math_rows`` raises at digest-publication time, which is the right
    behaviour for a single new digest. Assembly reads many already-validated
    digests, and one bad row must not deny every prover turn its context, so
    here the row is dropped instead.
    """
    try:
        rendered = _safe_math_rows([row], category)
    except ValueError:
        return ""
    return rendered[0] if rendered else ""


def _statement_core(statement: str) -> str:
    """Normalize a rendered statement for dedup (strip evidence suffixes)."""
    text = str(statement)
    text = re.sub(r"\s*\[evidence:.*?\]\s*", " ", text, flags=re.I | re.S)
    text = re.sub(r"\s*\[reason:.*?\]\s*", " ", text, flags=re.I | re.S)
    text = re.sub(r"\s*\[sha256:.*?\]\s*", " ", text, flags=re.I | re.S)
    text = re.sub(
        r"\s*\[carried from a superseded packet; reprove\]\s*",
        " ",
        text,
        flags=re.I,
    )
    return " ".join(text.lower().split())


def _dedup_key_for_row(
    raw: Dict[str, Any], category: str, section: str, statement: str
) -> str:
    if category == "computation" and isinstance(raw.get("sha256"), str):
        return "computation:" + raw["sha256"]
    return "%s:%s" % (section, _statement_core(statement))


def _rank_tuple(
    rank_key: str,
    *,
    packet_redundant: bool,
    fresh: bool,
    reinforced: bool,
    ordinal: int,
) -> tuple:
    return (
        CATEGORY_RANK[rank_key],
        1 if packet_redundant else 0,
        0 if fresh else 1,
        0 if reinforced else 1,
        -ordinal,
    )


def _packet_tokens(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _is_packet_redundant(statement: str, packet_lower: str, packet_tokens: Set[str]) -> bool:
    """Conservative: high overlap plus a distinctive anchor into the packet.

    Applied only to source-established and candidate rows. Never used to drop
    invalid constraints or mechanical/computation rows.
    """
    if not packet_tokens:
        return False
    core = _statement_core(statement)
    tokens = set(re.findall(r"[a-z0-9]{3,}", core))
    if len(tokens) < 8:
        return False
    overlap = len(tokens & packet_tokens) / float(len(tokens))
    if overlap < 0.72:
        return False
    fnd_ids = re.findall(r"fnd-\d+", core)
    if fnd_ids and any(fid in packet_lower for fid in fnd_ids):
        return True
    distinctive = {token for token in tokens if len(token) >= 8}
    if not distinctive:
        return False
    dist_overlap = len(distinctive & packet_tokens) / float(len(distinctive))
    return dist_overlap >= 0.65 and overlap >= 0.75


def _digest_rows(
    digest: Dict[str, Any],
    ordinal: int,
    fresh: bool,
    *,
    force_archive_dependencies: bool = False,
) -> List[Dict[str, Any]]:
    """Flatten one digest into ranked rows, demoting stale source claims.

    A packet change can retract or restate the findings and locators a digest
    leaned on, so a stale ``source``-evidenced fact is no longer established --
    it becomes a candidate requiring proof. Stale ``mechanical`` facts and
    sha-pinned computations are arithmetic and survive unchanged, and a refuted
    step stays refuted because its reason is self-contained.
    """
    rows: List[Dict[str, Any]] = []
    plan = [
        ("established", digest.get("established_facts") or []),
        ("candidate", digest.get("candidate_ideas") or []),
        ("invalid", digest.get("invalid_steps") or []),
        ("computation", digest.get("reusable_computations") or []),
        ("dependency", digest.get("unresolved_dependencies") or []),
    ]
    for category, values in plan:
        for row in values:
            if not isinstance(row, dict):
                continue
            section = category
            demoted = False
            if (
                category == "established"
                and not fresh
                and row.get("evidence_class") != "mechanical"
            ):
                section = "candidate"
                demoted = True
            statement = _render_row(
                row, "candidate" if demoted else category
            )
            if not statement:
                continue
            if demoted:
                statement += " [carried from a superseded packet; reprove]"
            if category == "established" and not demoted:
                rank_key = (
                    "established_mechanical"
                    if row.get("evidence_class") == "mechanical"
                    else "established_source"
                )
            elif demoted:
                rank_key = "candidate"
            else:
                rank_key = category
            force_archive = bool(
                category == "dependency" and force_archive_dependencies
            )
            rows.append(
                {
                    "section": section,
                    "statement": statement,
                    "fresh": fresh,
                    "ordinal": ordinal,
                    "rank_key": rank_key,
                    "rank": _rank_tuple(
                        rank_key,
                        packet_redundant=False,
                        fresh=fresh,
                        reinforced=False,
                        ordinal=ordinal,
                    ),
                    "dedup_key": _dedup_key_for_row(
                        row, category, section, statement
                    ),
                    "demoted": demoted,
                    "packet_redundant": False,
                    "reinforced": False,
                    "force_archive": force_archive,
                }
            )
    return rows


def collect_working_rows(campaign: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gather every campaign digest into deduplicated, ranked rows."""
    from .campaigns import campaign_packet_record, packet_binding_matches

    campaign_id = str(campaign["id"])
    digests = []
    for path in sorted(DIGEST_DIR.glob("DIGEST-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("campaign_id") == campaign_id:
            digests.append(value)
    packet_text = ""
    try:
        packet_text = str(campaign_packet_record(campaign_id).get("_text") or "")
    except Exception:
        packet_text = ""
    packet_lower = packet_text.lower()
    packet_tokens = _packet_tokens(packet_text)
    max_ordinal = len(digests)
    eligible_dep_ordinals = {
        ordinal
        for ordinal in range(
            max(1, max_ordinal - DEPENDENCY_DIGEST_WINDOW + 1),
            max_ordinal + 1,
        )
    }

    key_counts: Dict[str, int] = {}
    raw_rows: List[Dict[str, Any]] = []
    for ordinal, digest in enumerate(digests, 1):
        fresh = packet_binding_matches(digest, campaign_id)
        force_archive_deps = ordinal not in eligible_dep_ordinals
        for row in _digest_rows(
            digest,
            ordinal,
            fresh,
            force_archive_dependencies=force_archive_deps,
        ):
            key_counts[row["dedup_key"]] = key_counts.get(row["dedup_key"], 0) + 1
            raw_rows.append(row)

    rows: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    for row in raw_rows:
        reinforced = key_counts.get(row["dedup_key"], 0) >= 2
        # Source-established and candidate rows may restate packet material;
        # demote them in rank so primary prefers net-new content. Never mark
        # invalid/mechanical/computation rows redundant this way.
        packet_redundant = False
        if row["rank_key"] in ("established_source", "candidate"):
            packet_redundant = _is_packet_redundant(
                row["statement"], packet_lower, packet_tokens
            )
        row = dict(row)
        row["reinforced"] = reinforced
        row["packet_redundant"] = packet_redundant
        row["rank"] = _rank_tuple(
            row["rank_key"],
            packet_redundant=packet_redundant,
            fresh=row["fresh"],
            reinforced=reinforced,
            ordinal=int(row["ordinal"]),
        )
        existing = seen.get(row["dedup_key"])
        if existing is None:
            seen[row["dedup_key"]] = row
            rows.append(row)
        elif row["rank"] < existing["rank"]:
            # Keep the strongest surviving copy: a fact restated against a
            # current packet outranks the same fact carried from a stale one.
            # Preserve force_archive=False if any copy is injectable.
            force_archive = existing["force_archive"] and row["force_archive"]
            existing.update(row)
            existing["force_archive"] = force_archive
        else:
            if not row["force_archive"]:
                existing["force_archive"] = False
            if reinforced:
                existing["reinforced"] = True
                existing["rank"] = _rank_tuple(
                    existing["rank_key"],
                    packet_redundant=bool(existing.get("packet_redundant")),
                    fresh=existing["fresh"],
                    reinforced=True,
                    ordinal=int(existing["ordinal"]),
                )
    rows.sort(key=lambda item: item["rank"])
    return rows


def _render_tier(
    title: str,
    preamble: List[str],
    rows: List[Dict[str, Any]],
    *,
    headings: Optional[Dict[str, str]] = None,
) -> str:
    heading_map = headings or SECTION_HEADINGS
    lines = ["# " + title, ""]
    lines.extend(preamble)
    for category, _default in SECTIONS:
        heading = heading_map.get(category, SECTION_HEADINGS[category])
        section_rows = [row for row in rows if row["section"] == category]
        lines.extend(["", "## " + heading, ""])
        if section_rows:
            lines.extend("- " + row["statement"] for row in section_rows)
        else:
            lines.append("- None recorded.")
    return "\n".join(lines) + "\n"


def _row_cost(row: Dict[str, Any]) -> int:
    return len(("- " + row["statement"] + "\n").encode("utf-8"))


def _section_counts(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {category: 0 for category, _ in SECTIONS}
    for row in rows:
        section = str(row.get("section") or "")
        if section in counts:
            counts[section] += 1
    return counts


def _section_bytes(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    totals = {category: 0 for category, _ in SECTIONS}
    for row in rows:
        section = str(row.get("section") or "")
        if section in totals:
            totals[section] += _row_cost(row)
    return totals


def _allocate_tiers(
    rows: List[Dict[str, Any]],
    primary_budget: int = PRIMARY_BUDGET_BYTES,
    extended_budget: int = EXTENDED_BUDGET_BYTES,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split ranked rows into primary, extended and archive tiers.

    Primary uses value-weighted floors then global rank fill under hard caps on
    candidates and dependencies. Extended prefers remaining constraints first so
    anti-repeat signal stays injected even when primary is full. Rows marked
    ``force_archive`` (stale-window dependencies) skip both injected tiers.
    """
    active = [row for row in rows if not row.get("force_archive")]
    forced_archive = [row for row in rows if row.get("force_archive")]
    chosen: Set[int] = set()
    spent = 0
    section_row_counts = {category: 0 for category, _ in SECTIONS}
    section_byte_counts = {category: 0 for category, _ in SECTIONS}

    def _within_primary_caps(row: Dict[str, Any], cost: int) -> bool:
        section = row["section"]
        if section == "dependency":
            if section_row_counts["dependency"] >= PRIMARY_CAP_DEPENDENCY_ROWS:
                return False
            dep_cap = int(primary_budget * PRIMARY_CAP_DEPENDENCY_SHARE)
            if section_byte_counts["dependency"] + cost > dep_cap:
                return False
        if section == "candidate":
            if section_row_counts["candidate"] >= PRIMARY_CAP_CANDIDATE_ROWS:
                return False
            cand_cap = int(primary_budget * PRIMARY_CAP_CANDIDATE_SHARE)
            if section_byte_counts["candidate"] + cost > cand_cap:
                return False
        return True

    def _take_primary(row: Dict[str, Any], cost: int) -> bool:
        nonlocal spent
        if id(row) in chosen:
            return False
        if spent + cost > primary_budget:
            return False
        if not _within_primary_caps(row, cost):
            return False
        chosen.add(id(row))
        spent += cost
        section_row_counts[row["section"]] += 1
        section_byte_counts[row["section"]] += cost
        return True

    # Phase 1: floors for high-value sections (skip rows that do not fit the
    # remaining floor rather than stopping early on one oversized statement).
    floor_invalid = int(primary_budget * PRIMARY_FLOOR_INVALID)
    floor_mech = int(primary_budget * PRIMARY_FLOOR_MECH_COMP)
    floor_source = int(primary_budget * PRIMARY_FLOOR_SOURCE)
    inv_spent = 0
    for row in active:
        if row["section"] != "invalid":
            continue
        cost = _row_cost(row)
        if inv_spent + cost > floor_invalid:
            continue
        if _take_primary(row, cost):
            inv_spent += cost
    mech_spent = 0
    for row in active:
        if row.get("rank_key") not in (
            "computation",
            "established_mechanical",
        ):
            continue
        cost = _row_cost(row)
        if mech_spent + cost > floor_mech:
            continue
        if _take_primary(row, cost):
            mech_spent += cost
    source_spent = 0
    for row in active:
        if (
            row.get("rank_key") != "established_source"
            or not row.get("fresh")
            or row.get("demoted")
            or row.get("packet_redundant")
        ):
            continue
        cost = _row_cost(row)
        if source_spent + cost > floor_source:
            continue
        if _take_primary(row, cost):
            source_spent += cost
    # Frontier floor: keep a short list of open obligations visible in primary
    # even when established bulk would otherwise exhaust the budget.
    floor_dependency = int(primary_budget * PRIMARY_FLOOR_DEPENDENCY)
    dep_spent = 0
    for row in active:
        if row["section"] != "dependency":
            continue
        cost = _row_cost(row)
        if dep_spent + cost > floor_dependency:
            continue
        if _take_primary(row, cost):
            dep_spent += cost

    # Phase 2: global rank fill under caps.
    for row in active:
        if id(row) in chosen:
            continue
        _take_primary(row, _row_cost(row))

    primary = [row for row in active if id(row) in chosen]
    remaining = [row for row in active if id(row) not in chosen]

    def _extended_priority(row: Dict[str, Any]) -> tuple:
        rank_key = str(row.get("rank_key") or row.get("section") or "")
        if row["section"] == "invalid":
            section_pri = 0
        elif rank_key in ("computation", "established_mechanical"):
            section_pri = 1
        elif row["section"] == "established":
            section_pri = 2
        elif row["section"] == "candidate":
            section_pri = 3
        else:
            section_pri = 4
        return (section_pri, row["rank"])

    remaining_sorted = sorted(remaining, key=_extended_priority)
    extended: List[Dict[str, Any]] = []
    taken: Set[int] = set()
    ext_spent = 0
    ext_deps = 0
    for row in remaining_sorted:
        cost = _row_cost(row)
        if ext_spent + cost > extended_budget:
            continue
        if row["section"] == "dependency":
            # Prefer archiving open TODOs; keep only a thin fresh frontier.
            if not row.get("fresh") or ext_deps >= EXTENDED_CAP_DEPENDENCY_ROWS:
                continue
            ext_deps += 1
        extended.append(row)
        taken.add(id(row))
        ext_spent += cost
    archive = [
        row for row in remaining if id(row) not in taken
    ] + forced_archive
    # Preserve global rank order inside each tier for stable rendering.
    primary.sort(key=lambda item: item["rank"])
    extended.sort(key=lambda item: item["rank"])
    archive.sort(key=lambda item: item["rank"])
    return {"primary": primary, "extended": extended, "archive": archive}


def _write_tier(text: str, prefix: str) -> Dict[str, str]:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path = WORKING_CONTEXT_DIR / ("%s-%s.md" % (prefix, content_hash[:16]))
    if not path.exists():
        atomic_write_text(path, text)
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


PRIMARY_TITLE = "Mathematical working context"
PRIMARY_PREAMBLE = [
    "Treat candidates as unproved. Reprove every fact used in the "
    "final argument. Constraints below are hard stops: do not walk "
    "them again.",
]
EXTENDED_TITLE = "Extended mathematical working context"
EXTENDED_PREAMBLE = [
    "Overflow working context. Prefer primary when both apply. "
    "Constraints here still apply — do not repeat them. Candidates "
    "remain unproved and must be established independently before use.",
]
ARCHIVE_PREAMBLE = [
    "Retired context, retained for diagnosis and for review when a "
    "similar pattern recurs. Not supplied to prover turns.",
]


def _scaffolding_bytes(
    title: str,
    preamble: List[str],
    *,
    headings: Optional[Dict[str, str]] = None,
) -> int:
    """Bytes a tier costs before any row is added."""
    return len(
        _render_tier(title, preamble, [], headings=headings).encode("utf-8")
    )


def merge_working_context(campaign: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble every mined digest into the three working-context tiers."""
    rows = collect_working_rows(campaign)
    # The caps are on the rendered files, so headings come out of the budget.
    tiers = _allocate_tiers(
        rows,
        PRIMARY_BUDGET_BYTES
        - _scaffolding_bytes(
            PRIMARY_TITLE, PRIMARY_PREAMBLE, headings=PRIMARY_SECTION_HEADINGS
        ),
        EXTENDED_BUDGET_BYTES
        - _scaffolding_bytes(EXTENDED_TITLE, EXTENDED_PREAMBLE),
    )
    primary = _write_tier(
        _render_tier(
            PRIMARY_TITLE,
            PRIMARY_PREAMBLE,
            tiers["primary"],
            headings=PRIMARY_SECTION_HEADINGS,
        ),
        "WORKING",
    )
    extended = _write_tier(
        _render_tier(EXTENDED_TITLE, EXTENDED_PREAMBLE, tiers["extended"]),
        "WORKING-EXT",
    )
    archive = _write_tier(
        _render_tier(
            "Archived mathematical working context",
            ARCHIVE_PREAMBLE,
            tiers["archive"],
        ),
        "WORKING-ARCHIVE",
    )
    primary_bytes = sum(_row_cost(row) for row in tiers["primary"])
    primary_by_section = _section_bytes(tiers["primary"])
    extended_by_section = _section_bytes(tiers["extended"])
    return {
        "primary": primary,
        "extended": extended,
        "archive": archive,
        "stats": {
            "rows_total": len(rows),
            "rows_primary": len(tiers["primary"]),
            "rows_extended": len(tiers["extended"]),
            "rows_archived": len(tiers["archive"]),
            "rows_fresh": sum(1 for row in rows if row["fresh"]),
            "rows_demoted": sum(1 for row in rows if row["demoted"]),
            "rows_primary_by_section": _section_counts(tiers["primary"]),
            "rows_extended_by_section": _section_counts(tiers["extended"]),
            "bytes_primary": primary_bytes,
            "bytes_extended": sum(
                _row_cost(row) for row in tiers["extended"]
            ),
            "bytes_archive": sum(_row_cost(row) for row in tiers["archive"]),
            "bytes_primary_by_section": primary_by_section,
            "bytes_extended_by_section": extended_by_section,
            "primary_constraint_share": (
                primary_by_section.get("invalid", 0) / float(primary_bytes)
                if primary_bytes
                else 0.0
            ),
            "primary_fresh_share": (
                sum(1 for row in tiers["primary"] if row["fresh"])
                / float(len(tiers["primary"]))
                if tiers["primary"]
                else 0.0
            ),
            "primary_redundant_rows": sum(
                1 for row in tiers["primary"] if row.get("packet_redundant")
            ),
            "constraints_in_extended": sum(
                1
                for row in tiers["extended"]
                if row["section"] == "invalid"
            ),
        },
    }


def publish_working_context(
    campaign: Dict[str, Any],
    task: Dict[str, Any],
    digest: Dict[str, Any],
) -> Dict[str, Any]:
    record = merge_working_context(campaign)
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
    """Return the working-context files supplied to a prover turn.

    Only the primary and extended tiers are injected. The archive tier exists
    for diagnosis and is never handed to a prover.
    """
    merged = merge_working_context(campaign)
    return [merged["primary"], merged["extended"]]


def working_context_paths(record: Dict[str, Any]) -> List[Dict[str, str]]:
    """Normalize a ledger ``working_context`` value into path/hash records.

    Events recorded before the context was tiered carry a single flat
    ``{path, sha256}``; newer ones carry a record per tier.
    """
    if not isinstance(record, dict):
        return []
    if isinstance(record.get("path"), str):
        return [record]
    return [
        value
        for key in ("primary", "extended", "archive")
        for value in [record.get(key)]
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]


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
    *,
    review_engines: Optional[Sequence[str]] = None,
    escalation_order: Optional[Sequence[str]] = None,
    include_untried: bool = True,
) -> List[Dict[str, Any]]:
    """Preview paired paid steps without executing engines.

    ``standard_ready`` is emitted as an executable ``standard-fallback`` step.
    Trace-mining steps name the independent miner (not the source engine).
    Non-executable diagnostic states keep ``condition: current_state``.
    """
    from .routing import load_routing_config, select_reviewer

    escalation = list(
        escalation_order
        if escalation_order is not None
        else load_routing_config()["escalation_order"]
    )
    # Miners come from the review pool when provided; otherwise fall back to
    # the prover pool so standalone previews still resolve a miner.
    allowed_miners = list(
        review_engines if review_engines is not None else engines
    )
    events = []
    for engine in engines:
        state = pair_state(campaign, engine)["state"]
        if state == "forced_untried" and include_untried:
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
        elif state == "standard_ready":
            events.append(
                {
                    "phase": "standard-fallback",
                    "task_id": "TASK-%s-STANDARD-FALLBACK" % campaign["id"],
                    "engine": engine,
                    "condition": "always",
                    "packet_sha256": packet["packet_sha256"],
                }
            )
        elif state in {
            "forced_trace_mining",
            "standard_trace_mining",
            "infrastructure_trace_mining",
        }:
            miner = select_reviewer(
                engine,
                set(),
                escalation,
                allowed=allowed_miners,
            )
            if miner is None:
                events.append(
                    {
                        "phase": "trace-mining",
                        "task_id": "TASK-%s-TRACE-MINING" % campaign["id"],
                        "engine": None,
                        "source_engine": engine,
                        "condition": "blocked_no_miner",
                        "packet_sha256": packet["packet_sha256"],
                    }
                )
            else:
                events.append(
                    {
                        "phase": "trace-mining",
                        "task_id": "TASK-%s-TRACE-MINING" % campaign["id"],
                        "engine": miner,
                        "source_engine": engine,
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
        for context in working_context_paths(event.get("working_context")):
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
