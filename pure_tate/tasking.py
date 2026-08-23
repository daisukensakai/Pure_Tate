import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cases import compact_pairs, unresolved_cases
from .models import Claim, Source
from .packets import case_packet_record
from .research import stage_two_ready
from .store import ROOT, load_jsonl
from .targets import CONTEXT_REVISION


APPROACHES = [
    "extend-ckgp-or-gonality-stratification",
    "prove-pure-weight-tate-only",
    "exact-point-count-or-equivariant-stratification",
    "weight-spectral-sequence-or-graph-complex",
    "search-for-surviving-non-tate-motive",
]


def research_tasks() -> List[Dict[str, Any]]:
    return [
        {
            "id": "TASK-R-0001",
            "phase": "research",
            "role": "independent-reduction-auditor",
            "target": "RED-0001",
            "prompt": "prompts/RESEARCH_AUDIT.md",
            "inputs": [
                "data/target.json",
                "data/sources.jsonl",
                "claims named by exact primary-source locators only",
            ],
            "output": "research/audits/RAUD-####.json",
            "status": "ready",
            "created_on": datetime.date.today().isoformat(),
        }
    ]


def _relative(path: str) -> str:
    value = Path(path)
    if value.is_absolute():
        return str(value.relative_to(ROOT))
    return str(value)


def mathematics_tasks(
    config: Dict[str, Any], claims: Dict[str, Claim], sources: Dict[str, Source]
) -> List[Dict[str, Any]]:
    if not stage_two_ready(config, claims, sources):
        raise RuntimeError("Stage 2 is blocked by the independent research-audit gate")
    tasks = []
    ordinal = 1
    for case in unresolved_cases(16, config):
        packet = case_packet_record(case.genus, case.markings, claims)
        packet.pop("_text")
        packet["packet_path"] = _relative(packet["packet_path"])
        for approach in APPROACHES:
            tasks.append(
                {
                    "id": "TASK-M-%04d" % ordinal,
                    "phase": "mathematics",
                    "role": "prover-or-counterexample-searcher",
                    "target_claim_id": "RED-0001",
                    "target": packet["target"],
                    "approach_id": approach,
                    "approach": approach,
                    "context_revision": CONTEXT_REVISION,
                    "packet_id": packet["packet_id"],
                    "packet_revision": packet["packet_revision"],
                    "packet_sha256": packet["packet_sha256"],
                    "input_packet": packet["packet_path"],
                    "relevant_claims": packet["relevant_claims"],
                    "corroborated_findings": packet["corroborated_findings"],
                    "prompt": "prompts/MATHEMATICS.md",
                    "output": "proof/attempts/ATT-####.json",
                    "status": "ready",
                    "created_on": datetime.date.today().isoformat(),
                }
            )
            ordinal += 1
    return tasks


def campaign_mathematics_tasks(campaign_id: str) -> List[Dict[str, Any]]:
    from .artifacts import load_artifacts
    from .campaigns import (
        campaign_carried_forward_verifications,
        campaign_packet_record,
        campaign_quarantined_attempt_ids,
        campaign_route_policy_errors,
        load_campaign,
        load_campaign_attempts,
        packet_binding_matches,
    )
    from .proofs import attempt_is_complete

    campaign = load_campaign(campaign_id)
    packet = campaign_packet_record(campaign_id)
    packet.pop("_text")
    attempts = load_campaign_attempts(campaign_id, current_only=False)
    reviews = load_artifacts("reviews")
    quarantined_attempt_ids = campaign_quarantined_attempt_ids(campaign_id)
    carried_forward = campaign_carried_forward_verifications(campaign_id)

    def carried_record_matches(
        subproblem_id: str, attempt: Dict[str, Any], confirmations: List[Dict[str, Any]]
    ) -> bool:
        record = carried_forward.get(subproblem_id)
        if not isinstance(record, dict):
            return False
        attempt_record = record.get("attempt")
        if not isinstance(attempt_record, dict) or attempt_record.get("id") != attempt.get("id"):
            return False
        attempt_path = Path(str(attempt.get("_path", "")))
        if not attempt_path.is_file() or attempt_record.get("sha256") != hashlib.sha256(attempt_path.read_bytes()).hexdigest():
            return False
        expected_reviews = record.get("reviews")
        if not isinstance(expected_reviews, list):
            return False
        by_id = {item.get("id"): item for item in confirmations}
        for review_record in expected_reviews:
            if not isinstance(review_record, dict):
                return False
            review = by_id.get(review_record.get("id"))
            review_path = Path(str((review or {}).get("_path", "")))
            if not review_path.is_file() or review_record.get("sha256") != hashlib.sha256(review_path.read_bytes()).hexdigest():
                return False
        return True

    verified_dependencies: Dict[str, Dict[str, Any]] = {}
    for attempt in reversed(attempts):
        subproblem_id = attempt.get("subproblem_id")
        if not isinstance(subproblem_id, str):
            continue
        is_current = attempt.get("campaign_revision") == campaign["campaign_revision"]
        candidate_reviews = [
            review
            for review in reviews
            if review.get("attempt_id") == attempt.get("id")
            and review.get("verdict") == "confirmed"
            and review.get("independent") is True
            and review.get("reviewer_engine") != attempt.get("engine")
        ]
        is_carried = carried_record_matches(
            subproblem_id, attempt, candidate_reviews
        )
        if (
            attempt.get("id") in quarantined_attempt_ids
            or subproblem_id in verified_dependencies
            or not (is_current or is_carried)
            or not attempt_is_complete(attempt)
            or (not is_carried and not packet_binding_matches(attempt, campaign_id))
            or campaign_route_policy_errors(campaign, attempt)
        ):
            continue
        confirmations = [
            review
            for review in candidate_reviews
            if is_carried
            or (
                review.get("campaign_revision") == campaign["campaign_revision"]
                and packet_binding_matches(review, campaign_id)
            )
        ]
        # Extra confirmation passes (e.g. principal override audits) are allowed;
        # the gate only requires that both ordinary passes are present.
        if not {1, 2}.issubset(
            {item.get("review_pass") for item in confirmations}
        ):
            continue
        if len({item.get("reviewer_engine") for item in confirmations}) < 2:
            continue
        artifact_records = []
        for artifact in [attempt] + confirmations:
            path = Path(str(artifact["_path"]))
            artifact_records.append(
                {
                    "kind": (
                        "attempt"
                        if artifact is attempt
                        else "confirmation_review"
                    ),
                    "id": artifact.get("id"),
                    "path": str(path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        verified_dependencies[subproblem_id] = {
            "attempt_id": attempt.get("id"),
            "artifacts": artifact_records,
        }
    tasks = []
    for ordinal, subproblem in enumerate(campaign["subproblems"], 1):
        experiment_inputs = []
        experiment_id = subproblem.get("experiment_id")
        if experiment_id:
            for path in sorted(
                (ROOT / "experiments" / "results").glob(
                    experiment_id + "-run-*.json"
                )
            ):
                experiment_inputs.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
        dependency_ids = list(subproblem.get("dependencies", []))
        missing_dependencies = [
            dependency_id
            for dependency_id in dependency_ids
            if dependency_id not in verified_dependencies
        ]
        dependency_inputs = [
            artifact
            for dependency_id in dependency_ids
            for artifact in verified_dependencies.get(
                dependency_id, {}
            ).get("artifacts", [])
        ]
        context_dependency_ids = list(
            subproblem.get("context_dependencies", [])
        )
        context_inputs = [
            artifact
            for dependency_id in context_dependency_ids
            for artifact in verified_dependencies.get(
                dependency_id, {}
            ).get("artifacts", [])
        ]
        own_verification = verified_dependencies.get(subproblem["id"])
        artifact_contract = subproblem.get("artifact_contract")
        task = {
            "id": "TASK-C66-M-%03d" % ordinal,
            "phase": "mathematics",
            "role": "focused-prover-or-counterexample-searcher",
            "campaign_id": campaign_id,
            "campaign_revision": campaign["campaign_revision"],
            "target_claim_id": campaign["target_claim_id"],
            "target": packet["target"],
            "subproblem_id": subproblem["id"],
            "lane": subproblem["lane"],
            "subproblem": subproblem,
            "artifact_contract": artifact_contract,
            "context_revision": campaign["context_revision"],
            "packet_id": packet["packet_id"],
            "packet_sha256": packet["packet_sha256"],
            "packet_binding_sha256": packet.get("packet_binding_sha256"),
            "input_packet": packet["packet_path"],
            "blocked_routes": campaign["blocked_routes"],
            "new_input_declared": [],
            "input_artifacts": (
                dependency_inputs + context_inputs + experiment_inputs
            ),
            "dependency_artifacts": {
                dependency_id: verified_dependencies[
                    dependency_id
                ]["attempt_id"]
                for dependency_id in dependency_ids
                if dependency_id in verified_dependencies
            },
            "context_artifacts": {
                dependency_id: verified_dependencies[
                    dependency_id
                ]["attempt_id"]
                for dependency_id in context_dependency_ids
                if dependency_id in verified_dependencies
            },
            "verified_attempt_id": (
                own_verification["attempt_id"]
                if own_verification is not None
                else None
            ),
            "verification_artifacts": (
                own_verification["artifacts"]
                if own_verification is not None
                else []
            ),
            "blocked_dependencies": missing_dependencies,
            "route_policy": (
                "A blocked route may appear in methods_used only when new_inputs "
                "contains a matching route and evidence description."
            ),
            "prompt": "prompts/CAMPAIGN_MATHEMATICS.md",
            "output": "proof/attempts/ATT-####.json",
            "status": (
                "verified"
                if own_verification is not None
                else (
                    "ready" if not missing_dependencies else "blocked"
                )
            ),
            "created_on": datetime.date.today().isoformat(),
        }
        exact_theorem = subproblem.get("exact_theorem")
        if isinstance(exact_theorem, str) and exact_theorem.strip():
            task["exact_theorem"] = exact_theorem
        tasks.append(task)
    return tasks


def finding_audit_tasks(campaign_id: str) -> List[Dict[str, Any]]:
    from .campaigns import campaign_packet_record, load_campaign
    from .findings import load_findings

    campaign = load_campaign(campaign_id)
    packet = campaign_packet_record(campaign_id)
    packet.pop("_text")
    completed = {
        item.get("finding_id")
        for item in _load_json_objects(
            ROOT / "research" / "finding-audits", "FAUD"
        )
        if item.get("campaign_id") == campaign_id
    }
    candidates = [
        item
        for item in load_findings()
        if item.get("status") == "candidate"
        and item.get("case") in ("all", campaign["case"])
        and item.get("id") not in completed
    ]
    candidates.sort(
        key=lambda item: (
            0 if item.get("contradicts_claim_ids") else 1,
            item.get("id", ""),
        )
    )
    return [
        {
            "id": "TASK-F-%s" % finding["id"],
            "phase": "finding-audit",
            "role": "independent-finding-adjudicator",
            "campaign_id": campaign_id,
            "campaign_revision": campaign["campaign_revision"],
            "context_revision": campaign["context_revision"],
            "finding_id": finding["id"],
            "finding": finding,
            "excluded_engines": sorted(
                set(finding.get("reviewer_engines", []))
                | set(finding.get("supporting_reviewer_engines", []))
            ),
            "target": packet["target"],
            "packet_id": packet["packet_id"],
            "packet_sha256": packet["packet_sha256"],
            "packet_binding_sha256": packet.get("packet_binding_sha256"),
            "input_packet": packet["packet_path"],
            "requires_live_web": True,
            "prompt": "prompts/FINDING_AUDIT.md",
            "output": "research/finding-audits/FAUD-####.json",
            "status": "ready",
            "created_on": datetime.date.today().isoformat(),
        }
        for finding in candidates
    ]


def micro_research_tasks(claims: Dict[str, Claim]) -> List[Dict[str, Any]]:
    questions_path = ROOT / "research" / "questions.jsonl"
    if not questions_path.exists():
        return []
    completed_question_ids = {
        str(item.get("question_id"))
        for item in _load_json_objects(
            ROOT / "research" / "followups", "RF"
        )
        if item.get("context_revision") == CONTEXT_REVISION
        and isinstance(item.get("question_id"), str)
    }
    tasks = []
    for ordinal, question in enumerate(load_jsonl(questions_path), 1):
        if (
            question.get("status") != "open"
            or question.get("id") in completed_question_ids
        ):
            continue
        case = question.get("case", {})
        packet = case_packet_record(case["g"], case["n"], claims)
        packet.pop("_text")
        tasks.append(
            {
                "id": "TASK-Q-%04d" % ordinal,
                "phase": "micro-research",
                "role": "targeted-literature-researcher",
                "question_id": question["id"],
                "question": question,
                "target": packet["target"],
                "context_revision": CONTEXT_REVISION,
                "packet_id": packet["packet_id"],
                "packet_sha256": packet["packet_sha256"],
                "input_packet": _relative(packet["packet_path"]),
                "prompt": "prompts/MICRO_RESEARCH.md",
                "output": "research/followups/RF-####.json",
                "status": "ready",
                "requires_live_web": True,
                "created_on": datetime.date.today().isoformat(),
            }
        )
    return tasks


def _load_json_objects(directory: Path, prefix: str) -> List[Dict[str, Any]]:
    values = []
    for path in sorted(directory.glob(prefix + "-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            value["_path"] = str(path)
            values.append(value)
    return values


def _migration_at_root() -> Dict[str, Any]:
    path = ROOT / "proof" / "migrations" / "context-v2.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def review_tasks(attempt_id: Optional[str] = None) -> List[Dict[str, Any]]:
    from .proofs import derived_attempt_status

    attempts = _load_json_objects(ROOT / "proof" / "attempts", "ATT")
    reviews = _load_json_objects(ROOT / "proof" / "reviews", "REV")
    migration = _migration_at_root()
    legacy = set(migration.get("attempts", {}))
    reviews_by_attempt: Dict[str, List[Dict[str, Any]]] = {}
    review_engines_by_attempt: Dict[str, List[str]] = {}
    for review in reviews:
        if review.get("context_revision") != CONTEXT_REVISION:
            continue
        reviews_by_attempt.setdefault(
            str(review.get("attempt_id")), []
        ).append(review)
        engine = review.get("reviewer_engine")
        if isinstance(engine, str) and engine:
            review_engines_by_attempt.setdefault(
                str(review.get("attempt_id")), []
            ).append(engine)
    tasks = []
    for attempt in attempts:
        current = attempt.get("context_revision") == CONTEXT_REVISION
        compatibility_fixture = not migration and "context_revision" not in attempt
        if attempt.get("id") in legacy or not (current or compatibility_fixture):
            continue
        if attempt.get("campaign_id"):
            from .campaigns import (
                campaign_route_policy_errors,
                load_campaign,
                packet_binding_matches,
            )

            campaign = load_campaign(str(attempt["campaign_id"]))
            if attempt.get("campaign_revision") != campaign.get(
                "campaign_revision"
            ):
                continue
            if not packet_binding_matches(
                attempt, str(attempt["campaign_id"])
            ):
                continue
            if campaign_route_policy_errors(campaign, attempt):
                continue
        if attempt_id and attempt.get("id") != attempt_id:
            continue
        if attempt.get("status") not in {
            "proposed",
            "claimed_complete",
            "verified",
        }:
            continue
        # Completeness is derived from the attempt's structured content, not
        # from the status string the model chose to write. A complete lemma
        # that labelled itself "proposed" must still earn a second pass.
        status = derived_attempt_status(attempt)
        attached = reviews_by_attempt.get(str(attempt.get("id")), [])
        by_pass = {
            review.get("review_pass"): review
            for review in attached
            if review.get("review_pass") in {1, 2}
        }
        adverse = any(
            review.get("verdict") in {"incomplete", "refuted"}
            for review in attached
        )
        if adverse or status == "verified":
            required_passes: List[int] = []
        elif status == "proposed":
            # Incomplete work receives one triage review. A second expensive
            # pass is reserved for an attempt that is actually complete.
            required_passes = [] if 1 in by_pass else [1]
        elif status == "claimed_complete":
            if 1 not in by_pass:
                required_passes = [1]
            elif by_pass[1].get("verdict") == "confirmed" and 2 not in by_pass:
                required_passes = [2]
            else:
                required_passes = []
        else:
            required_passes = []
        for pass_number in required_passes:
            review_task_id = "TASK-V-%s-P%d" % (
                str(attempt.get("id")),
                pass_number,
            )
            input_artifacts = []
            for experiment_id in attempt.get("experiment_ids", []):
                for path in sorted(
                    (ROOT / "experiments" / "results").glob(
                        str(experiment_id) + "-run-*.json"
                    )
                ):
                    input_artifacts.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    )
            campaign_task: Optional[Dict[str, Any]] = None
            if attempt.get("campaign_id"):
                from .campaigns import load_campaign

                campaign = load_campaign(str(attempt["campaign_id"]))
                known_subproblems = {
                    item.get("id") for item in campaign.get("subproblems", [])
                }
                if attempt.get("subproblem_id") in known_subproblems:
                    campaign_task = next(
                        (
                            item
                            for item in campaign_mathematics_tasks(
                                str(attempt["campaign_id"])
                            )
                            if item.get("id") == attempt.get("task_id")
                        ),
                        None,
                    )
                seen_paths = {
                    str(item.get("path"))
                    for item in input_artifacts
                    if isinstance(item, dict)
                }
                for artifact_input in (campaign_task or {}).get(
                    "input_artifacts", []
                ):
                    if not isinstance(artifact_input, dict):
                        continue
                    path = artifact_input.get("path")
                    if not isinstance(path, str) or not path or path in seen_paths:
                        continue
                    input_artifacts.append(dict(artifact_input))
                    seen_paths.add(path)
            tasks.append(
                {
                    "id": review_task_id,
                    "phase": "review",
                    "role": "independent-adversarial-reviewer",
                    "target_attempt_id": attempt.get("id"),
                    "target_task_id": attempt.get("task_id"),
                    "review_pass": pass_number,
                    "context_revision": attempt.get(
                        "context_revision", CONTEXT_REVISION
                    ),
                    "packet_id": attempt.get("packet_id"),
                    "packet_sha256": attempt.get("packet_sha256"),
                    "target": attempt.get("target"),
                    "prover_engine": attempt.get("engine"),
                    "excluded_reviewer_engines": sorted(
                        set(
                            [attempt.get("engine")]
                            + review_engines_by_attempt.get(
                                str(attempt.get("id")), []
                            )
                        )
                        - {None}
                    ),
                    "prompt": "prompts/ADVERSARY.md",
                    "input_attempt": str(Path(attempt["_path"]).relative_to(ROOT)),
                    "input_packet": attempt.get("packet_path"),
                    "output": "proof/reviews/REV-####.json",
                    "status": "ready",
                    "created_on": datetime.date.today().isoformat(),
                    "input_artifacts": input_artifacts,
                    **(
                        {
                            "campaign_id": attempt.get("campaign_id"),
                            "campaign_revision": attempt.get(
                                "campaign_revision"
                            ),
                            "subproblem_id": attempt.get("subproblem_id"),
                            "lane": attempt.get("lane"),
                            "theorem_statement": attempt.get(
                                "theorem_statement"
                            ),
                            "packet_binding_sha256": attempt.get(
                                "packet_binding_sha256"
                            ),
                            "artifact_contract": (campaign_task or {}).get(
                                "artifact_contract"
                            ),
                        }
                        if attempt.get("campaign_id")
                        else {}
                    ),
                }
            )
    return tasks
