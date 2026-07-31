#!/usr/bin/env python3
"""Run bounded, read-only Grok streaming-json compatibility probes."""

from __future__ import annotations

import collections
import datetime
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "CLI_test"
RESULTS = LAB / "results"
MODEL = "grok-4.5"
TIMEOUT_SECONDS = 300


PROBES: List[Dict[str, Any]] = [
    {
        "name": "basic",
        "tools": "",
        "max_turns": "2",
        "prompt": (
            "Return exactly one JSON object and no Markdown or surrounding prose. "
            "Use exactly this value: "
            '{"probe":"basic","ok":true,"latex":"\\\\Gamma and \\\\omega_C"}.'
        ),
    },
    {
        "name": "read_tool",
        "tools": "read_file",
        "max_turns": "4",
        "prompt": (
            "Read CLI_test/read_fixture.txt using read_file. Then return exactly "
            "one JSON object and no Markdown or surrounding prose with keys "
            '"probe", "ok", "marker", and "latex". Set probe to "read_tool", ok '
            "to true, marker to the first line of the file, and latex to the "
            "mathematical payload line exactly as plain text."
        ),
    },
]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def event_summary(stdout: str) -> Dict[str, Any]:
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
    key_shapes = collections.Counter(
        ",".join(sorted(str(key) for key in event)) for event in parsed
    )
    return {
        "line_count": len(stdout.splitlines()),
        "parsed_event_count": len(parsed),
        "invalid_lines": invalid_lines,
        "event_type_counts": dict(sorted(type_counts.items())),
        "event_key_shapes": dict(sorted(key_shapes.items())),
        "first_event": parsed[0] if parsed else None,
        "last_event": parsed[-1] if parsed else None,
    }


def run_probe(probe: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(probe["prompt"])
    argv = [
        "grok",
        "-p",
        prompt,
        "--output-format",
        "streaming-json",
        "--max-turns",
        str(probe["max_turns"]),
        "--permission-mode",
        "dontAsk",
        "--always-approve",
        "--tools",
        str(probe["tools"]),
        "--disallowed-tools",
        "run_terminal_command,write,web_fetch,web_search,open_page",
        "--disable-web-search",
        "--model",
        MODEL,
    ]
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=ROOT,
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
    stdout_path = RESULTS / (name + ".stdout.jsonl")
    stderr_path = RESULTS / (name + ".stderr.txt")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    redacted_argv = list(argv)
    redacted_argv[redacted_argv.index("-p") + 1] = (
        "<prompt-sha256:%s>" % sha256_bytes(prompt.encode("utf-8"))
    )
    metadata = {
        "schema_version": 1,
        "probe": name,
        "model": MODEL,
        "executed_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "argv": redacted_argv,
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "stdout_path": str(stdout_path.relative_to(ROOT)),
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "summary": event_summary(stdout),
    }
    metadata_path = RESULTS / (name + ".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    results = [run_probe(probe) for probe in PROBES]
    manifest = {
        "schema_version": 1,
        "model": MODEL,
        "probes": results,
    }
    (RESULTS / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if all(item["returncode"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
