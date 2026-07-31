import re
from typing import Any, Dict, List

from .graph import ClaimGraph
from .models import (
    CLAIM_KINDS,
    EDGE_TYPES,
    RESEARCH_STATUSES,
    TRUTH_STATUSES,
    CheckResult,
    Claim,
    Edge,
    Source,
)


CLAIM_ID_RE = re.compile(r"^[A-Z]{2,6}-\d{4}$")
SOURCE_ID_RE = re.compile(r"^SRC-\d{4}$")


def validate_repository(
    config: Dict[str, Any],
    target: Dict[str, Any],
    sources: Dict[str, Source],
    claims: Dict[str, Claim],
    edges: List[Edge],
) -> CheckResult:
    result = CheckResult()
    if int(config.get("schema_version", 0)) != 1:
        result.errors.append("unsupported or missing schema_version")
    required_target = {
        "id",
        "statement",
        "degree",
        "coefficients",
        "realization",
        "object",
        "quantifier",
    }
    missing_target = sorted(required_target - set(target))
    if missing_target:
        result.errors.append(
            "target contract missing fields: %s" % ", ".join(missing_target)
        )
    if target.get("degree") != 16:
        result.warnings.append("target degree is not 16")

    for source in sources.values():
        if not SOURCE_ID_RE.match(source.id):
            result.errors.append("malformed source id %s" % source.id)
        if not source.title.strip() or not source.authors:
            result.errors.append("%s lacks title/authors" % source.id)

    graph = ClaimGraph(claims, edges)
    edge_pairs = graph.edge_pairs()
    for claim in claims.values():
        if not CLAIM_ID_RE.match(claim.id):
            result.errors.append("malformed claim id %s" % claim.id)
        if claim.kind not in CLAIM_KINDS:
            result.errors.append("%s has invalid kind %r" % (claim.id, claim.kind))
        if claim.verification_status not in RESEARCH_STATUSES:
            result.errors.append(
                "%s has invalid verification_status %r"
                % (claim.id, claim.verification_status)
            )
        if claim.truth_status not in TRUTH_STATUSES:
            result.errors.append(
                "%s has invalid truth_status %r" % (claim.id, claim.truth_status)
            )
        if not claim.statement.strip():
            result.errors.append("%s has empty statement" % claim.id)
        for dependency in claim.depends_on:
            if dependency not in claims:
                result.errors.append(
                    "%s depends on unknown claim %s" % (claim.id, dependency)
                )
            if (claim.id, dependency) not in edge_pairs:
                result.errors.append(
                    "%s dependency %s lacks a typed edge" % (claim.id, dependency)
                )

    seen_edges = set()
    for edge in edges:
        key = (edge.source, edge.target, edge.type)
        if key in seen_edges:
            result.errors.append("duplicate edge %s" % (key,))
        seen_edges.add(key)
        if edge.source not in claims or edge.target not in claims:
            result.errors.append(
                "edge %s -> %s references unknown claim"
                % (edge.source, edge.target)
            )
        if edge.type not in EDGE_TYPES:
            result.errors.append(
                "edge %s -> %s has invalid type %r"
                % (edge.source, edge.target, edge.type)
            )
        if not edge.note.strip():
            result.warnings.append(
                "edge %s -> %s has no explanatory note"
                % (edge.source, edge.target)
            )

    for cycle in graph.cycles():
        result.errors.append("dependency cycle: %s" % " -> ".join(cycle))

    if "CONJ-0001" not in claims:
        result.errors.append("canonical target claim CONJ-0001 is missing")
    if "RED-0001" not in claims:
        result.errors.append("degree-16 reduction claim RED-0001 is missing")
    return result

