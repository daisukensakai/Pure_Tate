import datetime
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .campaigns import NOVELTY_DIR, case_verified, load_campaign, proof_hash
from .store import ROOT, atomic_write_bytes


NOVELTY_QUERY_FAMILIES = [
    "exact-target-aliases",
    "tetragonal-casnati-ekedahl-evaluation-degeneracy",
    "equivalent-ckgp-chow-local-system-formulations",
    "src-0002-src-0004-backward-forward-citations",
    "relevant-authors-current-work",
]
SOURCE_TYPES = {
    "journal",
    "preprint",
    "survey",
    "repository",
    "author-page",
    "citation-index",
    "other-primary",
}
NOVELTY_VERDICTS = {"no_prior_result", "prior_result_found", "inconclusive"}


def source_record_errors(
    record: Dict[str, Any], require_known_query_family: bool = True
) -> List[str]:
    errors = []
    for field in (
        "query_family",
        "retrieved_at",
        "url",
        "source_type",
        "content_sha256",
    ):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append("source record lacks %s" % field)
    for field in ("doi", "arxiv_id", "arxiv_version"):
        if field not in record:
            errors.append("source record does not explicitly record %s" % field)
    if (
        require_known_query_family
        and record.get("query_family") not in NOVELTY_QUERY_FAMILIES
    ):
        errors.append("source record uses unknown query family")
    if record.get("source_type") not in SOURCE_TYPES:
        errors.append("source record uses unknown source type")
    digest = str(record.get("content_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("source record has invalid SHA-256")
    url = str(record.get("url", ""))
    if not url.startswith(("https://", "http://")):
        errors.append("source record URL is not public HTTP(S)")
    try:
        datetime.datetime.fromisoformat(
            str(record.get("retrieved_at", "")).replace("Z", "+00:00")
        )
    except ValueError:
        errors.append("source record retrieved_at is not ISO-8601")
    return errors


def fetch_public_source(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "pure-tate-novelty-audit/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def verify_source_records(
    records: Iterable[Dict[str, Any]],
    fetch: bool = True,
    timeout: int = 30,
    cache: bool = True,
) -> Dict[str, Any]:
    records = list(records)
    errors = []
    verified = []
    families = set()
    for record in records:
        item_errors = source_record_errors(record)
        if item_errors:
            errors.extend(item_errors)
            continue
        families.add(record["query_family"])
        if fetch:
            try:
                content = fetch_public_source(record["url"], timeout=timeout)
            except Exception as exc:
                errors.append("failed to retrieve %s: %s" % (record["url"], exc))
                continue
            actual = hashlib.sha256(content).hexdigest()
            if actual != record["content_sha256"]:
                errors.append(
                    "source hash mismatch for %s: expected %s got %s"
                    % (record["url"], record["content_sha256"], actual)
                )
                continue
            if cache:
                destination = (
                    ROOT
                    / "research"
                    / "source-cache"
                    / (actual + ".bin")
                )
                if not destination.exists():
                    atomic_write_bytes(destination, content)
        verified.append(record)
    missing_families = sorted(set(NOVELTY_QUERY_FAMILIES) - families)
    if missing_families:
        errors.append(
            "audit omitted query families: %s" % ", ".join(missing_families)
        )
    return {
        "ok": not errors,
        "errors": errors,
        "verified_count": len(verified),
        "query_families": sorted(families),
    }


def validate_novelty_artifact(
    task: Dict[str, Any],
    artifact: Dict[str, Any],
    fetch: bool = True,
    timeout: int = 30,
) -> None:
    required = {
        "schema_version",
        "id",
        "task_id",
        "campaign_id",
        "campaign_revision",
        "attempt_id",
        "proof_sha256",
        "theorem_statement",
        "theorem_scope",
        "audit_date",
        "query_families",
        "source_records",
        "verdict",
        "closest_prior_results",
        "scope_comparison",
        "engine",
        "independent",
        "live_web",
        "capability_attestation_sha256",
    }
    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError("novelty artifact lacks fields: %s" % ", ".join(missing))
    exact = {
        "schema_version": 1,
        "task_id": task.get("id"),
        "campaign_id": task.get("campaign_id"),
        "campaign_revision": task.get("campaign_revision"),
        "attempt_id": task.get("attempt_id"),
        "proof_sha256": task.get("proof_sha256"),
        "theorem_statement": task.get("theorem_statement"),
        "theorem_scope": task.get("theorem_scope"),
    }
    for field, expected in exact.items():
        if artifact.get(field) != expected:
            raise ValueError("novelty artifact %s does not match task" % field)
    if artifact.get("verdict") not in NOVELTY_VERDICTS:
        raise ValueError("novelty artifact has invalid verdict")
    if artifact.get("audit_date") != datetime.date.today().isoformat():
        raise ValueError("novelty audit date is not current")
    if artifact.get("independent") is not True:
        raise ValueError("novelty audit is not independent")
    if artifact.get("live_web") is not True:
        raise ValueError("corpus-only work cannot satisfy a novelty audit")
    if set(artifact.get("query_families", [])) != set(NOVELTY_QUERY_FAMILIES):
        raise ValueError("novelty artifact did not search every required family")
    if not isinstance(artifact.get("source_records"), list):
        raise ValueError("novelty source_records must be a list")
    verification = verify_source_records(
        artifact["source_records"], fetch=fetch, timeout=timeout
    )
    if not verification["ok"]:
        raise ValueError(
            "novelty source verification failed: %s"
            % "; ".join(verification["errors"])
        )
    artifact["sources_verified"] = True
    artifact["verified_source_count"] = verification["verified_count"]


def novelty_tasks(campaign_id: str) -> List[Dict[str, Any]]:
    campaign = load_campaign(campaign_id)
    verification = case_verified(campaign_id)
    if not verification["verified"]:
        return []
    attempt = verification["attempt"]
    existing = []
    for path in NOVELTY_DIR.glob("NOV-*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            value.get("campaign_id") == campaign_id
            and value.get("attempt_id") == attempt.get("id")
            and value.get("proof_sha256") == proof_hash(attempt)
        ):
            existing.append(value)
    if any(item.get("verdict") == "prior_result_found" for item in existing):
        return []
    used_engines = sorted(
        {
            item.get("engine")
            for item in existing
            if isinstance(item.get("engine"), str)
        }
    )
    needed = max(0, campaign["novelty_audit_count"] - len(existing))
    tasks = []
    for index in range(needed):
        pass_number = len(existing) + index + 1
        tasks.append(
            {
                "id": "TASK-N-%s-P%d" % (attempt["id"], pass_number),
                "phase": "novelty",
                "role": "independent-live-web-prior-art-auditor",
                "campaign_id": campaign_id,
                "campaign_revision": campaign["campaign_revision"],
                "context_revision": campaign["context_revision"],
                "attempt_id": attempt["id"],
                "proof_sha256": proof_hash(attempt),
                "theorem_statement": attempt.get("theorem_statement"),
                "theorem_scope": attempt.get(
                    "theorem_scope", {"g": 6, "n": 6, "target": attempt["target"]}
                ),
                "query_families": NOVELTY_QUERY_FAMILIES,
                "excluded_engines": used_engines,
                "requires_live_web": True,
                "prompt": "prompts/NOVELTY_AUDIT.md",
                "input_attempt": str(Path(attempt["_path"]).relative_to(ROOT)),
                "output": "research/novelty-audits/NOV-####.json",
                "status": "ready",
                "created_on": datetime.date.today().isoformat(),
            }
        )
    return tasks
