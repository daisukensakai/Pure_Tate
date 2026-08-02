import datetime
import shutil
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from .agents import (
    _engine_argv,
    _extract_grok_stream,
    _extract_json_object,
    _subprocess_env,
    load_engines,
)
from .process_runner import ProcessWatchdogError, run_captured_process
from .store import ROOT, atomic_write_json


HEALTH_DIR = ROOT / "research" / "engine-health"
LEVELS = {"basic": 1, "tools": 2, "artifact": 3}


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _latest_path(engine_id: str) -> Path:
    return HEALTH_DIR / ("latest-%s.json" % engine_id)


def load_engine_health(engine_id: str) -> Optional[Dict[str, Any]]:
    path = _latest_path(engine_id)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def engine_health_is_attested(
    engine_id: str,
    level: str = "artifact",
    max_age_hours: int = 168,
) -> bool:
    record = load_engine_health(engine_id)
    if record is None or record.get("status") != "pass":
        return False
    if LEVELS.get(str(record.get("level")), 0) < LEVELS[level]:
        return False
    config = load_engines().get(engine_id, {})
    if record.get("model") != config.get("model"):
        return False
    try:
        audited = datetime.datetime.fromisoformat(
            str(record["audited_at"]).replace("Z", "+00:00")
        )
    except (KeyError, TypeError, ValueError):
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - audited
    return age.total_seconds() <= max_age_hours * 3600


def engine_health_state(engine_id: str, phase: str) -> str:
    config = load_engines().get(engine_id, {})
    if phase not in set(config.get("requires_health_attestation", [])):
        return "not_required"
    record = load_engine_health(engine_id)
    if record is None:
        return "missing"
    return "pass" if engine_health_is_attested(engine_id) else "fail"


def eligible_engine_pool(
    engine_ids: list[str], phase: str, dry_run: bool = False
) -> list[str]:
    if dry_run:
        return list(engine_ids)
    return [
        engine_id
        for engine_id in engine_ids
        if engine_health_state(engine_id, phase) in {"pass", "not_required"}
    ]


def operational_engine_pool(
    engine_ids: list[str], phase: str, dry_run: bool = False
) -> list[str]:
    """Return phase-eligible engines whose configured executable is runnable.

    Dry runs model the configured pool without depending on the caller's local
    PATH; live dispatches must satisfy both the health and executable gates.
    """
    eligible = eligible_engine_pool(engine_ids, phase, dry_run=dry_run)
    if dry_run:
        return eligible
    from .agents import load_engines

    engines = load_engines()
    return [
        engine_id
        for engine_id in eligible
        if shutil.which(str(engines[engine_id].get("binary", engine_id)))
        is not None
    ]


def _probe_prompt(level: str) -> str:
    if level == "basic":
        return (
            'Return exactly this JSON object and no other text: '
            '{"probe":"basic","ok":true}'
        )
    if level == "tools":
        return (
            "Read ALPHA.txt and BETA.json in this workspace. Return exactly one "
            'JSON object with keys probe, alpha, and beta_sum. Set probe to "tools", '
            "alpha to the entire trimmed contents of ALPHA.txt, and beta_sum to "
            "the sum of the two integers in BETA.json. No Markdown."
        )
    return (
        "Read TASK.json, packet.md, and ATTEMPT.json. Act as an adversarial proof "
        "reviewer. Return exactly one JSON object with keys probe, task_id, "
        "attempt_id, packet_sha256, verdict, and checked_claims. Set probe to "
        '"artifact", copy the three identifiers exactly, set verdict to "reject", '
        "and set checked_claims to a one-item array explaining that the displayed "
        "argument does not prove its displayed theorem. No Markdown."
    )


def _write_probe_inputs(directory: Path, level: str) -> str:
    if level == "tools":
        (directory / "ALPHA.txt").write_text(
            "bounded-qwen-read\n", encoding="utf-8"
        )
        (directory / "BETA.json").write_text(
            '{"values":[17,25]}\n', encoding="utf-8"
        )
        return ""
    if level == "artifact":
        packet = "Synthetic packet. This is a health probe, not mathematics.\n"
        packet_hash = hashlib.sha256(packet.encode("utf-8")).hexdigest()
        (directory / "packet.md").write_text(packet, encoding="utf-8")
        (directory / "TASK.json").write_text(
            json.dumps(
                {
                    "id": "HEALTH-TASK-001",
                    "packet_sha256": packet_hash,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (directory / "ATTEMPT.json").write_text(
            json.dumps(
                {
                    "id": "HEALTH-ATTEMPT-001",
                    "theorem_statement": "Every integer is even.",
                    "argument_markdown": "The integer 2 is even.",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return packet_hash
    return ""


def _validate_probe(level: str, value: Dict[str, Any], packet_hash: str) -> None:
    if level == "basic":
        if value != {"probe": "basic", "ok": True}:
            raise ValueError("basic probe returned the wrong JSON")
    elif level == "tools":
        if value != {
            "probe": "tools",
            "alpha": "bounded-qwen-read",
            "beta_sum": 42,
        }:
            raise ValueError("tool-read probe returned the wrong JSON")
    else:
        expected = {
            "probe": "artifact",
            "task_id": "HEALTH-TASK-001",
            "attempt_id": "HEALTH-ATTEMPT-001",
            "packet_sha256": packet_hash,
            "verdict": "reject",
        }
        if any(value.get(key) != item for key, item in expected.items()):
            raise ValueError("artifact-turn probe returned the wrong identifiers")
        checked = value.get("checked_claims")
        if not isinstance(checked, list) or len(checked) != 1:
            raise ValueError("artifact-turn probe omitted checked_claims")


def audit_engine_health(
    engine_id: str,
    live: bool = False,
    level: str = "artifact",
    timeout: int = 180,
    inactivity_timeout: int = 60,
    model_override: Optional[str] = None,
) -> Dict[str, Any]:
    if level not in LEVELS:
        raise ValueError("unknown health level %s" % level)
    config = load_engines().get(engine_id)
    if config is None:
        raise ValueError("unknown engine %s" % engine_id)
    if not live:
        record = load_engine_health(engine_id)
        return record or {
            "schema_version": 1,
            "engine": engine_id,
            "status": "missing",
            "level": level,
            "detail": "no live health receipt exists",
        }
    binary = str(config.get("binary", engine_id))
    if shutil.which(binary) is None:
        raise RuntimeError("engine binary is unavailable: %s" % binary)

    checked_levels = [
        item
        for item, rank in LEVELS.items()
        if rank <= LEVELS[level]
    ]
    checks = []
    status = "pass"
    detail = "all requested probes passed"
    with tempfile.TemporaryDirectory(
        prefix="pure-tate-engine-health-"
    ) as name:
        workspace = Path(name)
        for check_level in checked_levels:
            packet_hash = _write_probe_inputs(workspace, check_level)
            prompt = _probe_prompt(check_level)
            command = _engine_argv(
                engine_id,
                prompt,
                workspace / "last-message.txt",
                context_files=(
                    ["ALPHA.txt", "BETA.json"]
                    if check_level == "tools"
                    else (
                        ["TASK.json", "packet.md", "ATTEMPT.json"]
                        if check_level == "artifact"
                        else []
                    )
                ),
            )
            if model_override:
                flag = "--model" if "--model" in command else "-m"
                command[command.index(flag) + 1] = model_override
            check: Dict[str, Any] = {
                "level": check_level,
                "command_sha256": hashlib.sha256(
                    "\0".join(command).encode("utf-8")
                ).hexdigest(),
            }
            try:
                process = run_captured_process(
                    command,
                    cwd=workspace,
                    env=_subprocess_env(config.get("family")),
                    timeout=timeout,
                    inactivity_timeout=inactivity_timeout,
                )
                raw = (
                    (workspace / "last-message.txt").read_text(encoding="utf-8")
                    if config.get("family") == "openai"
                    and (workspace / "last-message.txt").is_file()
                    else process.stdout
                )
                if process.returncode != 0:
                    raise RuntimeError(
                        "engine exited %d: %s"
                        % (process.returncode, process.stderr.strip()[:500])
                    )
                value = (
                    _extract_grok_stream(raw)
                    if config.get("family") == "grok"
                    else _extract_json_object(raw)
                )
                _validate_probe(check_level, value, packet_hash)
                check["status"] = "pass"
                check["stdout_sha256"] = hashlib.sha256(
                    raw.encode("utf-8")
                ).hexdigest()
            except (OSError, RuntimeError, ValueError, ProcessWatchdogError) as exc:
                check["status"] = "fail"
                check["detail"] = str(exc)
                if isinstance(exc, ProcessWatchdogError):
                    check["partial_stdout_sha256"] = hashlib.sha256(
                        exc.stdout.encode("utf-8")
                    ).hexdigest()
                    check["partial_stderr"] = exc.stderr[-1000:]
                status = "fail"
                detail = "%s probe failed: %s" % (check_level, exc)
                checks.append(check)
                break
            checks.append(check)

    record = {
        "schema_version": 1,
        "engine": engine_id,
        "family": config.get("family"),
        "model": model_override or config.get("model"),
        "configured_model": config.get("model"),
        "audited_at": _timestamp(),
        "live": True,
        "level": level,
        "status": status,
        "detail": detail,
        "checks": checks,
    }
    stamp = (
        datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y%m%dT%H%M%S%fZ")
    )
    atomic_write_json(
        HEALTH_DIR / ("HEALTH-%s-%s.json" % (engine_id, stamp)), record
    )
    atomic_write_json(_latest_path(engine_id), record)
    return record
