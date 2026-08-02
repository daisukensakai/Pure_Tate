#!/usr/bin/env python3
"""Minimal, redacted Qwen Model Studio connectivity probe.

Run from an interactive shell when the credential lives in shell startup files:
    zsh -ic 'python3 CLI_test/run_qwen_diagnostics.py'

The script never prints credentials or request headers.  It uses Model Studio's
OpenAI-compatible Chat Completions endpoint and performs exactly one request.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
TOKEN_PLAN_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-max"
KEY_ENVIRONMENTS = ("DASHSCOPE_API_KEY", "QWEN_API_KEY")


def _credential() -> Tuple[Optional[str], Optional[str]]:
    for name in KEY_ENVIRONMENTS:
        value = os.environ.get(name)
        if value:
            return name, value
    return None, None


def _endpoint(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def _default_base_url(api_key: str) -> str:
    """Choose the documented Model Studio endpoint for the credential family."""
    return TOKEN_PLAN_BASE_URL if api_key.startswith("sk-sp-") else DEFAULT_BASE_URL


def _error_payload(raw: bytes) -> Dict[str, Any]:
    text = raw.decode("utf-8", "replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"message": text[:500]}
    if isinstance(parsed, dict):
        error = parsed.get("error")
        return error if isinstance(error, dict) else parsed
    return {"message": text[:500]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible base URL (overrides environment and key-type defaults)",
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    key_name, api_key = _credential()
    if api_key is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No Qwen credential found",
                    "checked_environments": list(KEY_ENVIRONMENTS),
                }
            )
        )
        return 2

    base_url = (
        args.base_url
        or os.environ.get("QWEN_BASE_URL")
        or os.environ.get("DASHSCOPE_BASE_URL")
        or _default_base_url(api_key)
    )

    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": "Reply exactly: QWEN_WORKING"}],
        "temperature": 0,
        "max_tokens": 16,
        # qwen3.7-max is a hybrid-thinking model. This keeps the smoke test
        # minimal and avoids paying for an unnecessary reasoning trace.
        "enable_thinking": False,
    }
    request = urllib.request.Request(
        _endpoint(base_url),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "credential_environment": key_name,
                    "base_url": base_url,
                    "model": args.model,
                    "http": exc.code,
                    "error": _error_payload(exc.read()),
                },
                sort_keys=True,
            )
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic utility
        print(
            json.dumps(
                {
                    "ok": False,
                    "credential_environment": key_name,
                    "base_url": base_url,
                    "model": args.model,
                    "error": {"message": str(exc)},
                },
                sort_keys=True,
            )
        )
        return 1

    choices = payload.get("choices") if isinstance(payload, dict) else None
    message = choices[0].get("message", {}) if isinstance(choices, list) and choices else {}
    content = message.get("content") if isinstance(message, dict) else None
    result = {
        "ok": isinstance(content, str) and content.strip() == "QWEN_WORKING",
        "credential_environment": key_name,
        "base_url": base_url,
        "model": payload.get("model", args.model) if isinstance(payload, dict) else args.model,
        "response": content,
        "usage": payload.get("usage") if isinstance(payload, dict) else None,
        "request_id": payload.get("id") if isinstance(payload, dict) else None,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
