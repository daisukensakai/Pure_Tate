import datetime
import json
import re
from typing import Any, Dict, List

from .cases import compact_pairs, unresolved_cases
from .models import CheckResult, Claim, Source
from .store import ROOT


VERDICTS = {"agree", "disagree"}
AUDIT_ID_RE = re.compile(r"^RAUD-\d{4}$")


def load_research_audits() -> List[Dict[str, Any]]:
    audits = []
    directory = ROOT / "research" / "audits"
    for path in sorted(directory.glob("RAUD-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            audits.append({"_path": str(path), "_error": str(exc)})
            continue
        value["_path"] = str(path)
        audits.append(value)
    return audits


def audit_research_gate(
    config: Dict[str, Any], claims: Dict[str, Claim], sources: Dict[str, Source]
) -> CheckResult:
    result = CheckResult()
    expected = compact_pairs(unresolved_cases(16, config))
    agreeing = 0
    seen_ids = set()
    for audit in load_research_audits():
        if "_error" in audit:
            result.errors.append("%s: %s" % (audit["_path"], audit["_error"]))
            continue
        audit_id = audit.get("id")
        if (
            not isinstance(audit_id, str)
            or not AUDIT_ID_RE.match(audit_id)
            or audit_id in seen_ids
        ):
            result.errors.append("missing or duplicate research audit id %r" % audit_id)
            continue
        seen_ids.add(audit_id)
        if audit.get("target_claim_id") != "RED-0001":
            result.errors.append("%s audits the wrong target" % audit_id)
        if audit.get("verdict") not in VERDICTS:
            result.errors.append("%s has invalid verdict" % audit_id)
        if audit.get("independent") is not True:
            result.errors.append("%s is not independent" % audit_id)
        reviewer = audit.get("reviewer_engine")
        if not isinstance(reviewer, str) or not reviewer.strip():
            result.errors.append("%s lacks reviewer_engine" % audit_id)
        date_value = audit.get("forward_citation_check_date", "")
        try:
            if not isinstance(date_value, str):
                raise ValueError
            checked = datetime.date.fromisoformat(date_value)
            today = datetime.date.today()
            age = (today - checked).days
            if age < 0:
                result.errors.append("%s has a future citation check" % audit_id)
            elif age > int(config["citation_freshness_days"]):
                result.errors.append("%s has a stale citation check" % audit_id)
        except (TypeError, ValueError):
            result.errors.append("%s has malformed citation-check date" % audit_id)
        source_ids = audit.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            result.errors.append("%s records no source_ids" % audit_id)
            source_ids = []
        for source_id in source_ids:
            if source_id not in sources:
                result.errors.append("%s cites unknown source %s" % (audit_id, source_id))
        locators = audit.get("locators_checked")
        if (
            not isinstance(locators, list)
            or not locators
            or any(not isinstance(item, str) or not item.strip() for item in locators)
        ):
            result.errors.append("%s records no checked locators" % audit_id)
        raw_pairs = audit.get("inferred_pairs")
        pairs = []
        if not isinstance(raw_pairs, list):
            result.errors.append("%s has malformed inferred_pairs" % audit_id)
        else:
            for item in raw_pairs:
                if (
                    not isinstance(item, list)
                    or len(item) != 2
                    or any(type(value) is not int for value in item)
                ):
                    result.errors.append(
                        "%s has malformed inferred pair %r" % (audit_id, item)
                    )
                    continue
                pairs.append(tuple(item))
        if audit.get("verdict") == "agree":
            if pairs != expected:
                result.errors.append(
                    "%s says agree but inferred %s instead of %s"
                    % (audit_id, pairs, expected)
                )
            else:
                agreeing += 1
    reduction = claims["RED-0001"]
    if reduction.verification_status == config["research_completion_status"]:
        if agreeing < 1:
            result.errors.append(
                "RED-0001 is cross_checked without an agreeing independent audit"
            )
    elif agreeing:
        result.warnings.append(
            "an agreeing audit exists but RED-0001 has not been promoted to cross_checked"
        )
    else:
        result.warnings.append(
            "Stage 2 blocked: no agreeing independent audit for RED-0001"
        )
    return result


def stage_two_ready(
    config: Dict[str, Any], claims: Dict[str, Claim], sources: Dict[str, Source]
) -> bool:
    result = audit_research_gate(config, claims, sources)
    return (
        result.ok
        and claims["RED-0001"].verification_status
        == config["research_completion_status"]
        and not any("Stage 2 blocked" in warning for warning in result.warnings)
    )
