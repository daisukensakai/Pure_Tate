import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from .models import CheckResult, Claim
from .findings import (
    ADJUDICATION_ACTIONS,
    FINDING_STATUSES,
    PACKET_VISIBLE_STATUSES,
    load_finding_adjudications,
    load_findings,
)
from .store import DATA, ROOT, load_jsonl
from .targets import CONTEXT_REVISION, open_input_target
from .tasking import APPROACHES


ATTEMPT_STATUSES = {
    "draft",
    "proposed",
    "claimed_complete",
    "refuted",
    "verified",
}
REVIEW_VERDICTS = {"confirmed", "incomplete", "refuted"}


def _load_named_json(directory: Path, prefix: str) -> List[Dict[str, Any]]:
    values = []
    if not directory.exists():
        return values
    for path in sorted(directory.glob(prefix + "-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            values.append({"_path": str(path), "_error": str(exc)})
            continue
        value["_path"] = str(path)
        values.append(value)
    return values


def _migration() -> Dict[str, Any]:
    path = ROOT / "proof" / "migrations" / "context-v2.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _campaign_migration() -> Dict[str, Any]:
    path = (
        ROOT
        / "proof"
        / "migrations"
        / "campaign-C66-001-v3.json"
    )
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_task_id(target: Dict[str, Any], approach_id: str) -> str:
    cases = [(3, 12), (5, 8), (6, 6), (7, 4), (8, 0), (8, 1), (8, 2)]
    pair = (target.get("g"), target.get("n"))
    if pair not in cases or approach_id not in APPROACHES:
        return ""
    ordinal = cases.index(pair) * len(APPROACHES) + APPROACHES.index(approach_id) + 1
    return "TASK-M-%04d" % ordinal


def _check_legacy_integrity(
    result: CheckResult, migration: Dict[str, Any], kind: str
) -> None:
    directory = ROOT / "proof" / kind
    for artifact_id, record in migration.get(kind, {}).items():
        if not isinstance(record, dict):
            continue
        path = directory / (artifact_id + ".json")
        if not path.is_file():
            result.errors.append("legacy artifact %s is missing" % artifact_id)
            continue
        actual = _sha256(path)
        if actual != record.get("sha256"):
            result.errors.append(
                "legacy artifact %s changed byte-for-byte" % artifact_id
            )


def _check_run_artifact_integrity(result: CheckResult) -> None:
    receipt_path = ROOT / "proof" / "artifact-normalizations.json"
    receipts: List[Dict[str, Any]] = []
    if receipt_path.is_file():
        try:
            receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipts = receipt_data.get("normalizations", [])
            if not isinstance(receipts, list):
                raise ValueError("normalizations is not a list")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            result.errors.append("artifact normalization ledger is invalid: %s" % exc)
            receipts = []
    valid_receipts = set()
    for index, receipt in enumerate(receipts, 1):
        label = "artifact normalization %d" % index
        if not isinstance(receipt, dict):
            result.errors.append("%s is not an object" % label)
            continue
        path = ROOT / str(receipt.get("artifact_path", ""))
        if not path.is_file():
            result.errors.append("%s artifact is missing" % label)
            continue
        current = _sha256(path)
        if current != receipt.get("current_sha256"):
            result.errors.append("%s current artifact hash does not match" % label)
            continue
        trace_path = receipt.get("trace_path")
        if trace_path:
            trace = ROOT / str(trace_path)
            if not trace.is_file():
                result.errors.append("%s trace is missing" % label)
                continue
            if _sha256(trace) != receipt.get("trace_sha256"):
                result.errors.append("%s trace hash does not match" % label)
                continue
        valid_receipts.add(
            (
                str(receipt.get("artifact_path")),
                str(receipt.get("original_sha256")),
                str(receipt.get("current_sha256")),
            )
        )
    for run_path in sorted((ROOT / "reports" / "runs").glob("RUN-*.json")):
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result.errors.append("%s is invalid: %s" % (run_path.name, exc))
            continue
        for event in run.get("events", []):
            if not isinstance(event, dict) or event.get("state") != "completed":
                continue
            relative = event.get("output")
            recorded = event.get("artifact_sha256")
            if (
                not isinstance(relative, str)
                or not isinstance(recorded, str)
                or not relative.startswith(("proof/attempts/", "proof/reviews/"))
            ):
                continue
            path = ROOT / relative
            if not path.is_file():
                result.errors.append(
                    "%s completed artifact is missing: %s"
                    % (run_path.name, relative)
                )
                continue
            current = _sha256(path)
            if current != recorded and (
                relative,
                recorded,
                current,
            ) not in valid_receipts:
                result.errors.append(
                    "%s artifact hash changed without a normalization receipt: %s"
                    % (run_path.name, relative)
                )


def audit_proofs(claims: Dict[str, Claim]) -> CheckResult:
    result = CheckResult()
    from .paired import integrity_errors as paired_integrity_errors

    result.errors.extend(paired_integrity_errors())
    _check_run_artifact_integrity(result)
    attempts = _load_named_json(ROOT / "proof" / "attempts", "ATT")
    reviews = _load_named_json(ROOT / "proof" / "reviews", "REV")
    migration = _migration()
    campaign_migration = _campaign_migration()
    legacy_attempts = set(migration.get("attempts", {}))
    legacy_reviews = set(migration.get("reviews", {}))
    stale_campaign_attempts = set(
        campaign_migration.get("attempts", {})
    )
    stale_campaign_reviews = set(
        campaign_migration.get("reviews", {})
    )
    _check_legacy_integrity(result, migration, "attempts")
    _check_legacy_integrity(result, migration, "reviews")
    _check_legacy_integrity(
        result, campaign_migration, "attempts"
    )
    _check_legacy_integrity(
        result, campaign_migration, "reviews"
    )
    finding_ids = set()
    known_source_ids = {
        str(row.get("id"))
        for row in load_jsonl(DATA / "sources.jsonl")
        if isinstance(row.get("id"), str)
    }
    findings_by_id: Dict[str, Dict[str, Any]] = {}
    campaign_ledger_present = (
        ROOT / "proof" / "campaign_findings.jsonl"
    ).is_file()
    known_artifact_hashes = set()
    for directory, pattern in (
        (ROOT / "proof" / "attempts", "ATT-*.json"),
        (ROOT / "proof" / "reviews", "REV-*.json"),
        (ROOT / "research" / "followups", "RF-*.json"),
        (ROOT / "research" / "finding-audits", "FAUD-*.json"),
        (ROOT / "research" / "novelty-audits", "NOV-*.json"),
    ):
        for path in directory.glob(pattern):
            known_artifact_hashes.add(_sha256(path))
    for finding in load_findings():
        finding_id = finding.get("id")
        if not finding_id or finding_id in finding_ids:
            result.errors.append("missing or duplicate finding id %r" % finding_id)
        finding_ids.add(finding_id)
        if isinstance(finding_id, str):
            findings_by_id[finding_id] = finding
        if finding.get("status") not in FINDING_STATUSES:
            result.errors.append(
                "%s has invalid finding status %r"
                % (finding_id, finding.get("status"))
            )
        for field in (
            "scope",
            "evidence_class",
            "contradicts_claim_ids",
            "equivalence_group",
            "supporting_artifact_hashes",
        ):
            if field not in finding:
                result.errors.append("%s lacks finding field %s" % (finding_id, field))
        contradictions = finding.get("contradicts_claim_ids", [])
        if not isinstance(contradictions, list):
            result.errors.append("%s contradictions must be a list" % finding_id)
        else:
            for claim_id in contradictions:
                if claim_id not in claims:
                    result.errors.append(
                        "%s contradicts unknown claim %s" % (finding_id, claim_id)
                    )
        supporting_hashes = finding.get("supporting_artifact_hashes", [])
        if campaign_ledger_present and (
            not isinstance(supporting_hashes, list)
            or any(
                digest not in known_artifact_hashes
                for digest in supporting_hashes
            )
        ):
            result.errors.append(
                "%s has an unknown supporting-artifact hash" % finding_id
            )
        if (
            finding.get("status") in PACKET_VISIBLE_STATUSES
            and finding.get("contradicts_claim_ids")
            and not finding.get("contradiction_resolution_audit_id")
        ):
            result.errors.append(
                "%s is packet-visible despite an unresolved claim contradiction"
                % finding_id
            )
    adjudication_ids = set()
    for adjudication in load_finding_adjudications():
        adjudication_id = adjudication.get("id")
        if not adjudication_id or adjudication_id in adjudication_ids:
            result.errors.append(
                "missing or duplicate finding adjudication id %r"
                % adjudication_id
            )
        adjudication_ids.add(adjudication_id)
        if adjudication.get("finding_id") not in findings_by_id:
            result.errors.append(
                "%s targets an unknown finding" % adjudication_id
            )
        if adjudication.get("action") not in ADJUDICATION_ACTIONS:
            result.errors.append(
                "%s has invalid adjudication action" % adjudication_id
            )
        if (
            adjudication.get("action") == "merge"
            and adjudication.get("target_id") not in findings_by_id
        ):
            result.errors.append(
                "%s merges into an unknown finding" % adjudication_id
            )
        finding = findings_by_id.get(adjudication.get("finding_id"), {})
        action = adjudication.get("action")
        if action in {"retire", "merge"} and finding.get("status") != "retired":
            result.errors.append(
                "%s is inconsistent with the finding status" % adjudication_id
            )
        if action == "merge" and finding.get("duplicate_of") != adjudication.get(
            "target_id"
        ):
            result.errors.append(
                "%s is inconsistent with the finding merge target"
                % adjudication_id
            )
        if action == "corroborate" and finding.get("status") != "corroborated":
            result.errors.append(
                "%s is inconsistent with the finding status" % adjudication_id
            )
        if not str(adjudication.get("reason", "")).strip():
            result.errors.append("%s lacks a reason" % adjudication_id)
    attempts_by_id: Dict[str, Dict[str, Any]] = {}
    reviews_by_attempt: Dict[str, List[Dict[str, Any]]] = {}

    for attempt in attempts:
        if "_error" in attempt:
            result.errors.append("%s: %s" % (attempt["_path"], attempt["_error"]))
            continue
        attempt_id = attempt.get("id", "")
        if not attempt_id or attempt_id in attempts_by_id:
            result.errors.append("missing or duplicate proof attempt id %r" % attempt_id)
            continue
        attempts_by_id[attempt_id] = attempt
        if attempt_id in legacy_attempts:
            continue
        if attempt_id in stale_campaign_attempts:
            result.warnings.append(
                "%s is stale_campaign_context under %s"
                % (
                    attempt_id,
                    campaign_migration.get(
                        "reason", "campaign revision"
                    ),
                )
            )
            continue
        status = attempt.get("status")
        if status not in ATTEMPT_STATUSES:
            result.errors.append("%s has invalid status %r" % (attempt_id, status))
        target = attempt.get("target_claim_id")
        if target not in claims:
            result.errors.append("%s targets unknown claim %r" % (attempt_id, target))
        is_campaign = bool(attempt.get("campaign_id"))
        expected_schema = 3 if is_campaign else 2
        if migration and attempt.get("schema_version") != expected_schema:
            result.errors.append(
                "%s has wrong attempt schema for its context" % attempt_id
            )
        required_fields = [
            "task_id",
            "packet_id",
            "packet_path",
            "packet_sha256",
            "target",
            "summary",
            "argument_markdown",
            "claims",
            "gap_markers",
        ]
        if is_campaign:
            required_fields.extend(
                [
                    "campaign_revision",
                    "subproblem_id",
                    "lane",
                    "result_type",
                    "theorem_statement",
                    "proof_dependencies",
                    "experiment_ids",
                    "experiment_uses",
                    "novelty_claims",
                    "failed_approaches_addressed",
                    "methods_used",
                    "new_inputs",
                ]
            )
        else:
            required_fields.append("approach_id")
        for field in required_fields:
            if migration and field not in attempt:
                result.errors.append("%s lacks required field %s" % (attempt_id, field))
        if migration and attempt.get("context_revision") != CONTEXT_REVISION:
            result.errors.append("%s has stale context revision" % attempt_id)
        if migration and isinstance(attempt.get("target"), dict):
            target = attempt["target"]
            try:
                expected_target = open_input_target(
                    target.get("g"), target.get("n")
                ).as_dict()
            except (TypeError, ValueError):
                expected_target = None
            if target != expected_target:
                result.errors.append("%s has an incorrect target dictionary" % attempt_id)
            if is_campaign:
                if attempt.get("paired_turn_kind") == "forced-proof":
                    expected_task = "TASK-%s-FORCED-FULL" % attempt.get(
                        "campaign_id"
                    )
                else:
                    from .tasking import campaign_mathematics_tasks

                    task_ids = {
                        task["subproblem_id"]: task["id"]
                        for task in campaign_mathematics_tasks(
                            str(attempt.get("campaign_id"))
                        )
                    }
                    expected_task = task_ids.get(
                        attempt.get("subproblem_id"), ""
                    )
            else:
                expected_task = _expected_task_id(
                    target, str(attempt.get("approach_id", ""))
                )
            if attempt.get("task_id") != expected_task:
                result.errors.append("%s has incorrect task linkage" % attempt_id)
        if migration and isinstance(attempt.get("packet_path"), str):
            packet_path = ROOT / attempt["packet_path"]
            if not packet_path.is_file():
                result.errors.append("%s packet is missing" % attempt_id)
            elif _sha256(packet_path) != attempt.get("packet_sha256"):
                result.warnings.append(
                    "%s is stale_context because its packet hash was superseded"
                    % attempt_id
                )
        if migration:
            structured = attempt.get("claims")
            if not isinstance(structured, list) or any(
                not isinstance(item, dict)
                or not str(item.get("statement", "")).strip()
                for item in structured
            ):
                result.errors.append("%s claims are not structured" % attempt_id)
        for claim_id in attempt.get("source_claim_ids", []):
            if claim_id in findings_by_id:
                if findings_by_id[claim_id].get("status") not in PACKET_VISIBLE_STATUSES:
                    result.errors.append(
                        "%s cites finding %s below corroborated"
                        % (attempt_id, claim_id)
                    )
                continue
            if claim_id not in claims:
                result.errors.append(
                    "%s cites unknown claim %s" % (attempt_id, claim_id)
                )
            elif claims[claim_id].verification_status not in (
                "source_verified",
                "cross_checked",
            ):
                result.errors.append(
                    "%s relies on claim %s below source_verified"
                    % (attempt_id, claim_id)
                )
        for source_id in attempt.get("source_ids", []):
            if source_id not in known_source_ids:
                result.errors.append(
                    "%s cites unknown source %s" % (attempt_id, source_id)
                )
        gaps = attempt.get("gap_markers", [])
        if status in {"claimed_complete", "verified"} and gaps:
            result.errors.append(
                "%s is %s but retains gap markers" % (attempt_id, status)
            )
        if is_campaign and status in {"claimed_complete", "verified"}:
            experiment_results = []
            result_dir = ROOT / "experiments" / "results"
            for path in result_dir.glob("EXP-*.json"):
                try:
                    experiment_results.append(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                except (OSError, json.JSONDecodeError):
                    continue
            reproduced = {
                item.get("experiment_id")
                for item in experiment_results
                if item.get("reproduced") is True
            }
            for use in attempt.get("experiment_uses", []):
                if use.get("use") == "universal_identity":
                    if use.get("experiment_id") not in reproduced:
                        result.errors.append(
                            "%s uses an unreproduced universal computation"
                            % attempt_id
                        )
                    if not str(use.get("proof_coverage", "")).strip():
                        result.errors.append(
                            "%s lacks proof coverage for a universal computation"
                            % attempt_id
                        )
                elif use.get("used_in_proof") is True:
                    result.errors.append(
                        "%s uses a finite-sample experiment as proof" % attempt_id
                    )
        if attempt.get("paired_turn_kind") in {
            "forced-proof",
            "standard-fallback",
        }:
            from .paired import POLICY_REVISION, TRACE_DIR, problem_key
            from .campaigns import load_campaign

            campaign = load_campaign(str(attempt.get("campaign_id")))
            if (
                attempt.get("paired_attempt_policy_revision")
                != POLICY_REVISION
            ):
                result.errors.append(
                    "%s has invalid paired-turn linkage" % attempt_id
                )
            if attempt.get("paired_problem_key") != problem_key(campaign):
                result.warnings.append(
                    "%s is stale paired context after new packet evidence"
                    % attempt_id
                )
            trace_id = attempt.get("observable_trace_id")
            trace_path = TRACE_DIR / ("%s.json" % trace_id)
            if not trace_path.is_file():
                result.errors.append(
                    "%s observable trace is missing" % attempt_id
                )
            elif _sha256(trace_path) != attempt.get(
                "observable_trace_sha256"
            ):
                result.errors.append(
                    "%s observable trace hash does not match" % attempt_id
                )
            if attempt.get("paired_turn_kind") == "forced-proof":
                if (
                    attempt.get("theorem_statement")
                    != campaign["paired_attempt_policy"]["exact_theorem"]
                    or attempt.get("result_type") not in {"proof", "disproof"}
                    or attempt.get("status") != "claimed_complete"
                    or attempt.get("gap_markers")
                ):
                    result.errors.append(
                        "%s violates the forced-proof completion contract"
                        % attempt_id
                    )
        approach = attempt.get(
            "approach_id",
            attempt.get("subproblem_id", attempt.get("approach", "")),
        )
        if not isinstance(approach, str) or not approach.strip():
            result.errors.append("%s has no approach description" % attempt_id)

    for review in reviews:
        if "_error" in review:
            result.errors.append("%s: %s" % (review["_path"], review["_error"]))
            continue
        review_id = review.get("id", "")
        if review_id in legacy_reviews or review_id in stale_campaign_reviews:
            continue
        attempt_id = review.get("attempt_id")
        if attempt_id not in attempts_by_id:
            result.errors.append(
                "%s reviews unknown attempt %r"
                % (review.get("id", review["_path"]), attempt_id)
            )
            continue
        attempt = attempts_by_id[attempt_id]
        expected_review_schema = 3 if attempt.get("campaign_id") else 2
        if migration and review.get("schema_version") != expected_review_schema:
            result.errors.append("%s has wrong review schema" % review_id)
        if migration:
            for field in (
                "review_task_id",
                "review_pass",
                "packet_id",
                "packet_sha256",
                "target",
                "checked_claims",
                "finding_candidates",
            ):
                if field not in review:
                    result.errors.append(
                        "%s lacks required field %s" % (review_id, field)
                    )
        if migration and review.get("context_revision") != CONTEXT_REVISION:
            result.errors.append("%s has stale context revision" % review_id)
        if review.get("verdict") not in REVIEW_VERDICTS:
            result.errors.append(
                "%s has invalid verdict %r" % (review_id, review.get("verdict"))
            )
        if not review.get("independent", False):
            result.errors.append("%s is not an independent review" % review_id)
        if not str(review.get("strongest_attack", "")).strip():
            result.errors.append("%s lacks strongest_attack" % review_id)
        if review.get("reviewer_engine") == attempt.get("engine"):
            result.errors.append("%s uses the prover engine" % review_id)
        if migration and review.get("packet_sha256") != attempt.get("packet_sha256"):
            result.errors.append("%s reviews a different packet hash" % review_id)
        if migration and review.get("target") != attempt.get("target"):
            result.errors.append("%s reviews a different target" % review_id)
        if migration and review.get("review_task_id") != (
            "TASK-V-%s-P%s" % (attempt_id, review.get("review_pass"))
        ):
            result.errors.append("%s has incorrect review-task linkage" % review_id)
        if attempt.get("campaign_id"):
            for field in (
                "campaign_id",
                "campaign_revision",
                "subproblem_id",
                "theorem_statement",
                "proof_dependency_checks",
            ):
                if field not in review:
                    result.errors.append(
                        "%s lacks campaign review field %s" % (review_id, field)
                    )
            if review.get("campaign_id") != attempt.get("campaign_id"):
                result.errors.append("%s reviews a different campaign" % review_id)
            if review.get("theorem_statement") != attempt.get(
                "theorem_statement"
            ):
                result.errors.append("%s reviews a different theorem" % review_id)
        if migration:
            candidates = review.get("finding_candidates")
            if not isinstance(candidates, list) or any(
                not isinstance(item, dict)
                or not str(item.get("statement", "")).strip()
                for item in candidates
            ):
                result.errors.append("%s findings are not structured" % review_id)
        if attempt.get("campaign_id"):
            from .agents import _validate_review_verdict_consistency

            try:
                _validate_review_verdict_consistency(review)
            except ValueError as exc:
                result.warnings.append(
                    "%s has internally inconsistent review semantics: %s"
                    % (review_id, exc)
                )
        reviews_by_attempt.setdefault(attempt_id, []).append(review)

    if migration:
        for attempt_id, attached in reviews_by_attempt.items():
            passes = [review.get("review_pass") for review in attached]
            if len(passes) != len(set(passes)):
                result.errors.append(
                    "%s has duplicate completed review passes" % attempt_id
                )
            confirmations = [
                review
                for review in attached
                if review.get("verdict") == "confirmed"
            ]
            confirmation_engines = {
                review.get("reviewer_engine") for review in confirmations
            }
            if len(confirmations) >= 2 and len(confirmation_engines) < 2:
                result.errors.append(
                    "%s has confirmation passes from the same engine" % attempt_id
                )

    for attempt_id, attempt in attempts_by_id.items():
        if attempt_id in legacy_attempts or attempt.get("status") != "verified":
            continue
        confirmations = [
            review
            for review in reviews_by_attempt.get(attempt_id, [])
            if review.get("verdict") == "confirmed"
        ]
        engines = {review.get("reviewer_engine") for review in confirmations}
        passes = {review.get("review_pass") for review in confirmations}
        passes_invalid = bool(migration) and passes != {1, 2}
        if len(confirmations) < 2 or len(engines) < 2 or passes_invalid:
            result.errors.append(
                "%s verified without two independent cross-engine confirmations"
                % attempt_id
            )

    current_attempts = [
        attempt
        for attempt in attempts_by_id.values()
        if attempt.get("context_revision") == CONTEXT_REVISION
    ]
    verified = [
        attempt for attempt in current_attempts if attempt.get("status") == "verified"
    ]
    if not verified:
        result.warnings.append(
            "structural integrity has no verified mathematics result"
        )
    return result


def proof_status_report(
    claims: Dict[str, Claim],
    portfolio: Dict[str, Any],
) -> str:
    integrity = audit_proofs(claims)
    counts = portfolio["portfolio"]
    lines = [
        "# Proof integrity and portfolio status",
        "",
        "## Integrity status",
        "",
        "Status: **%s**" % ("PASS" if integrity.ok else "FAIL"),
        "",
        "- Errors: %d" % len(integrity.errors),
        "- Warnings: %d" % len(integrity.warnings),
        "",
        "## Portfolio status",
        "",
        "- Stale work: %(stale)d" % counts,
        "- Active attempts: %(active)d" % counts,
        "- Reviewed incomplete/blocked cells: %(incomplete)d" % counts,
        "- Verified cells: %(verified)d" % counts,
        "- Untried cells: %(untried)d" % counts,
        "",
    ]
    if counts["verified"] == 0:
        lines.append(
            "**No mathematical result is verified; integrity PASS is structural only.**"
        )
        lines.append("")
    if integrity.errors:
        lines.extend(["## Integrity errors", ""])
        lines.extend("- " + item for item in integrity.errors)
        lines.append("")
    if integrity.warnings:
        lines.extend(["## Integrity warnings", ""])
        lines.extend("- " + item for item in integrity.warnings)
        lines.append("")
    return "\n".join(lines)
