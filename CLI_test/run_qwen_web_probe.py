#!/usr/bin/env python3
"""Probe Qwen3.7-Max Responses API web search plus extraction.

Run through an interactive zsh so the locally configured Token Plan key is
available:
    zsh -ic 'python3 CLI_test/run_qwen_web_probe.py'

The script prints a compact receipt only; it never writes credentials or raw
provider reasoning to the repository.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


BASE_URL = "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
TARGET_URL = "https://api.github.com/repos/Macaulay2/M2/commits/HEAD"


def main() -> int:
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if not api_key:
        print(json.dumps({"ok": False, "error": "Qwen API key is not configured"}))
        return 2
    prompt = (
        "Use web search and web extraction to fetch %s. Return exactly JSON with "
        "keys url, commit_sha, web_search_used, web_extractor_used. "
        "Set each boolean true only if that tool was actually used." % TARGET_URL
    )
    request = urllib.request.Request(
        BASE_URL + "/responses",
        data=json.dumps(
            {
                "model": "qwen3.7-max",
                "input": prompt,
                "tools": [{"type": "web_search"}, {"type": "web_extractor"}],
                "enable_thinking": True,
            }
        ).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "http_status": exc.code,
                    "error": exc.read().decode("utf-8", "replace")[:1000],
                }
            )
        )
        return 1
    except OSError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    output = payload.get("output", []) if isinstance(payload, dict) else []
    tool_types = sorted(
        {
            str(item.get("type"))
            for item in output
            if isinstance(item, dict) and isinstance(item.get("type"), str)
        }
    )
    text = str(payload.get("output_text", ""))
    print(
        json.dumps(
            {
                "ok": "web_search_call" in tool_types
                and "web_extractor_call" in tool_types,
                "model": payload.get("model"),
                "tool_types": tool_types,
                "output_text": text[:1500],
                "usage_x_tools": payload.get("usage", {}).get("x_tools", {}),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
