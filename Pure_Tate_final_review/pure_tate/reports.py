import datetime
import json
from collections import Counter
from typing import Any, Dict, List

from .cases import compact_pairs, enumerate_reduction_cases, unresolved_cases
from .models import CheckResult, Claim, Source
from .findings import load_findings
from .targets import open_input_target, target_formula


def format_check_report(title: str, result: CheckResult) -> str:
    lines = ["# %s" % title, ""]
    lines.append("Status: **%s**" % ("PASS" if result.ok else "FAIL"))
    lines.extend(["", "## Errors", ""])
    lines.extend(["- %s" % item for item in result.errors] or ["- None."])
    lines.extend(["", "## Warnings", ""])
    lines.extend(["- %s" % item for item in result.warnings] or ["- None."])
    lines.append("")
    return "\n".join(lines)


def case_report(degree: int, config: Dict[str, Any]) -> str:
    cases = enumerate_reduction_cases(degree, config)
    unresolved = [case for case in cases if not case.covered]
    reasons = Counter(case.coverage_reason for case in cases if case.covered)
    lines = [
        "# Degree-%d reduction case matrix" % degree,
        "",
        "Generated from the finite inequalities recorded in `THM-0004` and the",
        "coverage ranges in `THM-0005`–`THM-0007`.",
        "",
        "- Required stable base pairs: %d" % len(cases),
        "- Covered by recorded results: %d" % (len(cases) - len(unresolved)),
        "- Unresolved: %d" % len(unresolved),
        "",
        "## Unresolved pairs",
        "",
    ]
    if unresolved:
        lines.append(
            ", ".join("$\\mathcal M_{%d,%d}$" % pair for pair in compact_pairs(unresolved))
        )
    else:
        lines.append("None.")
    lines.extend(["", "## Coverage summary", ""])
    for reason, count in sorted(reasons.items()):
        lines.append("- %d — %s" % (count, reason))
    lines.extend(
        [
            "",
            "## Full finite matrix",
            "",
            "| g | n | covered | reason |",
            "|---:|---:|:---:|---|",
        ]
    )
    for case in cases:
        lines.append(
            "| %d | %d | %s | %s |"
            % (
                case.genus,
                case.markings,
                "yes" if case.covered else "no",
                case.coverage_reason,
            )
        )
    lines.append("")
    return "\n".join(lines)


def obstruction_report(
    config: Dict[str, Any], claims: Dict[str, Claim], degree: int = 16
) -> str:
    reduction = claims["RED-0001"]
    unresolved = unresolved_cases(degree, config)
    ready = reduction.verification_status == config["research_completion_status"]
    lines = [
        "# Degree-16 obstruction report",
        "",
        "> Stage 2: **%s** — `RED-0001` is `%s`; required status is `%s`."
        % (
            "UNBLOCKED" if ready else "BLOCKED",
            reduction.verification_status,
            config["research_completion_status"],
        ),
        "",
        "## Candidate reduction",
        "",
        reduction.statement,
        "",
        "## Mechanically reproduced unresolved cases",
        "",
    ]
    for case in unresolved:
        target = open_input_target(case.genus, case.markings, degree)
        lines.append(
            "- $W_{-16}H^{BM}_{16}(\\mathcal M_{%d,%d})$, equivalently "
            "$W_{%d}H^{%d}(\\mathcal M_{%d,%d})(%d)$; ordinary Tate type "
            "$\\mathbb Q(-%d)$, Chow codimension %d — %s"
            % (
                case.genus,
                case.markings,
                target.ordinary_weight,
                target.ordinary_cohomology_degree,
                case.genus,
                case.markings,
                target.poincare_twist,
                target.chow_codimension,
                target.chow_codimension,
                case.coverage_reason,
            )
        )
    lines.extend(
        [
            "",
            "## Exact unresolved obstruction",
            "",
            "For every listed pair, with $d=3g-3+n$, prove that",
            "$W_{-16}H^{BM}_{16}(\\mathcal M_{g,n};\\mathbb Q)$ is a sum of",
            "$\\mathbb Q(8)$, equivalently that",
            "$W_{2d-16}H^{2d-16}(\\mathcal M_{g,n})(d)$ is Tate, or exhibit an",
            "off-diagonal Hodge summand that survives the compactification induction.",
            "",
            "The stronger assertions that these groups are algebraic or tautological are",
            "permitted proof strategies but are not part of the target.",
            "",
            "## Gate still owed",
            "",
        ]
    )
    if ready:
        lines.append("- The independent research derivation has been recorded.")
    else:
        lines.extend(
            [
                "- A clean-context researcher must independently reconstruct the degree-16",
                "  finite range and coverage subtraction from the primary sources.",
                "- It must check forward citations and newer versions through the current date.",
                "- On agreement, promote `RED-0001.verification_status` to `cross_checked`",
                "  and record the verifier artifact; on disagreement, revise the case matrix.",
            ]
        )
    lines.extend(
        [
            "",
            "Generated: %s" % datetime.date.today().isoformat(),
            "",
        ]
    )
    return "\n".join(lines)


def findings_report() -> str:
    findings = load_findings()
    counts = Counter(item.get("status") for item in findings)
    lines = [
        "# Adaptive findings ledger",
        "",
        "Only `corroborated` and `mechanically_verified` findings enter packets.",
        "",
    ]
    for status in (
        "candidate",
        "corroborated",
        "mechanically_verified",
        "retired",
    ):
        lines.append("- %s: %d" % (status, counts[status]))
    lines.extend(["", "| id | case | status | finding |", "|---|---|---|---|"])
    for item in findings:
        case = item.get("case")
        label = "all" if case == "all" else "(%d,%d)" % (case["g"], case["n"])
        lines.append(
            "| %s | %s | %s | %s |"
            % (item["id"], label, item["status"], item["statement"])
        )
    lines.append("")
    return "\n".join(lines)


def corpus_report(sources: Dict[str, Source], claims: Dict[str, Claim]) -> str:
    source_statuses = Counter(source.publication_status for source in sources.values())
    claim_statuses = Counter(claim.verification_status for claim in claims.values())
    lines = [
        "# Corpus snapshot",
        "",
        "- Sources: %d" % len(sources),
        "- Atomic claims: %d" % len(claims),
        "",
        "## Source status",
        "",
    ]
    for status, count in sorted(source_statuses.items()):
        lines.append("- %s: %d" % (status, count))
    lines.extend(["", "## Claim verification status", ""])
    for status, count in sorted(claim_statuses.items()):
        lines.append("- %s: %d" % (status, count))
    lines.extend(["", "## Sources", ""])
    for source in sorted(sources.values(), key=lambda item: item.id):
        lines.append(
            "- `%s` — %s — %s%s — checked %s"
            % (
                source.id,
                source.title,
                source.arxiv_id,
                source.arxiv_version,
                source.checked_on,
            )
        )
    lines.append("")
    return "\n".join(lines)
