#!/usr/bin/env python3
"""Run bounded, read-only Cursor Agent CLI probes pinned to Cursor Grok 4.5."""

from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "CLI_test"
RESULTS_ROOT = LAB / "results" / "cursor_grok"
MODEL = "cursor-grok-4.5-high"
TIMEOUT_SECONDS = 300


PROBES: List[Dict[str, Any]] = [
    {
        "name": "basic",
        "output_format": "stream-json",
        "prompt": (
            "Return exactly one JSON object and no Markdown or surrounding prose. "
            "Use exactly this value: "
            '{"probe":"basic","ok":true,"latex":"\\\\Gamma and \\\\omega_C"}.'
        ),
    },
    {
        "name": "read_tool",
        "output_format": "stream-json",
        "prompt": (
            "Read CLI_test/read_fixture.txt using a read-file tool. Then return "
            "exactly one JSON object and no Markdown or surrounding prose with "
            'keys "probe", "ok", "marker", and "latex". Set probe to "read_tool", '
            "ok to true, marker to the first line of the file, and latex to the "
            "mathematical payload line exactly as plain text."
        ),
    },
    {
        "name": "json_format",
        "output_format": "json",
        "prompt": (
            "Return exactly one JSON object and no Markdown or surrounding prose. "
            "Use exactly this value: "
            '{"probe":"json_format","ok":true,"latex":"\\\\Gamma and \\\\omega_C"}.'
        ),
    },
]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def resolve_agent_argv() -> List[str]:
    cursor_agent = shutil.which("cursor-agent")
    if cursor_agent:
        return [cursor_agent]
    cursor = shutil.which("cursor")
    if cursor:
        return [cursor, "agent"]
    raise SystemExit(
        "Neither cursor-agent nor cursor was found on PATH. "
        "Install the Cursor Agent CLI before running these probes."
    )


def require_api_key() -> str:
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "CURSOR_API_KEY is unset. Export it (e.g. via ~/.zshrc) or run:\n"
            "  zsh -lic 'python3 CLI_test/run_cursor_grok_probes.py'"
        )
    return key


def event_summary(stdout: str, *, output_format: str) -> Dict[str, Any]:
    if output_format == "json":
        stripped = stdout.strip()
        if not stripped:
            return {
                "format": "json",
                "parsed": False,
                "error": "empty stdout",
                "value": None,
            }
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return {
                "format": "json",
                "parsed": False,
                "error": str(exc),
                "prefix": stripped[:240],
                "value": None,
            }
        model = None
        result_text = None
        if isinstance(value, dict):
            model = value.get("model")
            result_text = value.get("result")
        return {
            "format": "json",
            "parsed": True,
            "error": None,
            "top_level_keys": (
                sorted(str(key) for key in value.keys())
                if isinstance(value, dict)
                else None
            ),
            "type": value.get("type") if isinstance(value, dict) else None,
            "subtype": value.get("subtype") if isinstance(value, dict) else None,
            "model": model,
            "result_prefix": (
                result_text[:240] if isinstance(result_text, str) else None
            ),
            "value": value if isinstance(value, dict) else {"non_object": value},
        }

    parsed: List[Dict[str, Any]] = []
    invalid_lines: List[Dict[str, Any]] = []
    for number, line in enumerate(stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid_lines.append(
                {"line": number, "error": str(exc), "prefix": line[:160]}
            )
            continue
        if isinstance(value, dict):
            parsed.append(value)
        else:
            invalid_lines.append(
                {
                    "line": number,
                    "error": "JSON value is not an object",
                    "prefix": line[:160],
                }
            )

    type_counts = collections.Counter(
        str(event.get("type", "<missing>")) for event in parsed
    )
    subtype_counts = collections.Counter(
        "%s/%s"
        % (
            event.get("type", "<missing>"),
            event.get("subtype", "<none>"),
        )
        for event in parsed
    )
    key_shapes = collections.Counter(
        ",".join(sorted(str(key) for key in event)) for event in parsed
    )

    init_model = None
    for event in parsed:
        if event.get("type") == "system" and event.get("subtype") == "init":
            init_model = event.get("model")
            break

    tool_names: List[str] = []
    for event in parsed:
        if event.get("type") != "tool_call":
            continue
        tool_call = event.get("tool_call")
        if not isinstance(tool_call, dict):
            continue
        tool_names.extend(sorted(str(key) for key in tool_call.keys()))

    result_event = next(
        (event for event in reversed(parsed) if event.get("type") == "result"),
        None,
    )
    return {
        "format": "stream-json",
        "line_count": len(stdout.splitlines()),
        "parsed_event_count": len(parsed),
        "invalid_lines": invalid_lines,
        "event_type_counts": dict(sorted(type_counts.items())),
        "event_subtype_counts": dict(sorted(subtype_counts.items())),
        "event_key_shapes": dict(sorted(key_shapes.items())),
        "init_model": init_model,
        "tool_call_keys": sorted(set(tool_names)),
        "result_subtype": (
            result_event.get("subtype") if isinstance(result_event, dict) else None
        ),
        "result_is_error": (
            result_event.get("is_error") if isinstance(result_event, dict) else None
        ),
        "result_prefix": (
            str(result_event.get("result"))[:240]
            if isinstance(result_event, dict) and result_event.get("result") is not None
            else None
        ),
        "first_event": parsed[0] if parsed else None,
        "last_event": parsed[-1] if parsed else None,
    }


def redact_argv(argv: Sequence[str], prompt: str) -> List[str]:
    redacted = list(argv)
    prompt_token = "<prompt-sha256:%s>" % sha256_bytes(prompt.encode("utf-8"))
    for index, value in enumerate(redacted):
        if value == prompt:
            redacted[index] = prompt_token
    return redacted


def run_probe(
    probe: Dict[str, Any],
    *,
    agent_argv: Sequence[str],
    model: str,
    run_dir: Path,
    env: Dict[str, str],
) -> Dict[str, Any]:
    prompt = str(probe["prompt"])
    output_format = str(probe["output_format"])
    argv = [
        *agent_argv,
        "-p",
        "--trust",
        "--mode",
        "ask",
        "--output-format",
        output_format,
        "--model",
        model,
        "--workspace",
        str(ROOT),
        prompt,
    ]
    if output_format == "stream-json":
        # Keep default aggregation (one assistant event per message segment).
        # Partial deltas are optional and noisier for fixture comparison.
        pass

    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    elapsed = time.monotonic() - started
    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    name = str(probe["name"])

    stdout_path = run_dir / (name + ".stdout.jsonl")
    if output_format == "json":
        stdout_path = run_dir / (name + ".stdout.json")
    stderr_path = run_dir / (name + ".stderr.txt")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    summary = event_summary(stdout, output_format=output_format)
    metadata = {
        "schema_version": 1,
        "probe": name,
        "model_requested": model,
        "output_format": output_format,
        "mode": "ask",
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent_argv0": list(agent_argv),
        "argv": redact_argv(argv, prompt),
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "stdout_path": str(stdout_path.relative_to(ROOT)),
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "summary": summary,
    }
    metadata_path = run_dir / (name + ".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def select_probes(only: Optional[Sequence[str]]) -> List[Dict[str, Any]]:
    if not only:
        return list(PROBES)
    wanted = set(only)
    selected = [probe for probe in PROBES if probe["name"] in wanted]
    missing = sorted(wanted - {str(probe["name"]) for probe in selected})
    if missing:
        raise SystemExit("Unknown probe name(s): %s" % ", ".join(missing))
    return selected


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe Cursor Agent CLI with Cursor Grok 4.5 (read-only)."
    )
    parser.add_argument(
        "--model",
        default=MODEL,
        help="Cursor model slug (default: %s)" % MODEL,
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only the named probe (repeatable).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    require_api_key()
    agent_argv = resolve_agent_argv()
    probes = select_probes(args.only)

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    # Never pass the key on argv; rely on the process environment only.
    results = [
        run_probe(
            probe,
            agent_argv=agent_argv,
            model=args.model,
            run_dir=run_dir,
            env=env,
        )
        for probe in probes
    ]
    manifest = {
        "schema_version": 1,
        "model_requested": args.model,
        "agent_argv0": list(agent_argv),
        "run_dir": str(run_dir.relative_to(ROOT)),
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cursor_api_key_present": True,
        "probes": results,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (RESULTS_ROOT / "latest.txt").write_text(
        str(run_dir.relative_to(ROOT)) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if all(item["returncode"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
