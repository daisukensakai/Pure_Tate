import re
from typing import Dict, Iterable, List, Sequence, Set

from .graph import ClaimGraph
from .models import Claim, Source


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> Set[str]:
    return {match.group(0).lower() for match in TOKEN_RE.finditer(text)}


def search_claims(
    query: str, claims: Dict[str, Claim], limit: int = 10
) -> List[Claim]:
    query_tokens = _tokens(query)
    scored = []
    for claim in claims.values():
        title_tokens = _tokens(claim.title)
        statement_tokens = _tokens(claim.statement)
        score = 3 * len(query_tokens & title_tokens) + len(
            query_tokens & statement_tokens
        )
        if score:
            scored.append((score, claim.id, claim))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def compile_packet(
    claim_id: str,
    claims: Dict[str, Claim],
    sources: Dict[str, Source],
    graph: ClaimGraph,
    claim_limit: int,
    source_limit: int,
) -> str:
    closure_ids = graph.dependency_closure(claim_id)
    if len(closure_ids) > claim_limit:
        raise ValueError(
            "dependency closure has %d claims; packet limit is %d"
            % (len(closure_ids), claim_limit)
        )
    selected = [claims[item] for item in closure_ids]
    source_ids: List[str] = []
    seen_sources: Set[str] = set()
    for claim in selected:
        for source_id in claim.source_ids:
            if source_id not in seen_sources:
                source_ids.append(source_id)
                seen_sources.add(source_id)
    if len(source_ids) > source_limit:
        raise ValueError(
            "dependency closure has %d sources; packet limit is %d"
            % (len(source_ids), source_limit)
        )

    target = claims[claim_id]
    ready = target.verification_status == "cross_checked"
    lines = [
        "# Research packet — %s" % claim_id,
        "",
        "> Stage-2 readiness: **%s**. Target verification status: `%s`."
        % ("READY" if ready else "BLOCKED", target.verification_status),
        "",
        "## Task",
        "",
        target.statement,
        "",
        "## Scope",
        "",
        "```json",
    ]
    import json

    lines.extend(json.dumps(target.scope, indent=2, sort_keys=True).splitlines())
    lines.extend(["```", "", "## Dependency-closed claims", ""])
    for claim in selected:
        lines.extend(
            [
                "### %s — %s" % (claim.id, claim.title),
                "",
                "- Kind: `%s`" % claim.kind,
                "- Truth: `%s`; research verification: `%s`"
                % (claim.truth_status, claim.verification_status),
                "- Statement: %s" % claim.statement,
                "- Dependencies: %s"
                % (", ".join(claim.depends_on) if claim.depends_on else "none"),
                "- Scope: `%s`" % json.dumps(claim.scope, sort_keys=True),
                "",
            ]
        )
        if claim.locators:
            lines.append("Evidence locators:")
            lines.append("")
            for locator in claim.locators:
                lines.append(
                    "- %s — %s — %s"
                    % (
                        locator.source_id,
                        locator.locator,
                        locator.evidence_note,
                    )
                )
            lines.append("")

    lines.extend(["## Sources", ""])
    for source_id in source_ids:
        source = sources[source_id]
        lines.extend(
            [
                "### %s — %s" % (source.id, source.title),
                "",
                "- Authors: %s" % ", ".join(source.authors),
                "- Status: %s; checked %s"
                % (source.publication_status, source.checked_on),
                "- arXiv: %s%s"
                % (source.arxiv_id, source.arxiv_version)
                if source.arxiv_id
                else "- arXiv: none",
                "- DOI: %s" % (source.doi or "none"),
                "- URL: %s" % source.url,
                "",
            ]
        )

    lines.extend(
        [
            "## Mandatory scope traps",
            "",
            "- Do not replace the stack by its coarse moduli space.",
            "- Do not replace rational Hodge structures by a semisimplified l-adic prediction.",
            "- Track Poincare duality, Gysin shifts, weights, and Tate twists explicitly.",
            "- Pure Tate is weaker than algebraic generation and tautological generation.",
            "- A claim below `source_verified` may orient research but may not support a proof.",
            "",
        ]
    )
    return "\n".join(lines)

