import datetime
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .store import ROOT, atomic_write_json


# Live-web *research* phases that require durable capability attestation.
WEB_PHASES = {"research", "micro-research", "finding-audit", "novelty"}
# Agent adapter phases that may enable web tools when the model chooses to use them.
# Experiment stays container-only and is excluded.
AGENT_WEB_PHASES = WEB_PHASES | {
    "mathematics",
    "review",
    "trace-mining",
    "forced-proof",
    "standard-fallback",
}
WEB_CAPABILITIES = {"web_search", "web_fetch"}
ATTESTATION_DIR = ROOT / "research" / "capability-audits"


def phase_allows_web(phase: Optional[str]) -> bool:
    """Whether the headless adapter should expose web tools for this phase."""
    if not phase:
        return False
    return phase in AGENT_WEB_PHASES


def declared_capabilities(
    engine: Dict[str, Any], phase: str
) -> List[str]:
    lookup_phase = "research" if phase == "micro-research" else phase
    value = engine.get("declared_capabilities", {}).get(lookup_phase, [])
    return sorted(item for item in value if isinstance(item, str))


def effective_capabilities_from_argv(
    family: str, argv: List[str], phase: str
) -> List[str]:
    capabilities = {"filesystem_read"}
    joined = " ".join(argv)
    if family == "claude":
        allowed_items = []
        if "--allowedTools" in argv:
            start = argv.index("--allowedTools") + 1
            for item in argv[start:]:
                if item.startswith("--"):
                    break
                allowed_items.extend(item.split(","))
        allowed = set(allowed_items)
        if "WebSearch" in allowed and "WebFetch" in allowed:
            capabilities.update(WEB_CAPABILITIES)
    elif family == "grok":
        tools = ""
        denied = ""
        if "--tools" in argv:
            tools = argv[argv.index("--tools") + 1]
        if "--disallowed-tools" in argv:
            denied = argv[argv.index("--disallowed-tools") + 1]
        enabled = set(tools.split(","))
        blocked = set(denied.split(","))
        if (
            "--disable-web-search" not in argv
            and "web_search" in enabled
            and "web_search" not in blocked
        ):
            capabilities.add("web_search")
        if "web_fetch" in enabled and "web_fetch" not in blocked:
            capabilities.add("web_fetch")
    elif family == "cursor":
        # Cursor Agent has no --tools ACL; mode ask is read-only. Web is
        # available on AGENT_WEB_PHASES via declared capabilities / default tools.
        if phase_allows_web(phase):
            capabilities.update(WEB_CAPABILITIES)
    elif family == "qwen":
        # Qwen3.7-Max uses the Responses API's native web_search and
        # web_extractor tools on web-enabled phases.
        if "--allow-web" in argv and phase_allows_web(phase):
            capabilities.update(WEB_CAPABILITIES)
    elif family == "openai":
        if "--search" in argv and phase_allows_web(phase):
            capabilities.update(WEB_CAPABILITIES)
    if phase == "experiment" and ("docker" in joined or "podman" in joined):
        capabilities.add("container")
    return sorted(capabilities)


def capability_attestation_path(engine_id: str, phase: str) -> Path:
    return ATTESTATION_DIR / ("%s-%s.json" % (engine_id, phase))


def attestation_receipt_path(digest: str) -> Path:
    return ATTESTATION_DIR / "receipts" / (digest + ".json")


def attestation_receipt_valid(digest: str) -> bool:
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    path = attestation_receipt_path(digest)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return value.get("status") == "pass" and value.get("live") is True


def load_capability_attestation(
    engine_id: str, phase: str
) -> Optional[Dict[str, Any]]:
    path = capability_attestation_path(engine_id, phase)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def capability_is_attested(
    engine_id: str, phase: str, required: Iterable[str] = WEB_CAPABILITIES
) -> bool:
    value = load_capability_attestation(engine_id, phase)
    if not value or value.get("status") != "pass" or value.get("live") is not True:
        return False
    return set(required).issubset(set(value.get("effective_capabilities", [])))


def audit_engine_capability(
    engine_id: str,
    phase: str,
    live: bool = False,
    timeout: int = 60,
) -> Dict[str, Any]:
    # Local import prevents a cycle: agents uses this module at dispatch time.
    from .agents import (
        _engine_argv,
        _extract_claude_stream,
        _extract_grok_stream,
        _extract_json_object,
        _extract_qwen_stream,
        load_engines,
    )

    engines = load_engines()
    if engine_id not in engines:
        raise ValueError("unknown engine %s" % engine_id)
    engine = engines[engine_id]
    declared = declared_capabilities(engine, phase)
    probe_token = hashlib.sha256(
        ("%s:%s:%s" % (engine_id, phase, datetime.date.today())).encode("utf-8")
    ).hexdigest()[:16]
    prompt = (
        "Read-only capability probe. You must first web-search for the Macaulay2 "
        "source repository and then web-fetch "
        "https://api.github.com/repos/Macaulay2/M2/commits/HEAD. Do not return "
        "an answer until both actions have completed. Return exactly "
        "JSON with probe_token, that exact url, the returned 40-character commit_sha, "
        "web_search=true, and web_fetch=true. probe_token=%s" % probe_token
    )
    with tempfile.TemporaryDirectory(prefix="pure-tate-capability-") as directory:
        last = Path(directory) / "last-message.txt"
        argv = _engine_argv(engine_id, prompt, last, phase=phase)
        effective = effective_capabilities_from_argv(
            str(engine.get("family", "")), argv, phase
        )
        declared_matches = set(effective) == set(declared)
        available = shutil.which(str(engine.get("binary", engine_id))) is not None
        live_pass = False
        live_detail = "not requested"
        if live:
            if not available:
                live_detail = "engine binary unavailable"
            elif not WEB_CAPABILITIES.issubset(set(effective)):
                live_detail = "constructed command does not permit web search and fetch"
            else:
                process = subprocess.run(
                    argv,
                    cwd=directory,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
                raw = (
                    last.read_text(encoding="utf-8")
                    if last.is_file()
                    else process.stdout or ""
                )
                if process.returncode:
                    live_detail = (process.stderr or raw).strip()[:1000]
                else:
                    try:
                        family = engine.get("family")
                        if family == "grok":
                            result = _extract_grok_stream(raw)
                        elif family in {"claude", "cursor"}:
                            result = _extract_claude_stream(raw)
                        elif family == "qwen":
                            result = _extract_qwen_stream(raw)
                        else:
                            result = _extract_json_object(raw)
                    except ValueError as exc:
                        live_detail = str(exc)
                    else:
                        expected_commit = ""
                        try:
                            request = urllib.request.Request(
                                "https://api.github.com/repos/Macaulay2/M2/commits/HEAD",
                                headers={
                                    "User-Agent": "pure-tate-capability-audit/1"
                                },
                            )
                            with urllib.request.urlopen(
                                request, timeout=timeout
                            ) as response:
                                expected_commit = json.loads(
                                    response.read().decode("utf-8")
                                ).get("sha", "")
                        except Exception as exc:
                            live_detail = (
                                "harness could not independently fetch probe: %s"
                                % exc
                            )
                        live_pass = (
                            bool(expected_commit)
                            and
                            result.get("probe_token") == probe_token
                            and result.get("url")
                            == "https://api.github.com/repos/Macaulay2/M2/commits/HEAD"
                            and result.get("commit_sha") == expected_commit
                            and result.get("web_search") is True
                            and result.get("web_fetch") is True
                        )
                        live_detail = "probe returned required receipt" if live_pass else "invalid probe receipt"
    status = (
        "pass"
        if declared_matches
        and (not live or live_pass)
        and (phase not in WEB_PHASES or WEB_CAPABILITIES.issubset(set(effective)))
        else "fail"
    )
    record = {
        "schema_version": 1,
        "engine": engine_id,
        "phase": phase,
        "audited_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "live": live,
        "available": available,
        "declared_capabilities": declared,
        "effective_capabilities": effective,
        "declared_matches_effective": declared_matches,
        "status": status,
        "detail": live_detail,
        "command_sha256": hashlib.sha256(
            "\0".join(argv).encode("utf-8")
        ).hexdigest(),
    }
    if live:
        latest = capability_attestation_path(engine_id, phase)
        atomic_write_json(latest, record)
        digest = hashlib.sha256(latest.read_bytes()).hexdigest()
        receipt = attestation_receipt_path(digest)
        if not receipt.exists():
            atomic_write_json(receipt, record)
    return record


def audit_capabilities(
    engine_ids: Iterable[str],
    phases: Iterable[str],
    live: bool = False,
    timeout: int = 60,
) -> List[Dict[str, Any]]:
    return [
        audit_engine_capability(engine_id, phase, live=live, timeout=timeout)
        for engine_id in engine_ids
        for phase in phases
    ]
