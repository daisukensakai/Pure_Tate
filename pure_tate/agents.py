import json
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .capabilities import WEB_CAPABILITIES, declared_capabilities
from .process_runner import ProcessWatchdogError, run_captured_process
from .store import DATA, ROOT, atomic_write_json, load_json
from .targets import CONTEXT_REVISION


ENGINE_CONFIG = DATA / "engines.json"
GEMINI_SYSTEM_MD = DATA / "gemini_system_minimal.md"


def _subprocess_env(
    family: Optional[str] = None,
    engine_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    env = dict(os.environ)
    if family == "gemini" and GEMINI_SYSTEM_MD.is_file():
        env["GEMINI_SYSTEM_MD"] = str(GEMINI_SYSTEM_MD.resolve())
    if family == "claude":
        # An inherited 32k setting must not silently defeat the pinned engine
        # configuration for long forced-proof artifacts.
        maximum = (engine_config or {}).get("max_output_tokens", 64000)
        if isinstance(maximum, int) and maximum > 0:
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(maximum)
    return env


def _extract_gemini_stream(text: str) -> Dict[str, Any]:
    """Reassemble Gemini CLI `-o stream-json` assistant deltas into one JSON object."""
    chunks: List[str] = []
    result_status: Optional[str] = None
    result_error: Optional[str] = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        etype = event.get("type")
        if etype == "message" and event.get("role") == "assistant":
            content = event.get("content")
            if isinstance(content, str) and content:
                chunks.append(content)
        elif etype == "result":
            result_status = str(event.get("status") or "")
            err = event.get("error") or event.get("message")
            if err is not None:
                result_error = str(err)
    if result_status and result_status != "success":
        raise ValueError(
            "gemini stream failed (%s): %s"
            % (result_status, result_error or "no detail")
        )
    if chunks:
        return _extract_json_object("".join(chunks))
    # Fallback for older `-o json` envelopes.
    return _extract_json_object(text)


def _extract_claude_stream(text: str) -> Dict[str, Any]:
    """Extract a final artifact from Claude CLI stream-json output."""
    results: List[str] = []
    assistant_text: List[str] = []
    partial_text: List[str] = []
    error_detail: Optional[str] = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "result":
            result = event.get("result")
            if isinstance(result, str) and result:
                results.append(result)
            subtype = str(event.get("subtype", "")).lower()
            if event.get("is_error") is True or subtype in {"error", "failed"}:
                error_detail = str(
                    event.get("error") or result or "Claude stream failed"
                )
        elif event_type == "assistant":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and isinstance(block.get("text"), str)
                    ):
                        assistant_text.append(block["text"])
        elif event_type == "stream_event":
            stream_event = event.get("event")
            delta = (
                stream_event.get("delta")
                if isinstance(stream_event, dict)
                else None
            )
            if (
                isinstance(delta, dict)
                and delta.get("type") == "text_delta"
                and isinstance(delta.get("text"), str)
            ):
                partial_text.append(delta["text"])
    for candidate in reversed(results):
        try:
            return _extract_json_object(candidate)
        except ValueError:
            continue
    for chunks in (assistant_text, partial_text):
        if chunks:
            try:
                return _extract_json_object("".join(chunks))
            except ValueError:
                continue
    if error_detail:
        raise ValueError(error_detail)
    # Backward compatibility for older single-result JSON envelopes.
    try:
        return _extract_json_object(text)
    except ValueError as exc:
        if str(exc) != "agent did not return a JSON object":
            raise
        raise ValueError(
            "Claude stream contained no complete JSON artifact"
        ) from exc


def _grok_stream_events(text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _extract_grok_stream(text: str) -> Dict[str, Any]:
    """Reassemble Grok streaming-json text deltas into one artifact."""
    events = _grok_stream_events(text)
    stream_types = {event.get("type") for event in events}
    if not stream_types.intersection({"text", "thought", "end", "error"}):
        # Backward compatibility for the former single-result JSON envelope.
        return _extract_json_object(text)
    errors = [
        str(event.get("message") or event.get("error") or "Grok stream failed")
        for event in events
        if event.get("type") == "error"
    ]
    chunks = [
        str(event.get("data"))
        for event in events
        if event.get("type") == "text"
        and isinstance(event.get("data"), str)
    ]
    if chunks:
        try:
            return _extract_json_object("".join(chunks))
        except ValueError as exc:
            if errors:
                raise ValueError(errors[-1]) from exc
            end = next(
                (
                    event
                    for event in reversed(events)
                    if event.get("type") == "end"
                ),
                {},
            )
            raise ValueError(
                "Grok stream ended with %s but no complete JSON artifact"
                % (end.get("stopReason") or "unknown status")
            ) from exc
    if errors:
        raise ValueError(errors[-1])
    raise ValueError("Grok stream contained no text artifact")


def _grok_observable_stream(text: str) -> str:
    """Quarantine Grok thought deltas from proof traces and trace miners."""
    retained = [
        json.dumps(event, sort_keys=True)
        for event in _grok_stream_events(text)
        if event.get("type") in {"text", "end", "error"}
    ]
    return "\n".join(retained) + ("\n" if retained else "")


def load_engines() -> Dict[str, Dict[str, Any]]:
    value = load_json(ENGINE_CONFIG)
    engines = value.get("engines")
    if not isinstance(engines, dict):
        raise ValueError("data/engines.json has no engines object")
    return engines


def _engine_has_web_access(config: Dict[str, Any]) -> bool:
    if config.get("web_access") is True:
        return True
    research_caps = set(declared_capabilities(config, "research"))
    return WEB_CAPABILITIES.issubset(research_caps)


def engine_inventory() -> List[Dict[str, Any]]:
    inventory = []
    for engine_id, config in sorted(load_engines().items()):
        binary = config.get("binary", engine_id)
        inventory.append(
            {
                "id": engine_id,
                "family": config.get("family", ""),
                "model": config.get("model", ""),
                "web_access": _engine_has_web_access(config),
                "binary": binary,
                "available": shutil.which(binary) is not None,
            }
        )
    return inventory


def _copy_if_present(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def build_isolated_context(task: Dict[str, Any], destination: Path) -> List[str]:
    phase = task.get("phase")
    copied = []

    def take(relative: str) -> None:
        if not relative:
            return
        source = ROOT / relative
        try:
            source.resolve().relative_to(ROOT.resolve())
        except ValueError as exc:
            raise ValueError("task input escapes the repository: %s" % relative) from exc
        target = destination / relative
        if source.exists():
            _copy_if_present(source, target)
            copied.append(relative)

    prompt = task.get("prompt")
    if isinstance(prompt, str):
        take(prompt)
    if phase == "research":
        for relative in (
            "data/target.json",
            "data/sources.jsonl",
            "corpus/manifest.json",
            "corpus/text",
            "corpus/chunks",
            "research/audits/AUDIT_TEMPLATE.json",
            "research/RED-0001.statement.json",
        ):
            take(relative)
    elif phase == "mathematics":
        take(str(task.get("input_packet", "")))
        take(
            "proof/CAMPAIGN_ATTEMPT_TEMPLATE.json"
            if task.get("campaign_id")
            else "proof/ATTEMPT_TEMPLATE.json"
        )
        for artifact_input in task.get("input_artifacts", []) or []:
            if isinstance(artifact_input, dict):
                take(str(artifact_input.get("path", "")))
    elif phase == "review":
        take(str(task.get("input_attempt", "")))
        take(str(task.get("input_packet", "")))
        take(
            "proof/CAMPAIGN_REVIEW_TEMPLATE.json"
            if task.get("campaign_id")
            else "proof/REVIEW_TEMPLATE.json"
        )
        for artifact_input in task.get("input_artifacts", []) or []:
            if isinstance(artifact_input, dict):
                take(str(artifact_input.get("path", "")))
    elif phase == "trace-mining":
        take(str(task.get("input_packet", "")))
        take(str(task.get("input_trace", "")))
        for artifact_input in task.get("input_artifacts", []) or []:
            if isinstance(artifact_input, dict):
                take(str(artifact_input.get("path", "")))
        take("research/paired-digests/DIGEST_TEMPLATE.json")
    elif phase == "finding-audit":
        take(str(task.get("input_packet", "")))
        take("proof/findings.jsonl")
        take("data/claims.jsonl")
        take("data/sources.jsonl")
        take("research/finding-audits/FINDING_AUDIT_TEMPLATE.json")
    elif phase == "novelty":
        take(str(task.get("input_attempt", "")))
        take("research/novelty-audits/NOVELTY_TEMPLATE.json")
    else:
        raise ValueError("unsupported task phase %r" % phase)
    atomic_write_json(
        destination / "TASK.json",
        _model_visible_task(task),
    )
    copied.append("TASK.json")
    return copied


def _model_visible_task(task: Dict[str, Any]) -> Dict[str, Any]:
    from .paired import model_visible_task

    return model_visible_task(task)


def assemble_prompt(
    task: Dict[str, Any],
    context_files: List[str],
    expected_artifact_id: Optional[str] = None,
    engine_id: Optional[str] = None,
) -> str:
    prompt_path = task.get("prompt")
    instructions = ""
    if isinstance(prompt_path, str) and (ROOT / prompt_path).is_file():
        instructions = (ROOT / prompt_path).read_text(encoding="utf-8")
    phase = task.get("phase")
    engine_field = "engine" if phase == "mathematics" else "reviewer_engine"
    parts = [
        instructions.strip(),
        "",
        "# Execution contract",
        "",
        "You are in an isolated, read-only task workspace. Read TASK.json and only "
        "the supplied files listed below. Do not infer the contents of files that "
        "are absent.",
        "",
        "\n".join("- " + item for item in context_files),
        "",
        "Return exactly one JSON object matching the supplied template. "
        "Do not use Markdown fences. The harness, not you, will decide whether "
        "the artifact passes its gate.",
    ]
    if expected_artifact_id:
        parts.append("The JSON object's id must be exactly: " + expected_artifact_id)
    if engine_id:
        parts.append(
            "The JSON object's %s field must be exactly: %s"
            % (engine_field, engine_id)
        )
        family = load_engines().get(engine_id, {}).get("family")
        if family == "grok":
            parts.append(
                "Your final answer must be exactly one JSON object with no prose "
                "before or after it. Prefer reading corpus/chunks over large text "
                "files when both are available. Use only read_file, grep, and "
                "list_dir. Never use run_terminal_command, write, web_fetch, "
                "web_search, or any shell. Put the completed JSON artifact in your "
                "final message only."
            )
        elif family == "gemini":
            parts.append(
                "Your final answer must be exactly one JSON object with no prose "
                "before or after it. Prefer reading corpus/chunks over large text "
                "files when both are available. Stay in read-only plan mode. "
                "Put the completed JSON artifact in your final message only."
            )
    if phase == "review" and task.get("campaign_id"):
        parts.append(
            "Campaign review: use schema_version 3 and "
            "proof/CAMPAIGN_REVIEW_TEMPLATE.json. Attack the exact theorem "
            "statement, fill campaign_id/campaign_revision/subproblem_id/"
            "theorem_statement from TASK.json, and put every proof dependency "
            "check in proof_dependency_checks as objects with dependency_id "
            "and verdict in {confirmed, failed, unresolved}. The top-level "
            "verdict judges the attempt's theorem_statement, not whether that "
            "lemma resolves the global campaign target. A proposed lemma may "
            "be confirmed without verifying the case. An incomplete/refuted "
            "verdict must identify a failed or unresolved structured check."
        )
    if task.get("paired_turn_kind") == "standard-fallback":
        parts.append(
            "The supplied mathematical working-context files are ordinary "
            "context. Candidate ideas in them are unproved and must be "
            "established independently before use."
        )
    parts.extend(["", "Phase: " + str(phase)])
    return "\n".join(parts)


def _engine_argv(
    engine_id: str,
    prompt: str,
    last_message_path: Optional[Path] = None,
    phase: Optional[str] = None,
) -> List[str]:
    from .capabilities import WEB_PHASES

    engines = load_engines()
    if engine_id not in engines:
        raise ValueError("unknown engine %s" % engine_id)
    config = engines[engine_id]
    binary = config.get("binary", engine_id)
    family = config.get("family")
    model = config.get("model")
    allow_web = phase in WEB_PHASES if phase else False
    if family == "openai":
        if last_message_path is None:
            raise ValueError("OpenAI engine requires a last-message path")
        command = [
            binary,
            "exec",
            "--skip-git-repo-check",
            "-m",
            model,
            "--sandbox",
            "read-only",
            "-c",
            'approval_policy="never"',
            "--json",
            "-o",
            str(last_message_path),
            prompt,
        ]
        return command
    if family == "claude":
        allowed = ["Read", "Grep", "Glob"]
        if allow_web:
            allowed.extend(["WebSearch", "WebFetch"])
        return [
            binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--permission-mode",
            "default",
            "--allowedTools",
            *allowed,
            "--disallowedTools",
            "Edit",
            "Write",
            "Bash",
            "--model",
            model,
        ]
    if family == "grok":
        # Grok tool ids are snake_case. Headless dontAsk/always-approve still
        # permission_cancels run_terminal_command, write, and web_fetch
        # (cancellation_category=permission_cancelled). Keep a strict local
        # read-only allowlist offline; enable web tools only for attested
        # live-web phases.
        tools = ["read_file", "grep", "list_dir"]
        denied = ["run_terminal_command", "write", "open_page"]
        command = [
            binary,
            "-p",
            prompt,
            "--output-format",
            "streaming-json",
            "--max-turns",
            "40",
            "--permission-mode",
            "dontAsk",
            "--always-approve",
        ]
        if allow_web:
            tools.extend(["web_search", "web_fetch"])
        else:
            denied.extend(["web_fetch", "web_search"])
        command.extend(
            [
                "--tools",
                ",".join(tools),
                "--disallowed-tools",
                ",".join(denied),
            ]
        )
        if not allow_web:
            command.append("--disable-web-search")
        command.extend(["-m", model])
        return command
    if family == "gemini":
        # Plan mode is read-only. stream-json gives heartbeat events for the
        # process watchdog and a reassembled final JSON artifact.
        return [
            binary,
            "-p",
            prompt,
            "-m",
            model,
            "-o",
            "stream-json",
            "--approval-mode",
            "plan",
            "--skip-trust",
        ]
    raise ValueError("unsupported engine family %r" % family)


def _envelope_error_detail(envelope: Dict[str, Any]) -> Optional[str]:
    if envelope.get("is_error") is True or envelope.get("api_error_status") is not None:
        detail = envelope.get("result") or envelope.get("api_error_status")
        return str(detail) if detail is not None else "agent reported an API error"
    stop = envelope.get("stopReason")
    if isinstance(stop, str) and stop.lower() in {"cancelled", "canceled", "error"}:
        # Grok sometimes cancels after writing a valid final JSON object into text.
        payload = envelope.get("text") or envelope.get("result") or ""
        if isinstance(payload, str) and _first_json_object(payload) is not None:
            return None
        detail = payload or stop
        return "agent stopped (%s): %s" % (stop, detail)
    return None


def _first_json_object(text: str) -> Optional[Dict[str, Any]]:
    decoder = json.JSONDecoder()
    candidates: List[Tuple[Dict[str, Any], int]] = []
    idx = 0
    while True:
        start = text.find("{", idx)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            idx = start + 1
            continue
        if isinstance(value, dict):
            candidates.append((value, end - start))
        idx = start + 1
    if not candidates:
        return None
    # Prefer the largest object so a nested dict (e.g. task target) is not
    # chosen when the outer artifact JSON failed to parse for a later reason.
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0][0]


_LATEX_COMMANDS_WITH_JSON_ESCAPE_PREFIX = {
    # These are especially dangerous because json.loads accepts their first
    # two characters as \b, \f, \n, \r, or \t and silently inserts a control
    # character instead of raising JSONDecodeError.
    "backslash",
    "bar",
    "begin",
    "beta",
    "bf",
    "binom",
    "boxed",
    "bullet",
    "cdot",
    "frac",
    "frak",
    "neq",
    "newcommand",
    "not",
    "nu",
    "nabla",
    "rho",
    "rightarrow",
    "rm",
    "sqrt",
    "text",
    "theta",
    "times",
    "to",
    "top",
}


def _repair_invalid_json_escapes(text: str) -> str:
    """Turn bare LaTeX backslashes into JSON-safe escapes inside strings.

    This runs before the first json.loads call. Waiting for JSONDecodeError is
    insufficient: commands such as ``\beta`` and ``\frac`` begin with valid
    JSON escapes and otherwise decode to control characters without an error.
    """
    out: List[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if not in_string:
            out.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue
        if ch == "\\":
            if i + 1 >= len(text):
                out.append("\\\\")
                i += 1
                continue
            nxt = text[i + 1]
            command_end = i + 1
            while command_end < len(text) and text[command_end].isalpha():
                command_end += 1
            command = text[i + 1 : command_end]
            if command in _LATEX_COMMANDS_WITH_JSON_ESCAPE_PREFIX:
                out.append("\\\\")
                i += 1
                continue
            if nxt in '"\\/bfnrt':
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            if (
                nxt == "u"
                and i + 5 < len(text)
                and all(
                    character in "0123456789abcdefABCDEF"
                    for character in text[i + 2 : i + 6]
                )
            ):
                out.append(text[i : i + 6])
                i += 6
                continue
            out.append("\\\\")
            i += 1
            continue
        if ch == '"':
            in_string = False
        out.append(ch)
        i += 1
    return "".join(out)


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1]).strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].lstrip()
    repaired = _repair_invalid_json_escapes(cleaned)
    try:
        value = json.loads(repaired)
    except json.JSONDecodeError:
        value = _first_json_object(repaired)
        if value is None:
            value = _first_json_object(cleaned)
        if value is None:
            raise ValueError("agent did not return a JSON object")
    if isinstance(value, dict):
        error = _envelope_error_detail(value)
        if error is not None:
            raise ValueError(error)
        # Claude wraps the model reply in "result".
        if isinstance(value.get("result"), str):
            return _extract_json_object(value["result"])
        # Grok headless wraps the model reply in "text".
        if isinstance(value.get("text"), str) and (
            "stopReason" in value or "sessionId" in value
        ):
            return _extract_json_object(value["text"])
        # Gemini CLI wraps the model reply in "response".
        response = value.get("response")
        if isinstance(response, str):
            return _extract_json_object(response)
        if isinstance(response, dict) and any(
            key in value for key in ("stats", "error", "session_id", "sessionId")
        ):
            return response
    if not isinstance(value, dict):
        raise ValueError("agent result is not a JSON object")
    return value


def _normalize_string_ids(raw: Any, field: str) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("%s must be a list" % field)
    normalized: List[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("%s entries must be nonempty strings" % field)
        identifier = item.strip()
        if identifier not in normalized:
            normalized.append(identifier)
    return normalized


def _normalize_source_references(artifact: Dict[str, Any]) -> None:
    """Separate claim dependencies from bibliographic source dependencies.

    Models commonly put SRC-* identifiers in source_claim_ids. Silently
    dropping them makes the proof audit pass by erasing provenance. Move them
    into source_ids instead, retaining a deterministic normalization record.
    """
    raw_claims = _normalize_string_ids(
        artifact.get("source_claim_ids"), "source_claim_ids"
    )
    source_ids = _normalize_string_ids(artifact.get("source_ids"), "source_ids")
    moved = [identifier for identifier in raw_claims if identifier.startswith("SRC-")]
    claim_ids = [
        identifier for identifier in raw_claims if not identifier.startswith("SRC-")
    ]
    for identifier in moved:
        if identifier not in source_ids:
            source_ids.append(identifier)
    artifact["source_claim_ids"] = claim_ids
    artifact["source_ids"] = source_ids
    if moved:
        normalizations = artifact.get("ingest_normalizations")
        if normalizations is None:
            normalizations = []
        if not isinstance(normalizations, list):
            raise ValueError("ingest_normalizations must be a list")
        entry = {
            "rule": "SOURCE-REFERENCE-SPLIT-0001",
            "moved_from": "source_claim_ids",
            "moved_to": "source_ids",
            "identifiers": moved,
        }
        if entry not in normalizations:
            normalizations.append(entry)
        artifact["ingest_normalizations"] = normalizations


def _normalize_inferred_pairs(raw: Any) -> List[List[int]]:
    if not isinstance(raw, list):
        raise ValueError("inferred_pairs must be a list")
    pairs: List[List[int]] = []
    for item in raw:
        if isinstance(item, list) and len(item) == 2 and all(type(v) is int for v in item):
            pairs.append([item[0], item[1]])
        elif (
            isinstance(item, dict)
            and type(item.get("g")) is int
            and type(item.get("n")) is int
        ):
            pairs.append([item["g"], item["n"]])
        else:
            raise ValueError("inferred_pairs entry must be [g, n] or {g, n}: %r" % item)
    return pairs


def _normalize_proof_dependency_checks(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("proof_dependency_checks must be a list")
    allowed = {"confirmed", "failed", "unresolved"}
    normalized: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("proof_dependency_checks entries must be objects")
        dependency_id = item.get("dependency_id")
        if not isinstance(dependency_id, str) or not dependency_id.strip():
            dependency_id = item.get("dependency")
        if not isinstance(dependency_id, str) or not dependency_id.strip():
            raise ValueError(
                "proof_dependency_checks entries need dependency_id"
            )
        verdict = item.get("verdict")
        if not isinstance(verdict, str) or not verdict.strip():
            status = item.get("status")
            if isinstance(status, str) and status.strip():
                lowered = status.strip().lower()
                if lowered in allowed:
                    verdict = lowered
                elif lowered.startswith("confirm"):
                    verdict = "confirmed"
                elif lowered.startswith("fail"):
                    verdict = "failed"
                else:
                    verdict = "unresolved"
        if verdict not in allowed:
            raise ValueError(
                "proof_dependency_checks verdict must be one of %s (got %r)"
                % (sorted(allowed), verdict)
            )
        entry = dict(item)
        entry["dependency_id"] = dependency_id.strip()
        entry["verdict"] = verdict
        normalized.append(entry)
    return normalized


def _normalize_finding_candidates(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("finding_candidates must be a list")
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(
                "finding_candidates[%d] must be an object" % index
            )
        entry = dict(item)
        key = entry.get("key")
        if not isinstance(key, str) or not key.strip():
            for alias in ("id", "finding_key", "slug"):
                alias_value = entry.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    key = alias_value
                    break
        statement = entry.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            for alias in ("finding", "claim", "text", "summary"):
                alias_value = entry.get(alias)
                if isinstance(alias_value, str) and alias_value.strip():
                    statement = alias_value
                    break
        if (
            (not isinstance(key, str) or not key.strip())
            and isinstance(statement, str)
            and statement.strip()
        ):
            slug = "".join(
                character.lower() if character.isalnum() else "-"
                for character in statement.strip()[:80]
            ).strip("-")
            while "--" in slug:
                slug = slug.replace("--", "-")
            key = slug or ("finding-candidate-%d" % (index + 1))
        if not isinstance(statement, str) or not statement.strip():
            # Drop empty placeholder rows rather than failing the whole review.
            continue
        if not isinstance(key, str) or not key.strip():
            raise ValueError(
                "finding_candidates[%d] needs a nonempty key" % index
            )
        entry["key"] = key.strip()
        entry["statement"] = statement.strip()
        normalized.append(entry)
    return normalized


def _validate_review_verdict_consistency(artifact: Dict[str, Any]) -> None:
    adverse = {
        "blocked",
        "failed",
        "incomplete",
        "rejected",
        "refuted",
        "unresolved",
    }
    claim_outcomes = {
        str(item.get("verdict") or item.get("result") or item.get("status"))
        .strip()
        .lower()
        for item in artifact.get("checked_claims", [])
        if isinstance(item, dict)
    }
    dependency_outcomes = {
        str(item.get("verdict", "")).strip().lower()
        for item in artifact.get("proof_dependency_checks", [])
        if isinstance(item, dict)
    }
    has_adverse_check = bool(
        (claim_outcomes | dependency_outcomes) & adverse
    )
    verdict = artifact.get("verdict")
    if verdict == "confirmed" and has_adverse_check:
        raise ValueError(
            "confirmed review contains a failed or unresolved structured check"
        )
    if verdict in {"incomplete", "refuted"} and not has_adverse_check:
        raise ValueError(
            "%s review must record a failed or unresolved structured check"
            % verdict
        )


def _validate_output_path(phase: str, output: Path) -> None:
    resolved = output.resolve()
    rules: Dict[str, Tuple[Path, str]] = {
        "research": (ROOT / "research" / "audits", "RAUD-"),
        "mathematics": (ROOT / "proof" / "attempts", "ATT-"),
        "review": (ROOT / "proof" / "reviews", "REV-"),
        "trace-mining": (ROOT / "research" / "paired-digests", "DIGEST-"),
        "finding-audit": (ROOT / "research" / "finding-audits", "FAUD-"),
        "novelty": (ROOT / "research" / "novelty-audits", "NOV-"),
    }
    if phase not in rules:
        raise ValueError("unsupported task phase %r" % phase)
    parent, prefix = rules[phase]
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise ValueError("output must stay under %s" % parent) from exc
    if not resolved.name.startswith(prefix) or resolved.suffix != ".json":
        raise ValueError("output filename must match %s*.json" % prefix)


def _validate_artifact(
    phase: str,
    task: Dict[str, Any],
    artifact: Dict[str, Any],
    output: Path,
    engine_id: Optional[str] = None,
) -> None:
    is_campaign = bool(task.get("campaign_id"))
    required = {
        "research": {
            "id",
            "target_claim_id",
            "verdict",
            "inferred_pairs",
            "source_ids",
            "locators_checked",
            "forward_citation_check_date",
            "reviewer_engine",
            "independent",
        },
        "mathematics": {
            "schema_version",
            "id",
            "task_id",
            "target_claim_id",
            "context_revision",
            "packet_id",
            "packet_path",
            "packet_sha256",
            "target",
            "summary",
            "argument_markdown",
            "claims",
            "status",
            "source_claim_ids",
            "gap_markers",
            "engine",
        },
        "review": {
            "schema_version",
            "id",
            "review_task_id",
            "review_pass",
            "attempt_id",
            "context_revision",
            "packet_id",
            "packet_sha256",
            "target",
            "verdict",
            "reviewer_engine",
            "independent",
            "checked_claims",
            "strongest_attack",
            "finding_candidates",
        },
    }[phase]
    if phase == "mathematics":
        if is_campaign:
            required = required | {
                "campaign_id",
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
            }
        else:
            required = required | {"approach_id"}
    if phase == "review" and is_campaign:
        required = required | {
            "campaign_id",
            "campaign_revision",
            "subproblem_id",
            "theorem_statement",
            "proof_dependency_checks",
        }
    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError("agent artifact lacks fields: %s" % ", ".join(missing))
    if artifact.get("id") != output.stem:
        raise ValueError(
            "artifact id %r does not match output filename %s"
            % (artifact.get("id"), output.name)
        )
    if phase == "research":
        artifact["inferred_pairs"] = _normalize_inferred_pairs(
            artifact.get("inferred_pairs")
        )
        if artifact.get("target_claim_id") != task.get("target"):
            raise ValueError("research artifact targets the wrong reduction")
    if phase == "review" and artifact.get("attempt_id") != task.get(
        "target_attempt_id"
    ):
        raise ValueError("review artifact targets the wrong attempt")
    if phase == "mathematics":
        exact = {
            "schema_version": 3 if is_campaign else 2,
            "task_id": task.get("id"),
            "target_claim_id": task.get("target_claim_id"),
            "context_revision": CONTEXT_REVISION,
            "packet_id": task.get("packet_id"),
            "packet_path": task.get("input_packet"),
            "packet_sha256": task.get("packet_sha256"),
            "target": task.get("target"),
        }
        if is_campaign:
            exact.update(
                {
                    "campaign_id": task.get("campaign_id"),
                    "campaign_revision": task.get("campaign_revision"),
                    "subproblem_id": task.get("subproblem_id"),
                }
            )
        else:
            exact["approach_id"] = task.get("approach_id")
        for field, expected in exact.items():
            if artifact.get(field) != expected:
                raise ValueError(
                    "mathematics artifact %s does not match task (expected %r)"
                    % (field, expected)
                )
        if is_campaign:
            if not isinstance(artifact.get("theorem_statement"), str) or not artifact[
                "theorem_statement"
            ].strip():
                raise ValueError(
                    "campaign mathematics theorem_statement must be nonempty"
                )
            if not isinstance(artifact.get("proof_dependencies"), list):
                raise ValueError("campaign mathematics proof_dependencies must be a list")
        if not isinstance(artifact.get("summary"), str) or not artifact[
            "summary"
        ].strip():
            raise ValueError("mathematics artifact summary must be nonempty")
        if artifact.get("status") not in {
            "draft",
            "proposed",
            "claimed_complete",
            "refuted",
            "verified",
        }:
            raise ValueError(
                "mathematics artifact status must use the exact schema enum (got %r)"
                % artifact.get("status")
            )
        if not isinstance(artifact.get("argument_markdown"), str) or not artifact[
            "argument_markdown"
        ].strip():
            raise ValueError("mathematics artifact argument_markdown must be nonempty")
        claims = artifact.get("claims")
        if not isinstance(claims, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("statement"), str)
            or not item["statement"].strip()
            for item in claims
        ):
            raise ValueError("mathematics claims must be structured claim objects")
        if not isinstance(artifact.get("gap_markers"), list):
            raise ValueError("mathematics gap_markers must be a list")
        _normalize_source_references(artifact)
        if is_campaign:
            from .campaigns import campaign_route_policy_errors, load_campaign

            campaign = load_campaign(str(task["campaign_id"]))
            route_errors = campaign_route_policy_errors(campaign, artifact)
            if route_errors:
                raise ValueError(route_errors[0])
        if task.get("paired_turn_kind") == "forced-proof":
            if artifact.get("result_type") not in {"proof", "disproof"}:
                raise ValueError(
                    "forced-proof result_type must be proof or disproof"
                )
            if artifact.get("status") != "claimed_complete":
                raise ValueError(
                    "forced-proof requires complete resolution (claimed_complete)"
                )
            if artifact.get("gap_markers"):
                raise ValueError("forced-proof forbids gap markers")
            exact_theorem = task.get("exact_theorem")
            if (
                isinstance(exact_theorem, str)
                and exact_theorem.strip()
                and artifact.get("theorem_statement") != exact_theorem
            ):
                raise ValueError(
                    "forced-proof theorem_statement must match the exact theorem"
                )
            claims = artifact.get("claims") or []
            if any(
                isinstance(item, dict)
                and item.get("status") not in {None, "proved"}
                for item in claims
            ):
                raise ValueError(
                    "forced-proof structured claims must all be proved"
                )
            attestation = artifact.get("completion_attestation")
            if not isinstance(attestation, dict):
                raise ValueError(
                    "forced-proof requires completion_attestation"
                )
            for field in (
                "resolves_exact_target",
                "no_undischarged_dependencies",
                "not_reduction_only",
                "no_problem_status_claim",
            ):
                if attestation.get(field) is not True:
                    raise ValueError(
                        "forced-proof completion_attestation.%s must be true"
                        % field
                    )
            if attestation.get("exact_problem_web_search_used") is not False:
                raise ValueError(
                    "forced-proof exact_problem_web_search_used must be false"
                )
    if phase == "review":
        exact = {
            "schema_version": 3 if is_campaign else 2,
            "review_task_id": task.get("id"),
            "review_pass": task.get("review_pass"),
            "context_revision": CONTEXT_REVISION,
            "packet_id": task.get("packet_id"),
            "packet_sha256": task.get("packet_sha256"),
            "target": task.get("target"),
        }
        if is_campaign:
            exact.update(
                {
                    "campaign_id": task.get("campaign_id"),
                    "campaign_revision": task.get("campaign_revision"),
                    "subproblem_id": task.get("subproblem_id"),
                }
            )
        for field, expected in exact.items():
            if artifact.get(field) != expected:
                raise ValueError(
                    "review artifact %s does not match task (expected %r)"
                    % (field, expected)
                )
        if is_campaign:
            if not isinstance(artifact.get("theorem_statement"), str) or not artifact[
                "theorem_statement"
            ].strip():
                raise ValueError("campaign review theorem_statement must be nonempty")
            if artifact.get("theorem_statement") != task.get("theorem_statement"):
                raise ValueError(
                    "campaign review theorem_statement does not match task"
                )
            artifact["proof_dependency_checks"] = _normalize_proof_dependency_checks(
                artifact.get("proof_dependency_checks")
            )
        if not isinstance(artifact.get("checked_claims"), list):
            raise ValueError("review checked_claims must be a list")
        artifact["finding_candidates"] = _normalize_finding_candidates(
            artifact.get("finding_candidates")
        )
        _validate_review_verdict_consistency(artifact)
        if artifact.get("reviewer_engine") == task.get("prover_engine"):
            raise ValueError("reviewer engine must differ from prover engine")
        if artifact.get("reviewer_engine") in task.get(
            "excluded_reviewer_engines", []
        ):
            raise ValueError("reviewer engine duplicates an excluded review engine")
    engine_field = "engine" if phase == "mathematics" else "reviewer_engine"
    if engine_id and artifact.get(engine_field) != engine_id:
        raise ValueError(
            "artifact %s %r does not match selected engine %s"
            % (engine_field, artifact.get(engine_field), engine_id)
        )
    if phase in {"research", "review"} and artifact.get("independent") is not True:
        raise ValueError("%s artifact is not marked independent" % phase)


def _validate_task_packet(task: Dict[str, Any]) -> None:
    if task.get("phase") not in {"mathematics", "review"}:
        return
    if task.get("context_revision") != CONTEXT_REVISION:
        raise ValueError("task context revision is stale")
    relative = task.get("input_packet")
    if not isinstance(relative, str) or not relative:
        raise ValueError("task packet is missing")
    path = ROOT / relative
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError("task packet escapes the repository") from exc
    if not path.is_file():
        raise ValueError("task packet is missing: %s" % relative)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != task.get("packet_sha256"):
        raise ValueError(
            "task packet hash mismatch: expected %s, got %s"
            % (task.get("packet_sha256"), actual)
        )
    target = task.get("target")
    if not isinstance(target, dict):
        raise ValueError("task target dictionary is missing")
    if task.get("campaign_id"):
        from .campaigns import campaign_packet_record

        canonical = campaign_packet_record(str(task["campaign_id"]))[
            "packet_sha256"
        ]
    else:
        from .packets import render_case_packet
        from .store import load_repository

        _config, _repository_target, _sources, claims, _edges = load_repository()
        canonical = hashlib.sha256(
            render_case_packet(target["g"], target["n"], claims).encode("utf-8")
        ).hexdigest()
    if canonical != task.get("packet_sha256"):
        raise ValueError(
            "task packet is stale relative to the current findings ledger"
        )


def _failure_detail(returncode: int, stderr: str, raw: str) -> str:
    detail = (stderr or "").strip()
    if not detail and raw.strip():
        try:
            envelope = json.loads(raw)
            if isinstance(envelope, dict):
                detail = str(
                    _envelope_error_detail(envelope)
                    or envelope.get("result")
                    or envelope.get("api_error_status")
                    or raw
                )
            else:
                detail = raw
        except json.JSONDecodeError:
            detail = raw
    if not detail:
        detail = "no error detail"
    return "agent failed with exit %d: %s" % (returncode, detail.strip()[:1000])


def _validate_finding_audit(
    task: Dict[str, Any],
    artifact: Dict[str, Any],
    output: Path,
    engine_id: str,
) -> None:
    required = {
        "schema_version",
        "id",
        "task_id",
        "campaign_id",
        "finding_id",
        "verdict",
        "scope",
        "evidence_class",
        "source_records",
        "contradiction_resolution",
        "engine",
        "independent",
    }
    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError("finding audit lacks fields: %s" % ", ".join(missing))
    if artifact.get("id") != output.stem:
        raise ValueError(
            "artifact id %r does not match output filename %s"
            % (artifact.get("id"), output.name)
        )
    exact = {
        "schema_version": 1,
        "task_id": task.get("id"),
        "campaign_id": task.get("campaign_id"),
        "finding_id": task.get("finding_id"),
    }
    for field, expected in exact.items():
        if artifact.get(field) != expected:
            raise ValueError("finding audit %s does not match task" % field)
    if artifact.get("verdict") not in {
        "retain_candidate",
        "promote",
        "retire",
        "merge",
    }:
        raise ValueError("finding audit has invalid verdict")
    if artifact.get("independent") is not True:
        raise ValueError("finding audit is not independent")
    if artifact.get("engine") != engine_id:
        raise ValueError("finding audit engine does not match selected engine")
    if not isinstance(artifact.get("source_records"), list):
        raise ValueError("finding audit source_records must be a list")


def run_task(
    task: Dict[str, Any],
    engine_id: str,
    output: Path,
    timeout: int = 3600,
    progress_callback: Optional[Callable[[str, int, float], None]] = None,
) -> Dict[str, Any]:
    from .capabilities import WEB_PHASES, capability_is_attested
    from .paired import (
        ArtifactValidationError,
        PairedInfrastructureError,
        SubstantiveAttemptError,
        validate_digest,
        write_observable_trace,
    )

    phase = str(task.get("phase", ""))
    _validate_output_path(phase, output)
    if phase in {"mathematics", "review"} and output.exists():
        raise ValueError("refusing to overwrite an existing proof artifact")
    _validate_task_packet(task)
    config = load_engines().get(engine_id)
    if config is None:
        raise ValueError("unknown engine %s" % engine_id)
    if phase in WEB_PHASES:
        if not _engine_has_web_access(config):
            raise ValueError(
                "%s tasks require an engine configured with web_access" % phase
            )
        if not capability_is_attested(engine_id, phase):
            raise ValueError(
                "%s engine %s lacks a passing live capability attestation"
                % (phase, engine_id)
            )
    binary = config.get("binary", engine_id)
    if shutil.which(binary) is None:
        raise RuntimeError("engine binary is unavailable: %s" % binary)

    paired_turn = task.get("paired_turn_kind")
    with tempfile.TemporaryDirectory(prefix="pure-tate-agent-") as directory:
        context = Path(directory)
        files = build_isolated_context(task, context)
        prompt = assemble_prompt(task, files, output.stem, engine_id)
        last_message = context / "last-message.txt"
        command = _engine_argv(engine_id, prompt, last_message, phase=phase)
        family = config.get("family")
        engine_max = config.get("max_task_seconds")
        task_timeout = timeout
        if isinstance(engine_max, int) and engine_max > 0:
            task_timeout = min(timeout, engine_max)
        inactivity = config.get("inactivity_timeout_seconds")
        if not isinstance(inactivity, int) or inactivity <= 0:
            inactivity = None
        abort_patterns = config.get("abort_stderr_pattern_counts")
        if not isinstance(abort_patterns, dict):
            abort_patterns = None
        activity_streams = config.get("activity_streams")
        if not isinstance(activity_streams, list) or not activity_streams:
            activity_streams = None
        try:
            process = run_captured_process(
                command,
                cwd=context,
                env=_subprocess_env(
                    str(family) if family else None, config
                ),
                timeout=task_timeout,
                inactivity_timeout=inactivity,
                abort_stderr_pattern_counts=abort_patterns,
                activity_streams=activity_streams,
                on_activity=progress_callback,
            )
        except ProcessWatchdogError as exc:
            detail = (
                "agent watchdog: %s; stderr: %s"
                % (exc, (exc.stderr or "").strip()[:800] or "no stderr")
            )
            if paired_turn in {"forced-proof", "standard-fallback"}:
                trace = write_observable_trace(
                    task,
                    engine_id,
                    exc.stdout or "",
                    exc.stderr or "",
                    validation_error=detail,
                    classification="infrastructure",
                )
                raise PairedInfrastructureError(
                    detail, trace["id"], trace["path"]
                ) from exc
            raise RuntimeError(detail) from exc
        process_stdout = process.stdout or ""
        if family == "openai" and last_message.is_file():
            raw = last_message.read_text(encoding="utf-8")
        else:
            raw = process_stdout
        # Codex already emits official JSONL progress events on stdout while
        # writing the final artifact to --output-last-message. Parse only the
        # final file, but preserve the event stream in paired traces.
        observable_stdout = (
            process_stdout if family == "openai" and process_stdout else raw
        )
        if family == "grok":
            observable_stdout = _grok_observable_stream(raw)
        if process.returncode != 0:
            detail = _failure_detail(process.returncode, process.stderr, raw)
            if paired_turn in {"forced-proof", "standard-fallback"}:
                trace = write_observable_trace(
                    task,
                    engine_id,
                    observable_stdout,
                    process.stderr or "",
                    validation_error=detail,
                    classification="infrastructure",
                )
                raise PairedInfrastructureError(
                    detail, trace["id"], trace["path"]
                )
            raise RuntimeError(detail)
        try:
            if family == "gemini":
                artifact = _extract_gemini_stream(raw)
            elif family == "claude":
                artifact = _extract_claude_stream(raw)
            elif family == "grok":
                artifact = _extract_grok_stream(raw)
            else:
                artifact = _extract_json_object(raw)
        except ValueError as exc:
            if paired_turn in {"forced-proof", "standard-fallback"}:
                trace = write_observable_trace(
                    task,
                    engine_id,
                    observable_stdout,
                    process.stderr or "",
                    validation_error=str(exc),
                    classification="parse_failure",
                )
                raise PairedInfrastructureError(
                    str(exc), trace["id"], trace["path"]
                ) from exc
            raise RuntimeError(str(exc)) from exc
        stdout = observable_stdout
        # Keep the unfiltered official payload for validation-failure traces.
        # Grok's thought quarantine can drop envelope-only replies to "".
        raw_stdout = raw
        stderr = process.stderr or ""

    try:
        if phase == "trace-mining":
            if artifact.get("id") != output.stem:
                raise ValueError(
                    "artifact id %r does not match output filename %s"
                    % (artifact.get("id"), output.name)
                )
            validate_digest(task, artifact)
            if engine_id and artifact.get("engine") != engine_id:
                raise ValueError(
                    "artifact engine %r does not match selected engine %s"
                    % (artifact.get("engine"), engine_id)
                )
        elif phase == "finding-audit":
            _validate_finding_audit(task, artifact, output, engine_id)
        elif phase == "novelty":
            from .novelty import validate_novelty_artifact

            validate_novelty_artifact(task, artifact)
            if artifact.get("id") != output.stem:
                raise ValueError(
                    "artifact id %r does not match output filename %s"
                    % (artifact.get("id"), output.name)
                )
            if engine_id and artifact.get("engine") != engine_id:
                raise ValueError(
                    "artifact engine %r does not match selected engine %s"
                    % (artifact.get("engine"), engine_id)
                )
        else:
            _validate_artifact(phase, task, artifact, output, engine_id)
    except ValueError as exc:
        if paired_turn in {"forced-proof", "standard-fallback"}:
            trace = write_observable_trace(
                task,
                engine_id,
                stdout,
                stderr,
                parsed_artifact=artifact,
                validation_error=str(exc),
            )
            raise SubstantiveAttemptError(
                str(exc), trace["id"], trace["path"]
            ) from exc
        if phase in {
            "review",
            "finding-audit",
            "novelty",
            "trace-mining",
            "mathematics",
            "research",
        }:
            trace_task = dict(task)
            if not trace_task.get("paired_turn_kind"):
                trace_task["paired_turn_kind"] = phase
            # Grok thought quarantine can empty envelope-only replies; fall
            # back to the unfiltered official subprocess payload.
            trace_stdout = stdout if str(stdout or "").strip() else raw_stdout
            trace = write_observable_trace(
                trace_task,
                engine_id,
                trace_stdout,
                stderr,
                parsed_artifact=artifact,
                validation_error=str(exc),
                classification="validation_failure",
            )
            raise ArtifactValidationError(
                str(exc), trace["id"], trace["path"]
            ) from exc
        raise

    if paired_turn in {"forced-proof", "standard-fallback"}:
        trace = write_observable_trace(
            task,
            engine_id,
            stdout,
            stderr,
            parsed_artifact=artifact,
        )
        artifact["observable_trace_id"] = trace["id"]
        artifact["observable_trace_sha256"] = trace["sha256"]
        for field in (
            "paired_turn_kind",
            "paired_problem_key",
            "paired_theorem_sha256",
            "paired_attempt_policy_revision",
        ):
            if field in task:
                artifact[field] = task[field]

    atomic_write_json(output, artifact)
    return artifact
