"""Lean verification campaign harness for the exact (6,6) proof.

Lean checks syntax and deduction.  It cannot decide whether an opaque axiom is a
faithful translation of the mathematics, so this module deliberately separates
mechanical elaboration from two hash-bound semantic reviews.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import CheckResult
from .store import ROOT, atomic_write_json, load_json


FORMAL = ROOT / "formal"
CAMPAIGNS = FORMAL / "campaigns"
ATTEMPTS = FORMAL / "attempts"
REVIEWS = FORMAL / "reviews"
DEFAULT_LEAN_CAMPAIGN = "LC66-001"

FORBIDDEN_TOKENS = (
    "admit",
    "extern",
    "implemented_by",
    "import",
    "native_decide",
    "opaque",
    "sorry",
    "unsafe",
)
OUTPUT_CONTROL_TOKENS = (
    "builtin_command_elab",
    "builtin_command_parser",
    "command_elab",
    "elab",
    "macro",
    "macro_rules",
    "run_tac",
    "syntax",
    "syntax_rules",
)
CORE_AXIOM_WHITELIST = {"Classical.choice", "propext", "Quot.sound"}
AXIOM_RE = re.compile(r"^\s*axiom\s+([^\s:(]+)", re.MULTILINE)
CONSTANT_RE = re.compile(r"^\s*constant\s+([^\s:(]+)", re.MULTILINE)
MAP_RE = re.compile(
    r"^-- LEAN-AXIOM\s+(\S+)\s+=>\s+(\S+)(?:\s+--\s+(.+))?$",
    re.MULTILINE,
)
HEADER_RE = re.compile(r"^-- (LEAN-[A-Z-]+)\s+(.+)$", re.MULTILINE)
ID_RE = re.compile(r"LATT-\d{4}")
LEAN_TYPE_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_.]*(?:\s+[A-Za-z_][A-Za-z0-9_.]*)*"
)
TARGET_CHECK_RE = re.compile(r"[a-z][a-z0-9_]*")
DEFAULT_REVIEW_TARGET_CHECKS = (
    "stack_not_coarse",
    "rational_coefficients",
    "genus_6",
    "markings_6",
    "bm_degree_16",
    "bm_weight_minus_16",
    "bm_tate_index_8",
    "ordinary_degree_26",
    "ordinary_weight_26",
    "ordinary_tate_index_minus_13",
    "dimension_and_twist_21",
    "zero_rank_allowed",
    "whole_group_not_proxy",
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def campaign_path(campaign_id: str = DEFAULT_LEAN_CAMPAIGN) -> Path:
    return CAMPAIGNS / (campaign_id + ".json")


def load_campaign(campaign_id: str = DEFAULT_LEAN_CAMPAIGN) -> Dict[str, Any]:
    campaign = load_json(campaign_path(campaign_id))
    if campaign.get("id") != campaign_id:
        raise ValueError("campaign id does not match its filename")
    return campaign


def _elan_binary() -> Optional[str]:
    candidate = Path.home() / ".elan" / "bin" / "elan"
    return str(candidate) if candidate.is_file() else None


def _toolchain_installed(pin: str) -> bool:
    elan = _elan_binary()
    if not elan or not Path(elan).exists():
        return False
    try:
        result = subprocess.run(
            [elan, "toolchain", "list"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and pin in result.stdout


def _attempt_dir(attempt_id: str) -> Path:
    if not ID_RE.fullmatch(attempt_id):
        raise ValueError("invalid Lean attempt id %r" % attempt_id)
    matches = [path for path in ATTEMPTS.glob(attempt_id + "-*") if path.is_dir()]
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one formal attempt directory for %s; found %d"
            % (attempt_id, len(matches))
        )
    return matches[0]


def _headers(text: str) -> Dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in HEADER_RE.finditer(text)}


def _code_without_comments(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def _parse_used_axioms(output: str, theorem: str) -> Tuple[Optional[List[str]], str]:
    dependency_matches = list(re.finditer(
        r"'%s' depends on axioms:\s*\[(.*?)\]" % re.escape(theorem),
        output,
        re.DOTALL,
    ))
    no_axiom_matches = list(re.finditer(
        r"'%s' does not depend on any axioms" % re.escape(theorem), output
    ))
    last_dependency = dependency_matches[-1] if dependency_matches else None
    last_no_axiom = no_axiom_matches[-1] if no_axiom_matches else None
    if last_dependency and (
        last_no_axiom is None or last_dependency.start() > last_no_axiom.start()
    ):
        return sorted(
            item.strip() for item in last_dependency.group(1).split(",") if item.strip()
        ), ""
    if last_no_axiom:
        return [], ""
    return None, "missing #print axioms output for %s" % theorem


def _required_strings(
    result: CheckResult, value: Dict[str, Any], fields: Iterable[str], label: str
) -> None:
    for field in fields:
        if not isinstance(value.get(field), str) or not value[field].strip():
            result.errors.append("%s missing nonempty %s" % (label, field))


def _review_target_checks(campaign: Dict[str, Any]) -> Tuple[str, ...]:
    configured = campaign.get("review_target_checks")
    if configured is None:
        return DEFAULT_REVIEW_TARGET_CHECKS
    return tuple(configured) if isinstance(configured, list) else ()


def _dependency_hashes(campaign: Dict[str, Any]) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for item in campaign.get("dependency_artifacts", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            hashes[item["id"]] = str(item.get("sha256", ""))
    for item in campaign.get("verified_lean_dependencies", []):
        if not isinstance(item, dict):
            continue
        prefix = "lean:%s:%s" % (
            item.get("campaign_id", ""), item.get("attempt_id", "")
        )
        hashes[prefix + ":campaign"] = str(item.get("campaign_sha256", ""))
        hashes[prefix + ":report"] = str(item.get("report_sha256", ""))
    return dict(sorted(hashes.items()))


def _prover_engines(value: Dict[str, Any]) -> Tuple[str, ...]:
    """Return every contributing engine that is ineligible to review independently."""
    configured = value.get("prover_engines")
    if isinstance(configured, list):
        return tuple(
            engine for engine in configured if isinstance(engine, str) and engine.strip()
        )
    primary = value.get("prover_engine")
    return (primary,) if isinstance(primary, str) and primary.strip() else ()


def validate_campaign_contract(campaign: Dict[str, Any]) -> CheckResult:
    result = CheckResult()
    _required_strings(
        result,
        campaign,
        (
            "id",
            "source_attempt_id",
            "source_attempt_path",
            "source_attempt_sha256",
            "claim_contract_id",
            "exact_theorem",
            "lean_target_contract",
            "target_signature",
            "trusted_prelude_path",
            "trusted_prelude_sha256",
            "required_theorem_type",
            "toolchain",
        ),
        "campaign",
    )
    if campaign.get("minimum_independent_reviews") != 2:
        result.errors.append("campaign must require exactly two or more reviews (minimum 2)")
    required_type = campaign.get("required_theorem_type")
    if isinstance(required_type, str) and not LEAN_TYPE_RE.fullmatch(required_type):
        result.errors.append("campaign required_theorem_type is not a safe simple Lean type")
    target_checks = campaign.get("review_target_checks")
    if target_checks is not None and (
        not isinstance(target_checks, list)
        or not target_checks
        or len(target_checks) != len(set(target_checks))
        or any(
            not isinstance(item, str) or not TARGET_CHECK_RE.fullmatch(item)
            for item in target_checks
        )
    ):
        result.errors.append(
            "campaign review_target_checks must be unique snake_case names"
        )
    if campaign.get("trusted_prelude_in_model") not in {None, False, True}:
        result.errors.append("campaign trusted_prelude_in_model must be boolean")
    pin_path = FORMAL / "lean-toolchain"
    if not pin_path.is_file() or pin_path.read_text(encoding="utf-8").strip() != campaign.get("toolchain"):
        result.errors.append("formal/lean-toolchain does not match the campaign pin")
    trusted_prelude = ROOT / str(campaign.get("trusted_prelude_path", ""))
    if not trusted_prelude.is_file():
        result.errors.append("trusted Lean target prelude is missing")
    elif sha256_path(trusted_prelude) != campaign.get("trusted_prelude_sha256"):
        result.errors.append("trusted Lean target prelude hash drift")
    source = ROOT / str(campaign.get("source_attempt_path", ""))
    if not source.is_file():
        result.errors.append("source attempt is missing")
    elif sha256_path(source) != campaign.get("source_attempt_sha256"):
        result.errors.append("source attempt hash drift")
    source_attempt: Dict[str, Any] = {}
    if source.is_file():
        try:
            source_attempt = load_json(source)
        except Exception as exc:
            result.errors.append("source attempt is invalid: %s" % exc)
    if source_attempt and source_attempt.get("id") != campaign.get("source_attempt_id"):
        result.errors.append("source attempt id mismatch")
    if source_attempt and source_attempt.get("theorem_statement") != campaign.get("exact_theorem"):
        result.errors.append("campaign exact_theorem is not verbatim from source attempt")
    shared_signature_path = campaign.get("shared_signature_path")
    if shared_signature_path is not None:
        if not isinstance(shared_signature_path, str) or not shared_signature_path:
            result.errors.append("campaign shared_signature_path must be nonempty")
        elif not isinstance(campaign.get("shared_signature_sha256"), str):
            result.errors.append("campaign shared_signature_sha256 is missing")
        else:
            shared_signature = ROOT / shared_signature_path
            if not shared_signature.is_file():
                result.errors.append("shared Lean signature is missing")
            elif sha256_path(shared_signature) != campaign.get("shared_signature_sha256"):
                result.errors.append("shared Lean signature hash drift")
    obligations = campaign.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        result.errors.append("campaign has no obligations")
    else:
        identifiers = [item.get("id") for item in obligations if isinstance(item, dict)]
        if len(identifiers) != len(set(identifiers)):
            result.errors.append("campaign obligation ids are not unique")
        for number, item in enumerate(obligations, 1):
            if not isinstance(item, dict):
                result.errors.append("obligation %d is not an object" % number)
                continue
            _required_strings(
                result, item, ("id", "source_claim_id", "statement"), "obligation %d" % number
            )
        if source_attempt:
            source_claim_ids = {
                item.get("id")
                for item in source_attempt.get("claims", [])
                if isinstance(item, dict)
            }
            obligation_claim_ids = {
                item.get("source_claim_id") for item in obligations if isinstance(item, dict)
            }
            if obligation_claim_ids != source_claim_ids:
                result.errors.append(
                    "campaign obligations do not cover the source attempt claims exactly"
                )
    optional_obligation_ids = campaign.get("optional_obligation_ids", [])
    if not isinstance(optional_obligation_ids, list) or not all(
        isinstance(item, str) for item in optional_obligation_ids
    ):
        result.errors.append("campaign optional_obligation_ids must be a string list")
    elif obligations:
        obligation_ids = {
            item.get("id") for item in obligations if isinstance(item, dict)
        }
        unknown_optional = sorted(set(optional_obligation_ids) - obligation_ids)
        if unknown_optional:
            result.errors.append(
                "unknown optional obligation ids: %s" % ", ".join(unknown_optional)
            )
    optional_axiom_names = campaign.get("optional_axiom_names", [])
    if not isinstance(optional_axiom_names, list) or not all(
        isinstance(item, str) and item for item in optional_axiom_names
    ):
        result.errors.append("campaign optional_axiom_names must be a string list")
    elif optional_axiom_names and not optional_obligation_ids:
        result.errors.append(
            "campaign optional_axiom_names requires optional_obligation_ids"
        )

    dependency_artifacts = campaign.get("dependency_artifacts", [])
    if not isinstance(dependency_artifacts, list):
        result.errors.append("campaign dependency_artifacts must be a list")
        dependency_artifacts = []
    dependency_ids: List[str] = []
    for number, item in enumerate(dependency_artifacts, 1):
        if not isinstance(item, dict):
            result.errors.append("dependency artifact %d is not an object" % number)
            continue
        _required_strings(
            result, item, ("id", "path", "sha256"),
            "dependency artifact %d" % number,
        )
        identifier = item.get("id")
        if isinstance(identifier, str):
            dependency_ids.append(identifier)
        path = ROOT / str(item.get("path", ""))
        if not path.is_file():
            result.errors.append("dependency artifact %d is missing" % number)
        elif sha256_path(path) != item.get("sha256"):
            result.errors.append("dependency artifact %d hash drift" % number)
    if len(dependency_ids) != len(set(dependency_ids)):
        result.errors.append("dependency artifact ids are not unique")

    verified_dependencies = campaign.get("verified_lean_dependencies", [])
    if not isinstance(verified_dependencies, list):
        result.errors.append("campaign verified_lean_dependencies must be a list")
        verified_dependencies = []
    for number, item in enumerate(verified_dependencies, 1):
        label = "verified Lean dependency %d" % number
        if not isinstance(item, dict):
            result.errors.append(label + " is not an object")
            continue
        _required_strings(
            result,
            item,
            (
                "campaign_id",
                "attempt_id",
                "theorem",
                "required_theorem_type",
                "campaign_sha256",
                "report_path",
                "report_sha256",
            ),
            label,
        )
        dependency_campaign_id = item.get("campaign_id")
        if dependency_campaign_id == campaign.get("id"):
            result.errors.append(label + " may not point to its own campaign")
            continue
        dependency_campaign_file = campaign_path(str(dependency_campaign_id))
        if not dependency_campaign_file.is_file():
            result.errors.append(label + " campaign is missing")
            continue
        if sha256_path(dependency_campaign_file) != item.get("campaign_sha256"):
            result.errors.append(label + " campaign hash drift")
        try:
            dependency_campaign = load_campaign(str(dependency_campaign_id))
        except Exception as exc:
            result.errors.append(label + " campaign is invalid: %s" % exc)
            continue
        if dependency_campaign.get("required_theorem_type") != item.get(
            "required_theorem_type"
        ):
            result.errors.append(label + " theorem type mismatch")
        report_path = ROOT / str(item.get("report_path", ""))
        if not report_path.is_file():
            result.errors.append(label + " report is missing")
            continue
        if sha256_path(report_path) != item.get("report_sha256"):
            result.errors.append(label + " report hash drift")
        try:
            dependency_report = load_json(report_path)
        except Exception as exc:
            result.errors.append(label + " report is invalid: %s" % exc)
            continue
        if dependency_report.get("attempt_id") != item.get("attempt_id"):
            result.errors.append(label + " attempt mismatch")
        if dependency_report.get("theorem") != item.get("theorem"):
            result.errors.append(label + " theorem mismatch")
        try:
            dependency_status = campaign_status(str(dependency_campaign_id))
        except Exception as exc:
            result.errors.append(label + " status failed: %s" % exc)
        else:
            if item.get("attempt_id") not in dependency_status.get(
                "verified_attempts", []
            ):
                result.errors.append(label + " attempt is not independently verified")
    return result


def check_attempt(
    attempt_id: str,
    campaign_id: str = DEFAULT_LEAN_CAMPAIGN,
    write: bool = False,
) -> Tuple[CheckResult, Dict[str, Any]]:
    """Run static checks and pinned Lean, returning a reproducible report."""
    result = CheckResult()
    campaign = load_campaign(campaign_id)
    result.extend(validate_campaign_contract(campaign))
    directory = _attempt_dir(attempt_id)
    claim_path = directory / "Claim.lean"
    model_path = directory / "Model.lean"
    manifest_path = directory / "manifest.json"
    for required in (claim_path, model_path, manifest_path):
        if not required.is_file():
            result.errors.append("%s is missing" % required.name)
    if result.errors:
        report = _report(campaign, attempt_id, directory, result, {}, [], [], {})
        if write:
            atomic_write_json(directory / "report.json", report)
        return result, report

    manifest = load_json(manifest_path)
    text = claim_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")
    header_matches = list(HEADER_RE.finditer(text))
    headers = {match.group(1): match.group(2).strip() for match in header_matches}
    code = _code_without_comments(text)
    mapping_matches = list(MAP_RE.finditer(text))
    mappings = {match.group(1): match.group(2) for match in mapping_matches}
    declared = AXIOM_RE.findall(code)
    trusted_text = (ROOT / campaign["trusted_prelude_path"]).read_text(encoding="utf-8")
    trusted_matches = re.findall(
        r"^-- LEAN-TRUSTED-PRELUDE-BEGIN\s*$\n(.*?)^-- LEAN-TRUSTED-PRELUDE-END\s*$",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if len(trusted_matches) != 1 or trusted_matches[0] != trusted_text:
        result.errors.append("Claim.lean trusted target prelude is missing or changed")
    if campaign.get("trusted_prelude_in_model") is True:
        model_trusted_matches = re.findall(
            r"^-- LEAN-TRUSTED-PRELUDE-BEGIN\s*$\n(.*?)^-- LEAN-TRUSTED-PRELUDE-END\s*$",
            model_text,
            re.MULTILINE | re.DOTALL,
        )
        if len(model_trusted_matches) != 1 or model_trusted_matches[0] != trusted_text:
            result.errors.append(
                "Model.lean trusted target prelude is missing or changed"
            )
    shared_signature_path = campaign.get("shared_signature_path")
    if isinstance(shared_signature_path, str) and shared_signature_path:
        shared_text = (ROOT / shared_signature_path).read_text(encoding="utf-8")
        claim_shared = re.findall(
            r"^-- LEAN-SHARED-SIGNATURE-BEGIN\s*$\n(.*?)^-- LEAN-SHARED-SIGNATURE-END\s*$",
            text,
            re.MULTILINE | re.DOTALL,
        )
        model_shared = re.findall(
            r"^-- LEAN-SHARED-SIGNATURE-BEGIN\s*$\n(.*?)^-- LEAN-SHARED-SIGNATURE-END\s*$",
            model_text,
            re.MULTILINE | re.DOTALL,
        )
        if len(claim_shared) != 1 or claim_shared[0] != shared_text:
            result.errors.append("Claim.lean shared signature is missing or changed")
        if len(model_shared) != 1 or model_shared[0] != shared_text:
            result.errors.append("Model.lean shared signature is missing or changed")
    expected_headers = {
        "LEAN-CAMPAIGN": campaign_id,
        "LEAN-ATTEMPT": attempt_id,
        "LEAN-SOURCE-ATTEMPT": campaign["source_attempt_id"],
        "LEAN-CLAIM-CONTRACT": campaign["claim_contract_id"],
        "LEAN-TARGET-SIGNATURE": campaign["target_signature"],
    }
    for key, expected in expected_headers.items():
        if headers.get(key) != expected:
            result.errors.append("header %s must equal %s" % (key, expected))
    header_names = [match.group(1) for match in header_matches]
    duplicate_headers = sorted(
        {
            name
            for name in header_names
            if name != "LEAN-AXIOM" and header_names.count(name) > 1
        }
    )
    if duplicate_headers:
        result.errors.append("duplicate Lean headers: %s" % ", ".join(duplicate_headers))
    theorem = headers.get("LEAN-THEOREM", "")
    if not theorem:
        result.errors.append("header LEAN-THEOREM is missing")
    elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", theorem):
        result.errors.append("LEAN-THEOREM must be a simple root-namespace identifier")
    if not headers.get("LEAN-WEIGHT"):
        result.errors.append("header LEAN-WEIGHT is missing")
    optional_obligation_ids = set(campaign.get("optional_obligation_ids", []))
    optional_theorem = headers.get("LEAN-OPTIONAL-THEOREM", "")
    if optional_obligation_ids:
        if not optional_theorem:
            result.errors.append("header LEAN-OPTIONAL-THEOREM is required")
        elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", optional_theorem):
            result.errors.append(
                "LEAN-OPTIONAL-THEOREM must be a simple root-namespace identifier"
            )
    elif optional_theorem:
        result.errors.append(
            "LEAN-OPTIONAL-THEOREM requires campaign optional_obligation_ids"
        )
    code_lines = [line.strip() for line in code.splitlines() if line.strip()]
    if not code_lines or code_lines[0] != "set_option autoImplicit false":
        result.errors.append("set_option autoImplicit false must be the first code line")
    forbidden = sorted(
        token for token in FORBIDDEN_TOKENS if re.search(r"\b%s\b" % token, code)
    )
    if forbidden:
        result.errors.append("forbidden Lean tokens: %s" % ", ".join(forbidden))
    output_control = sorted(
        token
        for token in OUTPUT_CONTROL_TOKENS
        if re.search(r"\b%s\b" % re.escape(token), code)
    )
    if re.search(r"#eval\b", code) or output_control:
        result.errors.append(
            "Claim.lean may not extend commands or emit spoofable output: %s"
            % ", ".join(
                (["#eval"] if re.search(r"#eval\b", code) else []) + output_control
            )
        )
    model_code = _code_without_comments(model_text)
    model_forbidden = sorted(
        token
        for token in FORBIDDEN_TOKENS
        if re.search(r"\b%s\b" % token, model_code)
    )
    if model_forbidden:
        result.errors.append(
            "forbidden Model.lean tokens: %s" % ", ".join(model_forbidden)
        )
    model_output_control = sorted(
        token
        for token in OUTPUT_CONTROL_TOKENS
        if re.search(r"\b%s\b" % re.escape(token), model_code)
    )
    if re.search(r"#eval\b", model_code) or model_output_control:
        result.errors.append(
            "Model.lean may not extend commands or emit spoofable output: %s"
            % ", ".join(
                (["#eval"] if re.search(r"#eval\b", model_code) else [])
                + model_output_control
            )
        )
    if AXIOM_RE.search(model_code):
        result.errors.append("Model.lean may not declare axioms")
    if CONSTANT_RE.search(model_code):
        result.errors.append("Model.lean may not declare constants")
    if not re.search(r"^-- LEAN-MODEL-WITNESS\s+\S", model_text, re.MULTILINE):
        result.errors.append("Model.lean is missing LEAN-MODEL-WITNESS")
    if not re.search(r"^-- LEAN-NONCOLLAPSE\s+\S", model_text, re.MULTILINE):
        result.errors.append("Model.lean is missing LEAN-NONCOLLAPSE")
    models_match = re.search(r"^-- LEAN-MODELS\s+(.+)$", model_text, re.MULTILINE)
    modeled_axioms = models_match.group(1).split() if models_match else []
    if set(modeled_axioms) != set(declared) or len(modeled_axioms) != len(declared):
        result.errors.append("Model.lean must name every Claim axiom exactly once in LEAN-MODELS")
    model_theorem_match = re.search(
        r"^-- LEAN-MODEL-THEOREM\s+(\S+)\s*$", model_text, re.MULTILINE
    )
    model_theorem = model_theorem_match.group(1) if model_theorem_match else ""
    if not model_theorem:
        result.errors.append("Model.lean is missing LEAN-MODEL-THEOREM")
    model_code_lines = [line.strip() for line in model_code.splitlines() if line.strip()]
    if model_theorem and (
        not model_code_lines
        or model_code_lines[-1] != "#print axioms %s" % model_theorem
    ):
        result.errors.append("Model.lean must end with #print axioms %s" % model_theorem)
    if sum(1 for line in model_code_lines if line.startswith("#print")) != 1:
        result.errors.append("Model.lean must contain exactly one #print command")
    expected_print = "#print axioms %s" % theorem if theorem else ""
    if theorem and (not code_lines or code_lines[-1] != expected_print):
        result.errors.append("final #print axioms %s is required" % theorem)
    print_count = sum(1 for line in code_lines if line.startswith("#print"))
    expected_print_count = 2 if optional_obligation_ids else 1
    if print_count != expected_print_count:
        result.errors.append(
            "Claim.lean must contain exactly %d #print command%s"
            % (expected_print_count, "s" if expected_print_count != 1 else "")
        )
    if optional_theorem and (
        "#print axioms %s" % optional_theorem not in code_lines
    ):
        result.errors.append(
            "#print axioms %s is required" % optional_theorem
        )
    if CONSTANT_RE.search(code):
        result.errors.append("Claim.lean may not use untracked constant declarations")
    if len(declared) != len(set(declared)):
        result.errors.append("duplicate Lean axiom declarations")
    for name in declared:
        if name not in mappings:
            result.errors.append("axiom %s has no LEAN-AXIOM mapping" % name)
    for name in mappings:
        if name not in declared:
            result.errors.append("LEAN-AXIOM mapping %s has no declaration" % name)
    mapped_names = [match.group(1) for match in mapping_matches]
    duplicate_mappings = sorted(
        {name for name in mapped_names if mapped_names.count(name) > 1}
    )
    if duplicate_mappings:
        result.errors.append(
            "axioms have multiple LEAN-AXIOM mappings: %s"
            % ", ".join(duplicate_mappings)
        )

    obligation_ids = {
        item["id"] for item in campaign.get("obligations", []) if isinstance(item, dict)
    }
    mapped_obligations = set(mappings.values())
    unknown = sorted(mapped_obligations - obligation_ids - {"VOCAB"})
    missing = sorted(obligation_ids - mapped_obligations)
    if unknown:
        result.errors.append("unknown obligation mappings: %s" % ", ".join(unknown))
    if missing:
        result.errors.append("required obligations not mapped: %s" % ", ".join(missing))

    manifest_expected = {
        "id": attempt_id,
        "campaign_id": campaign_id,
        "source_attempt_id": campaign["source_attempt_id"],
        "source_attempt_sha256": campaign["source_attempt_sha256"],
        "claim_contract_id": campaign["claim_contract_id"],
        "prover_engine": manifest.get("prover_engine"),
    }
    for key, expected in manifest_expected.items():
        if manifest.get(key) != expected:
            result.errors.append("manifest %s mismatch" % key)
    _required_strings(result, manifest, ("prover_engine", "formalization_scope"), "manifest")
    configured_provers = manifest.get("prover_engines")
    if configured_provers is not None:
        if (
            not isinstance(configured_provers, list)
            or not configured_provers
            or not all(
                isinstance(engine, str) and engine.strip()
                for engine in configured_provers
            )
            or len(configured_provers) != len(set(configured_provers))
        ):
            result.errors.append(
                "manifest prover_engines must be a nonempty duplicate-free string list"
            )
        elif manifest.get("prover_engine") not in configured_provers:
            result.errors.append("manifest prover_engines must include prover_engine")
    if manifest.get("formalization_scope") != "local deduction over audited black boxes":
        result.errors.append("manifest formalization_scope weakens the campaign contract")

    pin = campaign["toolchain"]
    elan = _elan_binary()
    lean_version = "n/a"
    lean_exit = -1
    lean_output = ""
    model_output = ""
    model_exit = -1
    if not elan or not Path(elan).exists():
        result.errors.append("elan executable not found")
    elif not _toolchain_installed(pin):
        result.errors.append("pinned toolchain %s is not installed" % pin)
    else:
        checked_claim_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="checked_claim_",
                suffix=".lean",
                dir=str(directory),
                delete=False,
            ) as checked_claim:
                checked_claim.write(text)
                checked_claim.write(
                    "\n#check (_root_.%s : %s)\n"
                    % (theorem, campaign["required_theorem_type"])
                )
                checked_claim_path = Path(checked_claim.name)
            lean_run = subprocess.run(
                [elan, "run", pin, "lean", checked_claim_path.name],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=int(campaign.get("timeout_seconds", 120)),
            )
            lean_exit = lean_run.returncode
            lean_output = (lean_run.stdout + lean_run.stderr).strip()
            version_run = subprocess.run(
                [elan, "run", pin, "lean", "--version"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
            lean_version = version_run.stdout.strip()
            expected_version = pin.rsplit(":v", 1)[-1]
            if "version %s" % expected_version not in lean_version:
                result.errors.append("executed Lean version does not match the campaign pin")
            if lean_exit != 0 or ": error:" in lean_output:
                result.errors.append("Claim.lean failed elaboration")
            model_run = subprocess.run(
                [elan, "run", pin, "lean", "Model.lean"],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=int(campaign.get("timeout_seconds", 120)),
            )
            model_exit = model_run.returncode
            model_output = (model_run.stdout + model_run.stderr).strip()
            if model_exit != 0 or ": error:" in model_output:
                result.errors.append("Model.lean consistency witness failed")
            elif model_theorem:
                model_used, model_parse_error = _parse_used_axioms(
                    model_output, model_theorem
                )
                if model_parse_error:
                    result.errors.append(model_parse_error)
                else:
                    model_unknown = sorted(
                        name
                        for name in (model_used or [])
                        if name not in CORE_AXIOM_WHITELIST
                    )
                    if model_unknown:
                        result.errors.append(
                            "Model.lean witness depends on non-core axioms: %s"
                            % ", ".join(model_unknown)
                        )
        except subprocess.TimeoutExpired:
            result.errors.append("Lean timed out")
        finally:
            if checked_claim_path is not None:
                checked_claim_path.unlink(missing_ok=True)

    used: List[str] = []
    optional_used: List[str] = []
    if theorem and lean_exit == 0:
        parsed, parse_error = _parse_used_axioms(lean_output, theorem)
        if parse_error:
            result.errors.append(parse_error)
        else:
            used = parsed or []
        if optional_theorem:
            optional_parsed, optional_parse_error = _parse_used_axioms(
                lean_output, optional_theorem
            )
            if optional_parse_error:
                result.errors.append(optional_parse_error)
            else:
                optional_used = optional_parsed or []
    unmapped_used = sorted(
        name for name in used if name not in mappings and name not in CORE_AXIOM_WHITELIST
    )
    if unmapped_used:
        result.errors.append("closed-world axiom violation: %s" % ", ".join(unmapped_used))
    used_union = set(used) | set(optional_used)
    unused = sorted(name for name in declared if name not in used_union)
    if unused:
        result.errors.append("declared axioms are unused: %s" % ", ".join(unused))
    if optional_obligation_ids:
        optional_declared = {
            name for name in declared if mappings.get(name) in optional_obligation_ids
        }
        configured_optional = set(campaign.get("optional_axiom_names", []))
        unknown_configured = sorted(configured_optional - set(declared))
        if unknown_configured:
            result.errors.append(
                "configured optional axioms are not declared: %s"
                % ", ".join(unknown_configured)
            )
        optional_declared |= configured_optional
        leaked_optional = sorted(optional_declared & set(used))
        if leaked_optional:
            result.errors.append(
                "optional axioms leak into exported theorem: %s"
                % ", ".join(leaked_optional)
            )
        missing_optional = sorted(optional_declared - set(optional_used))
        if missing_optional:
            result.errors.append(
                "optional theorem does not use its declared axioms: %s"
                % ", ".join(missing_optional)
            )
        required_declared = set(declared) - optional_declared
        missing_required = sorted(required_declared - set(used))
        if missing_required:
            result.errors.append(
                "exported theorem does not use required axioms: %s"
                % ", ".join(missing_required)
            )

    runtime = {
        "lean_exit": lean_exit,
        "model_exit": model_exit,
        "lean_version": lean_version,
        "theorem": theorem,
        "optional_theorem": optional_theorem,
        "lean_output": lean_output,
        "model_output": model_output,
    }
    report = _report(
        campaign, attempt_id, directory, result, manifest, declared, used, runtime,
        mappings, optional_used
    )
    if write:
        atomic_write_json(directory / "report.json", report)
    return result, report


def _report(
    campaign: Dict[str, Any],
    attempt_id: str,
    directory: Path,
    result: CheckResult,
    manifest: Dict[str, Any],
    declared: List[str],
    used: List[str],
    runtime: Dict[str, Any],
    mappings: Optional[Dict[str, str]] = None,
    optional_used: Optional[List[str]] = None,
) -> Dict[str, Any]:
    def digest(name: str) -> Optional[str]:
        path = directory / name
        return sha256_path(path) if path.is_file() else None

    return {
        "schema_version": 1,
        "campaign_id": campaign.get("id"),
        "campaign_sha256": sha256_path(campaign_path(str(campaign.get("id")))),
        "attempt_id": attempt_id,
        "source_attempt_id": campaign.get("source_attempt_id"),
        "source_attempt_sha256": campaign.get("source_attempt_sha256"),
        "claim_contract_id": campaign.get("claim_contract_id"),
        "claim_sha256": digest("Claim.lean"),
        "model_sha256": digest("Model.lean"),
        "manifest_sha256": digest("manifest.json"),
        "prover_engine": manifest.get("prover_engine"),
        **(
            {"prover_engines": list(_prover_engines(manifest))}
            if "prover_engines" in manifest
            else {}
        ),
        "toolchain": campaign.get("toolchain"),
        "lean_version": runtime.get("lean_version", "n/a"),
        "theorem": runtime.get("theorem"),
        "optional_theorem": runtime.get("optional_theorem"),
        "lean_exit": runtime.get("lean_exit", -1),
        "model_exit": runtime.get("model_exit", -1),
        "lean_output": runtime.get("lean_output", ""),
        "model_output": runtime.get("model_output", ""),
        "declared_axioms": sorted(declared),
        "used_axioms": sorted(used),
        "optional_used_axioms": sorted(optional_used or []),
        "axiom_mappings": dict(sorted((mappings or {}).items())),
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "result": "PASS" if result.ok else "FAIL",
    }


def _load_reviews(attempt_id: str) -> List[Dict[str, Any]]:
    reviews: List[Dict[str, Any]] = []
    if not REVIEWS.exists():
        return reviews
    for path in sorted(REVIEWS.glob("LREV-*.json")):
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(review, dict) and review.get("attempt_id") == attempt_id:
            review["_path"] = str(path)
            reviews.append(review)
    return reviews


def validate_review(
    review: Dict[str, Any], campaign: Dict[str, Any], report_path: Path
) -> CheckResult:
    result = CheckResult()
    label = str(review.get("id", "review"))
    _required_strings(
        result,
        review,
        (
            "id",
            "attempt_id",
            "campaign_id",
            "reviewer_engine",
            "claim_sha256",
            "model_sha256",
            "manifest_sha256",
            "report_sha256",
            "campaign_sha256",
            "review_task_id",
            "review_run_path",
            "statement_faithfulness",
            "axiom_faithfulness",
            "model_faithfulness",
            "strongest_attack",
        ),
        label,
    )
    if not report_path.is_file():
        result.errors.append("%s report is missing" % label)
        return result
    report = load_json(report_path)
    expected = {
        "campaign_id": campaign["id"],
        "campaign_sha256": sha256_path(campaign_path(campaign["id"])),
        "claim_sha256": report.get("claim_sha256"),
        "model_sha256": report.get("model_sha256"),
        "manifest_sha256": report.get("manifest_sha256"),
        "report_sha256": sha256_path(report_path),
    }
    for key, value in expected.items():
        if review.get(key) != value:
            result.errors.append("%s %s mismatch" % (label, key))
    if review.get("verdict") not in {"confirmed", "incomplete", "refuted"}:
        result.errors.append("%s has invalid verdict" % label)
    if review.get("independent") is not True:
        result.errors.append("%s is not independent" % label)
    if (
        campaign.get("review_policy", {}).get("reviewers_must_differ_from_prover") is True
        and review.get("verdict") == "confirmed"
        and review.get("reviewer_engine") in set(_prover_engines(report))
    ):
        result.errors.append("%s reviewer is a contributing prover" % label)
    if review.get("review_pass") not in {1, 2}:
        result.errors.append("%s review_pass must be 1 or 2" % label)
    expected_task_id = "TASK-LV-%s-P%s" % (
        review.get("attempt_id", ""), review.get("review_pass", "")
    )
    if review.get("review_task_id") != expected_task_id:
        result.errors.append("%s review_task_id mismatch" % label)
    review_path_value = review.get("_path")
    review_path = (
        Path(review_path_value).resolve() if isinstance(review_path_value, str) else None
    )
    if review_path is not None and (
        review_path.stem != review.get("id")
        or not re.fullmatch(r"LREV-\d{4}", str(review.get("id", "")))
    ):
        result.errors.append("%s id does not match its review filename" % label)
    run_path_value = review.get("review_run_path")
    runs_root = (ROOT / "reports" / "runs").resolve()
    run_path = (ROOT / str(run_path_value or "")).resolve()
    try:
        run_path.relative_to(runs_root)
    except ValueError:
        result.errors.append("%s review_run_path is outside reports/runs" % label)
    if not run_path.is_file():
        result.errors.append("%s review run receipt is missing" % label)
    elif review_path is None or not review_path.is_file():
        result.errors.append("%s review artifact path is unavailable" % label)
    else:
        try:
            run = load_json(run_path)
        except Exception as exc:
            result.errors.append("%s review run receipt is invalid: %s" % (label, exc))
        else:
            try:
                review_output = str(review_path.relative_to(ROOT.resolve()))
            except ValueError:
                review_output = ""
            artifact_sha = sha256_path(review_path)
            events = run.get("events")
            if not isinstance(events, list):
                result.errors.append("%s review run events is not a list" % label)
                events = []
            matches = [
                event
                for event in events
                if isinstance(event, dict)
                and event.get("phase") == "lean-review"
                and event.get("state") == "completed"
                and event.get("review_id") == review.get("id")
                and event.get("target_attempt_id") == review.get("attempt_id")
                and event.get("review_pass") == review.get("review_pass")
                and event.get("engine") == review.get("reviewer_engine")
                and event.get("task_id") == review.get("review_task_id")
                and event.get("output") == review_output
                and event.get("artifact_sha256") == artifact_sha
            ]
            if run.get("status") != "completed" or len(matches) != 1:
                result.errors.append(
                    "%s has no unique completed matching lean-review run event" % label
                )
    checked = review.get("checked_obligations")
    required = {
        item["id"] for item in campaign.get("obligations", []) if isinstance(item, dict)
    }
    if (
        not isinstance(checked, list)
        or set(checked) != required
        or len(checked) != len(required)
    ):
        result.errors.append("%s does not check every obligation exactly once" % label)
    target_checks = review.get("target_checks")
    required_target_checks = set(_review_target_checks(campaign))
    if not isinstance(target_checks, dict) or set(target_checks) != required_target_checks:
        result.errors.append("%s target_checks has the wrong fields" % label)
    elif any(not isinstance(value, bool) for value in target_checks.values()):
        result.errors.append("%s target_checks values must be booleans" % label)
    elif review.get("verdict") == "confirmed" and any(
        value is not True for value in target_checks.values()
    ):
        result.errors.append("%s does not confirm every exact-target field" % label)
    expected_dependency_hashes = _dependency_hashes(campaign)
    if expected_dependency_hashes:
        if review.get("dependency_hashes") != expected_dependency_hashes:
            result.errors.append("%s dependency_hashes mismatch" % label)
    model_checks = review.get("model_checks")
    required_model_checks = {
        "models_every_claim_axiom",
        "witness_is_axiom_free",
        "noncollapse_is_material",
        "model_matches_claim_vocabulary",
    }
    if not isinstance(model_checks, dict) or set(model_checks) != required_model_checks:
        result.errors.append("%s model_checks has the wrong fields" % label)
    elif any(not isinstance(value, bool) for value in model_checks.values()):
        result.errors.append("%s model_checks values must be booleans" % label)
    elif review.get("verdict") == "confirmed" and any(
        value is not True for value in model_checks.values()
    ):
        result.errors.append("%s does not confirm every model-faithfulness field" % label)
    axiom_checks = review.get("axiom_checks")
    report_mappings = report.get("axiom_mappings") or {}
    seen_axioms: List[str] = []
    if not isinstance(axiom_checks, list):
        result.errors.append("%s axiom_checks is not a list" % label)
    else:
        for number, item in enumerate(axiom_checks, 1):
            if not isinstance(item, dict):
                result.errors.append("%s axiom check %d is not an object" % (label, number))
                continue
            name = item.get("axiom")
            seen_axioms.append(name)
            if item.get("obligation_id") != report_mappings.get(name):
                result.errors.append("%s axiom check %d mapping mismatch" % (label, number))
            if item.get("verdict") not in {"confirmed", "failed", "unresolved"}:
                result.errors.append("%s axiom %s has invalid verdict" % (label, name))
            elif review.get("verdict") == "confirmed" and item.get("verdict") != "confirmed":
                result.errors.append("%s does not confirm axiom %s" % (label, name))
            if not isinstance(item.get("note"), str) or not item["note"].strip():
                result.errors.append("%s axiom %s has no audit note" % (label, name))
        if len(seen_axioms) != len(report_mappings) or set(seen_axioms) != set(report_mappings):
            result.errors.append("%s does not audit every axiom exactly once" % label)
    return result


def campaign_status(campaign_id: str = DEFAULT_LEAN_CAMPAIGN) -> Dict[str, Any]:
    campaign = load_campaign(campaign_id)
    campaign_check = validate_campaign_contract(campaign)
    if REVIEWS.exists():
        for path in sorted(REVIEWS.glob("LREV-*.json")):
            try:
                load_json(path)
            except Exception as exc:
                campaign_check.errors.append(
                    "malformed Lean review %s: %s" % (path.name, exc)
                )
    attempts: List[Dict[str, Any]] = []
    for directory in sorted(ATTEMPTS.glob("LATT-*-*")) if ATTEMPTS.exists() else []:
        if not directory.is_dir():
            continue
        attempt_id = directory.name.split("-", 2)[0] + "-" + directory.name.split("-", 2)[1]
        if not ID_RE.fullmatch(attempt_id):
            continue
        manifest_path = directory / "manifest.json"
        try:
            manifest_campaign_id = load_json(manifest_path).get("campaign_id")
        except Exception:
            manifest_campaign_id = None
        if manifest_campaign_id != campaign_id:
            continue
        check, fresh_report = check_attempt(attempt_id, campaign_id, write=False)
        report_path = directory / "report.json"
        report_matches = report_path.is_file() and load_json(report_path) == fresh_report
        reviews = _load_reviews(attempt_id)
        valid_confirmations: List[Dict[str, Any]] = []
        review_errors: List[str] = []
        for review in reviews:
            review_check = validate_review(review, campaign, report_path)
            review_errors.extend(review_check.errors)
            if review_check.ok and review.get("verdict") == "confirmed":
                valid_confirmations.append(review)
        provers = set(_prover_engines(fresh_report))
        engines = {review.get("reviewer_engine") for review in valid_confirmations}
        independent_engines = {
            engine for engine in engines if engine and engine not in provers
        }
        confirmed_passes = {
            review.get("review_pass")
            for review in valid_confirmations
            if review.get("reviewer_engine") in independent_engines
        }
        has_refutation = any(
            review.get("verdict") == "refuted"
            and validate_review(review, campaign, report_path).ok
            for review in reviews
        )
        verified = (
            check.ok
            and report_matches
            and not review_errors
            and len(independent_engines) >= int(campaign["minimum_independent_reviews"])
            and confirmed_passes == {1, 2}
            and not has_refutation
        )
        attempts.append(
            {
                "id": attempt_id,
                "mechanical_check": "PASS" if check.ok else "FAIL",
                "committed_report_matches": report_matches,
                "confirmed_review_engines": sorted(independent_engines),
                "confirmed_review_passes": sorted(confirmed_passes),
                "has_refutation": has_refutation,
                "review_errors": review_errors,
                "status": "verified" if verified else "candidate",
            }
        )
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "campaign_contract": "PASS" if campaign_check.ok else "FAIL",
        "campaign_errors": campaign_check.errors,
        "source_attempt_id": campaign.get("source_attempt_id"),
        "source_attempt_sha256": campaign.get("source_attempt_sha256"),
        "claim_contract_id": campaign.get("claim_contract_id"),
        "attempts": attempts,
        "verified_attempts": [item["id"] for item in attempts if item["status"] == "verified"],
    }


def audit_campaign(campaign_id: str = DEFAULT_LEAN_CAMPAIGN) -> CheckResult:
    status = campaign_status(campaign_id)
    result = CheckResult(errors=list(status["campaign_errors"]))
    for attempt in status["attempts"]:
        if attempt["mechanical_check"] != "PASS":
            result.errors.append("%s mechanical check failed" % attempt["id"])
        if not attempt["committed_report_matches"]:
            result.errors.append("%s report is missing or stale" % attempt["id"])
        result.errors.extend(attempt["review_errors"])
    if not status["attempts"]:
        result.warnings.append("campaign has no Lean attempts yet")
    elif not status["verified_attempts"]:
        result.errors.append("campaign has attempts but no independently verified attempt")
    return result
