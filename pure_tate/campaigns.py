import datetime
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .artifacts import load_artifacts, sha256_file
from .findings import findings_for_case, load_findings
from .routing import (
    load_high_tier_ledger,
    load_routing_config,
    next_escalation_engine,
)
from .store import DATA, PACKETS_GENERATED, REPORTS_GENERATED, ROOT, atomic_write_json, atomic_write_text, load_json
from .targets import CONTEXT_REVISION, open_input_target, target_formula


DEFAULT_CAMPAIGN = "C66-001"
CAMPAIGN_REVISION = 6
CAMPAIGN_DIR = DATA / "campaigns"
CAMPAIGN_ARTIFACT_DIR = ROOT / "proof" / "campaign-attempts"
NOVELTY_DIR = ROOT / "research" / "novelty-audits"
EXPERIMENT_RESULT_DIR = ROOT / "experiments" / "results"


BLOCKED_ROUTE_METHOD_ALIASES = {
    "vcd-only-vanishing": {
        "vcd-only-vanishing",
        "top-vcd-vanishing",
        "vanishing-at-vcd",
        "top-degree-rational-vanishing-for-mapping-class-groups",
    },
    "undecorated-cgp-top-weight-graph-complex": {
        "undecorated-cgp-top-weight-graph-complex",
        "undecorated-top-weight-graph-complex",
    },
    "point-count-without-degree-parity-separation": {
        "point-count-without-degree-parity-separation",
        "point-count-only",
    },
    "forgetful-map-renaming-local-system-unknown": {
        "forgetful-map-renaming-local-system-unknown",
        "forgetful-map-only-reduction",
    },
}


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
        or policy.get("revision") != 2
        or policy.get("engine_order")
        != ["claude", "codex"]
        or not str(policy.get("exact_theorem", "")).strip()
    ):
        raise ValueError("campaign has an invalid paired-attempt policy")
    return campaign


def used_blocked_routes(
    campaign: Dict[str, Any], methods: Any
) -> Set[str]:
    """Map model-supplied method labels onto canonical blocked routes.

    Method labels remain extensible, so exact string comparison is too weak:
    an engine can otherwise rename ``vcd-only-vanishing`` and bypass the gate.
    The conservative semantic checks below cover the known route families while
    leaving unrelated methods alone.
    """
    labels = {
        item.strip().lower().replace("_", "-").replace(" ", "-")
        for item in (methods if isinstance(methods, list) else [])
        if isinstance(item, str) and item.strip()
    }
    used: Set[str] = set()
    blocked = set(campaign.get("blocked_routes", []))
    for route in blocked:
        aliases = BLOCKED_ROUTE_METHOD_ALIASES.get(route, {route})
        if labels & aliases:
            used.add(route)
    for label in labels:
        if (
            "vcd-only-vanishing" in blocked
            and "vanish" in label
            and (
                "vcd" in label
                or "virtual-cohomological-dimension" in label
                or "top-degree-rational" in label
            )
        ):
            used.add("vcd-only-vanishing")
        if (
            "undecorated-cgp-top-weight-graph-complex" in blocked
            and "graph-complex" in label
            and "undecorated" in label
        ):
            used.add("undecorated-cgp-top-weight-graph-complex")
        if (
            "point-count-without-degree-parity-separation" in blocked
            and "point-count" in label
            and "degree-separation" not in label
            and "parity-separation" not in label
        ):
            used.add("point-count-without-degree-parity-separation")
        if (
            "forgetful-map-renaming-local-system-unknown" in blocked
            and "forgetful" in label
            and "local-system" in label
        ):
            used.add("forgetful-map-renaming-local-system-unknown")
    return used


def verified_new_input_routes(artifact: Dict[str, Any]) -> Set[str]:
    """Return blocked routes reopened by evidence admitted through Stage 1.

    Free-form citations are not enough to overturn an adjudicated route block.
    A new input must name the canonical route, explain the evidence, and point
    to at least one source-verified or cross-checked claim in the repository.
    """
    from .store import load_repository

    _config, _target, _sources, claims, _edges = load_repository()
    verified_claims = {
        claim_id
        for claim_id, claim in claims.items()
        if claim.verification_status in {"source_verified", "cross_checked"}
    }
    reopened: Set[str] = set()
    for item in artifact.get("new_inputs", []):
        if not isinstance(item, dict):
            continue
        route = item.get("route")
        evidence = item.get("evidence")
        evidence_claim_ids = item.get("evidence_claim_ids")
        if (
            isinstance(route, str)
            and route.strip()
            and isinstance(evidence, str)
            and evidence.strip()
            and isinstance(evidence_claim_ids, list)
            and any(
                isinstance(claim_id, str) and claim_id in verified_claims
                for claim_id in evidence_claim_ids
            )
        ):
            reopened.add(route)
    return reopened


def campaign_route_policy_errors(
    campaign: Dict[str, Any], artifact: Dict[str, Any]
) -> List[str]:
    used = used_blocked_routes(campaign, artifact.get("methods_used"))
    reopened = verified_new_input_routes(artifact)
    unsupported = sorted(used - reopened)
    if not unsupported:
        return []
    return [
        "blocked campaign route used without source-verified new evidence: %s"
        % ", ".join(unsupported)
    ]


def campaign_packet_path(campaign_id: str = DEFAULT_CAMPAIGN) -> Path:
    campaign = load_campaign(campaign_id)
    return PACKETS_GENERATED / (
        "%s-v%d.md" % (campaign_id, campaign["campaign_revision"])
    )


def campaign_packet_snapshot_path(working_path: Path, packet_sha256: str) -> Path:
    """Content-addressed snapshot path for a packet with ``packet_sha256``.

    The working path is rewritten on every finding adjudication, so the snapshot
    is the only stable copy of the text an artifact was actually produced
    against. Both the writer and the task-packet validator derive the name here
    so the convention cannot drift between them.
    """
    stem = working_path.stem
    marker = "-%s" % packet_sha256[:16]
    if stem.endswith(marker):
        # Already a snapshot path; do not nest a second digest.
        return working_path
    return working_path.with_name("%s%s%s" % (stem, marker, working_path.suffix))


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


def campaign_packet_binding(
    campaign_id: str = DEFAULT_CAMPAIGN,
) -> Dict[str, Any]:
    """Return the identity-bearing packet inputs, excluding adjudicated findings.

    An attempt's validity depends on the target, the exact theorem, the
    bottleneck conventions, the subproblem graph, the blocked routes, and the
    pinned primary-source excerpts. It does not depend on the packet's running
    list of adjudicated findings: that section grows every time a finding audit
    lands, and hashing it into artifact identity invalidates in-flight work
    faster than it can earn two review passes. Finding dependence is enforced
    per citation instead -- an attempt citing a finding below ``corroborated``
    is rejected by ``audit_proofs`` -- so it does not belong in this hash.
    """
    campaign = load_campaign(campaign_id)
    case = campaign["case"]
    target = open_input_target(case["g"], case["n"])
    return {
        "campaign_id": campaign_id,
        "campaign_revision": campaign["campaign_revision"],
        "context_revision": campaign["context_revision"],
        "target": target.as_dict(),
        "exact_theorem": campaign["paired_attempt_policy"]["exact_theorem"],
        "bottleneck": campaign["bottleneck"],
        "subproblems": [
            {
                "id": item["id"],
                "lane": item["lane"],
                "title": item["title"],
                "dependencies": list(item.get("dependencies", [])),
                "exact_theorem": item.get("exact_theorem", ""),
                "artifact_contract": item.get("artifact_contract", {}),
            }
            for item in campaign["subproblems"]
        ],
        "blocked_routes": list(campaign["blocked_routes"]),
        "primary_sources": {
            source_id: hashlib.sha256(
                _primary_locator_excerpt(source_id).encode("utf-8")
            ).hexdigest()
            for source_id in campaign["primary_source_ids"]
        },
    }


def campaign_packet_binding_sha256(
    campaign_id: str = DEFAULT_CAMPAIGN,
) -> str:
    return hashlib.sha256(
        json.dumps(
            campaign_packet_binding(campaign_id), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def _binding_migration(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    path = (
        ROOT
        / "proof"
        / "migrations"
        / ("campaign-%s-binding.json" % campaign_id)
    )
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def campaign_revision_migration(
    campaign_id: str = DEFAULT_CAMPAIGN,
) -> Dict[str, Any]:
    """Load the migration ledger governing the campaign's current revision."""
    campaign = load_campaign(campaign_id)
    path = (
        ROOT
        / "proof"
        / "migrations"
        / (
            "campaign-%s-v%s.json"
            % (campaign_id, campaign["campaign_revision"])
        )
    )
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def campaign_carried_forward_verifications(
    campaign_id: str = DEFAULT_CAMPAIGN,
) -> Dict[str, Dict[str, Any]]:
    """Return hash-pinned prior-revision verifications explicitly retained.

    A campaign revision normally makes all prior attempts stale.  A narrow
    migration exception is allowed only for subproblems whose theorem and
    dependencies are unchanged; task construction verifies every listed file
    hash before treating such a record as current context.
    """
    migration = campaign_revision_migration(campaign_id)
    values = migration.get("carry_forward_verifications", {})
    if not isinstance(values, dict):
        return {}
    return {
        str(subproblem_id): record
        for subproblem_id, record in values.items()
        if isinstance(subproblem_id, str) and isinstance(record, dict)
    }


def artifact_contract_errors(
    contract: Any, artifact: Dict[str, Any]
) -> List[str]:
    """Validate a declarative campaign artifact contract.

    Contracts deliberately check only the required interface metadata.  The
    mathematical truth of those fields remains the subject of independent
    review, but a worker cannot omit the target-facing data altogether.
    """
    if not isinstance(contract, dict):
        return []
    object_field = contract.get("object_field")
    if not isinstance(object_field, str) or not object_field:
        return ["artifact contract lacks object_field"]
    value = artifact.get(object_field)
    if not isinstance(value, dict):
        return ["artifact lacks object %s" % object_field]
    errors: List[str] = []
    for field in contract.get("required_nonempty_strings", []):
        if not isinstance(value.get(field), str) or not value[field].strip():
            errors.append("%s.%s must be a nonempty string" % (object_field, field))
    for field in contract.get("required_nonempty_lists", []):
        entries = value.get(field)
        if not isinstance(entries, list) or not entries:
            errors.append("%s.%s must be a nonempty list" % (object_field, field))
    return errors


def campaign_quarantined_attempt_ids(
    campaign_id: str = DEFAULT_CAMPAIGN,
) -> Set[str]:
    migration = campaign_revision_migration(campaign_id)
    attempts = migration.get("attempts", {})
    if not isinstance(attempts, dict):
        return set()
    return {str(attempt_id) for attempt_id in attempts}


def packet_binding_matches(
    artifact: Dict[str, Any], campaign_id: str = DEFAULT_CAMPAIGN
) -> bool:
    """Report whether an artifact was produced against the current packet identity.

    Acceptance paths (first match wins):

    1. Explicit ``packet_binding_sha256`` equals the live campaign binding hash.
    2. Missing binding, but ``packet_sha256`` equals the **current** full-content
       packet hash (artifact was issued against the exact live packet bytes).
    3. Missing binding, live migration binding still current, and content hash is
       listed in ``equivalent_packet_sha256`` — for pre-binding artifacts whose
       packet texts were overwritten in place and are not recoverable
       (``proof/migrations/campaign-*-binding.json``).
    """
    current_binding = campaign_packet_binding_sha256(campaign_id)
    binding = artifact.get("packet_binding_sha256")
    if isinstance(binding, str) and binding:
        return binding == current_binding
    content = artifact.get("packet_sha256")
    if isinstance(content, str) and content:
        try:
            live_content = campaign_packet_record(campaign_id).get("packet_sha256")
        except (OSError, ValueError, KeyError, TypeError):
            live_content = None
        if content == live_content:
            return True
    migration = _binding_migration(campaign_id)
    if migration.get("binding_sha256") != current_binding:
        return False
    equivalent = migration.get("equivalent_packet_sha256")
    if not isinstance(equivalent, dict):
        return False
    return content in equivalent


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
        context_dependencies = ", ".join(
            item.get("context_dependencies", [])
        )
        lines.append(
            "- `%s` (%s): %s. Dependencies: %s."
            % (item["id"], item["lane"], item["title"], dependencies)
        )
        if context_dependencies:
            lines.append(
                "  Verified supporting context (non-blocking): %s."
                % context_dependencies
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
        "packet_binding_sha256": campaign_packet_binding_sha256(campaign_id),
        "target": open_input_target(
            campaign["case"]["g"], campaign["case"]["n"]
        ).as_dict(),
        "_text": text,
    }


def write_campaign_packet(campaign_id: str = DEFAULT_CAMPAIGN) -> Dict[str, Any]:
    record = campaign_packet_record(campaign_id)
    path = campaign_packet_path(campaign_id)
    atomic_write_text(path, record["_text"])
    # The working path is overwritten on every finding adjudication. Keep an
    # immutable content-addressed copy so a superseded packet stays readable and
    # binding equivalence remains checkable after the fact.
    snapshot = campaign_packet_snapshot_path(path, record["packet_sha256"])
    if not snapshot.exists():
        atomic_write_text(snapshot, record["_text"])
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
    from .paired import problem_key_aliases

    from .proofs import attempt_is_complete

    for attempt in reversed(load_campaign_attempts(campaign_id)):
        if not attempt_is_complete(attempt):
            continue
        if not packet_binding_matches(attempt, campaign_id):
            continue
        # Subproblem lemmas may be double-confirmed for the DAG without
        # discharging the full RED-0001 case. Only proof/disproof attempts that
        # state the campaign's exact theorem count as case verification.
        if attempt.get("result_type") not in {"proof", "disproof"}:
            continue
        exact_theorem = (campaign.get("paired_attempt_policy") or {}).get(
            "exact_theorem"
        )
        if (
            isinstance(exact_theorem, str)
            and exact_theorem.strip()
            and attempt.get("theorem_statement") != exact_theorem
        ):
            continue
        if attempt.get("paired_turn_kind") and attempt.get(
            "paired_problem_key"
        ) not in problem_key_aliases(campaign):
            continue
        if campaign_route_policy_errors(campaign, attempt):
            continue
        attached = [
            item
            for item in reviews
            if item.get("attempt_id") == attempt.get("id")
            and item.get("verdict") == "confirmed"
            and packet_binding_matches(item, campaign_id)
            and item.get("independent") is True
            and item.get("reviewer_engine") != attempt.get("engine")
        ]
        engines = {item.get("reviewer_engine") for item in attached}
        passes = {item.get("review_pass") for item in attached}
        from .proofs import proof_dependency_ids

        dependencies = set(proof_dependency_ids(attempt.get("proof_dependencies")))
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
    high_tier_ledger = load_high_tier_ledger()
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
                for engine in (
                    routing["escalation_order"]
                    + routing["high_tier_chain_engines"]
                )
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
    from .paired import merge_working_context
    from .tasking import review_tasks

    # Counting attempts made looks like progress even when the subproblem graph
    # has not advanced a single node, which is how a frozen pipeline stayed
    # invisible. Report advancement and packet identity directly.
    verified_subproblems = sorted(
        task["subproblem_id"]
        for task in math_tasks
        if task.get("status") == "verified"
    )
    dag_progress = {
        "verified": len(verified_subproblems),
        "verified_subproblems": verified_subproblems,
        "executable": sum(
            1 for task in math_tasks if task["status"] == "ready"
        ),
        "blocked": sum(
            1 for task in math_tasks if task["status"] == "blocked"
        ),
        "blocked_by": {
            task["subproblem_id"]: task["blocked_dependencies"]
            for task in math_tasks
            if task.get("blocked_dependencies")
        },
        "queued_review_tasks": len(review_tasks()),
    }
    stale_by_identity = sum(
        1
        for attempt in attempts
        if not packet_binding_matches(attempt, campaign_id)
    )
    packet_identity = {
        "binding_sha256": packet["packet_binding_sha256"],
        "content_sha256": packet["packet_sha256"],
        "attempts_stale_by_identity": stale_by_identity,
        "attempts_stale_by_content": sum(
            1
            for attempt in attempts
            if attempt.get("packet_sha256") != packet["packet_sha256"]
        ),
    }
    working_context = merge_working_context(campaign)["stats"]
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
        "dag_progress": dag_progress,
        "packet_identity": packet_identity,
        "working_context_health": working_context,
        "routing_policy": {
            "fresh_rotation": routing["prover_rotation"],
            "retry_escalation": routing["escalation_order"],
            "review_escalation": routing["escalation_order"],
            "high_tier_chain_engines": routing["high_tier_chain_engines"],
            "last_high_tier_chain_order": high_tier_ledger[
                "last_chain_order"
            ],
            "pending_high_tier_chains": [
                {
                    "id": chain.get("id"),
                    "pending": chain.get("pending", []),
                }
                for chain in high_tier_ledger["chains"]
                if chain.get("pending")
            ],
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
    dag = status["dag_progress"]
    identity = status["packet_identity"]
    context = status["working_context_health"]
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
        "## Subproblem graph advancement",
        "",
        "- Verified subproblems: %d (%s)"
        % (
            dag["verified"],
            ", ".join(dag["verified_subproblems"]) or "none",
        ),
        "- Executable now: %d; blocked: %d" % (dag["executable"], dag["blocked"]),
        "- Queued review tasks: %d" % dag["queued_review_tasks"],
        "",
        "Attempts made are not advancement. A campaign with attempts, no",
        "verified subproblem and no queued review task is frozen.",
        "",
        "## Packet identity",
        "",
        "- Binding: `%s`" % identity["binding_sha256"][:16],
        "- Content: `%s`" % identity["content_sha256"][:16],
        "- Attempts stale by identity: %d (blocking); by content only: %d (benign)"
        % (
            identity["attempts_stale_by_identity"],
            identity["attempts_stale_by_content"],
        ),
        "",
        "## Working context",
        "",
        "- Rows: %d total; %d primary, %d extended, %d archived."
        % (
            context["rows_total"],
            context["rows_primary"],
            context["rows_extended"],
            context["rows_archived"],
        ),
        "- %d rows are current-packet; %d were demoted from a superseded packet."
        % (context["rows_fresh"], context["rows_demoted"]),
        "- Injected bytes: %d primary + %d extended."
        % (context["bytes_primary"], context["bytes_extended"]),
        "- Primary constraint share: %.0f%%; fresh share: %.0f%%; packet-redundant rows: %d."
        % (
            100.0 * float(context.get("primary_constraint_share") or 0.0),
            100.0 * float(context.get("primary_fresh_share") or 0.0),
            int(context.get("primary_redundant_rows") or 0),
        ),
        "- Primary by section: constraints %d, computations %d, established %d, candidates %d, frontier deps %d."
        % (
            (context.get("rows_primary_by_section") or {}).get("invalid", 0),
            (context.get("rows_primary_by_section") or {}).get("computation", 0),
            (context.get("rows_primary_by_section") or {}).get("established", 0),
            (context.get("rows_primary_by_section") or {}).get("candidate", 0),
            (context.get("rows_primary_by_section") or {}).get("dependency", 0),
        ),
        "- Constraints also in extended (overflow): %d."
        % int(context.get("constraints_in_extended") or 0),
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
