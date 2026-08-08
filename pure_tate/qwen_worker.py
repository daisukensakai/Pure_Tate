"""Qwen Model Studio adapter with a strictly scoped local tool bridge.

The model receives only a task prompt and an allowlist of paths in the current
isolated workspace.  It may read a listed path on demand.  When enabled by the
harness, it may also ask a hard-capped Grok worker for an assistive result.

Stdout protocol (JSONL, one object per line, flushed immediately):
  stage, heartbeat, thought, text, tool_call, tool_result, error, end

Provider calls use Server-Sent Events by default so the campaign inactivity
watchdog sees progress and partial tokens survive process kill in traces.
Set QWEN_STREAM=0 to force non-streaming requests (emergency only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, TextIO


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


DEFAULT_BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-max"
DEFAULT_REASONING_EFFORT = "xhigh"
# reasoning_effort levels for Qwen3.8-Max: xhigh (default), medium, low.
VALID_REASONING_EFFORTS = frozenset({"xhigh", "medium", "low"})
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
# Heartbeats while waiting for the first SSE byte keep the harness inactivity
# watchdog from treating long prefill/thinking as a dead process.
HEARTBEAT_INTERVAL_SECONDS = 15.0


def _responses_timeout() -> int:
    raw = os.environ.get("QWEN_RESPONSES_TIMEOUT", "10800")
    try:
        return max(1, min(int(raw), 10_800))
    except ValueError:
        return 10_800


def _stream_enabled() -> bool:
    raw = os.environ.get("QWEN_STREAM", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _api_key() -> Optional[str]:
    return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")


def _base_url() -> str:
    return (
        os.environ.get("QWEN_BASE_URL")
        or os.environ.get("DASHSCOPE_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def _emit(event: Dict[str, Any], stream: Optional[TextIO] = None) -> None:
    """Write one JSONL progress event and flush (resets harness inactivity)."""
    out = stream if stream is not None else sys.stdout
    out.write(json.dumps(event, ensure_ascii=False) + "\n")
    out.flush()


class _FirstByteHeartbeat:
    """Emit heartbeat events until the first SSE payload arrives."""

    def __init__(
        self,
        label: str,
        interval: float = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self.label = label
        self.interval = interval
        self._stop = threading.Event()
        self._first_byte = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.started = 0.0

    def __enter__(self) -> "_FirstByteHeartbeat":
        self.started = time.monotonic()
        self._thread = threading.Thread(
            target=self._run, name="qwen-hb-" + self.label, daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def mark_first_byte(self) -> None:
        self._first_byte.set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            if self._first_byte.is_set():
                return
            _emit(
                {
                    "type": "heartbeat",
                    "stage": self.label,
                    "elapsed_seconds": round(time.monotonic() - self.started, 1),
                }
            )


def _iter_sse_json(response: Any) -> Iterator[Dict[str, Any]]:
    """Yield JSON objects from an OpenAI-compatible SSE response body."""
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", "replace")
        else:
            line = str(raw_line)
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            payload = line[5:].strip()
        else:
            # Some gateways omit the data: prefix.
            payload = line
        if payload == "[DONE]":
            break
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield parsed


def _http_error_message(exc: urllib.error.HTTPError, prefix: str) -> str:
    raw = exc.read().decode("utf-8", "replace")
    try:
        error = json.loads(raw).get("error", {})
        if isinstance(error, dict):
            return "%s HTTP %d: %s" % (prefix, exc.code, error)
    except json.JSONDecodeError:
        pass
    return "%s HTTP %d: %s" % (prefix, exc.code, raw[:1000])


def _merge_tool_call_delta(
    buckets: Dict[int, Dict[str, Any]], delta_calls: List[Any]
) -> None:
    for item in delta_calls:
        if not isinstance(item, dict):
            continue
        index = item.get("index", 0)
        try:
            index_i = int(index)
        except (TypeError, ValueError):
            index_i = 0
        bucket = buckets.setdefault(
            index_i,
            {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            },
        )
        if isinstance(item.get("id"), str) and item["id"]:
            bucket["id"] = item["id"]
        if isinstance(item.get("type"), str) and item["type"]:
            bucket["type"] = item["type"]
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        fn = bucket["function"]
        if isinstance(function.get("name"), str) and function["name"]:
            # Name is usually sent once on the first delta; do not concatenate.
            if not fn.get("name"):
                fn["name"] = function["name"]
        if isinstance(function.get("arguments"), str):
            fn["arguments"] = (fn.get("arguments") or "") + function["arguments"]


def _consume_chat_sse(
    response: Any, *, stage: str
) -> Dict[str, Any]:
    """Reassemble a Chat Completions stream into a non-stream payload shape."""
    content_parts: List[str] = []
    reasoning_parts: List[str] = []
    tool_buckets: Dict[int, Dict[str, Any]] = {}
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    response_id: Optional[str] = None
    model: Optional[str] = None
    with _FirstByteHeartbeat(stage) as heartbeat:
        for chunk in _iter_sse_json(response):
            heartbeat.mark_first_byte()
            if isinstance(chunk.get("id"), str) and chunk["id"]:
                response_id = chunk["id"]
            if isinstance(chunk.get("model"), str) and chunk["model"]:
                model = chunk["model"]
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            choice = choices[0]
            if not isinstance(choice, dict):
                continue
            if isinstance(choice.get("finish_reason"), str):
                finish_reason = choice["finish_reason"]
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                # Some non-incremental builds put a full message on the chunk.
                message = choice.get("message")
                if isinstance(message, dict):
                    if isinstance(message.get("content"), str) and message["content"]:
                        content_parts.append(message["content"])
                        _emit({"type": "text", "data": message["content"]})
                    if (
                        isinstance(message.get("reasoning_content"), str)
                        and message["reasoning_content"]
                    ):
                        reasoning_parts.append(message["reasoning_content"])
                        _emit(
                            {
                                "type": "thought",
                                "data": message["reasoning_content"],
                            }
                        )
                continue
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                reasoning_parts.append(reasoning)
                _emit({"type": "thought", "data": reasoning})
            content = delta.get("content")
            if isinstance(content, str) and content:
                content_parts.append(content)
                _emit({"type": "text", "data": content})
            tool_calls = delta.get("tool_calls")
            if isinstance(tool_calls, list):
                _merge_tool_call_delta(tool_buckets, tool_calls)
    content = "".join(content_parts)
    reasoning_content = "".join(reasoning_parts)
    tool_calls_list = [
        tool_buckets[index]
        for index in sorted(tool_buckets)
        if tool_buckets[index].get("function", {}).get("name")
        or tool_buckets[index].get("id")
    ]
    for call in tool_calls_list:
        _emit(
            {
                "type": "tool_call",
                "id": call.get("id"),
                "name": (call.get("function") or {}).get("name"),
                "arguments": (call.get("function") or {}).get("arguments"),
            }
        )
    message: Dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if reasoning_content:
        message["reasoning_content"] = reasoning_content
    if tool_calls_list:
        message["tool_calls"] = tool_calls_list
    payload: Dict[str, Any] = {
        "id": response_id,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason or ("tool_calls" if tool_calls_list else "stop"),
            }
        ],
    }
    if usage is not None:
        payload["usage"] = usage
    _emit(
        {
            "type": "end",
            "stage": stage,
            "stopReason": finish_reason or ("tool_calls" if tool_calls_list else "stop"),
            "id": response_id,
            "usage": usage,
        }
    )
    return payload


def _consume_responses_sse(
    response: Any, *, stage: str
) -> Dict[str, Any]:
    """Reassemble a Responses API stream into a non-stream payload shape."""
    text_parts: List[str] = []
    reasoning_parts: List[str] = []
    output_items: Dict[str, Dict[str, Any]] = {}
    output_order: List[str] = []
    completed: Optional[Dict[str, Any]] = None
    response_id: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

    def _remember_item(item: Dict[str, Any]) -> None:
        item_id = item.get("id")
        key = str(item_id) if isinstance(item_id, str) and item_id else "anon-%d" % len(output_order)
        if key not in output_items:
            output_order.append(key)
        output_items[key] = item

    with _FirstByteHeartbeat(stage) as heartbeat:
        for event in _iter_sse_json(response):
            heartbeat.mark_first_byte()
            event_type = event.get("type")
            if event_type in {"response.created", "response.in_progress"}:
                response_obj = event.get("response")
                if isinstance(response_obj, dict):
                    if isinstance(response_obj.get("id"), str):
                        response_id = response_obj["id"]
                    if isinstance(response_obj.get("model"), str):
                        model = response_obj["model"]
                    if isinstance(response_obj.get("status"), str):
                        status = response_obj["status"]
                continue
            if event_type == "response.output_text.delta":
                delta = event.get("delta")
                if isinstance(delta, str) and delta:
                    text_parts.append(delta)
                    _emit({"type": "text", "data": delta})
                continue
            if event_type in {
                "response.reasoning_text.delta",
                "response.reasoning_summary_text.delta",
            }:
                delta = event.get("delta")
                if isinstance(delta, str) and delta:
                    reasoning_parts.append(delta)
                    _emit({"type": "thought", "data": delta})
                continue
            if event_type == "response.output_item.added":
                item = event.get("item")
                if isinstance(item, dict):
                    _remember_item(item)
                continue
            if event_type == "response.output_item.done":
                item = event.get("item")
                if isinstance(item, dict):
                    _remember_item(item)
                    item_type = item.get("type")
                    if item_type in {
                        "function_call",
                        "web_search_call",
                        "web_extractor_call",
                    }:
                        _emit(
                            {
                                "type": "tool_call",
                                "item_type": item_type,
                                "id": item.get("id"),
                                "call_id": item.get("call_id"),
                                "name": item.get("name"),
                                "arguments": item.get("arguments"),
                                "status": item.get("status"),
                            }
                        )
                    if item_type == "reasoning":
                        for summary in item.get("summary") or []:
                            if isinstance(summary, dict) and isinstance(
                                summary.get("text"), str
                            ):
                                reasoning_parts.append(summary["text"])
                                _emit(
                                    {"type": "thought", "data": summary["text"]}
                                )
                continue
            if event_type == "response.completed":
                response_obj = event.get("response")
                if isinstance(response_obj, dict):
                    completed = response_obj
                    if isinstance(response_obj.get("id"), str):
                        response_id = response_obj["id"]
                    if isinstance(response_obj.get("model"), str):
                        model = response_obj["model"]
                    if isinstance(response_obj.get("usage"), dict):
                        usage = response_obj["usage"]
                    if isinstance(response_obj.get("status"), str):
                        status = response_obj["status"]
                continue
            if event_type == "error" or event.get("error"):
                err = event.get("error") or event
                message = (
                    err.get("message")
                    if isinstance(err, dict)
                    else str(err)
                )
                _emit({"type": "error", "message": message})
                raise RuntimeError("Qwen Responses stream error: %s" % message)

    if completed is not None:
        payload = completed
        # Ensure stream-assembled text is available even if the provider omits
        # top-level output_text on the completed object.
        if not isinstance(payload.get("output_text"), str) or not payload["output_text"]:
            joined = "".join(text_parts)
            if joined:
                payload = dict(payload)
                payload["output_text"] = joined
        if not payload.get("output") and output_items:
            payload = dict(payload)
            payload["output"] = [output_items[key] for key in output_order]
    else:
        joined = "".join(text_parts)
        output_list = [output_items[key] for key in output_order]
        if joined and not any(
            isinstance(item, dict) and item.get("type") == "message"
            for item in output_list
        ):
            output_list.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": joined}],
                }
            )
        payload = {
            "id": response_id,
            "model": model,
            "status": status or "completed",
            "output": output_list,
            "output_text": joined,
        }
        if usage is not None:
            payload["usage"] = usage

    # If the completed payload has message text that never arrived as deltas,
    # surface it once for artifact extraction and activity.
    final_text = _responses_text(payload)
    streamed = "".join(text_parts)
    if final_text and final_text != streamed and not streamed:
        _emit({"type": "text", "data": final_text})

    _emit(
        {
            "type": "end",
            "stage": stage,
            "stopReason": status or "completed",
            "id": payload.get("id") or response_id,
            "usage": payload.get("usage") or usage,
        }
    )
    return payload


def _normalize_reasoning_effort(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text not in VALID_REASONING_EFFORTS:
        raise ValueError(
            "reasoning_effort must be one of %s (got %r)"
            % (sorted(VALID_REASONING_EFFORTS), value)
        )
    return text


def _request(
    *, api_key: str, model: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
    max_tokens: int, thinking_budget: int, tool_choice: str = "auto",
    stage: str = "chat",
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "enable_thinking": True,
    }
    # Qwen3.8-Max: reasoning_effort and thinking_budget are mutually exclusive.
    # Prefer effort levels (xhigh/medium/low) when configured.
    effort = _normalize_reasoning_effort(reasoning_effort)
    if effort:
        body["reasoning_effort"] = effort
    else:
        body["thinking_budget"] = thinking_budget
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    use_stream = _stream_enabled()
    if use_stream:
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
    request = urllib.request.Request(
        _base_url() + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_responses_timeout()) as response:
            if use_stream:
                return _consume_chat_sse(response, stage=stage)
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = _http_error_message(exc, "Qwen API")
        _emit({"type": "error", "message": detail})
        raise RuntimeError(detail) from exc
    except Exception as exc:  # noqa: BLE001 - present provider errors to the runner
        detail = "Qwen API request failed: %s" % exc
        _emit({"type": "error", "message": detail})
        raise RuntimeError(detail) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Qwen API returned a non-object response")
    # Non-stream path: emit the full content as a single text event so the
    # harness still sees activity and can extract an artifact.
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            if isinstance(message.get("reasoning_content"), str) and message[
                "reasoning_content"
            ]:
                _emit({"type": "thought", "data": message["reasoning_content"]})
            if isinstance(message.get("content"), str) and message["content"]:
                _emit({"type": "text", "data": message["content"]})
            if isinstance(message.get("tool_calls"), list):
                for call in message["tool_calls"]:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function") if isinstance(call.get("function"), dict) else {}
                    _emit(
                        {
                            "type": "tool_call",
                            "id": call.get("id"),
                            "name": function.get("name"),
                            "arguments": function.get("arguments"),
                        }
                    )
    _emit(
        {
            "type": "end",
            "stage": stage,
            "stopReason": "stop",
            "id": payload.get("id"),
            "usage": payload.get("usage"),
        }
    )
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
    stage: str = "responses",
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """Call Qwen's Responses API, which exposes native web tools for Max models."""
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
        # Same mutual exclusion as chat completions: effort OR budget, not both.
        effort = _normalize_reasoning_effort(reasoning_effort)
        if effort:
            body["reasoning_effort"] = effort
        else:
            body["thinking"] = {"budget_tokens": thinking_budget}
    else:
        body["enable_thinking"] = False
    if previous_response_id:
        body["previous_response_id"] = previous_response_id
    use_stream = _stream_enabled()
    if use_stream:
        body["stream"] = True
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
            if use_stream:
                return _consume_responses_sse(response, stage=stage)
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = _http_error_message(exc, "Qwen Responses API")
        _emit({"type": "error", "message": detail})
        raise RuntimeError(detail) from exc
    except Exception as exc:  # noqa: BLE001 - present provider errors to the runner
        detail = "Qwen Responses API request failed: %s" % exc
        _emit({"type": "error", "message": detail})
        raise RuntimeError(detail) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Qwen Responses API returned a non-object response")
    text = _responses_text(payload)
    if text:
        _emit({"type": "text", "data": text})
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {
            "function_call",
            "web_search_call",
            "web_extractor_call",
        }:
            _emit(
                {
                    "type": "tool_call",
                    "item_type": item.get("type"),
                    "id": item.get("id"),
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": item.get("arguments"),
                    "status": item.get("status"),
                }
            )
    _emit(
        {
            "type": "end",
            "stage": stage,
            "stopReason": payload.get("status") or "completed",
            "id": payload.get("id"),
            "usage": payload.get("usage"),
        }
    )
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


def _tool_result_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Compact tool result for stdout (avoid dumping huge file contents)."""
    summary: Dict[str, Any] = {"ok": result.get("ok")}
    if "path" in result:
        summary["path"] = result["path"]
    if "error" in result:
        summary["error"] = result["error"]
    if "bytes" in result:
        summary["bytes"] = result["bytes"]
    content = result.get("content")
    if isinstance(content, str):
        summary["content_chars"] = len(content)
    if "worker_id" in result:
        summary["worker_id"] = result["worker_id"]
    if "status" in result:
        summary["status"] = result["status"]
    return summary


def _run_web_evidence(
    prompt: str,
    allowlist: Dict[str, Path],
    *,
    api_key: str,
    model: str,
    max_tokens: int,
    thinking_budget: int,
    reasoning_effort: Optional[str] = None,
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
    _emit({"type": "stage", "stage": "web_evidence_start"})
    try:
        for _round in range(MAX_WEB_EVIDENCE_TOOL_ROUNDS):
            final_round = _round == MAX_WEB_EVIDENCE_TOOL_ROUNDS - 1
            stage = "web_evidence_round_%d" % (_round + 1)
            _emit(
                {
                    "type": "stage",
                    "stage": stage,
                    "round": _round + 1,
                    "allow_tools": not final_round,
                }
            )
            payload = _responses_request(
                api_key=api_key,
                model=model,
                input_items=pending,
                instructions=instructions,
                previous_response_id=previous_response_id,
                max_tokens=min(max_tokens, WEB_EVIDENCE_MAX_TOKENS),
                thinking_budget=min(thinking_budget, WEB_EVIDENCE_THINKING_BUDGET),
                # Max models require thinking mode when web_extractor is present,
                # even for a compact evidence docket.
                enable_thinking=True,
                timeout_seconds=WEB_EVIDENCE_TIMEOUT_SECONDS,
                allow_tools=not final_round,
                stage=stage,
                # Keep evidence stage cheap; final proof turn uses full effort.
                reasoning_effort="low" if reasoning_effort else None,
            )
            previous_response_id = str(payload.get("id") or "") or None
            calls = _responses_function_calls(payload)
            if not calls:
                content = _responses_text(payload)
                if content:
                    _emit({"type": "stage", "stage": "web_evidence_end", "ok": True})
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
                _emit(
                    {
                        "type": "tool_result",
                        "name": call.get("name"),
                        "call_id": call.get("call_id"),
                        "result": _tool_result_summary(result),
                    }
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
    except Exception:
        _emit({"type": "stage", "stage": "web_evidence_end", "ok": False})
        raise


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
    reasoning_effort: Optional[str] = None,
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
    _emit({"type": "stage", "stage": "final_start"})
    try:
        for _round in range(max_tool_rounds):
            final_round = _round == max_tool_rounds - 1
            stage = "final_round_%d" % (_round + 1)
            _emit(
                {
                    "type": "stage",
                    "stage": stage,
                    "round": _round + 1,
                    "allow_tools": not final_round,
                }
            )
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
                stage=stage,
                reasoning_effort=reasoning_effort,
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
                _emit({"type": "stage", "stage": "final_end", "ok": True})
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
                _emit(
                    {
                        "type": "tool_result",
                        "name": name,
                        "id": call.get("id"),
                        "result": _tool_result_summary(result),
                    }
                )
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
    except Exception:
        _emit({"type": "stage", "stage": "final_end", "ok": False})
        raise
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
    reasoning_effort: Optional[str] = None,
) -> str:
    key = _api_key()
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY or QWEN_API_KEY is not set")
    allowlist = _allowlist(context_files)
    effort = _normalize_reasoning_effort(reasoning_effort) or DEFAULT_REASONING_EFFORT
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
                reasoning_effort=effort,
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
        reasoning_effort=effort,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--context-file", action="append", default=[])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--allow-grok-workers", action="store_true")
    parser.add_argument("--allow-web", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=65536)
    parser.add_argument("--thinking-budget", type=int, default=65536)
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_REASONING_EFFORT,
        choices=sorted(VALID_REASONING_EFFORTS),
        help="Qwen3.8 reasoning depth: xhigh (default), medium, or low",
    )
    args = parser.parse_args()
    try:
        # Progress and artifact text are emitted as JSONL on stdout during the
        # run. The harness reconstructs the final artifact from text events.
        run(
            args.prompt,
            args.context_file,
            model=args.model,
            allow_grok=args.allow_grok_workers,
            allow_web=args.allow_web,
            max_tokens=args.max_tokens,
            thinking_budget=args.thinking_budget,
            reasoning_effort=args.reasoning_effort,
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - subprocess error boundary
        try:
            _emit({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001 - never mask the real failure
            pass
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
