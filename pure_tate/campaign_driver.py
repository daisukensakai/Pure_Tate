import json
import datetime
import hashlib
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .agents import load_engines, run_task
from .artifacts import load_artifacts, next_artifact_id
from .campaigns import (
    case_verified,
    campaign_status,
    load_campaign,
    load_campaign_attempts,
    novelty_status,
    write_campaign_packet,
)
from .capabilities import (
    WEB_CAPABILITIES,
    capability_is_attested,
    declared_capabilities,
    load_capability_attestation,
)
from .experiments import experiment_tasks, run_experiment
from .findings import adjudicate_finding, load_findings, record_review_findings
from .health import (
    eligible_engine_pool,
    engine_health_state,
    engine_runtime_issue,
    operational_engine_pool,
)
from .novelty import novelty_tasks
from .notifications import notify_campaign_run, notify_campaign_step
from .routing import (
    load_routing_config,
    high_tier_chain_order,
    next_escalation_engine,
    record_high_tier_dispatch,
    select_prover_for_cell,
    select_reviewer,
)
from .run_lifecycle import (
    CampaignAlreadyRunning,
    CampaignRunLock,
    live_run_ledgers,
    recover_stale_run_ledgers,
    release_artifact_reservation,
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from .store import ROOT, atomic_write_json, load_repository
from .tasking import (
    campaign_mathematics_tasks,
    finding_audit_tasks,
    review_tasks,
)
from .paired import (
    DIGEST_DIR,
    ArtifactValidationError,
    PairedInfrastructureError,
    SubstantiveAttemptError,
    attempt_pending_recoveries,
    dry_run_preview,
    forced_task,
    pair_state,
    problem_key,
    publish_working_context,
    record_event,
    recover_attempt_from_trace,
    standard_fallback_task,
    trace_mining_task,
    unrecovered_validation_traces,
    working_context_records,
)


CAMPAIGN_PHASES = {
    "finding-audit",
    "novelty",
    "experiment",
    "mathematics",
    "review",
    "forced-proof",
    "trace-mining",
    "standard-fallback",
}
RUN_LEDGER_DIR = ROOT / "reports" / "runs"


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _new_run_ledger(
    campaign_id: str,
    steps: int,
    research_engines: Sequence[str],
    prover_engines: Sequence[str],
    review_engines: Sequence[str],
) -> Tuple[Dict[str, Any], Path]:
    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = "RUN-%s-%s-%d" % (
        campaign_id,
        now.strftime("%Y%m%dT%H%M%S%fZ"),
        os.getpid(),
    )
    path = RUN_LEDGER_DIR / (run_id + ".json")
    ledger = {
        "schema_version": 2,
        "run_id": run_id,
        "campaign_id": campaign_id,
        "parent_pid": os.getpid(),
        "parent_process_group": os.getpgrp(),
        "status": "running",
        "started_at": now.isoformat(),
        "requested_steps": steps,
        "engine_pools": {
            "research": list(research_engines),
            "prover": list(prover_engines),
            "review": list(review_engines),
        },
        "events": [],
    }
    _write_run_ledger(path, ledger)
    return ledger, path


def _write_run_ledger(path: Path, ledger: Dict[str, Any]) -> None:
    atomic_write_json(path, ledger)
    atomic_write_json(RUN_LEDGER_DIR / "latest.json", ledger)


def _campaign_reviews(campaign_id: str) -> List[Dict[str, Any]]:
    return [
        task
        for task in review_tasks()
        if task.get("campaign_id") == campaign_id
    ]


def _load_bearing_experiments(campaign_id: str) -> List[Dict[str, Any]]:
    attempts = load_campaign_attempts(campaign_id)
    declared = {
        experiment_id
        for attempt in attempts
        for experiment_id in attempt.get("experiment_ids", [])
        if isinstance(experiment_id, str)
    }
    return [
        task
        for task in experiment_tasks(campaign_id)
        if task["experiment_id"] in declared
    ]


def _finding_audit_is_blocking(task: Dict[str, Any]) -> bool:
    finding = task.get("finding", {})
    return bool(
        finding.get("contradicts_claim_ids")
        or finding.get("blocks_campaign_packet")
    )


def _subproblem_engines_used(
    attempts: Sequence[Dict[str, Any]], subproblem_id: str
) -> Set[str]:
    return {
        str(item["engine"])
        for item in attempts
        if item.get("subproblem_id") == subproblem_id
        and isinstance(item.get("engine"), str)
        and item["engine"]
    }


def _escalation_ladder_exhausted(used_engines: Iterable[str]) -> bool:
    """True when every engine on the retry ladder has already been tried."""
    used = {engine for engine in used_engines if engine}
    if not used:
        return False
    routing = load_routing_config()
    return (
        next_escalation_engine(
            used,
            routing["escalation_order"],
            high_tier_order=routing["high_tier_chain_engines"],
        )
        is None
    )


def _math_task(
    campaign_id: str,
    exclude_task_ids: Optional[Set[str]] = None,
    retry: bool = False,
) -> Optional[Dict[str, Any]]:
    tasks = campaign_mathematics_tasks(campaign_id)
    attempts = load_campaign_attempts(campaign_id)
    by_task: Dict[str, List[Dict[str, Any]]] = {}
    for attempt in attempts:
        by_task.setdefault(str(attempt.get("task_id")), []).append(attempt)
    excluded = exclude_task_ids or set()
    lane_load = Counter(item.get("lane") for item in attempts)
    subproblem_load = Counter(item.get("subproblem_id") for item in attempts)
    for task in tasks:
        if task["id"] in excluded:
            lane_load[task["lane"]] += 1
            subproblem_load[task["subproblem_id"]] += 1
    eligible = []
    for task in tasks:
        if task.get("status") != "ready":
            continue
        prior = by_task.get(task["id"], [])
        if task["id"] in excluded:
            continue
        if prior and not retry:
            # First-pass scheduling skips tried cells unless the forward-only
            # retry ladder is exhausted.  Then a fresh rotation start is
            # allowed so the bottleneck can reuse engines with new context.
            used = _subproblem_engines_used(
                attempts, str(task.get("subproblem_id") or "")
            )
            if not _escalation_ladder_exhausted(used):
                continue
        eligible.append(task)
    eligible.sort(
        key=lambda task: (
            lane_load[task["lane"]],
            subproblem_load[task["subproblem_id"]],
            task["id"],
        )
    )
    return eligible[0] if eligible else None


def next_campaign_task(
    campaign_id: str,
    phase: str,
    retry: bool = False,
) -> Optional[Dict[str, Any]]:
    packet = write_campaign_packet(campaign_id)
    campaign = load_campaign(campaign_id)
    started_verified = case_verified(campaign_id)["verified"]
    if phase not in CAMPAIGN_PHASES:
        raise ValueError("unknown campaign phase %s" % phase)
    if phase == "review":
        tasks = _campaign_reviews(campaign_id)
    elif phase == "finding-audit":
        tasks = finding_audit_tasks(campaign_id)
    elif phase == "novelty":
        tasks = novelty_tasks(campaign_id)
    elif phase == "experiment":
        tasks = _load_bearing_experiments(campaign_id)
    elif phase == "forced-proof":
        allowed = set(
            operational_engine_pool(
                list(campaign["paired_attempt_policy"]["engine_order"]),
                "mathematics",
            )
        )
        task = _next_due_forced_task(
            campaign, packet, allowed, dry_run=False
        )
        tasks = [task] if task else []
    elif phase == "trace-mining":
        tasks = []
        for engine in campaign["paired_attempt_policy"]["engine_order"]:
            state = pair_state(campaign, engine)
            if state["state"] not in {
                "forced_trace_mining",
                "standard_trace_mining",
            }:
                continue
            miner = select_reviewer(
                engine,
                set(),
                load_routing_config()["escalation_order"],
            )
            if miner:
                source_turn = (
                    "forced-proof"
                    if state["state"] == "forced_trace_mining"
                    else "standard-fallback"
                )
                task = trace_mining_task(
                    campaign,
                    packet,
                    engine,
                    source_turn,
                    str(state.get("trace_id")),
                )
                task["selected_engine"] = miner
                tasks = [task]
                break
    elif phase == "standard-fallback":
        tasks = []
        for engine in campaign["paired_attempt_policy"]["engine_order"]:
            if pair_state(campaign, engine)["state"] != "standard_ready":
                continue
            base = _math_task(campaign_id, retry=True)
            if base:
                task = standard_fallback_task(
                    base, campaign, working_context_records(campaign)
                )
                task["selected_engine"] = engine
                tasks = [task]
            break
    else:
        task = _math_task(campaign_id, retry=retry)
        tasks = [task] if task else []
    return tasks[0] if tasks else None


def _validate_engine_lists(
    research_engines: Sequence[str],
    prover_engines: Sequence[str],
    review_engines: Sequence[str],
    dry_run: bool,
) -> None:
    configured = load_engines()
    if not research_engines or not prover_engines or not review_engines:
        raise ValueError(
            "campaign driver requires explicit research, prover, and review engines"
        )
    unknown = (
        set(research_engines) | set(prover_engines) | set(review_engines)
    ) - set(configured)
    if unknown:
        raise ValueError("unknown campaign engine(s): %s" % ", ".join(sorted(unknown)))
    if len(set(review_engines)) < 2:
        raise ValueError("two distinct review engines are required")
    declared_web_engines = []
    for engine_id in research_engines:
        declared = set(declared_capabilities(configured[engine_id], "novelty"))
        if WEB_CAPABILITIES.issubset(declared):
            declared_web_engines.append(engine_id)
    if not declared_web_engines:
        raise ValueError("research pool has no declared live-web engine")


def _research_capability_state(
    engine_id: str, phase: str
) -> str:
    attestation = load_capability_attestation(engine_id, phase)
    if attestation is None:
        return "missing"
    return (
        "pass"
        if capability_is_attested(engine_id, phase)
        else "fail"
    )


def _eligible_research_pool(
    engines: Sequence[str], phase: str, dry_run: bool
) -> List[str]:
    configured = load_engines()
    declared = [
        engine_id
        for engine_id in engines
        if WEB_CAPABILITIES.issubset(
            set(declared_capabilities(configured[engine_id], phase))
        )
    ]
    states = {
        engine_id: _research_capability_state(engine_id, phase)
        for engine_id in declared
    }
    if dry_run and all(state == "missing" for state in states.values()):
        # A first no-spend preview remains possible before any live probe. Once
        # a live result exists, dry-run reflects it and excludes failed engines.
        return declared
    attested = [
        engine_id for engine_id in declared if states[engine_id] == "pass"
    ]
    return operational_engine_pool(attested, phase, dry_run=dry_run)


def _research_capability_blocker(
    engines: Sequence[str],
    phase: str,
    excluded_engines: Set[str],
    dry_run: bool,
) -> Optional[Dict[str, Any]]:
    configured = load_engines()
    independent_declared = [
        engine_id
        for engine_id in engines
        if engine_id not in excluded_engines
        and WEB_CAPABILITIES.issubset(
            set(declared_capabilities(configured[engine_id], phase))
        )
    ]
    if not independent_declared:
        return None
    eligible = set(_eligible_research_pool(engines, phase, dry_run))
    if any(engine_id in eligible for engine_id in independent_declared):
        return None
    return {
        "phase": phase,
        "reason": (
            "no independent research engine has both a passing live-web "
            "attestation and an operational local runtime"
        ),
        "independent_engine_states": {
            engine_id: {
                "capability": _research_capability_state(engine_id, phase),
                "runtime_issue": engine_runtime_issue(
                    engine_id, configured[engine_id]
                ),
            }
            for engine_id in independent_declared
        },
        "excluded_engines": sorted(excluded_engines),
    }


def _existing_engines_for_subproblem(campaign_id: str) -> Dict[str, Set[str]]:
    result: Dict[str, Set[str]] = {}
    for attempt in load_campaign_attempts(campaign_id):
        if attempt.get("engine") and attempt.get("subproblem_id"):
            result.setdefault(attempt["subproblem_id"], set()).add(attempt["engine"])
    return result


def _current_ordinary_proof_count(campaign_id: str) -> int:
    """Count fresh rotation starts, excluding paired retries and forced turns."""
    return sum(
        1
        for attempt in load_campaign_attempts(campaign_id)
        if not attempt.get("paired_turn_kind")
    )


def _current_forced_attempts(campaign_id: str) -> List[Dict[str, Any]]:
    return [
        attempt
        for attempt in load_campaign_attempts(campaign_id)
        if attempt.get("paired_turn_kind") == "forced-proof"
    ]


def _next_due_forced_task(
    campaign: Dict[str, Any],
    packet: Dict[str, Any],
    allowed_provers: Set[str],
    *,
    dry_run: bool,
    slot_override: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Return the next periodic Opus/GPT forced-proof slot, if it is due.

    Every third fresh ordinary proof opens a forced slot.  Two consecutive
    slots share one stable high-tier chain: one after start three and the
    partner after start six.
    """
    ordinary = _current_ordinary_proof_count(str(campaign["id"]))
    due_slots = ordinary // 3
    forced = _current_forced_attempts(str(campaign["id"]))
    slot = len(forced) if slot_override is None else slot_override
    if slot >= due_slots:
        return None
    chain_id = "forced:%s:%d" % (campaign["id"], slot // 2)
    order = high_tier_chain_order(chain_id, persist=not dry_run)
    engine = order[slot % 2]
    if engine not in allowed_provers:
        # Do not substitute the partner: this exact forced slot remains due.
        return None
    task = forced_task(campaign, packet, working_context_records(campaign))
    task["selected_engine"] = engine
    task["routing_chain_id"] = chain_id
    task["forced_cycle_slot"] = slot
    return task


def _apply_finding_audit(artifact: Dict[str, Any]) -> None:
    findings = {item["id"]: item for item in load_findings()}
    finding = findings[artifact["finding_id"]]
    if artifact["verdict"] == "retain_candidate":
        return
    if artifact["verdict"] == "promote":
        finding.setdefault("reviewer_engines", []).append(artifact["engine"])
        finding["reviewer_engines"] = sorted(set(finding["reviewer_engines"]))
        # The original adversarial reviewer plus this independent audit must
        # provide two distinct engines before adjudication can promote it.
        if len(set(finding["reviewer_engines"])) < 2:
            return
        adjudicate_finding(
            finding["id"],
            "corroborate",
            artifact.get("contradiction_resolution")
            or "Independent finding audit confirmed exact scope.",
            adjudicator=artifact["id"],
            supporting_engine=artifact["engine"],
            supporting_audit_id=artifact["id"],
        )
    elif artifact["verdict"] == "retire":
        adjudicate_finding(
            finding["id"],
            "retire",
            artifact.get("contradiction_resolution")
            or "Independent finding audit refuted or superseded the candidate.",
            adjudicator=artifact["id"],
        )
    elif artifact["verdict"] == "merge":
        target = artifact.get("merge_target_id")
        adjudicate_finding(
            finding["id"],
            "merge",
            artifact.get("contradiction_resolution")
            or "Independent finding audit established semantic duplication.",
            target_id=target,
            adjudicator=artifact["id"],
        )


def _drive_campaign_unlocked(
    campaign_id: str,
    steps: int,
    research_engines: Sequence[str],
    prover_engines: Sequence[str],
    review_engines: Sequence[str],
    timeout: int = 10800,
    dry_run: bool = False,
    retry: bool = False,
    desktop_notifications: bool = False,
    ntfy_notifications: bool = False,
) -> Dict[str, Any]:
    campaign = load_campaign(campaign_id)
    if steps <= 0 or steps > campaign["batch_step_limit"]:
        raise ValueError(
            "campaign step limit must be between 1 and %d"
            % campaign["batch_step_limit"]
        )
    _validate_engine_lists(
        research_engines, prover_engines, review_engines, dry_run
    )
    routing = load_routing_config()
    started_verified = case_verified(campaign_id)["verified"]
    capability_states = {
        phase: {
            engine_id: _research_capability_state(engine_id, phase)
            for engine_id in research_engines
        }
        for phase in ("finding-audit", "novelty")
    }
    engine_health_states = {
        "mathematics": {
            engine_id: engine_health_state(engine_id, "mathematics")
            for engine_id in prover_engines
        },
        "review": {
            engine_id: engine_health_state(engine_id, "review")
            for engine_id in review_engines
        },
    }
    packet = write_campaign_packet(campaign_id)
    if dry_run:
        ordered = [
            engine
            for engine in campaign["paired_attempt_policy"]["engine_order"]
            if engine in set(prover_engines)
        ]
        preview: List[Dict[str, Any]] = []
        planned_reviewers: Dict[str, Set[str]] = {}
        allowed_reviewers = eligible_engine_pool(
            list(review_engines), "review", dry_run=True
        )
        next_review_number = int(next_artifact_id("reviews").split("-")[1])
        for task in _campaign_reviews(campaign_id):
            if len(preview) >= steps:
                break
            attempt_id = str(task["target_attempt_id"])
            used = {
                item.get("reviewer_engine")
                for item in load_artifacts("reviews")
                if item.get("attempt_id") == attempt_id
            }
            used |= planned_reviewers.get(attempt_id, set())
            engine = select_reviewer(
                task.get("prover_engine"),
                used,
                routing["escalation_order"],
                allowed=allowed_reviewers,
            )
            if engine is None:
                continue
            preview.append(
                {
                    "phase": "review",
                    "task_id": task["id"],
                    "engine": engine,
                    "condition": "always",
                    "output": "proof/reviews/REV-%04d.json"
                    % next_review_number,
                    "packet_sha256": task["packet_sha256"],
                }
            )
            next_review_number += 1
            planned_reviewers.setdefault(attempt_id, set()).add(engine)
        paired_preview = dry_run_preview(
            campaign,
            packet,
            ordered,
            steps,
            review_engines=allowed_reviewers,
            escalation_order=routing["escalation_order"],
            include_untried=False,
        )
        # Keep only executable paired steps. Diagnostic snapshots
        # (current_state) and blocked_no_miner rows are not paid work; live
        # prioritizes pending reviews before paired turns.
        preview.extend(
            event
            for event in paired_preview
            if event.get("condition")
            in {"always", "only_after_substantive_forced_failure"}
        )
        ordinary = _current_ordinary_proof_count(campaign_id)
        completed_forced = len(_current_forced_attempts(campaign_id))
        due_slots = max(0, ordinary // 3 - completed_forced)
        for offset in range(due_slots):
            due_forced = _next_due_forced_task(
                campaign,
                packet,
                set(
                    operational_engine_pool(
                        ordered, "mathematics", dry_run=True
                    )
                ),
                dry_run=True,
                slot_override=completed_forced + offset,
            )
            if due_forced is None:
                continue
            preview.extend(
                [
                    {
                        "phase": "forced-proof",
                        "task_id": due_forced["id"],
                        "engine": due_forced["selected_engine"],
                        "condition": "periodic_due",
                        "packet_sha256": due_forced["packet_sha256"],
                    },
                    {
                        "phase": "standard-fallback",
                        "task_id": "TASK-%s-STANDARD-CONDITIONAL"
                        % campaign_id,
                        "engine": due_forced["selected_engine"],
                        "condition": "only_after_substantive_forced_failure",
                        "packet_sha256": due_forced["packet_sha256"],
                    },
                ]
            )
        # Ordinary cell mathematics (after reviews / paired due work).
        planned_math: Set[str] = set()
        # Seed with historical engines so exhausted ladders preview as fresh
        # rotation rather than as an untried cell.
        used_preview: Dict[str, Set[str]] = {
            subproblem_id: set(engines)
            for subproblem_id, engines in _existing_engines_for_subproblem(
                campaign_id
            ).items()
        }
        math_count = ordinary
        allowed_provers = operational_engine_pool(
            list(prover_engines), "mathematics", dry_run=True
        )
        while len(preview) < steps:
            task = _math_task(
                campaign_id,
                exclude_task_ids=planned_math,
                retry=False,
            )
            if task is None:
                break
            used = used_preview.setdefault(str(task["subproblem_id"]), set())
            engine = select_prover_for_cell(
                math_count,
                used,
                routing["prover_rotation"],
                routing["escalation_order"],
                allowed=allowed_provers,
                chain_id="proof:%s:%s" % (campaign_id, task["id"]),
                persist_chain=False,
            )
            if engine is None:
                break
            preview.append(
                {
                    "phase": "mathematics",
                    "task_id": task["id"],
                    "engine": engine,
                    "condition": "always",
                    "subproblem_id": task.get("subproblem_id"),
                    "packet_sha256": task.get("packet_sha256"),
                }
            )
            planned_math.add(task["id"])
            used.add(engine)
            math_count += 1
        preview = [
            {"step": index + 1, **{k: v for k, v in event.items() if k != "step"}}
            for index, event in enumerate(preview[:steps])
        ]
        engine_configs = load_engines()
        for event in preview:
            output_limit = engine_configs.get(
                str(event.get("engine")), {}
            ).get("max_output_tokens")
            if isinstance(output_limit, int) and output_limit > 0:
                event["max_output_tokens"] = output_limit
        return {
            "campaign_id": campaign_id,
            "dry_run": True,
            "requested_steps": steps,
            "executed_steps": len(preview),
            "stop_reason": "dry_run_preview",
            "events": preview,
            "paired_state_snapshot": {
                engine: pair_state(campaign, engine)["state"]
                for engine in ordered
            },
            "research_capability_states": capability_states,
            "engine_health_states": engine_health_states,
            "capability_blockers": [],
            "run_id": None,
            "run_ledger": None,
        }
    events: List[Dict[str, Any]] = []
    planned_tasks: Set[str] = set()
    deferred_math_tasks: Set[str] = set()
    planned_reviewers: Dict[str, Set[str]] = {}
    planned_research_engines: Dict[Tuple[str, str], Set[str]] = {}
    failed_engines: Set[str] = set()
    # Per (phase, task_id, engine): count of schema/validation failures. The
    # first failure requeues the task for the same engine; a second bans that
    # engine for the rest of the batch so another reviewer can take over.
    schema_validation_failures: Dict[Tuple[str, str, str], int] = {}
    schema_validation_retry_limit = 1
    used_by_subproblem = _existing_engines_for_subproblem(campaign_id)
    campaign_attempt_count = _current_ordinary_proof_count(campaign_id)
    planned_math_count = 0
    capability_blockers: List[Dict[str, Any]] = []
    stop_reason = "step_limit"
    ledger: Optional[Dict[str, Any]] = None
    ledger_path: Optional[Path] = None
    pre_run_recoveries: List[Dict[str, Any]] = []
    if not dry_run:
        # Mandatory: attempt recovery of any paid validation-failure streams
        # before spending another turn on the same task. Reattempts, if still
        # needed, always reserve a new artifact slot and never rewrite.
        pre_run_recoveries = attempt_pending_recoveries(campaign_id)
        ledger, ledger_path = _new_run_ledger(
            campaign_id,
            steps,
            research_engines,
            prover_engines,
            review_engines,
        )
        if pre_run_recoveries:
            ledger["pre_run_recoveries"] = pre_run_recoveries
            _write_run_ledger(ledger_path, ledger)

    for index in range(steps):
        # Finding audits (and other ledger writes) can change the campaign
        # packet mid-batch; always bind tasks to the current packet hash.
        packet = write_campaign_packet(campaign_id)
        current = campaign_status(campaign_id)
        if current["structural_integrity"] != "ready":
            stop_reason = "validation_failure"
            break
        if current["case_verification"]["case_verified"]:
            if current["novelty_certification"]["novelty_certified"]:
                stop_reason = "case_verified_and_novelty_certified"
                break
            if current["novelty_certification"]["reason"] == "conflicting_prior_art":
                stop_reason = "contradictory_novelty_audits"
                break
            if not started_verified:
                stop_reason = "case_verified_awaiting_novelty"
                break
            # A later explicitly authorized batch may perform the two novelty
            # audits; proof work cannot continue after verification.
            phases = ["novelty"]
        else:
            # Ordinary mathematics is intentional work, not a residual else
            # branch. Without this phase the drive can report no_eligible_task
            # while ready proof cells remain (reviews/audits empty, forced
            # slots not yet due).
            phases = [
                "review",
                "paired",
                "experiment",
                "blocking-finding-audit",
                "finding-audit",
                "mathematics",
            ]

        task = None
        phase = ""
        paired_transition_blocked = False
        for candidate_phase in phases:
            if candidate_phase == "review":
                candidates = _campaign_reviews(campaign_id)
            elif candidate_phase == "blocking-finding-audit":
                candidates = [
                    item
                    for item in finding_audit_tasks(campaign_id)
                    if _finding_audit_is_blocking(item)
                ]
            elif candidate_phase == "finding-audit":
                candidates = finding_audit_tasks(campaign_id)
            elif candidate_phase == "novelty":
                candidates = novelty_tasks(campaign_id)
            elif candidate_phase == "experiment":
                candidates = _load_bearing_experiments(campaign_id)
            elif candidate_phase == "paired":
                candidates = []
                allowed_provers = set(
                    operational_engine_pool(
                        list(prover_engines), "mathematics", dry_run=False
                    )
                ) - failed_engines
                allowed_miners = set(
                    operational_engine_pool(
                        list(review_engines), "review", dry_run=False
                    )
                ) - failed_engines
                for paired_engine in campaign[
                    "paired_attempt_policy"
                ]["engine_order"]:
                    if paired_engine not in set(prover_engines):
                        continue
                    if paired_engine in failed_engines:
                        continue
                    state = pair_state(campaign, paired_engine)
                    state_name = state["state"]
                    if state_name == "verified":
                        continue
                    if state_name == "forced_untried":
                        # The periodic cadence below opens new forced slots.
                        continue
                    if state_name in {
                        "forced_trace_mining",
                        "standard_trace_mining",
                        "infrastructure_trace_mining",
                    }:
                        miner = select_reviewer(
                            paired_engine,
                            set(),
                            routing["escalation_order"],
                            allowed=list(allowed_miners),
                        )
                        if miner is None:
                            paired_transition_blocked = True
                            break
                        source_turn = (
                            "forced-proof"
                            if state_name == "forced_trace_mining"
                            else (
                                "standard-fallback"
                                if state_name == "standard_trace_mining"
                                else (
                                    "infrastructure-standard-fallback"
                                    if state.get("retry_turn")
                                    == "standard-fallback"
                                    else "infrastructure-forced-proof"
                                )
                            )
                        )
                        candidates = [
                            trace_mining_task(
                                campaign,
                                packet,
                                paired_engine,
                                source_turn,
                                str(state.get("trace_id")),
                            )
                        ]
                        candidates[0]["selected_engine"] = miner
                        break
                    if state_name == "standard_ready":
                        if paired_engine not in allowed_provers:
                            continue
                        base = _math_task(campaign_id, retry=True)
                        if base is None:
                            continue
                        candidates = [
                            standard_fallback_task(
                                base,
                                campaign,
                                working_context_records(campaign),
                            )
                            ]
                        candidates[0]["selected_engine"] = paired_engine
                        break
                if not candidates and not paired_transition_blocked:
                    due_forced = _next_due_forced_task(
                        campaign,
                        packet,
                        allowed_provers,
                        dry_run=False,
                    )
                    if due_forced is not None:
                        candidates = [due_forced]
            else:
                candidate = _math_task(
                    campaign_id,
                    exclude_task_ids=planned_tasks | deferred_math_tasks,
                    retry=retry,
                )
                candidates = [candidate] if candidate else []
            if candidate_phase == "paired" and paired_transition_blocked:
                break
            candidate = next(
                (
                    item
                    for item in candidates
                    if item
                    and (
                        candidate_phase == "paired"
                        or item["id"] not in planned_tasks
                    )
                ),
                None,
            )
            if candidate:
                task = candidate
                phase = (
                    "finding-audit"
                    if candidate_phase == "blocking-finding-audit"
                    else (
                        candidate.get("paired_turn_kind", "trace-mining")
                        if candidate_phase == "paired"
                        else candidate_phase
                    )
                )
                break
        if task is None:
            stop_reason = (
                "health_failure"
                if paired_transition_blocked
                else "no_eligible_task"
            )
            break

        reservation_path: Optional[Path] = None
        if ledger is None:
            raise RuntimeError("live campaign drive has no run ledger")
        run_id = str(ledger["run_id"])
        if phase == "review":
            attempt_id = str(task["target_attempt_id"])
            used = {
                item.get("reviewer_engine")
                for item in load_artifacts("reviews")
                if item.get("attempt_id") == attempt_id
            }
            used |= planned_reviewers.get(attempt_id, set())
            engine = select_reviewer(
                task.get("prover_engine"),
                used,
                routing["escalation_order"],
                allowed=[
                    item
                    for item in operational_engine_pool(
                        list(review_engines), "review", dry_run=dry_run
                    )
                    if item not in failed_engines
                ],
            )
            if engine is None:
                deferred_math_tasks.add(task["id"])
                # A pending high-tier slot must not block independent proof
                # chains.  The next iteration skips this chain until its
                # preferred model is operational again.
                if not dry_run:
                    continue
                stop_reason = (
                    "health_failure"
                    if not operational_engine_pool(
                        list(review_engines), "review", dry_run=dry_run
                    )
                    else "no_eligible_task"
                )
                break
            artifact_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "proof" / "reviews", "REV", run_id
            )
            output = ROOT / "proof" / "reviews" / (artifact_id + ".json")
            planned_reviewers.setdefault(attempt_id, set()).add(engine)
        elif phase in {"finding-audit", "novelty"}:
            used = set(task.get("excluded_engines", []))
            used |= planned_research_engines.get(
                (phase, str(task.get("finding_id", task.get("attempt_id")))), set()
            )
            eligible_research = _eligible_research_pool(
                research_engines, phase, dry_run
            )
            engine = next(
                (
                    item
                    for item in eligible_research
                    if item not in used and item not in failed_engines
                ),
                None,
            )
            if engine is None:
                blocker = _research_capability_blocker(
                    research_engines, phase, used, dry_run
                )
                if blocker:
                    blocker["task_id"] = task["id"]
                    capability_blockers.append(blocker)
                    stop_reason = "capability_failure"
                else:
                    stop_reason = "no_eligible_task"
                break
            prefix = "FAUD" if phase == "finding-audit" else "NOV"
            directory = (
                ROOT / "research" / "finding-audits"
                if phase == "finding-audit"
                else ROOT / "research" / "novelty-audits"
            )
            artifact_id, reservation_path = reserve_prefixed_artifact(
                directory, prefix, run_id
            )
            output = directory / (artifact_id + ".json")
            planned_research_engines.setdefault(
                (phase, str(task.get("finding_id", task.get("attempt_id")))), set()
            ).add(engine)
        elif phase == "experiment":
            engine = "container:macaulay2"
            output = ROOT / task["output"]
        elif phase == "trace-mining":
            engine = str(task["selected_engine"])
            artifact_id, reservation_path = reserve_prefixed_artifact(
                DIGEST_DIR, "DIGEST", run_id
            )
            output = DIGEST_DIR / (artifact_id + ".json")
        else:
            used = used_by_subproblem.setdefault(task["subproblem_id"], set())
            engine = task.get("selected_engine")
            if not engine:
                allowed_provers = [
                    item
                    for item in operational_engine_pool(
                        list(prover_engines), "mathematics", dry_run=dry_run
                    )
                    if item not in failed_engines
                ]
                engine = select_prover_for_cell(
                    campaign_attempt_count + planned_math_count,
                    used,
                    routing["prover_rotation"],
                    routing["escalation_order"],
                    allowed=allowed_provers,
                    chain_id="proof:%s:%s" % (campaign_id, task["id"]),
                    persist_chain=not dry_run,
                )
            if engine is None:
                stop_reason = (
                    "health_failure"
                    if not operational_engine_pool(
                        list(prover_engines),
                        "mathematics",
                        dry_run=dry_run,
                    )
                    else "no_eligible_task"
                )
                break
            artifact_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "proof" / "attempts", "ATT", run_id
            )
            output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
            used.add(engine)
            task.setdefault(
                "routing_chain_id", "proof:%s:%s" % (campaign_id, task["id"])
            )
            if not task.get("paired_turn_kind"):
                planned_math_count += 1

        event = {
            "step": index + 1,
            "phase": phase,
            "task_id": task["id"],
            "engine": engine,
            "output": str(output.relative_to(ROOT)),
        }
        output_limit = load_engines().get(engine, {}).get(
            "max_output_tokens"
        )
        if isinstance(output_limit, int) and output_limit > 0:
            event["max_output_tokens"] = output_limit
        events.append(event)
        planned_tasks.add(task["id"])
        if dry_run:
            continue
        event["state"] = "running"
        event["started_at"] = _timestamp()
        if ledger is not None and ledger_path is not None:
            ledger["events"] = events
            _write_run_ledger(ledger_path, ledger)

        last_ledger_activity = [0.0]

        def record_activity(
            stream: str, byte_count: int, elapsed: float
        ) -> None:
            event["last_activity_at"] = _timestamp()
            event["last_activity_stream"] = stream
            event["activity_bytes"] = int(
                event.get("activity_bytes", 0)
            ) + byte_count
            if (
                ledger is not None
                and ledger_path is not None
                and elapsed - last_ledger_activity[0] >= 1.0
            ):
                last_ledger_activity[0] = elapsed
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)

        def record_process_start(process_meta: Dict[str, Any]) -> None:
            record = dict(process_meta)
            record["started_at"] = _timestamp()
            event.setdefault("processes", []).append(record)
            event["engine_pid"] = record.get("engine_pid")
            event["engine_process_group"] = record.get(
                "engine_process_group"
            )
            event["supervisor_pid"] = record.get("supervisor_pid")
            if ledger is not None and ledger_path is not None:
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)

        try:
            chain_id = task.get("routing_chain_id")
            if (
                isinstance(chain_id, str)
                and engine in routing["high_tier_chain_engines"]
            ):
                record_high_tier_dispatch(chain_id, engine)
            if phase == "experiment":
                run_experiment(task, output, timeout=timeout)
            else:
                artifact = run_task(
                    task,
                    engine,
                    output,
                    timeout=timeout,
                    progress_callback=record_activity,
                    process_start_callback=record_process_start,
                )
                if phase in {"forced-proof", "standard-fallback"}:
                    record_event(
                        {
                            "event": phase + "_artifact_written",
                            "campaign_id": campaign_id,
                            "problem_key": problem_key(campaign),
                            "engine": engine,
                            "turn_kind": phase,
                            "packet_sha256": task["packet_sha256"],
                            "classification": "substantive",
                            "attempt_id": artifact["id"],
                            "trace_id": artifact["observable_trace_id"],
                            "trace_path": (
                                "research/paired-traces/%s.json"
                                % artifact["observable_trace_id"]
                            ),
                            "trace_sha256": artifact[
                                "observable_trace_sha256"
                            ],
                            "review_state": "pending",
                            "fallback_eligible": False,
                        }
                    )
                if phase == "review":
                    attempts = {
                        item.get("id"): item
                        for item in load_artifacts("attempts")
                        if "_error" not in item
                    }
                    record_review_findings(
                        artifact, attempts[task["target_attempt_id"]]
                    )
                    reviewed_attempt = attempts[task["target_attempt_id"]]
                    if reviewed_attempt.get("paired_problem_key"):
                        record_event(
                            {
                                "event": "paired_review_completed",
                                "campaign_id": campaign_id,
                                "problem_key": reviewed_attempt[
                                    "paired_problem_key"
                                ],
                                "engine": reviewed_attempt["engine"],
                                "turn_kind": reviewed_attempt[
                                    "paired_turn_kind"
                                ],
                                "packet_sha256": reviewed_attempt[
                                    "packet_sha256"
                                ],
                                "classification": "review",
                                "attempt_id": reviewed_attempt["id"],
                                "review_id": artifact["id"],
                                "review_pass": artifact["review_pass"],
                                "reviewer_engine": artifact[
                                    "reviewer_engine"
                                ],
                                "review_state": artifact["verdict"],
                                "fallback_eligible": (
                                    reviewed_attempt["paired_turn_kind"]
                                    == "forced-proof"
                                    and artifact["verdict"]
                                    in {"incomplete", "refuted"}
                                ),
                            }
                        )
                elif phase == "finding-audit":
                    _apply_finding_audit(artifact)
                    packet = write_campaign_packet(campaign_id)
                elif phase == "trace-mining":
                    context_record = publish_working_context(
                        campaign, task, artifact
                    )
                    event["working_context"] = context_record
            event["state"] = "completed"
            event["completed_at"] = _timestamp()
            if output.is_file():
                event["artifact_sha256"] = hashlib.sha256(
                    output.read_bytes()
                ).hexdigest()
        except SubstantiveAttemptError as exc:
            event["error"] = str(exc)
            event["state"] = "substantive_rejected"
            event["completed_at"] = _timestamp()
            event["trace_id"] = exc.trace_id
            event["trace_path"] = exc.trace_path
            trace_path = ROOT / exc.trace_path
            record_event(
                {
                    "event": (
                        "forced_substantive_rejected"
                        if phase == "forced-proof"
                        else "standard_substantive_rejected"
                    ),
                    "campaign_id": campaign_id,
                    "problem_key": problem_key(campaign),
                    "engine": engine,
                    "turn_kind": phase,
                    "packet_sha256": task["packet_sha256"],
                    "classification": "substantive",
                    "trace_id": exc.trace_id,
                    "trace_path": exc.trace_path,
                    "trace_sha256": hashlib.sha256(
                        trace_path.read_bytes()
                    ).hexdigest(),
                    "review_state": "not_applicable",
                    "fallback_eligible": phase == "forced-proof",
                }
            )
            continue
        except ValueError as exc:
            event["error"] = str(exc)
            event["state"] = "failed"
            event["completed_at"] = _timestamp()
            if isinstance(exc, ArtifactValidationError):
                event["trace_id"] = exc.trace_id
                event["trace_path"] = exc.trace_path
                trace_path = ROOT / exc.trace_path
                if trace_path.is_file():
                    event["trace_sha256"] = hashlib.sha256(
                        trace_path.read_bytes()
                    ).hexdigest()
                # Immediate recovery attempt: do not waste a re-run while a
                # paid stream is still recoverable. Never rewrite existing work.
                if phase in {
                    "mathematics",
                    "forced-proof",
                    "standard-fallback",
                } and not output.exists():
                    try:
                        receipt = recover_attempt_from_trace(
                            exc.trace_id, output
                        )
                        event["state"] = "completed"
                        event["recovery"] = receipt
                        event["classification"] = "parser_recovery"
                        event.pop("error", None)
                        if output.is_file():
                            event["artifact_sha256"] = hashlib.sha256(
                                output.read_bytes()
                            ).hexdigest()
                        event["completed_at"] = _timestamp()
                        continue
                    except (OSError, RuntimeError, ValueError) as recovery_exc:
                        event["recovery_attempt"] = {
                            "status": "recovery_failed",
                            "error": str(recovery_exc),
                            "trace_id": exc.trace_id,
                        }
            # Schema/shape failures should not kill the whole batch. Reviews and
            # research allow one same-engine retry; mathematics bans the engine
            # after the first failure so the next prover in rotation can run.
            # Reattempts always reserve a *new* artifact slot (spent IDs are
            # never reused).
            if phase in {
                "review",
                "finding-audit",
                "novelty",
                "trace-mining",
                "mathematics",
                "forced-proof",
                "standard-fallback",
            }:
                if isinstance(engine, str) and engine:
                    failure_key = (phase, str(task["id"]), engine)
                    schema_validation_failures[failure_key] = (
                        schema_validation_failures.get(failure_key, 0) + 1
                    )
                    if phase in {
                        "mathematics",
                        "forced-proof",
                        "standard-fallback",
                    }:
                        failed_engines.add(engine)
                    elif (
                        schema_validation_failures[failure_key]
                        > schema_validation_retry_limit
                    ):
                        failed_engines.add(engine)
                    if phase == "review":
                        planned_reviewers.get(
                            str(task["target_attempt_id"]), set()
                        ).discard(engine)
                    elif phase in {"finding-audit", "novelty"}:
                        planned_research_engines.get(
                            (
                                phase,
                                str(
                                    task.get(
                                        "finding_id", task.get("attempt_id")
                                    )
                                ),
                            ),
                            set(),
                        ).discard(engine)
                planned_tasks.discard(task["id"])
                continue
            stop_reason = "artifact_validation_failure"
            break
        except PairedInfrastructureError as exc:
            event["error"] = str(exc)
            event["state"] = "failed"
            event["completed_at"] = _timestamp()
            event["trace_id"] = exc.trace_id
            event["trace_path"] = exc.trace_path
            trace_path = ROOT / exc.trace_path
            trace_sha256 = hashlib.sha256(trace_path.read_bytes()).hexdigest()
            event["trace_sha256"] = trace_sha256
            detail = str(exc).lower()
            stop_reason = (
                "interrupted" if "interrupted" in detail else "engine_failure"
            )
            record_event(
                {
                    "event": phase + "_infrastructure_failure",
                    "campaign_id": campaign_id,
                    "problem_key": problem_key(campaign),
                    "engine": engine,
                    "turn_kind": phase,
                    "packet_sha256": task["packet_sha256"],
                    "classification": "infrastructure",
                    "trace_id": exc.trace_id,
                    "trace_path": exc.trace_path,
                    "trace_sha256": trace_sha256,
                    "review_state": "not_applicable",
                    "fallback_eligible": False,
                }
            )
            break
        except (OSError, RuntimeError) as exc:
            event["error"] = str(exc)
            event["state"] = "failed"
            event["completed_at"] = _timestamp()
            detail = str(exc).lower()
            if isinstance(engine, str) and engine:
                failed_engines.add(engine)
            if phase in {
                "review",
                "finding-audit",
                "novelty",
                "trace-mining",
            }:
                # Leave the underlying work queued for another engine.
                planned_tasks.discard(task["id"])
                continue
            if "interrupted" in detail:
                stop_reason = "interrupted"
            elif "capabilit" in detail or "attestation" in detail:
                stop_reason = "capability_failure"
            else:
                stop_reason = "engine_failure"
            if phase in {"forced-proof", "standard-fallback"}:
                record_event(
                    {
                        "event": phase + "_infrastructure_failure",
                        "campaign_id": campaign_id,
                        "problem_key": problem_key(campaign),
                        "engine": engine,
                        "turn_kind": phase,
                        "packet_sha256": task["packet_sha256"],
                        "classification": "infrastructure",
                        "review_state": "not_applicable",
                        "fallback_eligible": False,
                    }
                )
            break
        finally:
            # Slot discipline: durable work owns the ID via the on-disk file;
            # any paid turn that produced a recoverable trace permanently spends
            # the reserved slot so a reattempt cannot rewrite or reuse it.
            if reservation_path is not None:
                if output.is_file() and event.get("state") == "completed":
                    release_artifact_reservation(reservation_path)
                elif event.get("trace_id") or event.get("state") in {
                    "failed",
                    "abandoned",
                    "substantive_rejected",
                }:
                    spend_artifact_reservation(
                        reservation_path,
                        reason=str(
                            event.get("state")
                            or event.get("error")
                            or "dispatch_consumed"
                        ),
                        trace_id=(
                            str(event["trace_id"])
                            if event.get("trace_id")
                            else None
                        ),
                        task_id=str(task.get("id") or "") or None,
                    )
                else:
                    spend_artifact_reservation(
                        reservation_path,
                        reason="dispatch_consumed",
                        task_id=str(task.get("id") or "") or None,
                    )
            if desktop_notifications or ntfy_notifications:
                event["notification_delivery"] = notify_campaign_step(
                    campaign_id,
                    event,
                    steps,
                    desktop=desktop_notifications,
                    ntfy=ntfy_notifications,
                )
            if ledger is not None and ledger_path is not None:
                ledger["events"] = events
                _write_run_ledger(ledger_path, ledger)
    if ledger is not None and ledger_path is not None:
        has_failed_events = any(
            event.get("state") in {"failed", "abandoned"}
            for event in events
        )
        if stop_reason == "step_limit" and has_failed_events:
            stop_reason = "step_limit_with_failures"
        ledger["status"] = (
            ("completed_with_failures" if has_failed_events else "completed")
            if stop_reason
            in {
                "step_limit",
                "step_limit_with_failures",
                "no_eligible_task",
                "case_verified_and_novelty_certified",
                "case_verified_awaiting_novelty",
            }
            else "stopped"
        )
        ledger["stop_reason"] = stop_reason
        ledger["completed_at"] = _timestamp()
        ledger["executed_steps"] = len(events)
        _write_run_ledger(ledger_path, ledger)
        if desktop_notifications or ntfy_notifications:
            ledger["run_notification_delivery"] = notify_campaign_run(
                campaign_id,
                len(events),
                steps,
                ledger["status"],
                stop_reason,
                desktop=desktop_notifications,
                ntfy=ntfy_notifications,
            )
            _write_run_ledger(ledger_path, ledger)
    return {
        "campaign_id": campaign_id,
        "dry_run": dry_run,
        "requested_steps": steps,
        "executed_steps": len(events),
        "stop_reason": stop_reason,
        "events": events,
        "pre_run_recoveries": pre_run_recoveries,
        "research_capability_states": capability_states,
        "engine_health_states": engine_health_states,
        "capability_blockers": capability_blockers,
        "run_id": ledger.get("run_id") if ledger else None,
        "run_ledger": (
            str(ledger_path.relative_to(ROOT)) if ledger_path else None
        ),
    }


def drive_campaign(
    campaign_id: str,
    steps: int,
    research_engines: Sequence[str],
    prover_engines: Sequence[str],
    review_engines: Sequence[str],
    timeout: int = 10800,
    dry_run: bool = False,
    retry: bool = False,
    desktop_notifications: bool = False,
    ntfy_notifications: bool = False,
) -> Dict[str, Any]:
    """Drive one campaign under an exclusive, crash-released campaign lease."""
    if dry_run:
        return _drive_campaign_unlocked(
            campaign_id,
            steps,
            research_engines,
            prover_engines,
            review_engines,
            timeout=timeout,
            dry_run=True,
            retry=retry,
            desktop_notifications=desktop_notifications,
            ntfy_notifications=ntfy_notifications,
        )
    with CampaignRunLock(campaign_id):
        recovered = recover_stale_run_ledgers(campaign_id)
        active = live_run_ledgers(campaign_id)
        if active:
            raise CampaignAlreadyRunning(
                "campaign %s has a live legacy drive: %s"
                % (campaign_id, ", ".join(active))
            )
        result = _drive_campaign_unlocked(
            campaign_id,
            steps,
            research_engines,
            prover_engines,
            review_engines,
            timeout=timeout,
            dry_run=False,
            retry=retry,
            desktop_notifications=desktop_notifications,
            ntfy_notifications=ntfy_notifications,
        )
        result["recovered_stale_runs"] = recovered
        result.setdefault("pre_run_recoveries", [])
        # Surface any still-unrecovered paid streams so operators know not to
        # re-run blindly; recovery is mandatory before another paid attempt.
        result["unrecovered_validation_traces"] = unrecovered_validation_traces(
            campaign_id
        )
        return result
