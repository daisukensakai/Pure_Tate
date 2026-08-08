import json
import hashlib
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .grok_workers import WorkerSession

from .capabilities import WEB_CAPABILITIES, declared_capabilities
from .process_runner import ProcessWatchdogError, run_captured_process
from .store import DATA, ROOT, atomic_write_json, load_json
from .targets import CONTEXT_REVISION


ENGINE_CONFIG = DATA / "engines.json"
def _subprocess_env(
    family: Optional[str] = None,
    engine_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    env = dict(os.environ)
    if family == "claude":
        # An inherited 32k setting must not silently defeat the pinned engine
        # configuration for long forced-proof artifacts.
        maximum = (engine_config or {}).get("max_output_tokens", 64000)
        if isinstance(maximum, int) and maximum > 0:
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(maximum)
    return env


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


def _qwen_stream_events(text: str) -> List[Dict[str, Any]]:
    """Parse Qwen worker JSONL progress events from subprocess stdout."""
    events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and isinstance(event.get("type"), str):
            events.append(event)
    return events


def _extract_qwen_stream(text: str) -> Dict[str, Any]:
    """Reassemble Qwen worker text events into one JSON artifact.

    Falls back to plain-stdout JSON extraction for legacy non-stream workers.
    """
    events = _qwen_stream_events(text)
    stream_types = {event.get("type") for event in events}
    if not stream_types.intersection(
        {"text", "thought", "stage", "end", "error", "tool_call", "tool_result", "heartbeat"}
    ):
        return _extract_json_object(text)
    errors = [
        str(event.get("message") or event.get("error") or "Qwen stream failed")
        for event in events
        if event.get("type") == "error"
    ]
    chunks = [
        str(event.get("data"))
        for event in events
        if event.get("type") == "text" and isinstance(event.get("data"), str)
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
                "Qwen stream ended with %s but no complete JSON artifact"
                % (end.get("stopReason") or "unknown status")
            ) from exc
    if errors:
        raise ValueError(errors[-1])
    # Prefer a structured error over a silent empty stream.
    raise ValueError("Qwen stream contained no text artifact")


def _qwen_observable_stream(text: str) -> str:
    """Quarantine Qwen thoughts and heartbeats from proof traces / miners."""
    retained = [
        json.dumps(event, sort_keys=True)
        for event in _qwen_stream_events(text)
        if event.get("type")
        in {"text", "stage", "tool_call", "tool_result", "end", "error"}
    ]
    return "\n".join(retained) + ("\n" if retained else "")


def load_engines_config() -> Dict[str, Any]:
    value = load_json(ENGINE_CONFIG)
    if not isinstance(value, dict):
        raise ValueError("data/engines.json is not an object")
    return value


def load_engines() -> Dict[str, Dict[str, Any]]:
    value = load_engines_config()
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
    workers_enabled: bool = False,
    max_workers: int = 0,
) -> str:
    from .capabilities import phase_allows_web

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
        allow_web = phase_allows_web(str(phase) if phase else None)
        if family == "grok":
            tool_line = (
                "Use only read_file, grep, list_dir"
                + (
                    ", search_tool, and use_tool (for optional Grok workers)"
                    if workers_enabled
                    else ""
                )
                + (
                    ", and optional web_search/web_fetch when needed"
                    if allow_web
                    else ""
                )
                + "."
            )
            parts.append(
                "Your final answer must be exactly one JSON object with no prose "
                "before or after it. Prefer reading corpus/chunks over large text "
                "files when both are available. "
                + tool_line
                + " Never use run_terminal_command, write, or any shell. "
                "Put the completed JSON artifact in your final message only."
            )
        elif family == "qwen":
            parts.append(
                "Your final answer must be exactly one JSON object with no prose "
                "before or after it. Prefer reading corpus/chunks over large text "
                "files when both are available. Use only the supplied read_file "
                "tool for workspace context. "
                "Put the completed JSON artifact in your final message only."
            )
    if workers_enabled and max_workers > 0:
        from .grok_workers import worker_dispatch_parent_policy

        parts.append(worker_dispatch_parent_policy(max_workers))
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
            "verdict must identify a failed or unresolved structured check. "
            "A confirmed verdict forbids any failed or unresolved checked "
            "claim or proof dependency—including non-load-bearing or unused "
            "listed sources. Mark unused sources confirmed with a note, omit "
            "them, or choose incomplete/refuted; the harness rejects confirmed "
            "reviews that carry any adverse structured check."
        )
    primary_wc = next(
        (
            path
            for path in context_files
            if isinstance(path, str)
            and path
            and "paired-working-context" in path.replace("\\", "/")
            and Path(path).name.startswith("WORKING-")
            and not Path(path).name.startswith("WORKING-EXT-")
            and not Path(path).name.startswith("WORKING-ARCHIVE-")
        ),
        None,
    )
    if phase == "mathematics" and primary_wc:
        parts.append(
            "Required first action: before drafting any theorem or argument, "
            "read the primary mathematical working-context file end-to-end via "
            "your read tool: %s. Use its frontier obligations and mathematical "
            "constraints to avoid repeating dead routes; treat candidates as "
            "unproved. Prefer primary; the extended working-context file (if "
            "supplied) is overflow only, but constraints there still bind. Do "
            "not claim progress that merely restates a primary constraint."
            % primary_wc
        )
    elif task.get("paired_turn_kind") == "standard-fallback":
        parts.append(
            "The supplied mathematical working-context files are ordinary "
            "context. Prefer the primary file; the extended file is overflow. "
            "Mathematical constraints in either file still apply and must not "
            "be repeated. Candidate ideas are unproved and must be established "
            "independently before use."
        )
    parts.extend(["", "Phase: " + str(phase)])
    return "\n".join(parts)


def _engine_argv(
    engine_id: str,
    prompt: str,
    last_message_path: Optional[Path] = None,
    phase: Optional[str] = None,
    workers: Optional["WorkerSession"] = None,
    context_files: Optional[List[str]] = None,
) -> List[str]:
    from .capabilities import phase_allows_web
    from .grok_workers import apply_workers_to_argv

    engines = load_engines()
    if engine_id not in engines:
        raise ValueError("unknown engine %s" % engine_id)
    config = engines[engine_id]
    binary = config.get("binary", engine_id)
    family = config.get("family")
    model = config.get("model")
    workers_on = workers is not None and getattr(workers, "enabled", False)
    # Web tools are available on agent phases so the model can look up
    # supporting mathematics when it chooses. Research-family phases still
    # require live capability attestation before dispatch.
    allow_web = phase_allows_web(phase)
    if family == "openai":
        if last_message_path is None:
            raise ValueError("OpenAI engine requires a last-message path")
        # CLI_test: codex exec read-only still can invoke web_search items.
        # Effort: gpt-5.6-sol uses Extra High via model_reasoning_effort=xhigh
        # (see CLI_test/EFFORT_FINDINGS.md).
        command = [binary]
        if allow_web:
            command.append("--search")
        command.extend(
            [
                "exec",
                "--skip-git-repo-check",
                "-m",
                model,
                "--sandbox",
                "read-only",
                "-c",
                'approval_policy="never"',
            ]
        )
        reasoning_effort = config.get("model_reasoning_effort")
        if isinstance(reasoning_effort, str) and reasoning_effort.strip():
            command.extend(
                [
                    "-c",
                    'model_reasoning_effort="%s"' % reasoning_effort.strip(),
                ]
            )
        command.extend(
            [
                "--json",
                "-o",
                str(last_message_path),
                prompt,
            ]
        )
        return apply_workers_to_argv(command, "openai", workers)
    if family == "claude":
        allowed = ["Read", "Grep", "Glob"]
        if allow_web:
            allowed.extend(["WebSearch", "WebFetch"])
        # When workers are enabled, CLI_test showed bypassPermissions is needed
        # for headless MCP; write/shell remain disallowed.
        permission_mode = "bypassPermissions" if workers_on else "default"
        command = [
            binary,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--permission-mode",
            permission_mode,
            "--allowedTools",
            *allowed,
            "--disallowedTools",
            "Edit",
            "Write",
            "Bash",
            "--model",
            model,
        ]
        # Effort max for Claude attempts (CLI_test/EFFORT_FINDINGS.md).
        effort = config.get("effort")
        if isinstance(effort, str) and effort.strip():
            command.extend(["--effort", effort.strip()])
        return apply_workers_to_argv(command, "claude", workers)
    if family == "grok":
        # Grok tool ids are snake_case. Never add spawn_subagent to --tools
        # (allowlist collapse). Workers attach via MCP search_tool/use_tool.
        # dontAsk cancels MCP use_tool; workers require bypassPermissions while
        # write/shell stay denied by the allowlist.
        tools = ["read_file", "grep", "list_dir"]
        denied = ["run_terminal_command", "write", "open_page"]
        permission_mode = "bypassPermissions" if workers_on else "dontAsk"
        command = [
            binary,
            "-p",
            prompt,
            "--output-format",
            "streaming-json",
            "--max-turns",
            "50" if workers_on else "40",
            "--permission-mode",
            permission_mode,
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
        return apply_workers_to_argv(command, "grok", workers)
    if family == "qwen":
        reasoning_effort = config.get("reasoning_effort", "xhigh")
        command = [
            sys.executable,
            str((Path(__file__).with_name("qwen_worker.py")).resolve()),
            "--model",
            str(model),
            "--prompt",
            prompt,
            "--max-tokens",
            str(config.get("max_output_tokens", 65536)),
            "--thinking-budget",
            str(config.get("thinking_budget", 65536)),
            "--reasoning-effort",
            str(reasoning_effort),
        ]
        for relative in context_files or []:
            command.extend(["--context-file", relative])
        if allow_web:
            command.append("--allow-web")
        if workers_on:
            command.append("--allow-grok-workers")
        return command
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


def _normalize_failed_approaches(
    artifact: Dict[str, Any], blocked_routes: Any = ()
) -> None:
    """Canonicalize `failed_approaches_addressed` into one schema.

    Engines emit at least four shapes for this field -- a bare string, and dicts
    keyed {route, how_addressed}, {approach, resolution} or {disposition,
    reason}. That variance made the field unreadable, so there was no way to
    tell whether a prover engaged with the working context's constraints or
    merely restated the packet's blocked routes. Each entry is normalized to
    {subject, kind, disposition} where `kind` separates the two.
    """
    entries = artifact.get("failed_approaches_addressed")
    if not isinstance(entries, list):
        return
    routes = {str(item) for item in (blocked_routes or ())}
    normalized = []
    for entry in entries:
        if isinstance(entry, str):
            subject, disposition = entry, ""
        elif isinstance(entry, dict):
            subject = str(
                entry.get("route")
                or entry.get("approach")
                or entry.get("id")
                or entry.get("description")
                or entry.get("statement")
                or ""
            ).strip()
            disposition = str(
                entry.get("how_addressed")
                or entry.get("resolution")
                or entry.get("reason")
                or entry.get("disposition")
                or entry.get("description")
                or ""
            ).strip()
        else:
            continue
        subject = " ".join(str(subject).split())
        if not subject:
            continue
        if disposition == subject:
            disposition = ""
        normalized.append(
            {
                "subject": subject,
                "kind": (
                    "blocked_route"
                    if subject in routes
                    else "working_context_constraint"
                ),
                "disposition": " ".join(disposition.split()),
            }
        )
    artifact["failed_approaches_addressed"] = normalized


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
    from .validation_repair import coerce_identity_field

    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError("agent artifact lacks fields: %s" % ", ".join(missing))
    # Slot id is reserved by the harness; stamp rather than waste the turn.
    coerce_identity_field(artifact, "id", output.stem)
    if phase == "research":
        artifact["inferred_pairs"] = _normalize_inferred_pairs(
            artifact.get("inferred_pairs")
        )
        if artifact.get("target_claim_id") != task.get("target"):
            raise ValueError("research artifact targets the wrong reduction")
    if phase == "review":
        coerce_identity_field(
            artifact, "attempt_id", task.get("target_attempt_id")
        )
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
        # The target dictionary is the statement under proof, not bookkeeping.
        # An artifact that names a different cohomology degree or codimension
        # proved something else, and silently relabelling it would launder that
        # claim into the ledger under the task's target. Absent keys are still
        # filled in -- models routinely omit the compact aliases -- but a key
        # that is present and contradictory fails the turn.
        expected_target = task.get("target")
        artifact_target = artifact.get("target")
        if isinstance(expected_target, dict) and isinstance(artifact_target, dict):
            contradicted = sorted(
                "%s=%r (task %r)" % (key, artifact_target[key], value)
                for key, value in expected_target.items()
                if key in artifact_target and artifact_target[key] != value
            )
            if contradicted:
                raise ValueError(
                    "artifact target contradicts the task target: %s"
                    % ", ".join(contradicted)
                )
        # Remaining identity fields are owned by the harness/task. Models often
        # omit or slightly rewrite them; coerce rather than waste a full paid
        # turn on copy-paste mismatch.
        for field, expected in exact.items():
            coerce_identity_field(artifact, field, expected)
        if is_campaign:
            if task.get("packet_binding_sha256"):
                coerce_identity_field(
                    artifact,
                    "packet_binding_sha256",
                    task.get("packet_binding_sha256"),
                )
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
        # Accept common model aliases so a near-schema claim object is not
        # rejected solely for using text/type instead of statement/status.
        claims = artifact.get("claims")
        if isinstance(claims, list):
            normalized_claims = []
            for item in claims:
                if not isinstance(item, dict):
                    normalized_claims.append(item)
                    continue
                claim = dict(item)
                if not isinstance(claim.get("statement"), str) or not str(
                    claim.get("statement") or ""
                ).strip():
                    for alias in ("text", "claim", "content"):
                        value = claim.get(alias)
                        if isinstance(value, str) and value.strip():
                            claim["statement"] = value.strip()
                            break
                if not isinstance(claim.get("status"), str) or not str(
                    claim.get("status") or ""
                ).strip():
                    for alias in ("type", "verdict"):
                        value = claim.get(alias)
                        if isinstance(value, str) and value.strip():
                            claim["status"] = value.strip()
                            break
                normalized_claims.append(claim)
            artifact["claims"] = normalized_claims
            claims = normalized_claims
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
        # The harness, not the model, decides whether this attempt is complete.
        # Leaving `status` to the prover let a gap-free, fully proved lemma
        # label itself "proposed" and so lock itself out of its second review
        # pass, which stalls the subproblem graph behind it.
        from .proofs import attempt_completeness

        completeness = attempt_completeness(artifact)
        artifact["status"] = (
            "claimed_complete" if completeness["complete"] else "proposed"
        )
        if is_campaign:
            from .campaigns import campaign_route_policy_errors, load_campaign

            campaign = load_campaign(str(task["campaign_id"]))
            _normalize_failed_approaches(
                artifact, campaign.get("blocked_routes")
            )
            route_errors = campaign_route_policy_errors(campaign, artifact)
            if route_errors:
                raise ValueError(route_errors[0])
        if task.get("paired_turn_kind") == "forced-proof":
            if artifact.get("result_type") not in {"proof", "disproof"}:
                raise ValueError(
                    "forced-proof result_type must be proof or disproof"
                )
            if not completeness["complete"]:
                raise ValueError(
                    "forced-proof requires complete resolution: %s"
                    % "; ".join(completeness["reasons"])
                )
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
        # Review identity fields are harness-owned (same posture as mathematics).
        for field, expected in exact.items():
            coerce_identity_field(artifact, field, expected)
        if is_campaign:
            # Harness-owned packet identity: models often omit binding; stamp
            # from the task so verified-dependency gates do not false-negative.
            if task.get("packet_binding_sha256"):
                coerce_identity_field(
                    artifact,
                    "packet_binding_sha256",
                    task.get("packet_binding_sha256"),
                )
            if not isinstance(artifact.get("theorem_statement"), str) or not artifact[
                "theorem_statement"
            ].strip():
                raise ValueError("campaign review theorem_statement must be nonempty")
            # Theorem text is harness-owned identity of the attempt under review.
            # Models routinely paraphrase or swap lookalike glyphs; coerce rather
            # than burn a paid turn on an exact-string mismatch.
            expected_theorem = task.get("theorem_statement")
            if (
                isinstance(expected_theorem, str)
                and expected_theorem.strip()
            ):
                coerce_identity_field(
                    artifact, "theorem_statement", expected_theorem
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
    # Stamp selected engine before independence / exclusion checks.
    if phase == "mathematics":
        engine_field = "engine"
    elif phase in {"review", "research"}:
        engine_field = "reviewer_engine"
    else:
        engine_field = "engine"
    if engine_id and phase in {"mathematics", "review", "research"}:
        coerce_identity_field(artifact, engine_field, engine_id)
    if phase == "review":
        if artifact.get("reviewer_engine") == task.get("prover_engine"):
            raise ValueError("reviewer engine must differ from prover engine")
        if artifact.get("reviewer_engine") in task.get(
            "excluded_reviewer_engines", []
        ):
            raise ValueError("reviewer engine duplicates an excluded review engine")
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
    target = task.get("target")
    if not isinstance(target, dict):
        raise ValueError("task target dictionary is missing")
    if task.get("campaign_id"):
        from .campaigns import (
            campaign_packet_snapshot_path,
            packet_binding_matches,
        )

        # Staleness is judged on packet identity, not packet content: a finding
        # adjudication landing between task construction and dispatch rewrites
        # the findings section (and the mutable working path) and must not
        # invalidate in-flight work. Content-hash equality against the working
        # path is therefore not required for campaign tasks; binding match is.
        if not packet_binding_matches(task, str(task["campaign_id"])):
            raise ValueError(
                "task packet is stale relative to the current packet identity"
            )
        expected = task.get("packet_sha256")
        if not isinstance(expected, str) or not expected or actual == expected:
            return
        # The recorded text is still pinned: every packet write leaves an
        # immutable content-addressed snapshot, so a task that carries a binding
        # hash must be able to produce the exact packet it was built against.
        # Pre-binding artifacts predate the snapshots and their superseded texts
        # were overwritten in place, so identity equivalence is all that remains
        # checkable for them -- see proof/migrations/campaign-*-binding.json.
        if not task.get("packet_binding_sha256"):
            return
        snapshot = campaign_packet_snapshot_path(path, expected)
        if not snapshot.is_file():
            raise ValueError(
                "task packet snapshot is missing for %s: %s"
                % (expected, snapshot.name)
            )
        snapshot_hash = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        if snapshot_hash != expected:
            raise ValueError(
                "task packet hash mismatch: expected %s, got %s"
                % (expected, snapshot_hash)
            )
        return
    if actual != task.get("packet_sha256"):
        raise ValueError(
            "task packet hash mismatch: expected %s, got %s"
            % (task.get("packet_sha256"), actual)
        )
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
        # Streaming CLIs commonly begin with a very large init envelope and
        # put the actionable failure in their final JSONL event. Inspect those
        # events from the end before falling back to raw text.
        for line in reversed(raw.splitlines()):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type") or "").lower()
            subtype = str(event.get("subtype") or "").lower()
            if (
                event.get("is_error") is True
                or event_type == "error"
                or subtype in {"error", "failed", "failure"}
            ):
                value = (
                    event.get("error")
                    or event.get("result")
                    or event.get("message")
                )
                if isinstance(value, dict):
                    value = value.get("message") or value
                detail = str(value or line)
                break
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
            detail = raw.strip()[-1000:]
    if not detail:
        detail = "no error detail"
    return "agent failed with exit %d: %s" % (returncode, detail.strip()[-1000:])


class _ControllerProcess:
    """Process-shaped result for the multi-turn Codex controller adapter."""

    def __init__(self, stdout: str, stderr: str) -> None:
        self.returncode = 0
        self.stdout = stdout
        self.stderr = stderr


def _codex_controller_settings(config_root: Dict[str, Any]) -> Dict[str, Any]:
    raw = config_root.get("codex_controller_workers")
    raw = raw if isinstance(raw, dict) else {}

    def bounded(name: str, default: int, lower: int, upper: int) -> int:
        try:
            value = int(raw.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(lower, min(upper, value))

    return {
        "enabled": raw.get("enabled", True) is not False,
        "max_requests": bounded("max_requests", 4, 0, 4),
        "retry_limit": bounded("retry_limit", 1, 0, 1),
        "max_attempts": bounded("max_attempts", 8, 1, 8),
        "max_result_chars": bounded("max_result_chars", 12000, 500, 50000),
    }


def _codex_controller_decision_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "request"],
        "properties": {
            "action": {"type": "string", "enum": ["dispatch", "finalize"]},
            "request": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["request_id", "description", "prompt"],
                        "properties": {
                            "request_id": {"type": "string"},
                            "description": {"type": "string"},
                            "prompt": {"type": "string"},
                        },
                    },
                    {"type": "null"},
                ]
            },
        },
    }


def _parse_codex_controller_decision(
    raw: str, seen_ids: set[str]
) -> Dict[str, str]:
    value = _extract_json_object(raw)
    action = value.get("action")
    if action == "finalize":
        if value.get("request") is not None:
            raise ValueError("controller finalize decision request must be null")
        return {"action": "finalize"}
    if action != "dispatch" or not isinstance(value.get("request"), dict):
        raise ValueError("controller decision must be dispatch or finalize")
    request = value["request"]
    request_id = request.get("request_id")
    description = request.get("description")
    prompt = request.get("prompt")
    if (
        not isinstance(request_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", request_id)
        or request_id in seen_ids
    ):
        raise ValueError("controller request_id is invalid or duplicated")
    if not isinstance(description, str) or not description.strip() or len(description) > 500:
        raise ValueError("controller request description is invalid")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
        raise ValueError("controller request prompt is invalid")
    return {
        "action": "dispatch",
        "request_id": request_id,
        "description": description.strip(),
        "prompt": prompt.strip(),
    }


def _codex_controller_transcript(
    entries: List[Dict[str, Any]], max_result_chars: int
) -> str:
    if not entries:
        return "No Grok workers have been requested yet."
    rows = []
    for entry in entries:
        row = {
            "request_id": entry["request_id"],
            "description": entry["description"],
            "status": entry["status"],
            "attempts": entry["attempts"],
            "worker_ids": entry["worker_ids"],
        }
        if entry["status"] == "completed":
            row["result"] = entry.get("result", "")[:max_result_chars]
        else:
            row["error"] = entry.get("error", "worker failed")[:1000]
        rows.append(row)
    return json.dumps(rows, indent=2, sort_keys=True)


def _codex_controller_decision_prompt(
    base_prompt: str,
    transcript: str,
    remaining_requests: int,
) -> str:
    return (
        base_prompt
        + "\n\n# Controller decision turn\n\n"
        + "You are the mastermind controller. Do not return the task artifact "
        + "on this turn. You have "
        + str(remaining_requests)
        + " remaining logical Grok-worker requests. Review the controller "
        + "transcript below, then return exactly one JSON object matching the "
        + "decision schema: either action=dispatch with one focused request, or "
        + "action=finalize when you have enough information.\n\n"
        + "Division of labor (mandatory for every dispatch):\n"
        + "- Codex owns thinking, analysis, critical decisions, routing, and "
        + "the eventual synthesis structure.\n"
        + "- Dispatch Grok liberally for bulk reading of packet/corpus sources, "
        + "locator extraction, literature/web lookup, enumerations, and draft "
        + "fragments. Prefer spending remaining requests over early finalize "
        + "when useful subproblems remain.\n"
        + "- Do not re-read sources a worker already covered; analyze their "
        + "reports instead. Spot-check only if a load-bearing claim is "
        + "contested or the report is incomplete/incoherent.\n"
        + "- Grok results are assistive; you still own correctness of every "
        + "load-bearing step in the final artifact.\n\n"
        + "# Controller transcript\n\n"
        + transcript
    )


def _codex_controller_synthesis_prompt(base_prompt: str, transcript: str) -> str:
    return (
        base_prompt
        + "\n\n# Controller Grok-worker transcript\n\n"
        + transcript
        + "\n\nYou are the mastermind synthesizing the final artifact. Use the "
        + "worker transcript as your reading layer for bulk source content — "
        + "do not re-open sources workers already extracted unless a "
        + "load-bearing claim is contested or a report is incomplete. Spend "
        + "Codex tokens on analysis, critical decisions, and assembling a "
        + "correct proof/disproof structure; verify load-bearing logic "
        + "yourself. Now return the required task artifact exactly as the "
        + "execution contract requires."
    )


def _run_codex_controller(
    *,
    task: Dict[str, Any],
    context: Path,
    context_files: List[str],
    expected_artifact_id: str,
    phase: str,
    workers: "WorkerSession",
    settings: Dict[str, Any],
    task_timeout: int,
    inactivity: Optional[int],
    abort_patterns: Optional[Dict[str, Any]],
    activity_streams: Optional[List[str]],
    progress_callback: Optional[Callable[[str, int, float], None]],
    process_start_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> _ControllerProcess:
    """Run bounded tool-free Codex decisions and direct trusted worker dispatch."""
    from .grok_workers import GrokWorkerPool, PoolError

    if workers.dispatch_log is None:
        raise RuntimeError("controller worker session lacks durable dispatch log")
    max_requests = int(settings["max_requests"])
    retry_limit = int(settings["retry_limit"])
    max_attempts = int(settings["max_attempts"])
    max_result_chars = int(settings["max_result_chars"])
    base_prompt = assemble_prompt(
        task, context_files, expected_artifact_id, "codex", workers_enabled=False
    )
    decision_schema_path = context / "codex-controller-decision-schema.json"
    atomic_write_json(decision_schema_path, _codex_controller_decision_schema())
    pool = GrokWorkerPool(
        max_concurrent=1,
        max_total=max_attempts,
        model=workers.env_updates.get("GROK_WORKER_MODEL", "grok-4.5"),
        timeout_seconds=int(workers.env_updates.get("GROK_WORKER_TIMEOUT", "300")),
        allow_web=workers.allow_web,
        work_dir=context,
        results_dir=workers.results_dir,
        dispatch_log=workers.dispatch_log,
    )
    entries: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    observable: List[str] = []
    stderr_chunks: List[str] = []
    started = time.monotonic()

    def invoke(prompt: str, output_path: Path, schema: Optional[Path] = None) -> str:
        remaining = max(1, int(task_timeout - (time.monotonic() - started)))
        command = _engine_argv("codex", prompt, output_path, phase=phase, workers=None)
        if schema is not None:
            command[-1:-1] = ["--output-schema", str(schema)]
        process = run_captured_process(
            command,
            cwd=context,
            env=_subprocess_env("openai", load_engines().get("codex")),
            timeout=remaining,
            inactivity_timeout=inactivity,
            abort_stderr_pattern_counts=abort_patterns,
            activity_streams=activity_streams,
            on_activity=progress_callback,
            on_process_start=process_start_callback,
        )
        observable.append(process.stdout or "")
        stderr_chunks.append(process.stderr or "")
        if process.returncode != 0:
            detail = _failure_detail(
                process.returncode, process.stderr or "", process.stdout or ""
            )
            if process.stdout:
                detail += "; stdout: " + process.stdout.strip()[-1200:]
            raise RuntimeError(detail)
        if not output_path.is_file():
            raise RuntimeError("Codex controller turn did not write output")
        return output_path.read_text(encoding="utf-8")

    try:
        for round_index in range(max_requests):
            workers.dispatch_log.log(
                "controller_decision_started",
                round=round_index + 1,
                remaining_requests=max_requests - round_index,
            )
            decision_path = context / ("codex-controller-decision-%d.json" % (round_index + 1))
            raw_decision = invoke(
                _codex_controller_decision_prompt(
                    base_prompt,
                    _codex_controller_transcript(entries, max_result_chars),
                    max_requests - round_index,
                ),
                decision_path,
                decision_schema_path,
            )
            try:
                decision = _parse_codex_controller_decision(raw_decision, seen_ids)
            except ValueError as exc:
                workers.dispatch_log.log(
                    "controller_decision_invalid", round=round_index + 1, error=str(exc)
                )
                raise
            if decision["action"] == "finalize":
                workers.dispatch_log.log("controller_decision_finalized", round=round_index + 1)
                break
            seen_ids.add(decision["request_id"])
            workers.dispatch_log.log(
                "controller_request_accepted",
                round=round_index + 1,
                request_id=decision["request_id"],
                description=decision["description"],
                prompt_sha256=hashlib.sha256(decision["prompt"].encode("utf-8")).hexdigest(),
            )
            entry: Dict[str, Any] = {
                "request_id": decision["request_id"],
                "description": decision["description"],
                "status": "failed",
                "attempts": 0,
                "worker_ids": [],
                "error": "worker was not dispatched",
            }
            for attempt in range(retry_limit + 1):
                if pool.dispatched_count >= max_attempts:
                    entry["error"] = "controller worker-attempt budget exhausted"
                    break
                try:
                    result = pool.dispatch(
                        decision["prompt"], decision["description"], wait=True
                    )
                except PoolError as exc:
                    entry["error"] = exc.message
                    break
                entry["attempts"] += 1
                entry["worker_ids"].append(str(result.get("worker_id")))
                if result.get("status") == "completed":
                    entry["status"] = "completed"
                    entry["result"] = str(result.get("result_text") or "")
                    workers.dispatch_log.log(
                        "controller_worker_finished",
                        request_id=entry["request_id"],
                        attempt=attempt + 1,
                        worker_id=result.get("worker_id"),
                        status="completed",
                    )
                    break
                entry["error"] = str(result.get("error") or "worker failed")
                workers.dispatch_log.log(
                    "controller_worker_finished",
                    request_id=entry["request_id"],
                    attempt=attempt + 1,
                    worker_id=result.get("worker_id"),
                    status=str(result.get("status") or "failed"),
                    error=entry["error"],
                )
                if attempt < retry_limit:
                    workers.dispatch_log.log(
                        "controller_retry",
                        request_id=entry["request_id"],
                        attempt=attempt + 2,
                        previous_worker_id=result.get("worker_id"),
                        error=entry["error"],
                    )
            if entry["status"] != "completed":
                workers.dispatch_log.log(
                    "controller_worker_exhausted",
                    request_id=entry["request_id"],
                    attempts=entry["attempts"],
                    error=entry["error"],
                )
            entries.append(entry)
        else:
            workers.dispatch_log.log("controller_forced_finalization", rounds=max_requests)

        workers.dispatch_log.log("controller_synthesis_started", rounds=len(entries))
        final_path = context / "last-message.txt"
        invoke(
            _codex_controller_synthesis_prompt(
                base_prompt, _codex_controller_transcript(entries, max_result_chars)
            ),
            final_path,
        )
        workers.dispatch_log.log("controller_synthesis_finished", rounds=len(entries))
        return _ControllerProcess("\n".join(observable), "\n".join(stderr_chunks))
    finally:
        pool.shutdown(cancel_live=True)


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
    from .validation_repair import coerce_identity_field

    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError("finding audit lacks fields: %s" % ", ".join(missing))
    coerce_identity_field(artifact, "id", output.stem)
    exact = {
        "schema_version": 1,
        "task_id": task.get("id"),
        "campaign_id": task.get("campaign_id"),
        "finding_id": task.get("finding_id"),
    }
    for field, expected in exact.items():
        coerce_identity_field(artifact, field, expected)
    # Coerce common model aliases to the harness enum (string mismatch only).
    verdict_aliases = {
        "promote_to_corroborated": "promote",
        "promote_to_corroboration": "promote",
        "corroborate": "promote",
        "corroborated": "promote",
        "retain": "retain_candidate",
        "keep_candidate": "retain_candidate",
        "retain_as_candidate": "retain_candidate",
        "retire_finding": "retire",
        "merge_finding": "merge",
    }
    raw_verdict = artifact.get("verdict")
    if isinstance(raw_verdict, str) and raw_verdict in verdict_aliases:
        artifact["verdict"] = verdict_aliases[raw_verdict]
    if artifact.get("verdict") not in {
        "retain_candidate",
        "promote",
        "retire",
        "merge",
    }:
        raise ValueError("finding audit has invalid verdict")
    if artifact.get("independent") is not True:
        raise ValueError("finding audit is not independent")
    if engine_id:
        coerce_identity_field(artifact, "engine", engine_id)
    if not isinstance(artifact.get("source_records"), list):
        raise ValueError("finding audit source_records must be a list")


def run_task(
    task: Dict[str, Any],
    engine_id: str,
    output: Path,
    timeout: int = 10800,
    progress_callback: Optional[Callable[[str, int, float], None]] = None,
    process_start_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
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
    # Existing durable work is never rewritten. Reattempts must reserve a new
    # artifact slot; recover validation failures from the official trace first.
    if phase in {
        "mathematics",
        "review",
        "finding-audit",
        "novelty",
        "trace-mining",
        "research",
    } and output.exists():
        raise ValueError(
            "refusing to overwrite existing artifact %s; reattempts require a "
            "new reserved slot and recovery must be attempted before re-running"
            % output
        )
    _validate_task_packet(task)
    config = load_engines().get(engine_id)
    if config is None:
        raise ValueError("unknown engine %s" % engine_id)
    from .health import engine_runtime_issue

    runtime_issue = engine_runtime_issue(engine_id, config)
    if runtime_issue is not None:
        raise RuntimeError(runtime_issue)
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
    paired_turn = task.get("paired_turn_kind")
    with tempfile.TemporaryDirectory(prefix="pure-tate-agent-") as directory:
        context = Path(directory)
        files = build_isolated_context(task, context)
        family = config.get("family")
        from .capabilities import phase_allows_web
        from .grok_workers import (
            max_grok_workers_from_config,
            merge_worker_env,
            prepare_worker_session,
            record_parent_mcp_events,
        )

        engines_root = load_engines_config()
        max_workers = max_grok_workers_from_config(engines_root)
        controller_settings = _codex_controller_settings(engines_root)
        codex_controller = bool(
            engine_id == "codex"
            and family == "openai"
            and controller_settings["enabled"]
            and max_workers > 0
        )
        allow_web = phase_allows_web(phase)
        worker_model = (
            load_engines().get("grok", {}).get("model") or "grok-4.5"
        )
        workers = prepare_worker_session(
            context,
            family=str(family or ""),
            max_workers=max_workers,
            allow_web=allow_web,
            worker_model=str(worker_model),
            worker_timeout=min(timeout, 3600),
            parent_meta={
                "engine": engine_id,
                "family": str(family or ""),
                "phase": phase,
                "task_id": task.get("id"),
                "output": str(output),
                "paired_turn_kind": task.get("paired_turn_kind"),
                "campaign_id": task.get("campaign_id"),
                "worker_mode": "controller" if codex_controller else "mcp",
            },
            attach_mcp=not codex_controller,
        )
        workers_on = (
            workers is not None and workers.enabled and not codex_controller
        )
        from .validation_repair import (
            assemble_validation_repair_prompt,
            is_mechanical_validation_error,
            summarize_repair,
            validation_repair_settings,
        )

        base_prompt = assemble_prompt(
            task,
            files,
            output.stem,
            engine_id,
            workers_enabled=workers_on,
            max_workers=max_workers if workers_on else 0,
        )
        last_message = context / "last-message.txt"
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
        env = merge_worker_env(
            _subprocess_env(str(family) if family else None, config),
            workers,
        )
        repair_settings = validation_repair_settings(engines_root)
        repair_limit = (
            int(repair_settings["retry_limit"])
            if repair_settings["enabled"]
            else 0
        )
        # Codex controller is multi-turn already; skip nested repair for it.
        if codex_controller:
            repair_limit = 0

        repair_errors: List[str] = []
        previous_artifact: Optional[Dict[str, Any]] = None
        artifact: Dict[str, Any] = {}
        stdout = ""
        raw_stdout = ""
        stderr = ""
        repaired = False

        def _validate_phase_artifact(candidate: Dict[str, Any]) -> None:
            if phase == "trace-mining":
                from .validation_repair import coerce_identity_field

                coerce_identity_field(candidate, "id", output.stem)
                validate_digest(task, candidate)
                if engine_id:
                    coerce_identity_field(candidate, "engine", engine_id)
            elif phase == "finding-audit":
                _validate_finding_audit(task, candidate, output, engine_id)
            elif phase == "novelty":
                from .novelty import validate_novelty_artifact
                from .validation_repair import coerce_identity_field

                validate_novelty_artifact(task, candidate)
                coerce_identity_field(candidate, "id", output.stem)
                if engine_id:
                    coerce_identity_field(candidate, "engine", engine_id)
            else:
                _validate_artifact(phase, task, candidate, output, engine_id)

        def _raise_validation_failure(
            exc: ValueError, candidate: Dict[str, Any]
        ) -> None:
            if paired_turn in {"forced-proof", "standard-fallback"}:
                trace = write_observable_trace(
                    task,
                    engine_id,
                    stdout,
                    stderr,
                    parsed_artifact=candidate,
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
                    parsed_artifact=candidate,
                    validation_error=str(exc),
                    classification="validation_failure",
                )
                raise ArtifactValidationError(
                    str(exc), trace["id"], trace["path"]
                ) from exc
            raise

        for attempt in range(repair_limit + 1):
            if attempt == 0 or previous_artifact is None:
                prompt = base_prompt
            else:
                prompt = assemble_validation_repair_prompt(
                    base_prompt=base_prompt,
                    phase=phase,
                    task=task,
                    output_stem=output.stem,
                    engine_id=engine_id,
                    previous_artifact=previous_artifact,
                    validation_errors=repair_errors,
                )
            # Fresh last-message path each attempt so prior content cannot leak.
            if last_message.is_file():
                last_message.unlink()
            command = _engine_argv(
                engine_id,
                prompt,
                last_message,
                phase=phase,
                workers=workers if workers_on else None,
                context_files=files,
            )
            # After the first attempt only allow progress callbacks; process
            # start is reported once so the drive ledger does not thrash.
            start_cb = process_start_callback if attempt == 0 else None
            try:
                if codex_controller:
                    if workers is None:
                        raise RuntimeError(
                            "Codex controller worker session is unavailable"
                        )
                    process = _run_codex_controller(
                        task=task,
                        context=context,
                        context_files=files,
                        expected_artifact_id=output.stem,
                        phase=phase,
                        workers=workers,
                        settings=controller_settings,
                        task_timeout=task_timeout,
                        inactivity=inactivity,
                        abort_patterns=abort_patterns,
                        activity_streams=activity_streams,
                        progress_callback=progress_callback,
                        process_start_callback=start_cb,
                    )
                else:
                    process = run_captured_process(
                        command,
                        cwd=context,
                        env=env,
                        timeout=task_timeout,
                        inactivity_timeout=inactivity,
                        abort_stderr_pattern_counts=abort_patterns,
                        activity_streams=activity_streams,
                        on_activity=progress_callback,
                        on_process_start=start_cb,
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
            # The worker server records calls it receives. Capture engine-side MCP
            # events as well, so approval cancellations are not mistaken for a
            # parent that simply elected not to dispatch a worker.
            record_parent_mcp_events(workers, process_stdout)
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
            elif family == "qwen":
                observable_stdout = _qwen_observable_stream(raw)
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
                if family == "claude":
                    artifact = _extract_claude_stream(raw)
                elif family == "grok":
                    artifact = _extract_grok_stream(raw)
                elif family == "qwen":
                    artifact = _extract_qwen_stream(raw)
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
                _validate_phase_artifact(artifact)
            except ValueError as exc:
                if (
                    attempt < repair_limit
                    and is_mechanical_validation_error(str(exc))
                    and isinstance(artifact, dict)
                ):
                    repair_errors.append(str(exc))
                    previous_artifact = dict(artifact)
                    continue
                _raise_validation_failure(exc, artifact)
            else:
                if repair_errors:
                    repaired = True
                    artifact["validation_repair"] = summarize_repair(
                        attempts=attempt + 1,
                        errors=repair_errors,
                        repaired=True,
                    )
                break
        else:
            # Loop exhausted without success (should not reach: final attempt
            # raises inside). Defensive fallback.
            raise RuntimeError("validation repair loop exhausted without result")

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
                "routing_chain_id",
            ):
                if field in task:
                    artifact[field] = task[field]

        atomic_write_json(output, artifact)
        return artifact
