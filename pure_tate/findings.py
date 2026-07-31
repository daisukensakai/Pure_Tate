import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from .store import ROOT, atomic_write_text, load_json, load_jsonl


FINDING_STATUSES = {
    "candidate",
    "corroborated",
    "mechanically_verified",
    "retired",
}
PACKET_VISIBLE_STATUSES = {"corroborated", "mechanically_verified"}
ADJUDICATION_ACTIONS = {"corroborate", "retire", "merge"}


def load_findings() -> List[Dict[str, Any]]:
    path = ROOT / "proof" / "findings.jsonl"
    if not path.exists():
        return []
    findings = load_jsonl(path)
    campaign_path = ROOT / "proof" / "campaign_findings.jsonl"
    if campaign_path.exists():
        campaign_findings = load_jsonl(campaign_path)
        for finding in campaign_findings:
            finding.setdefault("campaign_id", "C66-001")
        findings.extend(campaign_findings)
    review_engines = {}
    reviews_dir = ROOT / "proof" / "reviews"
    if reviews_dir.exists():
        for review_path in reviews_dir.glob("REV-*.json"):
            try:
                review = json.loads(review_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if review.get("id") and review.get("reviewer_engine"):
                review_engines[review["id"]] = review["reviewer_engine"]
    migration_path = (
        ROOT / "proof" / "migrations" / "campaign-C66-001-findings.json"
    )
    updates = {}
    if migration_path.exists():
        updates = load_json(migration_path).get("updates", {})
    for finding in findings:
        if finding.get("id") in updates:
            finding.update(updates[finding["id"]])
        case = finding.get("case")
        finding.setdefault(
            "scope",
            {"cases": "all"} if case == "all" else {"case": case},
        )
        finding.setdefault("evidence_class", "legacy_artifact")
        finding.setdefault("contradicts_claim_ids", [])
        finding.setdefault(
            "equivalence_group",
            finding.get("candidate_key", finding.get("id")),
        )
        finding.setdefault("supporting_artifact_hashes", [])
        inferred_engines = {
            review_engines[review_id]
            for review_id in finding.get("source_review_ids", [])
            if review_id in review_engines
        }
        if inferred_engines:
            finding["reviewer_engines"] = sorted(
                set(finding.get("reviewer_engines", [])) | inferred_engines
            )
    return findings


def findings_for_case(
    genus: int,
    markings: int,
    visible_only: bool = False,
    campaign_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    selected = []
    for finding in load_findings():
        finding_campaign = finding.get("campaign_id")
        if finding_campaign and finding_campaign != campaign_id:
            continue
        case = finding.get("case")
        applies = case == {"g": genus, "n": markings} or case == "all"
        if not applies:
            continue
        if visible_only and finding.get("status") not in PACKET_VISIBLE_STATUSES:
            continue
        selected.append(finding)
    return selected


def finding_by_id(finding_id: str) -> Optional[Dict[str, Any]]:
    for finding in load_findings():
        if finding.get("id") == finding_id:
            return finding
    return None


def load_finding_adjudications() -> List[Dict[str, Any]]:
    path = ROOT / "proof" / "finding_adjudications.jsonl"
    if not path.exists():
        return []
    return load_jsonl(path)


def _write_jsonl(path, rows: List[Dict[str, Any]]) -> None:
    atomic_write_text(
        path,
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in rows),
    )


def _write_findings(rows: List[Dict[str, Any]]) -> None:
    campaign_path = ROOT / "proof" / "campaign_findings.jsonl"
    if not campaign_path.exists():
        _write_jsonl(ROOT / "proof" / "findings.jsonl", rows)
        return
    legacy = []
    campaign = []
    for item in rows:
        match = re.fullmatch(r"FND-(\d{4})", str(item.get("id", "")))
        (campaign if match and int(match.group(1)) >= 35 else legacy).append(item)
    _write_jsonl(ROOT / "proof" / "findings.jsonl", legacy)
    _write_jsonl(campaign_path, campaign)


def adjudicate_finding(
    finding_id: str,
    action: str,
    reason: str,
    target_id: Optional[str] = None,
    adjudicator: str = "human",
    supporting_engine: Optional[str] = None,
    supporting_audit_id: Optional[str] = None,
) -> Dict[str, Any]:
    if action not in ADJUDICATION_ACTIONS:
        raise ValueError("invalid finding adjudication action %r" % action)
    if not reason.strip():
        raise ValueError("finding adjudication requires a reason")
    findings = load_findings()
    by_id = {item.get("id"): item for item in findings}
    if finding_id not in by_id:
        raise ValueError("unknown finding %s" % finding_id)
    finding = by_id[finding_id]
    if supporting_engine:
        finding["reviewer_engines"] = sorted(
            set(finding.get("reviewer_engines", [])) | {supporting_engine}
        )
    if supporting_audit_id:
        finding["supporting_audit_ids"] = sorted(
            set(finding.get("supporting_audit_ids", []))
            | {supporting_audit_id}
        )
        audit_path = (
            ROOT
            / "research"
            / "finding-audits"
            / (supporting_audit_id + ".json")
        )
        if audit_path.is_file():
            finding["supporting_artifact_hashes"] = sorted(
                set(finding.get("supporting_artifact_hashes", []))
                | {hashlib.sha256(audit_path.read_bytes()).hexdigest()}
            )
    if finding.get("adjudication_status") == "decided":
        raise ValueError("finding %s is already adjudicated" % finding_id)
    if action == "corroborate":
        if finding.get("contradicts_claim_ids") and not finding.get(
            "contradiction_resolution_audit_id"
        ):
            if supporting_audit_id:
                finding[
                    "contradiction_resolution_audit_id"
                ] = supporting_audit_id
            else:
                raise ValueError(
                    "finding contradicts cross-checked claims and requires an "
                    "explicit contradiction-resolution audit"
                )
        engines = set(finding.get("reviewer_engines", []))
        if len(engines) < 2:
            raise ValueError(
                "corroboration requires evidence from two distinct reviewer engines"
            )
        finding["status"] = "corroborated"
        finding.pop("duplicate_of", None)
    elif action == "merge":
        if not target_id or target_id not in by_id or target_id == finding_id:
            raise ValueError("merge requires a distinct existing target finding")
        target = by_id[target_id]
        for field in (
            "source_attempt_ids",
            "source_review_ids",
            "reviewer_engines",
            "supporting_review_ids",
            "supporting_reviewer_engines",
        ):
            merged = set(target.get(field, [])) | set(finding.get(field, []))
            if merged:
                target[field] = sorted(merged)
        finding["status"] = "retired"
        finding["duplicate_of"] = target_id
    else:
        finding["status"] = "retired"
        finding.pop("duplicate_of", None)
    finding["adjudication_reason"] = reason
    finding["adjudicator"] = adjudicator
    finding["adjudication_status"] = "decided"
    _write_findings(findings)

    adjudications = load_finding_adjudications()
    ordinals = [
        int(match.group(1))
        for item in adjudications
        for match in [re.fullmatch(r"FADJ-(\d{4})", str(item.get("id", "")))]
        if match
    ]
    ordinal = (max(ordinals) if ordinals else 0) + 1
    record = {
        "id": "FADJ-%04d" % ordinal,
        "finding_id": finding_id,
        "action": action,
        "target_id": target_id,
        "reason": reason,
        "adjudicator": adjudicator,
    }
    adjudications.append(record)
    _write_jsonl(
        ROOT / "proof" / "finding_adjudications.jsonl", adjudications
    )
    return record


def record_review_findings(
    review: Dict[str, Any], attempt: Dict[str, Any]
) -> List[Dict[str, Any]]:
    findings = load_findings()
    changed = False
    touched = []
    for candidate in review.get("finding_candidates", []):
        supports = candidate.get("supports_finding_id")
        if isinstance(supports, str) and supports:
            existing = next(
                (item for item in findings if item.get("id") == supports),
                None,
            )
            if existing is not None:
                existing.setdefault("supporting_review_ids", []).append(review["id"])
                existing.setdefault("supporting_reviewer_engines", []).append(
                    review["reviewer_engine"]
                )
                existing["supporting_review_ids"] = sorted(
                    set(existing["supporting_review_ids"])
                )
                existing["supporting_reviewer_engines"] = sorted(
                    set(existing["supporting_reviewer_engines"])
                )
                touched.append(existing)
                changed = True
                continue
        key = str(candidate.get("key", "")).strip()
        if not key:
            continue
        attempt_case = {
            "g": attempt["target"]["g"],
            "n": attempt["target"]["n"],
        }
        existing = next(
            (
                item
                for item in findings
                if item.get("candidate_key") == key
                and item.get("case") == attempt_case
            ),
            None,
        )
        if existing is None:
            numbers = [
                int(match.group(1))
                for item in findings
                for match in [re.fullmatch(r"FND-(\d{4})", str(item.get("id", "")))]
                if match
            ]
            existing = {
                "id": "FND-%04d" % ((max(numbers) if numbers else 0) + 1),
                "candidate_key": key,
                "case": attempt_case,
                "kind": candidate.get("kind", "obstruction"),
                "status": "candidate",
                "adjudication_status": "pending",
                "statement": candidate["statement"],
                "source_attempt_ids": [attempt["id"]],
                "source_review_ids": [review["id"]],
                "reviewer_engines": [review["reviewer_engine"]],
                "verification_method": "revision-2 adversarial review",
                "impacts_approach_ids": candidate.get(
                    "impacts_approach_ids",
                    [
                        attempt.get(
                            "approach_id", attempt.get("subproblem_id", "unknown")
                        )
                    ],
                ),
                "created_on": review.get("created_on"),
                "scope": candidate.get("scope", {"case": attempt_case}),
                "evidence_class": candidate.get(
                    "evidence_class", "adversarial_review"
                ),
                "contradicts_claim_ids": candidate.get(
                    "contradicts_claim_ids", []
                ),
                "equivalence_group": candidate.get(
                    "equivalence_group", key
                ),
                "supporting_artifact_hashes": candidate.get(
                    "supporting_artifact_hashes", []
                ),
            }
            findings.append(existing)
            changed = True
        else:
            engines = set(existing.get("reviewer_engines", []))
            if review["reviewer_engine"] not in engines:
                engines.add(review["reviewer_engine"])
                existing["reviewer_engines"] = sorted(engines)
                existing.setdefault("source_review_ids", []).append(review["id"])
                if len(engines) >= 2 and existing.get("status") == "candidate":
                    existing["corroboration_ready"] = True
                changed = True
        touched.append(existing)
    if changed:
        _write_findings(findings)
    return touched
