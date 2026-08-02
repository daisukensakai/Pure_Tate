from pathlib import Path
from typing import Any, Dict, List, Sequence

from .agents import load_engines, run_task
from .artifacts import load_artifacts, next_artifact_id
from .board import build_board, next_task
from .proofs import audit_proofs
from .findings import record_review_findings
from .health import operational_engine_pool, eligible_engine_pool, engine_health_state
from .packets import write_case_packets
from .routing import (
    load_routing_config,
    record_high_tier_dispatch,
    select_prover_for_cell,
    select_reviewer,
)
from .store import ROOT, load_repository
from .targets import CONTEXT_REVISION
from .tasking import review_tasks


def _validate_engines(
    provers: Sequence[str], reviewers: Sequence[str]
) -> None:
    configured = load_engines()
    if not provers or not reviewers:
        raise ValueError("driver requires explicit prover and review engines")
    unknown = sorted((set(provers) | set(reviewers)) - set(configured))
    if unknown:
        raise ValueError("unknown driver engine(s): %s" % ", ".join(unknown))
    if len(set(reviewers)) < 2:
        raise ValueError("two distinct review engines are required")


def _current_attempt_engines_by_task() -> Dict[str, List[str]]:
    by_task: Dict[str, List[str]] = {}
    for attempt in load_artifacts("attempts"):
        if "_error" in attempt:
            continue
        if attempt.get("context_revision") != CONTEXT_REVISION:
            continue
        task_id = attempt.get("task_id")
        engine = attempt.get("engine")
        if not isinstance(task_id, str) or not task_id:
            continue
        if not isinstance(engine, str) or not engine:
            continue
        by_task.setdefault(task_id, []).append(engine)
    return by_task


def _current_math_attempt_count() -> int:
    return sum(
        1
        for attempt in load_artifacts("attempts")
        if "_error" not in attempt
        and attempt.get("context_revision") == CONTEXT_REVISION
    )


def drive(
    steps: int,
    prover_engines: Sequence[str],
    review_engines: Sequence[str],
    timeout: int = 3600,
    dry_run: bool = False,
    retry: bool = False,
) -> Dict[str, Any]:
    if steps <= 0:
        raise ValueError("driver step limit must be positive")
    routing = load_routing_config()
    provers = list(prover_engines)
    reviewers = list(review_engines)
    _validate_engines(provers, reviewers)
    config, _target, sources, claims, _edges = load_repository()
    events: List[Dict[str, Any]] = []
    planned_math_tasks = set()
    deferred_math_tasks = set()
    planned_math_count = 0
    planned_reviewers_by_attempt: Dict[str, set] = {}
    planned_review_passes = set()
    engines_by_task = _current_attempt_engines_by_task()
    next_attempt_number = int(next_artifact_id("attempts").split("-")[1])
    next_review_number = int(next_artifact_id("reviews").split("-")[1])
    stop_reason = "step_limit"
    health_states = {
        "mathematics": {
            engine: engine_health_state(engine, "mathematics")
            for engine in provers
        },
        "review": {
            engine: engine_health_state(engine, "review")
            for engine in reviewers
        },
    }
    for index in range(steps):
        if not audit_proofs(claims).ok:
            stop_reason = "audit_failure"
            break
        board = build_board(config, claims, sources)
        if board["portfolio"]["verified"]:
            stop_reason = "verified_case_result"
            break
        pending_reviews = [
            task
            for task in review_tasks()
            if (task.get("target_attempt_id"), task.get("review_pass"))
            not in planned_review_passes
        ]
        review = pending_reviews[0] if pending_reviews else None
        if review is not None:
            attempt_id = str(review["target_attempt_id"])
            used = {
                artifact.get("reviewer_engine")
                for artifact in load_artifacts("reviews")
                if artifact.get("attempt_id") == attempt_id
                and artifact.get("context_revision") == CONTEXT_REVISION
                and isinstance(artifact.get("reviewer_engine"), str)
            }
            used |= planned_reviewers_by_attempt.get(attempt_id, set())
            engine = select_reviewer(
                review.get("prover_engine"),
                used,
                routing["escalation_order"],
                allowed=eligible_engine_pool(
                    reviewers, "review", dry_run=dry_run
                ),
            )
            if engine is None:
                stop_reason = (
                    "health_failure"
                    if not eligible_engine_pool(
                        reviewers, "review", dry_run=dry_run
                    )
                    else "no_eligible_task"
                )
                break
            artifact_id = "REV-%04d" % next_review_number
            next_review_number += 1
            output = ROOT / "proof" / "reviews" / (artifact_id + ".json")
            event = {
                "step": index + 1,
                "phase": "review",
                "task_id": review["id"],
                "engine": engine,
                "output": str(output.relative_to(ROOT)),
            }
            planned_review_passes.add((attempt_id, review.get("review_pass")))
            planned_reviewers_by_attempt.setdefault(attempt_id, set()).add(engine)
        else:
            task = next_task(
                "mathematics",
                config,
                claims,
                sources,
                retry=retry,
                exclude_task_ids=planned_math_tasks | deferred_math_tasks,
            )
            if task is None:
                stop_reason = "no_eligible_task"
                break
            cell = next(
                (
                    item
                    for item in board["cells"]
                    if item["task_id"] == task["id"]
                ),
                None,
            )
            used_on_cell = list(engines_by_task.get(task["id"], []))
            is_retry = bool(
                cell
                and cell["status"] in {"reviewed_incomplete", "stale_context"}
            )
            ordinal = _current_math_attempt_count() + planned_math_count
            engine = select_prover_for_cell(
                ordinal,
                used_on_cell if is_retry or used_on_cell else [],
                routing["prover_rotation"],
                routing["escalation_order"],
                allowed=operational_engine_pool(
                    provers, "mathematics", dry_run=dry_run
                ),
                chain_id="proof:%s" % task["id"],
                persist_chain=not dry_run,
            )
            if engine is None:
                # Preserve an unavailable high-tier slot and allow another
                # proof chain to make progress in the next scheduler pass.
                deferred_math_tasks.add(task["id"])
                if not dry_run:
                    continue
                stop_reason = (
                    "health_failure"
                    if not eligible_engine_pool(
                        provers, "mathematics", dry_run=dry_run
                    )
                    else "no_eligible_task"
                )
                break
            artifact_id = "ATT-%04d" % next_attempt_number
            next_attempt_number += 1
            output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
            event = {
                "step": index + 1,
                "phase": "mathematics",
                "task_id": task["id"],
                "engine": engine,
                "output": str(output.relative_to(ROOT)),
            }
            review = task
            review["routing_chain_id"] = "proof:%s" % task["id"]
            planned_math_tasks.add(task["id"])
            planned_math_count += 1
            engines_by_task.setdefault(task["id"], []).append(engine)
        events.append(event)
        if dry_run:
            continue
        try:
            if (
                not dry_run
                and review.get("routing_chain_id")
                and engine in routing["high_tier_chain_engines"]
            ):
                record_high_tier_dispatch(review["routing_chain_id"], engine)
            artifact = run_task(review, engine, output, timeout=timeout)
            if review["phase"] == "review":
                attempts = {
                    item.get("id"): item
                    for item in load_artifacts("attempts")
                    if "_error" not in item
                }
                touched = record_review_findings(
                    artifact, attempts[review["target_attempt_id"]]
                )
                if any(
                    item.get("status")
                    in {"corroborated", "mechanically_verified"}
                    for item in touched
                ):
                    target = attempts[review["target_attempt_id"]]["target"]
                    write_case_packets(
                        [(target["g"], target["n"])], claims
                    )
        except (OSError, RuntimeError, ValueError) as exc:
            stop_reason = (
                "artifact_validation_failure"
                if isinstance(exc, ValueError)
                else "engine_failure"
            )
            event["error"] = str(exc)
            break
    return {
        "dry_run": dry_run,
        "requested_steps": steps,
        "executed_steps": len(events),
        "stop_reason": stop_reason,
        "events": events,
        "engine_health_states": health_states,
    }
