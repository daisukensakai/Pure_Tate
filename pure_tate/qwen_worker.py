"""Qwen Model Studio adapter with a strictly scoped local tool bridge.

The model receives only a task prompt and an allowlist of paths in the current
isolated workspace.  It may read a listed path on demand.  When enabled by the
harness, it may also ask a hard-capped Grok worker for an assistive result.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


DEFAULT_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-max"
# A Qwen task may make at most six model/tool rounds in total. Web-enabled
# tasks reserve up to half for a short evidence docket and carry the remaining
# budget into the final proof/audit stage.
MAX_TOOL_ROUNDS = 6
MAX_WEB_EVIDENCE_TOOL_ROUNDS = 3
MAX_FILE_BYTES = 1_000_000
WEB_EVIDENCE_MAX_TOKENS = 6_000
WEB_EVIDENCE_THINKING_BUDGET = 2_048
MAX_WEB_EVIDENCE_CHARS = 32_000
WEB_EVIDENCE_TIMEOUT_SECONDS = 3_600


def _responses_timeout() -> int:
    raw = os.environ.get("QWEN_RESPONSES_TIMEOUT", "10800")
    try:
        return max(1, min(int(raw), 10_800))
    except ValueError:
        return 10_800


def _api_key() -> Optional[str]:
    return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")


def _base_url() -> str:
    return (
        os.environ.get("QWEN_BASE_URL")
        or os.environ.get("DASHSCOPE_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def _request(
    *, api_key: str, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
    max_tokens: int, thinking_budget: int, tool_choice: str = "auto",
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "enable_thinking": True,
        "thinking_budget": thinking_budget,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    request = urllib.request.Request(
        _base_url() + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_responses_timeout()) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            error = json.loads(raw).get("error", {})
        except json.JSONDecodeError:
            error = {"message": raw[:500]}
        raise RuntimeError("Qwen API HTTP %d: %s" % (exc.code, error)) from exc
    except Exception as exc:  # noqa: BLE001 - present provider errors to the runner
        raise RuntimeError("Qwen API request failed: %s" % exc) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Qwen API returned a non-object response")
    return payload


def _responses_request(
    *,
    api_key: str,
    model: str,
    input_items: List[Dict[str, Any]],
    instructions: str,
    previous_response_id: Optional[str],
    max_tokens: int,
    thinking_budget: int,
    enable_thinking: bool = True,
    timeout_seconds: Optional[int] = None,
    allow_tools: bool = True,
) -> Dict[str, Any]:
    """Call Qwen's Responses API, which exposes native web tools for 3.7 Max."""
    body: Dict[str, Any] = {
        "model": model,
        "input": input_items,
        "instructions": instructions,
        "store": True,
        "max_output_tokens": max_tokens,
    }
    body["tools"] = [
        {"type": "web_search"},
        {"type": "web_extractor"},
        {
            "type": "function",
            "name": "read_file",
            "description": "Read one file from the isolated task workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    ]
    body["tool_choice"] = "auto" if allow_tools else "none"
    if enable_thinking:
        body["enable_thinking"] = True
        body["thinking"] = {"budget_tokens": thinking_budget}
    else:
        body["enable_thinking"] = False
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    request = urllib.request.Request(
        _base_url() + "/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "x-dashscope-session-cache": "enable",
        },
        method="POST",
    )
    try:
        request_timeout = (
            _responses_timeout() if timeout_seconds is None else timeout_seconds
        )
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        raise RuntimeError("Qwen Responses API HTTP %d: %s" % (exc.code, raw[:1000])) from exc
    except Exception as exc:  # noqa: BLE001 - present provider errors to the runner
        raise RuntimeError("Qwen Responses API request failed: %s" % exc) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Qwen Responses API returned a non-object response")
    return payload


def _tools(allow_grok: bool) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read one file from the isolated task workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    if allow_grok:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "ask_grok",
                    "description": (
                        "Ask a bounded, read-only Grok worker for an assistive "
                        "mathematical or research check. Its result is untrusted "
                        "working context and must be independently verified."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["prompt"],
                        "additionalProperties": False,
                    },
                },
            }
        )
    return tools


def _allowlist(paths: Iterable[str]) -> Dict[str, Path]:
    root = Path.cwd().resolve()
    allowed: Dict[str, Path] = {}
    for item in paths:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            allowed[relative.as_posix()] = candidate
    return allowed


def _tool_arguments(call: Dict[str, Any]) -> Dict[str, Any]:
    function = call.get("function")
    raw = function.get("arguments", "{}") if isinstance(function, dict) else "{}"
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _read_file(arguments: Dict[str, Any], allowlist: Dict[str, Path]) -> Dict[str, Any]:
    path = arguments.get("path")
    if not isinstance(path, str) or path not in allowlist:
        return {"ok": False, "error": "path is not in the task allowlist"}
    source = allowlist[path]
    size = source.stat().st_size
    if size > MAX_FILE_BYTES:
        return {
            "ok": False,
            "error": "file is too large for a single read; use a smaller supplied file",
            "bytes": size,
        }
    return {"ok": True, "path": path, "content": source.read_text(encoding="utf-8")}


def _ask_grok(arguments: Dict[str, Any], pool: Any) -> Dict[str, Any]:
    prompt = arguments.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return {"ok": False, "error": "ask_grok requires a non-empty prompt"}
    from pure_tate.grok_workers import PoolError

    try:
        result = pool.dispatch(
            prompt,
            str(arguments.get("description") or "qwen-assist"),
            wait=True,
        )
    except PoolError as exc:
        return exc.as_dict()
    return {
        "ok": result.get("status") == "completed",
        "worker_id": result.get("worker_id"),
        "status": result.get("status"),
        "result_text": result.get("result_text", ""),
        "error": result.get("error"),
    }


def _assistant_message(message: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content") or "",
    }
    if isinstance(message.get("tool_calls"), list):
        out["tool_calls"] = message["tool_calls"]
    # Model Studio returns reasoning in a separate field. Preserve it across
    # tool rounds when present rather than injecting it into visible content.
    if isinstance(message.get("reasoning_content"), str):
        out["reasoning_content"] = message["reasoning_content"]
    return out


def _responses_text(payload: Dict[str, Any]) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text:
        return text
    parts: List[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts)


def _responses_function_calls(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        item
        for item in payload.get("output", [])
        if isinstance(item, dict) and item.get("type") == "function_call"
    ]


def _run_web_evidence(
    prompt: str,
    allowlist: Dict[str, Path],
    *,
    api_key: str,
    model: str,
    max_tokens: int,
    thinking_budget: int,
) -> str:
    names = "\n".join("- " + path for path in sorted(allowlist)) or "- (none)"
    instructions = (
        "You are stage 1 of a read-only Pure Tate task. Build a compact evidence "
        "docket for the later proof/audit agent, not the final task artifact. "
        "Use native web_search and web_extractor only when current sources are "
        "needed; prefer at most two searches and two extractions. You may read "
        "only the listed workspace files through read_file. Return promptly with "
        "source URLs, the precise claims they support, and any caveats. Do not "
        "attempt the full proof, write a long exposition, or return final JSON.\n\n"
        "Allowed workspace files:\n" + names
    )
    pending: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    previous_response_id: Optional[str] = None
    for _round in range(MAX_WEB_EVIDENCE_TOOL_ROUNDS):
        final_round = _round == MAX_WEB_EVIDENCE_TOOL_ROUNDS - 1
        payload = _responses_request(
            api_key=api_key,
            model=model,
            input_items=pending,
            instructions=instructions,
            previous_response_id=previous_response_id,
            max_tokens=min(max_tokens, WEB_EVIDENCE_MAX_TOKENS),
            thinking_budget=min(thinking_budget, WEB_EVIDENCE_THINKING_BUDGET),
            # The Singapore Qwen3.7-Max endpoint requires thinking mode when
            # web_extractor is present, even for a compact evidence docket.
            enable_thinking=True,
            timeout_seconds=WEB_EVIDENCE_TIMEOUT_SECONDS,
            allow_tools=not final_round,
        )
        previous_response_id = str(payload.get("id") or "") or None
        calls = _responses_function_calls(payload)
        if not calls:
            content = _responses_text(payload)
            if content:
                return content[:MAX_WEB_EVIDENCE_CHARS]
            raise RuntimeError("Qwen Responses API returned no final text")
        if final_round:
            raise RuntimeError(
                "Qwen web-evidence stage returned a tool call during its "
                "tool-free final round"
            )
        pending = []
        for call in calls:
            arguments = call.get("arguments", "{}")
            try:
                parsed = json.loads(arguments) if isinstance(arguments, str) else {}
            except json.JSONDecodeError:
                parsed = {}
            result = (
                _read_file(parsed if isinstance(parsed, dict) else {}, allowlist)
                if call.get("name") == "read_file"
                else {"ok": False, "error": "tool is unavailable"}
            )
            call_id = call.get("call_id")
            if not isinstance(call_id, str) or not call_id:
                raise RuntimeError("Qwen Responses function call has no call_id")
            pending.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )
    raise RuntimeError(
        "Qwen web-evidence stage exceeded the %d tool-round limit"
        % MAX_WEB_EVIDENCE_TOOL_ROUNDS
    )


def _run_without_web(
    prompt: str,
    allowlist: Dict[str, Path],
    *,
    api_key: str,
    model: str,
    allow_grok: bool,
    max_tokens: int,
    thinking_budget: int,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
) -> str:
    """Run the final task through Chat Completions and local bounded tools."""
    grok_pool: Optional[Any] = None
    if allow_grok:
        from pure_tate.grok_workers import build_pool_from_env

        # One pool per Qwen turn enforces its total-dispatch cap across every
        # ask_grok call the model makes during this conversation.
        grok_pool = build_pool_from_env()
    names = "\n".join("- " + path for path in sorted(allowlist)) or "- (none)"
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a read-only Pure Tate task agent. You may access only "
                "the listed workspace files through read_file. Do not invent file "
                "contents. Return the required final JSON artifact as plain text.\n\n"
                "Allowed workspace files:\n" + names
            ),
        },
        {"role": "user", "content": prompt},
    ]
    tools = _tools(allow_grok)
    try:
        for _round in range(max_tool_rounds):
            final_round = _round == max_tool_rounds - 1
            if final_round:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The tool budget is exhausted. Do not request any "
                            "more tools. Synthesize the required final JSON "
                            "artifact now from the context already gathered."
                        ),
                    }
                )
            payload = _request(
                api_key=api_key,
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                thinking_budget=thinking_budget,
                tool_choice="none" if final_round else "auto",
            )
            choices = payload.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise RuntimeError("Qwen API response has no completion choice")
            message = choices[0].get("message")
            if not isinstance(message, dict):
                raise RuntimeError("Qwen API response has no assistant message")
            calls = message.get("tool_calls")
            if not isinstance(calls, list) or not calls:
                content = message.get("content")
                if not isinstance(content, str):
                    raise RuntimeError("Qwen API response has no final text")
                return content
            if final_round:
                raise RuntimeError(
                    "Qwen returned a tool call during its tool-free final round"
                )
            messages.append(_assistant_message(message))
            for call in calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                name = function.get("name") if isinstance(function, dict) else ""
                arguments = _tool_arguments(call)
                if name == "read_file":
                    result = _read_file(arguments, allowlist)
                elif name == "ask_grok" and grok_pool is not None:
                    result = _ask_grok(arguments, grok_pool)
                else:
                    result = {"ok": False, "error": "tool is unavailable"}
                call_id = call.get("id")
                if not isinstance(call_id, str) or not call_id:
                    raise RuntimeError("Qwen tool call has no id")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        raise RuntimeError("Qwen exceeded the %d tool-round limit" % max_tool_rounds)
    finally:
        if grok_pool is not None:
            grok_pool.shutdown(cancel_live=True)


def run(
    prompt: str,
    context_files: Iterable[str],
    *,
    model: str,
    allow_grok: bool,
    allow_web: bool,
    max_tokens: int,
    thinking_budget: int,
) -> str:
    key = _api_key()
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY or QWEN_API_KEY is not set")
    allowlist = _allowlist(context_files)
    final_tool_rounds = MAX_TOOL_ROUNDS
    if allow_web:
        try:
            evidence = _run_web_evidence(
                prompt,
                allowlist,
                api_key=key,
                model=model,
                max_tokens=max_tokens,
                thinking_budget=thinking_budget,
            )
        except RuntimeError as exc:
            evidence = (
                "Native web-evidence stage was bounded and unavailable: %s. "
                "Do not invent web findings. Use supplied local sources and, "
                "when enabled, a bounded Grok helper for any indispensable "
                "live-source check; state any remaining evidence limitation."
                % str(exc)[:1000]
            )
        prompt = (
            prompt
            + "\n\n--- Stage-1 web evidence docket (untrusted working context; "
            "verify it and now complete the requested final artifact) ---\n"
            + evidence
        )
        final_tool_rounds -= MAX_WEB_EVIDENCE_TOOL_ROUNDS
    return _run_without_web(
        prompt,
        allowlist,
        api_key=key,
        model=model,
        allow_grok=allow_grok,
        max_tokens=max_tokens,
        thinking_budget=thinking_budget,
        max_tool_rounds=final_tool_rounds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--context-file", action="append", default=[])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--allow-grok-workers", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=64000)
    parser.add_argument("--thinking-budget", type=int, default=16384)
    args = parser.parse_args()
    try:
        sys.stdout.write(
            run(
                args.prompt,
                args.context_file,
                model=args.model,
                allow_grok=args.allow_grok_workers,
                allow_web=args.allow_web,
                max_tokens=args.max_tokens,
                thinking_budget=args.thinking_budget,
            )
        )
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # noqa: BLE001 - subprocess error boundary
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
