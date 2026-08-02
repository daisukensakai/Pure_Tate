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


BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-max"
API_KEY_ENV = "DASHSCOPE_API_KEY"
MAX_TOOL_ROUNDS = 8
MAX_FILE_BYTES = 1_000_000


def _responses_timeout() -> int:
    raw = os.environ.get("QWEN_RESPONSES_TIMEOUT", "2700")
    try:
        return max(1, min(int(raw), 3600))
    except ValueError:
        return 180


def _max_tool_rounds() -> int:
    """Return a bounded per-invocation tool-turn limit.

    A provider can impose a shorter response-stream deadline than the harness.
    Keeping the default preserves the normal multi-stage workflow, while an
    operator can request a one-turn Qwen attempt with
    ``QWEN_MAX_TOOL_ROUNDS=1`` when diagnosing that deadline.
    """
    raw = os.environ.get("QWEN_MAX_TOOL_ROUNDS", str(MAX_TOOL_ROUNDS))
    try:
        return max(1, min(int(raw), MAX_TOOL_ROUNDS))
    except ValueError:
        return MAX_TOOL_ROUNDS


def _api_key() -> Optional[str]:
    return os.environ.get(API_KEY_ENV)


def _request(
    *, api_key: str, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
    max_tokens: int, thinking_budget: int,
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
        body["tool_choice"] = "auto"
    request = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
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
) -> Dict[str, Any]:
    """Call Qwen's Responses API, which exposes native web tools for 3.7 Max."""
    body: Dict[str, Any] = {
        "model": model,
        "input": input_items,
        "instructions": instructions,
        "tools": [
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
        ],
        "enable_thinking": True,
        "max_output_tokens": max_tokens,
        "thinking": {"budget_tokens": thinking_budget},
    }
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    request = urllib.request.Request(
        BASE_URL + "/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_responses_timeout()) as response:
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


def _run_with_web(
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
        "You are a read-only Pure Tate task agent. Use native web_search and "
        "web_extractor for current sources when needed. You may read only the "
        "listed workspace files through read_file. Return the required final "
        "JSON artifact as plain text.\n\nAllowed workspace files:\n" + names
    )
    pending: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    previous_response_id: Optional[str] = None
    max_tool_rounds = _max_tool_rounds()
    for _round in range(max_tool_rounds):
        payload = _responses_request(
            api_key=api_key,
            model=model,
            input_items=pending,
            instructions=instructions,
            previous_response_id=previous_response_id,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
        )
        previous_response_id = str(payload.get("id") or "") or None
        calls = _responses_function_calls(payload)
        if not calls:
            content = _responses_text(payload)
            if content:
                return content
            raise RuntimeError("Qwen Responses API returned no final text")
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
        "Qwen Responses API exceeded the %d tool-round limit" % max_tool_rounds
    )


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
        raise RuntimeError("%s is not set" % API_KEY_ENV)
    allowlist = _allowlist(context_files)
    if allow_web:
        return _run_with_web(
            prompt,
            allowlist,
            api_key=key,
            model=model,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
        )
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
        max_tool_rounds = _max_tool_rounds()
        for _round in range(max_tool_rounds):
            payload = _request(
                api_key=key,
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                thinking_budget=thinking_budget,
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
