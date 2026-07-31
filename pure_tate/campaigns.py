import datetime
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifacts import load_artifacts, sha256_file
from .findings import findings_for_case, load_findings
from .routing import load_routing_config, next_escalation_engine
from .store import DATA, PACKETS_GENERATED, REPORTS_GENERATED, ROOT, atomic_write_json, atomic_write_text, load_json
from .targets import CONTEXT_REVISION, open_input_target, target_formula


DEFAULT_CAMPAIGN = "C66-001"
CAMPAIGN_REVISION = 3
CAMPAIGN_DIR = DATA / "campaigns"
CAMPAIGN_ARTIFACT_DIR = ROOT / "proof" / "campaign-attempts"
NOVELTY_DIR = ROOT / "research" / "novelty-audits"
EXPERIMENT_RESULT_DIR = ROOT / "experiments" / "results"


def load_campaign(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    campaign = load_json(CAMPAIGN_DIR / (campaign_id + ".json"))
    if campaign.get("id") != campaign_id:
        raise ValueError("campaign file id mismatch")
    if campaign.get("context_revision") != CONTEXT_REVISION:
        raise ValueError("campaign has stale target context")
    if campaign.get("campaign_revision") != CAMPAIGN_REVISION:
        raise ValueError("unsupported campaign revision")
    if campaign.get("batch_step_limit") != 12:
        raise ValueError("C66 campaign must retain its 12-step batch limit")
    policy = campaign.get("paired_attempt_policy")
    if (
        not isinstance(policy, dict)
        or policy.get("revision") != 1
        or policy.get("engine_order")
        != ["grok", "gemini", "codex", "claude"]
        or not str(policy.get("exact_theorem", "")).strip()
    ):
        raise ValueError("campaign has an invalid paired-attempt policy")
    return campaign


def campaign_packet_path(campaign_id: str = DEFAULT_CAMPAIGN) -> Path:
    campaign = load_campaign(campaign_id)
    return PACKETS_GENERATED / (
        "%s-v%d.md" % (campaign_id, campaign["campaign_revision"])
    )


def _primary_locator_excerpt(source_id: str) -> str:
    text_path = ROOT / "corpus" / "text" / (source_id + ".txt")
    if not text_path.is_file():
        return "Pinned source text unavailable."
    text = text_path.read_text(encoding="utf-8", errors="replace")
    if source_id == "SRC-0004":
        start_marker = "For i = 1, 2, set Wfi"
        end_marker = "equivalently if, n ≤"
        start = text.find(start_marker)
        end = text.find(end_marker, start)
        if start >= 0 and end > start:
            excerpt = " ".join(text[start : end + len(end_marker)].split())
            return (
                "Lemma 10.6 (degree/Serre-duality calculation): "
                + excerpt
            )
        needles = ["Lemma 10.6. Let E"]
    else:
        needles = ["Equation (6.1)", "Table 1", "Proposition 4.5"]
    positions = [text.find(needle) for needle in needles if text.find(needle) >= 0]
    if not positions:
        return "See the pinned primary-source locators in the claim database."
    start = max(0, max(positions) - 120)
    # Locator snippets are deliberately short; the packet points agents to the
    # pinned source text for surrounding context.
    return " ".join(text[start : start + 500].split()[:24])


def _failed_attempt_ledger(campaign: Dict[str, Any]) -> List[str]:
    case = campaign["case"]
    rows = []
    for attempt in load_artifacts("attempts"):
        if attempt.get("campaign_id"):
            if (
                attempt.get("campaign_id") != campaign["id"]
                or attempt.get("campaign_revision")
                == campaign["campaign_revision"]
            ):
                continue
            summary = str(attempt.get("summary", "")).strip().replace(
                "\n", " "
            )
            rows.append(
                "%s [stale_campaign_context/%s]: %s"
                % (
                    attempt.get("id"),
                    attempt.get("subproblem_id", "unknown"),
                    summary[:320],
                )
            )
            continue
        target = attempt.get("target", {})
        if target.get("g") != case["g"] or target.get("n") != case["n"]:
            continue
        summary = str(attempt.get("summary", "")).strip().replace("\n", " ")
        rows.append(
            "%s [%s/%s]: %s"
            % (
                attempt.get("id"),
                attempt.get("approach_id", "unknown"),
                attempt.get("status", "unknown"),
                summary[:320],
            )
        )
    return rows


def render_campaign_packet(campaign_id: str = DEFAULT_CAMPAIGN) -> str:
    campaign = load_campaign(campaign_id)
    case = campaign["case"]
    target = open_input_target(case["g"], case["n"])
    visible = findings_for_case(
        case["g"], case["n"], visible_only=True, campaign_id=campaign_id
    )
    quarantined = [
        item
        for item in load_findings()
        if item.get("case") in ("all", case)
        and item.get("status") == "candidate"
    ]
    lines = [
        "# Focused campaign packet: %s" % campaign_id,
        "",
        "- Campaign revision: `%d`" % campaign["campaign_revision"],
        "- Target context revision: `%d`" % campaign["context_revision"],
        "- Exact target: `%s`" % target_formula(target),
        "- Exact theorem: `%s`"
        % campaign["paired_attempt_policy"]["exact_theorem"],
        "",
        "## Canonical geometric bottleneck",
        "",
        "- Balanced tetragonal splitting: `%s`." % campaign["bottleneck"]["splitting"],
        "- CE line-bundle convention: `%s`."
        % campaign["bottleneck"]["ce_line_bundle"],
        "- Degree calculation: `%s`."
        % campaign["bottleneck"]["degree_formula"],
        "- Six-point failure locus: `%s`." % campaign["bottleneck"]["failure_locus"],
    ]
    lines.extend("- " + item for item in campaign["bottleneck"]["program"])
    lines.extend(["", "## Subproblem graph", ""])
    for item in campaign["subproblems"]:
        dependencies = ", ".join(item.get("dependencies", [])) or "none"
        lines.append(
            "- `%s` (%s): %s. Dependencies: %s."
            % (item["id"], item["lane"], item["title"], dependencies)
        )
    lines.extend(["", "## Adjudicated findings", ""])
    if visible:
        for finding in visible:
            lines.append(
                "- `%s` [%s; %s]: %s"
                % (
                    finding["id"],
                    finding["status"],
                    finding.get("scope", "legacy scope"),
                    finding["statement"],
                )
            )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Unadjudicated candidate findings are quarantined and excluded from this packet.",
            "",
            "## Primary locator excerpts",
            "",
        ]
    )
    for source_id in campaign["primary_source_ids"]:
        lines.extend(
            [
                "### %s" % source_id,
                "",
                _primary_locator_excerpt(source_id),
                "",
            ]
        )
    lines.extend(["## Blocked routes", ""])
    for route in campaign["blocked_routes"]:
        lines.append(
            "- `%s` may be used only when the task declares genuinely new input."
            % route
        )
    lines.extend(
        [
            "",
            "## Execution boundary",
            "",
            "Finite computation may generate a hypothesis but cannot prove a universal claim. "
            "A complete result must identify every proof dependency and every experiment. "
            "No raw review or candidate finding is evidence in this packet.",
            "",
        ]
    )
    return "\n".join(lines)


def campaign_packet_record(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    text = render_campaign_packet(campaign_id)
    campaign = load_campaign(campaign_id)
    path = campaign_packet_path(campaign_id)
    return {
        "campaign_id": campaign_id,
        "campaign_revision": campaign["campaign_revision"],
        "context_revision": campaign["context_revision"],
        "packet_id": "%s-v%d" % (campaign_id, campaign["campaign_revision"]),
        "packet_path": str(path.relative_to(ROOT)),
        "packet_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "target": open_input_target(
            campaign["case"]["g"], campaign["case"]["n"]
        ).as_dict(),
        "_text": text,
    }


def write_campaign_packet(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    record = campaign_packet_record(campaign_id)
    atomic_write_text(campaign_packet_path(campaign_id), record["_text"])
    return {key: value for key, value in record.items() if key != "_text"}


def load_campaign_attempts(
    campaign_id: str, current_only: bool = True
) -> List[Dict[str, Any]]:
    current_revision = (
        load_campaign(campaign_id)["campaign_revision"]
        if current_only
        else None
    )
    rows = []
    for path in sorted((ROOT / "proof" / "attempts").glob("ATT-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            value.get("campaign_id") == campaign_id
            and (
                current_revision is None
                or value.get("campaign_revision") == current_revision
            )
        ):
            value["_path"] = str(path)
            rows.append(value)
    return rows


def load_novelty_audits(campaign_id: str) -> List[Dict[str, Any]]:
    rows = []
    for path in sorted(NOVELTY_DIR.glob("NOV-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("campaign_id") == campaign_id:
            value["_path"] = str(path)
            rows.append(value)
    return rows


def case_verified(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    reviews = load_artifacts("reviews")
    campaign = load_campaign(campaign_id)
    packet = campaign_packet_record(campaign_id)
    from .paired import problem_key

    for attempt in reversed(load_campaign_attempts(campaign_id)):
        if attempt.get("status") not in {"claimed_complete", "verified"}:
            continue
        if attempt.get("gap_markers"):
            continue
        if attempt.get("packet_sha256") != packet["packet_sha256"]:
            continue
        if (
            attempt.get("paired_turn_kind")
            and attempt.get("paired_problem_key") != problem_key(campaign)
        ):
            continue
        attached = [
            item
            for item in reviews
            if item.get("attempt_id") == attempt.get("id")
            and item.get("verdict") == "confirmed"
            and item.get("packet_sha256") == attempt.get("packet_sha256")
            and item.get("independent") is True
            and item.get("reviewer_engine") != attempt.get("engine")
        ]
        engines = {item.get("reviewer_engine") for item in attached}
        passes = {item.get("review_pass") for item in attached}
        dependencies = {
            (
                item.get("id")
                if isinstance(item, dict)
                else str(item)
            )
            for item in attempt.get("proof_dependencies", [])
        }
        dependency_checks_ok = all(
            dependencies.issubset(
                {
                    str(check.get("dependency_id"))
                    for check in review.get("proof_dependency_checks", [])
                    if isinstance(check, dict)
                    and check.get("verdict") == "confirmed"
                }
            )
            for review in attached
        )
        if (
            len(attached) >= 2
            and len(engines) >= 2
            and {1, 2}.issubset(passes)
            and dependency_checks_ok
        ):
            return {"verified": True, "attempt": attempt, "reviews": attached}
    return {"verified": False, "attempt": None, "reviews": []}


def proof_hash(attempt: Dict[str, Any]) -> str:
    payload = {
        "theorem_statement": attempt.get("theorem_statement"),
        "theorem_scope": attempt.get("theorem_scope"),
        "target": attempt.get("target"),
        "result_type": attempt.get("result_type"),
        "argument_markdown": attempt.get("argument_markdown"),
        "proof_dependencies": attempt.get("proof_dependencies", []),
        "experiment_ids": attempt.get("experiment_ids", []),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def novelty_status(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    from .capabilities import attestation_receipt_valid

    verified = case_verified(campaign_id)
    if not verified["verified"]:
        return {"certified": False, "reason": "case_not_verified", "audits": []}
    attempt = verified["attempt"]
    expected_hash = proof_hash(attempt)
    audits = [
        audit
        for audit in load_novelty_audits(campaign_id)
        if audit.get("attempt_id") == attempt.get("id")
        and audit.get("proof_sha256") == expected_hash
        and audit.get("theorem_statement") == attempt.get("theorem_statement")
        and audit.get("sources_verified") is True
        and audit.get("live_web") is True
        and isinstance(audit.get("capability_attestation_sha256"), str)
        and attestation_receipt_valid(
            audit.get("capability_attestation_sha256", "")
        )
    ]
    conflicts = [item for item in audits if item.get("verdict") == "prior_result_found"]
    if conflicts:
        return {"certified": False, "reason": "conflicting_prior_art", "audits": audits}
    clean = [item for item in audits if item.get("verdict") == "no_prior_result"]
    engines = {item.get("engine") for item in clean}
    scopes = {
        json.dumps(item.get("theorem_scope"), sort_keys=True)
        for item in clean
    }
    certified = len(clean) >= 2 and len(engines) >= 2 and len(scopes) == 1
    return {
        "certified": certified,
        "reason": "certified" if certified else "insufficient_independent_audits",
        "audits": audits,
    }


def campaign_status(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    campaign = load_campaign(campaign_id)
    from .proofs import audit_proofs
    from .health import engine_health_state
    from .store import load_repository
    from .tasking import campaign_mathematics_tasks

    _config, _target, _sources, claims, _edges = load_repository()
    integrity = audit_proofs(claims)
    packet = campaign_packet_record(campaign_id)
    packet_path = ROOT / packet["packet_path"]
    packet_ok = (
        packet_path.is_file()
        and sha256_file(packet_path) == packet["packet_sha256"]
    )
    attempts = load_campaign_attempts(campaign_id)
    historical_attempts = load_campaign_attempts(
        campaign_id, current_only=False
    )
    routing = load_routing_config()
    from .paired import (
        POLICY_REVISION,
        pair_statuses,
        problem_key,
        theorem_sha256,
    )

    paired_engines = campaign["paired_attempt_policy"]["engine_order"]
    paired_states = pair_statuses(campaign, paired_engines)
    by_subproblem = Counter(
        item.get("subproblem_id") for item in attempts if item.get("subproblem_id")
    )
    engines_by_subproblem: Dict[str, List[str]] = {}
    for attempt in attempts:
        subproblem_id = attempt.get("subproblem_id")
        engine = attempt.get("engine")
        if not isinstance(subproblem_id, str) or not isinstance(engine, str):
            continue
        engines = engines_by_subproblem.setdefault(subproblem_id, [])
        if engine not in engines:
            engines.append(engine)
    engine_coverage = {}
    for subproblem in campaign["subproblems"]:
        subproblem_id = subproblem["id"]
        used = engines_by_subproblem.get(subproblem_id, [])
        engine_coverage[subproblem_id] = {
            "lane": subproblem["lane"],
            "attempted_engines": used,
            "next_retry_engine": (
                next_escalation_engine(used, routing["escalation_order"])
                if used
                else None
            ),
            "remaining_retry_engines": [
                engine
                for engine in routing["escalation_order"]
                if engine not in set(used)
            ],
        }
    verification = case_verified(campaign_id)
    novelty = novelty_status(campaign_id)
    findings = findings_for_case(
        campaign["case"]["g"],
        campaign["case"]["n"],
        visible_only=False,
        campaign_id=campaign_id,
    )
    math_tasks = campaign_mathematics_tasks(campaign_id)
    gap_dependencies = {
        gap
        for item in attempts
        for gap in item.get("gap_markers", [])
        if isinstance(gap, str) and gap
    }
    dag_dependencies = {
        "%s requires %s" % (task["subproblem_id"], dependency)
        for task in math_tasks
        for dependency in task.get("blocked_dependencies", [])
    }
    unresolved_dependencies = sorted(
        gap_dependencies | dag_dependencies
    )
    subproblem_statuses = {
        task["subproblem_id"]: task["status"] for task in math_tasks
    }
    engine_health = {
        phase: {
            engine: engine_health_state(engine, phase)
            for engine in routing["engines"]
        }
        for phase in ("mathematics", "review")
    }
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "campaign_revision": campaign["campaign_revision"],
        "context_revision": campaign["context_revision"],
        "generated_on": datetime.date.today().isoformat(),
        "structural_integrity": (
            "ready" if integrity.ok and packet_ok else "blocked"
        ),
        "integrity_errors": integrity.errors
        + ([] if packet_ok else ["campaign packet missing or stale"]),
        "campaign_progress": {
            "attempts": len(attempts),
            "stale_campaign_attempts": len(historical_attempts) - len(attempts),
            "subproblems_tried": len(by_subproblem),
            "subproblem_attempt_counts": dict(sorted(by_subproblem.items())),
            "subproblem_engine_coverage": engine_coverage,
            "subproblem_statuses": subproblem_statuses,
            "lane_count": len({item["lane"] for item in campaign["subproblems"]}),
        },
        "routing_policy": {
            "fresh_rotation": routing["prover_rotation"],
            "retry_escalation": routing["escalation_order"],
            "review_escalation": routing["escalation_order"],
        },
        "paired_attempt_policy": {
            "revision": POLICY_REVISION,
            "theorem_sha256": theorem_sha256(campaign),
            "engine_order": paired_engines,
            "engine_states": paired_states,
            "exhausted_pairs": sum(
                state["state"] == "pair_exhausted"
                for state in paired_states.values()
            ),
            "complete_candidates": sum(
                attempt.get("paired_problem_key") == problem_key(campaign)
                and attempt.get("status")
                in {"claimed_complete", "verified"}
                for attempt in attempts
            ),
        },
        "engine_health": engine_health,
        "case_verification": {
            "case_verified": verification["verified"],
            "attempt_id": (
                verification["attempt"].get("id")
                if verification["attempt"]
                else None
            ),
        },
        "novelty_certification": {
            "novelty_certified": novelty["certified"],
            "reason": novelty["reason"],
        },
        "unresolved_proof_dependencies": unresolved_dependencies,
        "candidate_finding_backlog": sum(
            item.get("status") == "candidate" for item in findings
        ),
    }


def campaign_status_markdown(status: Dict[str, Any]) -> str:
    progress = status["campaign_progress"]
    verification = status["case_verification"]
    novelty = status["novelty_certification"]
    paired = status["paired_attempt_policy"]
    lines = [
        "# Campaign status: %s" % status["campaign_id"],
        "",
        "## Structural integrity",
        "",
        "- Status: **%s**" % status["structural_integrity"].upper(),
        "- Context revision: `%d`; campaign revision: `%d`."
        % (status["context_revision"], status["campaign_revision"]),
        "",
        "## Campaign progress",
        "",
        "- Attempts: %d" % progress["attempts"],
        "- Stale campaign attempts retained: %d"
        % progress.get("stale_campaign_attempts", 0),
        "- Subproblems tried: %d" % progress["subproblems_tried"],
        "- Four-lane program present: %s" % ("yes" if progress["lane_count"] == 4 else "no"),
        "",
        "## Paired full-proof policy",
        "",
        "- Policy revision: `%d`" % paired["revision"],
        "- Exhausted engine/problem pairs: `%d`" % paired["exhausted_pairs"],
        "- Complete candidates under review or verified: `%d`"
        % paired["complete_candidates"],
        "",
        "| Engine | Pair state |",
        "|---|---|",
    ]
    lines.extend(
        "| `%s` | `%s` |" % (engine, row["state"])
        for engine, row in paired["engine_states"].items()
    )
    lines.extend(
        [
        "",
        "### Per-cell engine coverage",
        "",
        "| Subproblem | Lane | Attempted engines | Next retry |",
        "|---|---|---|---|",
        ]
    )
    lines.extend(
        "| `%s` | %s | %s | %s |"
        % (
            subproblem_id,
            coverage["lane"],
            ", ".join(coverage["attempted_engines"]) or "none",
            coverage["next_retry_engine"] or "fresh rotation",
        )
        for subproblem_id, coverage in progress[
            "subproblem_engine_coverage"
        ].items()
    )
    lines.extend(
        [
        "",
        "## Case verification",
        "",
        "- `case_verified`: **%s**" % str(verification["case_verified"]).lower(),
        "- Verified attempt: `%s`" % (verification["attempt_id"] or "none"),
        "",
        "## Novelty certification",
        "",
        "- `novelty_certified`: **%s**" % str(novelty["novelty_certified"]).lower(),
        "- Gate state: `%s`" % novelty["reason"],
        "",
        "The label **novel** is unavailable unless both gates above are true.",
        "",
        "## Unresolved proof dependencies",
        "",
        ]
    )
    if status.get("integrity_errors"):
        lines[6:6] = [
            "- Integrity error: %s" % item
            for item in status["integrity_errors"]
        ]
    lines.extend(
        "- " + item
        for item in status["unresolved_proof_dependencies"] or ["None recorded."]
    )
    lines.extend(
        [
            "",
            "## Candidate-finding backlog",
            "",
            "- Quarantined candidates: %d" % status["candidate_finding_backlog"],
            "",
        ]
    )
    return "\n".join(lines)


def write_campaign_status(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    write_campaign_packet(campaign_id)
    status = campaign_status(campaign_id)
    atomic_write_json(
        REPORTS_GENERATED / ("%s-STATUS.json" % campaign_id), status
    )
    atomic_write_text(
        REPORTS_GENERATED / ("%s-STATUS.md" % campaign_id),
        campaign_status_markdown(status),
    )
    return status
