import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .artifacts import sha256_text
from .findings import findings_for_case
from .models import Claim
from .store import PACKETS_GENERATED, ROOT, atomic_write_text
from .targets import CONTEXT_REVISION, OpenInputTarget, open_input_target, target_formula


PACKET_CLAIM_IDS = [
    "CONJ-0001",
    "THM-0001",
    "THM-0002",
    "THM-0003",
    "THM-0004",
    "THM-0005",
    "THM-0006",
    "THM-0007",
    "OBS-0001",
    "RED-0001",
]


def case_packet_path(genus: int, markings: int) -> Path:
    return PACKETS_GENERATED / (
        "CASE-%d-%d-v%d.md" % (genus, markings, CONTEXT_REVISION)
    )


def _claim_record(claim: Claim) -> Dict[str, Any]:
    return {
        "id": claim.id,
        "title": claim.title,
        "statement": claim.statement,
        "verification_status": claim.verification_status,
        "truth_status": claim.truth_status,
        "source_ids": claim.source_ids,
        "locators": [
            {
                "source_id": locator.source_id,
                "locator": locator.locator,
                "evidence_note": locator.evidence_note,
            }
            for locator in claim.locators
        ],
    }


def relevant_claims(claims: Dict[str, Claim]) -> List[Dict[str, Any]]:
    return [_claim_record(claims[item]) for item in PACKET_CLAIM_IDS if item in claims]


def render_case_packet(
    genus: int,
    markings: int,
    claims: Dict[str, Claim],
) -> str:
    target = open_input_target(genus, markings)
    findings = findings_for_case(genus, markings, visible_only=True)
    claim_records = relevant_claims(claims)
    lines = [
        "# Revision-2 mathematics packet: M_%d,%d" % (genus, markings),
        "",
        "- Packet ID: `%s`" % target.packet_id,
        "- Context revision: `%d`" % CONTEXT_REVISION,
        "- Reduction: `RED-0001` (`cross_checked`)",
        "",
        "## Exact open-input target",
        "",
        "`%s`" % target_formula(target),
        "",
        "- Borel–Moore target: `W_%d H^BM_%d`, expected `%s`."
        % (target.open_bm_weight, target.open_bm_degree, target.open_bm_tate_type),
        "- Ordinary realization: `W_%d H^%d(%d)`, with untwisted Tate type `%s`."
        % (
            target.ordinary_weight,
            target.ordinary_cohomology_degree,
            target.poincare_twist,
            target.ordinary_tate_type,
        ),
        "- Chow codimension: `%d`." % target.chow_codimension,
        "",
        "```json",
        json.dumps(target.as_dict(), indent=2, sort_keys=True),
        "```",
        "",
        "## Verified context findings",
        "",
    ]
    if findings:
        for finding in findings:
            lines.append(
                "- `%s` [%s] — %s"
                % (finding["id"], finding["status"], finding["statement"])
            )
    else:
        lines.append("- No corroborated case-specific finding.")
    lines.extend(["", "## Dependency-closed claim records", ""])
    for claim in claim_records:
        lines.extend(
            [
                "### %s — %s" % (claim["id"], claim["title"]),
                "",
                claim["statement"],
                "",
                "- Verification: `%s`; truth status: `%s`."
                % (claim["verification_status"], claim["truth_status"]),
            ]
        )
        for locator in claim["locators"]:
            lines.append(
                "- `%s`, %s — %s"
                % (
                    locator["source_id"],
                    locator["locator"],
                    locator["evidence_note"],
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Execution boundary",
            "",
            "A proof may establish Tate type without proving CKgP, algebraicity, or",
            "tautological generation. A disproof must exhibit a surviving non-Tate",
            "summand in the exact Borel–Moore target (equivalently its stated",
            "ordinary-cohomology realization). Every degree and twist must be checked.",
            "",
        ]
    )
    return "\n".join(lines)


def case_packet_record(
    genus: int,
    markings: int,
    claims: Dict[str, Claim],
) -> Dict[str, Any]:
    text = render_case_packet(genus, markings, claims)
    target = open_input_target(genus, markings)
    return {
        "packet_id": target.packet_id,
        "packet_revision": CONTEXT_REVISION,
        "packet_path": str(case_packet_path(genus, markings).relative_to(ROOT)),
        "packet_sha256": sha256_text(text),
        "target": target.as_dict(),
        "relevant_claims": relevant_claims(claims),
        "corroborated_findings": findings_for_case(
            genus, markings, visible_only=True
        ),
        "_text": text,
    }


def write_case_packets(
    cases: List[Tuple[int, int]], claims: Dict[str, Claim]
) -> List[Dict[str, Any]]:
    records = []
    for genus, markings in cases:
        record = case_packet_record(genus, markings, claims)
        atomic_write_text(case_packet_path(genus, markings), record.pop("_text"))
        records.append(record)
    return records
