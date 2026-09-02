"""Mechanical validation repair: classify exact-match failures and build feedback.

Harness-owned identity mismatches should not waste a paid mathematical turn.
This module classifies those errors, records free coercions, and builds a
compact second-call prompt that feeds the prior JSON + validation feedback
back to the same engine.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

# Substantive failures must never trigger a free-form "fix strings" retry.
_NON_MECHANICAL_PATTERNS = (
    re.compile(r"contradicts the task target", re.I),
    re.compile(r"forced-proof requires complete resolution", re.I),
    re.compile(r"completion_attestation", re.I),
    re.compile(r"forced-proof result_type", re.I),
    re.compile(r"forced-proof structured claims", re.I),
    re.compile(r"forced-proof theorem_statement must match", re.I),
    re.compile(r"confirmed review contains a failed or unresolved", re.I),
    re.compile(r"blocked route", re.I),
    re.compile(r"route policy", re.I),
    re.compile(r"new_inputs", re.I),
    re.compile(r"watchdog", re.I),
    re.compile(r"infrastructure", re.I),
    re.compile(r"agent failed with exit", re.I),
)

# Exact-string / shape mismatches the engine can usually fix from feedback.
_MECHANICAL_PATTERNS = (
    re.compile(r"does not match", re.I),
    re.compile(r"does not match task", re.I),
    re.compile(r"does not match output filename", re.I),
    re.compile(r"does not match selected engine", re.I),
    re.compile(r"lacks fields", re.I),
    re.compile(r"must use the exact schema enum", re.I),
    re.compile(r"must be structured claim objects", re.I),
    re.compile(r"must be a list", re.I),
    re.compile(r"must be nonempty", re.I),
    re.compile(r"has invalid verdict", re.I),
    re.compile(r"is not marked independent", re.I),
    re.compile(r"is not independent", re.I),
    re.compile(r"agent artifact lacks fields", re.I),
    re.compile(r"finding audit lacks fields", re.I),
    re.compile(r"finding audit .+ does not match task", re.I),
)


def validation_repair_settings(config_root: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return enabled flag and retry_limit (default on, limit 1)."""
    raw = (config_root or {}).get("validation_repair")
    raw = raw if isinstance(raw, dict) else {}
    enabled = raw.get("enabled", True) is not False
    try:
        retry_limit = int(raw.get("retry_limit", 1))
    except (TypeError, ValueError):
        retry_limit = 1
    retry_limit = max(0, min(2, retry_limit))
    return {"enabled": enabled, "retry_limit": retry_limit}


def is_mechanical_validation_error(message: str) -> bool:
    """True when the error is an exact-match / schema-shape issue safe to retry."""
    text = str(message or "").strip()
    if not text:
        return False
    for pattern in _NON_MECHANICAL_PATTERNS:
        if pattern.search(text):
            return False
    for pattern in _MECHANICAL_PATTERNS:
        if pattern.search(text):
            return True
    return False


def record_field_coercion(
    artifact: Dict[str, Any],
    field: str,
    previous: Any,
    expected: Any,
    *,
    rule: str = "HARNESS-IDENTITY-COERCE-0001",
) -> None:
    """Append an audit row for a harness-owned field stamp."""
    normalizations = artifact.get("ingest_normalizations")
    if normalizations is None:
        normalizations = []
    if not isinstance(normalizations, list):
        raise ValueError("ingest_normalizations must be a list")

    def _clip(value: Any) -> Any:
        if isinstance(value, str) and len(value) > 240:
            return value[:240] + "…"
        return value

    entry = {
        "rule": rule,
        "field": field,
        "previous": _clip(previous),
        "expected": _clip(expected),
    }
    if entry not in normalizations:
        normalizations.append(entry)
    artifact["ingest_normalizations"] = normalizations


def coerce_identity_field(
    artifact: Dict[str, Any],
    field: str,
    expected: Any,
) -> bool:
    """If field differs from expected, stamp expected and record. Return whether changed."""
    if expected is None:
        return False
    previous = artifact.get(field)
    if previous == expected:
        return False
    record_field_coercion(artifact, field, previous, expected)
    artifact[field] = expected
    return True


def expected_identity_values(
    phase: str,
    task: Dict[str, Any],
    output_stem: str,
    engine_id: Optional[str],
) -> Dict[str, Any]:
    """Harness-owned identity values the model must copy exactly."""
    values: Dict[str, Any] = {"id": output_stem}
    if engine_id:
        if phase == "mathematics":
            values["engine"] = engine_id
        elif phase == "review":
            values["reviewer_engine"] = engine_id
        elif phase in {"finding-audit", "novelty", "trace-mining"}:
            values["engine"] = engine_id
    if phase == "mathematics":
        for key in (
            "task_id",
            "target_claim_id",
            "packet_id",
            "packet_path",
            "packet_sha256",
            "campaign_id",
            "campaign_revision",
            "subproblem_id",
        ):
            if key == "task_id":
                values[key] = task.get("id")
            elif key == "packet_path":
                values[key] = task.get("input_packet")
            elif task.get(key) is not None:
                values[key] = task.get(key)
        values["target"] = task.get("target")
    elif phase == "review":
        values["review_task_id"] = task.get("id")
        values["review_pass"] = task.get("review_pass")
        values["attempt_id"] = task.get("target_attempt_id")
        for key in (
            "packet_id",
            "packet_sha256",
            "campaign_id",
            "campaign_revision",
            "subproblem_id",
            "theorem_statement",
        ):
            if task.get(key) is not None:
                values[key] = task.get(key)
        values["target"] = task.get("target")
    elif phase == "finding-audit":
        values["task_id"] = task.get("id")
        values["campaign_id"] = task.get("campaign_id")
        values["finding_id"] = task.get("finding_id")
    return values


def assemble_validation_repair_prompt(
    *,
    base_prompt: str,
    phase: str,
    task: Dict[str, Any],
    output_stem: str,
    engine_id: Optional[str],
    previous_artifact: Dict[str, Any],
    validation_errors: Sequence[str],
    max_json_chars: int = 24000,
) -> str:
    """Build a second-call prompt that feeds validation feedback + prior JSON."""
    identity = expected_identity_values(phase, task, output_stem, engine_id)
    identity_lines = []
    for key, value in identity.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, sort_keys=True, ensure_ascii=False)
        else:
            rendered = json.dumps(value, ensure_ascii=False)
        identity_lines.append("- %s: %s" % (key, rendered))

    error_lines = ["- %s" % err for err in validation_errors if str(err).strip()]
    if not error_lines:
        error_lines = ["- (unspecified mechanical validation failure)"]

    payload = json.dumps(previous_artifact, sort_keys=True, ensure_ascii=False, indent=2)
    if len(payload) > max_json_chars:
        # Prefer field-level diffs over a truncated blob when oversized.
        snippet_keys = sorted(set(identity) | {"summary", "status", "verdict", "result_type"})
        slim = {
            key: previous_artifact.get(key)
            for key in snippet_keys
            if key in previous_artifact
        }
        payload = (
            json.dumps(slim, sort_keys=True, ensure_ascii=False, indent=2)
            + "\n/* previous JSON truncated; fix identity fields and re-emit full artifact */"
        )

    repair_block = "\n".join(
        [
            "",
            "# VALIDATION REPAIR (harness feedback — mechanical fix only)",
            "",
            "Your previous JSON failed harness validation:",
            *error_lines,
            "",
            "Expected identity values (copy exactly):",
            *identity_lines,
            "",
            "Previous JSON:",
            payload,
            "",
            "Return exactly one corrected JSON object matching the template.",
            "Do not restart the mathematics or re-read the corpus unless a required",
            "field is empty. Prefer minimal edits that clear the listed errors.",
            "No Markdown fences, no prose before or after the JSON.",
            "",
        ]
    )
    return base_prompt.rstrip() + "\n" + repair_block


def summarize_repair(
    *,
    attempts: int,
    errors: List[str],
    repaired: bool,
) -> Dict[str, Any]:
    return {
        "attempts": attempts,
        "errors": list(errors),
        "repaired": repaired,
        "classification": "mechanical_validation_repair",
    }
