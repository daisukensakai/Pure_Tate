import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .store import (
    ROOT,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    load_json,
    load_jsonl,
)


FINDING_STATUSES = {
    "candidate",
    "corroborated",
    "mechanically_verified",
    "retired",
}
PACKET_VISIBLE_STATUSES = {"corroborated", "mechanically_verified"}
ADJUDICATION_ACTIONS = {"corroborate", "retire", "merge"}
FINDING_SOURCE_ATTESTATION_REASON = "C66-FINDING-SOURCE-ATTESTATION-0001"


def _finding_audit_dir() -> Path:
    return ROOT / "research" / "finding-audits"


def _finding_audit_raw_dir() -> Path:
    return _finding_audit_dir() / "raw-pre-attestation"


def _finding_source_attestation_path() -> Path:
    return ROOT / "proof" / "migrations" / "finding-source-attestation.json"


def _finding_source_url_substitutions_path() -> Path:
    return ROOT / "proof" / "migrations" / "finding-source-url-substitutions.json"


def _finding_source_additions_path() -> Path:
    return ROOT / "proof" / "migrations" / "finding-source-additions.json"


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
    replacements = _finding_source_hash_replacements()
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
        if replacements and finding.get("supporting_artifact_hashes"):
            finding["supporting_artifact_hashes"] = [
                replacements.get(digest, digest)
                for digest in finding["supporting_artifact_hashes"]
            ]
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
    allowed_campaign_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    selected = []
    allowed = (
        {item for item in allowed_campaign_ids if isinstance(item, str) and item}
        if allowed_campaign_ids is not None
        else None
    )
    for finding in load_findings():
        finding_campaign = finding.get("campaign_id")
        if allowed is not None:
            if finding_campaign and finding_campaign not in allowed:
                continue
        elif finding_campaign and finding_campaign != campaign_id:
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
    supporting_evidence_class: Optional[str] = None,
    supporting_scope: Optional[Dict[str, Any]] = None,
    adjudicated_statement: Optional[str] = None,
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
    if supporting_evidence_class:
        finding["evidence_class"] = supporting_evidence_class
    if isinstance(supporting_scope, dict) and supporting_scope:
        finding["scope"] = supporting_scope
    if isinstance(adjudicated_statement, str) and adjudicated_statement.strip():
        revised = adjudicated_statement.strip()
        if revised != finding.get("statement"):
            finding.setdefault(
                "pre_adjudication_statement", finding.get("statement")
            )
            finding["statement"] = revised
            if supporting_audit_id:
                finding["statement_revision_audit_id"] = supporting_audit_id
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


def _finding_source_hash_replacements() -> Dict[str, str]:
    path = _finding_source_attestation_path()
    if not path.exists():
        return {}
    try:
        payload = load_json(path)
    except (OSError, ValueError):
        return {}
    replacements = payload.get("finding_hash_replacements", {})
    if not isinstance(replacements, dict):
        return {}
    direct = {
        str(old): str(new)
        for old, new in replacements.items()
        if old and new
    }
    resolved: Dict[str, str] = {}
    for old, first in direct.items():
        current = first
        seen = {old}
        while current in direct and current not in seen:
            seen.add(current)
            current = direct[current]
        # A cycle is malformed provenance. Leave the original digest in place
        # so the proof audit fails closed instead of blessing an arbitrary hop.
        resolved[old] = old if current in seen else current
    return resolved


def _load_source_url_substitutions() -> Dict[str, Optional[str]]:
    path = _finding_source_url_substitutions_path()
    if not path.exists():
        return {}
    try:
        payload = load_json(path)
    except (OSError, ValueError):
        return {}
    substitutions = payload.get("substitutions", {})
    if not isinstance(substitutions, dict):
        return {}
    resolved = {}
    for old, new in substitutions.items():
        if not old:
            continue
        if new is None:
            resolved[str(old)] = None
        elif isinstance(new, str) and new.strip():
            resolved[str(old)] = new.strip()
    return resolved


def _arxiv_identity_from_url(url: str) -> Dict[str, Optional[str]]:
    match = re.search(
        r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})(v\d+)?",
        url,
    )
    if not match:
        return {}
    return {
        "arxiv_id": match.group(1),
        "arxiv_version": match.group(2),
    }


def _apply_source_url_substitutions(
    records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    substitutions = _load_source_url_substitutions()
    if not substitutions:
        return records, []
    updated = []
    transformations = []
    for record in records:
        if not isinstance(record, dict):
            continue
        url = str(record.get("url") or "")
        if url not in substitutions:
            updated.append(record)
            continue
        replacement = substitutions[url]
        if replacement is None:
            transformations.append("dropped unfetchable %s" % url)
            continue
        rewritten = dict(record)
        rewritten["url"] = replacement
        rewritten.update(_arxiv_identity_from_url(replacement))
        transformations.append("replaced %s with %s" % (url, replacement))
        updated.append(rewritten)
    return updated, transformations


def _load_source_additions(audit_id: str) -> List[Dict[str, Any]]:
    path = _finding_source_additions_path()
    if not path.exists():
        return []
    try:
        payload = load_json(path)
    except (OSError, ValueError):
        return []
    additions = payload.get("additions", {})
    if not isinstance(additions, dict):
        return []
    rows = additions.get(audit_id)
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("url")]


def _apply_source_additions(
    audit_id: str,
    records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    extras = _load_source_additions(audit_id)
    if not extras:
        return records, []
    existing = {str(record.get("url") or "") for record in records}
    updated = list(records)
    transformations = []
    for extra in extras:
        url = str(extra.get("url") or "")
        if not url or url in existing:
            continue
        prepared = dict(extra)
        prepared.setdefault("retrieved_at", "2026-08-17T00:00:00Z")
        for field in ("doi", "arxiv_id", "arxiv_version"):
            prepared.setdefault(field, None)
        updated.append(prepared)
        existing.add(url)
        transformations.append("added public source %s" % url)
    return updated, transformations


def _prepare_public_source_record(record: Dict[str, Any]) -> Dict[str, Any]:
    from .novelty import normalize_finding_source_type

    prepared = dict(record)
    prepared["source_type"] = normalize_finding_source_type(
        prepared.get("source_type")
    )
    for field in ("doi", "arxiv_id", "arxiv_version"):
        prepared.setdefault(field, None)
    return prepared


def _attest_local_source_record(record: Dict[str, Any]) -> Dict[str, Any]:
    from .novelty import local_source_path

    path = local_source_path(record.get("url"), root=ROOT)
    if path is None:
        return dict(record)
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    updated = dict(record)
    reported = updated.get("content_sha256")
    if reported != actual:
        updated["reported_content_sha256"] = reported
    updated["content_sha256"] = actual
    updated["hash_attested_by"] = "pure_tate_harness"
    return updated


def _serialized_finding_audit(artifact: Dict[str, Any]) -> bytes:
    return (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode("utf-8")


def repair_finding_audit_sources(
    artifact: Dict[str, Any],
    timeout: int = 30,
    fetch_cache: Optional[Dict[str, bytes]] = None,
) -> Dict[str, Any]:
    from .novelty import attest_source_records, is_public_source_url

    if artifact.get("sources_verified") is True:
        return {
            "status": "already_verified",
            "artifact": artifact,
            "transformations": [],
            "errors": [],
            "verified_source_count": artifact.get("verified_source_count", 0),
            "local_evidence_count": len(artifact.get("local_evidence_records") or []),
            "changed": False,
        }

    previous_migration = artifact.get("source_attestation_migration")
    if not isinstance(previous_migration, dict):
        previous_migration = {}
    records = artifact.get("source_records")
    if not isinstance(records, list):
        records = []
    records, transformations = _apply_source_url_substitutions(records)
    records, added = _apply_source_additions(str(artifact.get("id") or ""), records)
    transformations.extend(added)
    public_originals = []
    public_prepared = []
    local_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if is_public_source_url(record.get("url")):
            prepared = _prepare_public_source_record(record)
            if prepared.get("source_type") != record.get("source_type"):
                transformations.append(
                    "normalized %s source_type to %s"
                    % (record.get("source_type"), prepared["source_type"])
                )
            public_originals.append(record)
            public_prepared.append(prepared)
        else:
            attested_local = _attest_local_source_record(record)
            if attested_local.get("hash_attested_by") == "pure_tate_harness":
                transformations.append(
                    "hashed local evidence %s" % record.get("url")
                )
            local_records.append(attested_local)

    errors = []
    attested_public = []
    leftover_public = []
    if public_prepared:
        verification = attest_source_records(
            public_prepared,
            timeout=timeout,
            require_known_query_families=False,
            fetch_cache=fetch_cache,
        )
        errors.extend(verification.get("errors") or [])
        by_index = verification.get("by_index") or {}
        for index, original in enumerate(public_originals):
            attested = by_index.get(index)
            if attested is not None:
                attested_public.append(attested)
                continue
            leftover = dict(public_prepared[index])
            leftover["content_sha256"] = original.get("content_sha256")
            leftover_public.append(leftover)

    if local_records:
        transformations.append(
            "moved non-public records to local_evidence_records"
        )

    remaining_public = attested_public + leftover_public
    artifact["source_records"] = remaining_public
    if local_records:
        existing_local = artifact.get("local_evidence_records")
        if not isinstance(existing_local, list):
            existing_local = []
        artifact["local_evidence_records"] = existing_local + local_records

    verified_count = len(attested_public)
    if attested_public and not leftover_public:
        artifact["sources_verified"] = True
        artifact["verified_source_count"] = verified_count
        status = "attested"
    elif not public_originals:
        status = "skipped_no_public"
    elif attested_public:
        status = "partial"
        artifact["verified_source_count"] = verified_count
    else:
        status = "unchanged" if not local_records and not transformations else "partial"
        if verified_count:
            artifact["verified_source_count"] = verified_count

    previous_transformations = previous_migration.get("transformations")
    if not isinstance(previous_transformations, list):
        previous_transformations = []
    merged_transformations = []
    for item in previous_transformations + transformations:
        if item not in merged_transformations:
            merged_transformations.append(item)
    migration = {
        "attested_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "reason": FINDING_SOURCE_ATTESTATION_REASON,
        "transformations": merged_transformations,
        "errors": errors,
    }
    for field in ("raw_artifact_path", "raw_artifact_sha256"):
        if previous_migration.get(field):
            migration[field] = previous_migration[field]
    artifact["source_attestation_migration"] = migration
    transformations = merged_transformations
    return {
        "status": status,
        "artifact": artifact,
        "transformations": transformations,
        "errors": errors,
        "verified_source_count": verified_count,
        "local_evidence_count": len(artifact.get("local_evidence_records") or []),
        "changed": True,
    }


def repair_finding_audit_corpus(
    dry_run: bool = False,
    audit_ids: Optional[Sequence[str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    wanted = set(audit_ids) if audit_ids else None
    fetch_cache: Dict[str, bytes] = {}
    existing: Dict[str, Any] = {}
    receipt_path = _finding_source_attestation_path()
    if receipt_path.exists():
        try:
            existing = load_json(receipt_path)
        except (OSError, ValueError):
            existing = {}
    audit_rows = dict(existing.get("audits") or {})
    replacements = dict(existing.get("finding_hash_replacements") or {})
    results = []

    for path in sorted(_finding_audit_dir().glob("FAUD-*.json")):
        audit_id = path.stem
        if wanted is not None and audit_id not in wanted:
            continue
        original_bytes = path.read_bytes()
        old_sha = hashlib.sha256(original_bytes).hexdigest()
        artifact = json.loads(original_bytes.decode("utf-8"))
        if not isinstance(artifact, dict):
            raise ValueError("%s is not a JSON object" % audit_id)
        repair = repair_finding_audit_sources(
            artifact, timeout=timeout, fetch_cache=fetch_cache
        )
        new_bytes = _serialized_finding_audit(repair["artifact"])
        new_sha = hashlib.sha256(new_bytes).hexdigest()
        raw_rel = "research/finding-audits/raw-pre-attestation/%s.json" % audit_id
        row = {
            "status": repair["status"],
            "raw_artifact_path": raw_rel,
            "raw_artifact_sha256": old_sha,
            "new_artifact_sha256": new_sha,
            "verified_source_count": repair["verified_source_count"],
            "local_evidence_count": repair["local_evidence_count"],
            "errors": repair["errors"],
            "transformations": repair["transformations"],
        }
        if repair["status"] == "already_verified":
            previous = audit_rows.get(audit_id)
            if isinstance(previous, dict):
                row = dict(previous)
            else:
                row["raw_artifact_path"] = None
                row["new_artifact_sha256"] = old_sha
        elif repair["changed"] and old_sha != new_sha:
            replacements[old_sha] = new_sha
            if not dry_run:
                raw_path = _finding_audit_raw_dir() / (audit_id + ".json")
                if not raw_path.exists():
                    atomic_write_bytes(raw_path, original_bytes)
                migration = repair["artifact"].setdefault(
                    "source_attestation_migration", {}
                )
                migration.setdefault("raw_artifact_path", raw_rel)
                migration.setdefault(
                    "raw_artifact_sha256",
                    hashlib.sha256(
                        raw_path.read_bytes() if raw_path.exists() else original_bytes
                    ).hexdigest(),
                )
                row["raw_artifact_path"] = migration.get("raw_artifact_path", raw_rel)
                row["raw_artifact_sha256"] = migration.get(
                    "raw_artifact_sha256", old_sha
                )
                new_bytes = _serialized_finding_audit(repair["artifact"])
                new_sha = hashlib.sha256(new_bytes).hexdigest()
                row["new_artifact_sha256"] = new_sha
                replacements[old_sha] = new_sha
                atomic_write_bytes(path, new_bytes)
        audit_rows[audit_id] = row
        results.append({"id": audit_id, **row})

    summary: Dict[str, int] = {}
    for item in audit_rows.values():
        if isinstance(item, dict) and item.get("status"):
            summary[item["status"]] = summary.get(item["status"], 0) + 1
    receipt = {
        "schema_version": 1,
        "campaign_id": "C66-001",
        "reason": FINDING_SOURCE_ATTESTATION_REASON,
        "preserves_original_ledger": True,
        "does_not_change_adjudication": True,
        "recorded_on": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "audits": audit_rows,
        "finding_hash_replacements": replacements,
        "summary": summary,
    }
    if not dry_run:
        atomic_write_json(receipt_path, receipt)
    return {
        "dry_run": dry_run,
        "summary": summary,
        "results": results,
        "receipt": receipt,
    }
