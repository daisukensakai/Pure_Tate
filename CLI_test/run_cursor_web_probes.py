#!/usr/bin/env python3
"""Diagnose Cursor Agent CLI web fetch under worker-like argv variants.

Isolated lab only — not loaded by the Pure Tate harness.
"""

from __future__ import annotations

import argparse
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
RESULTS_ROOT = LAB / "results" / "cursor_web"
MODEL = "cursor-grok-4.5-high"
TIMEOUT_SECONDS = 180
EXAMPLE_URL = "https://example.com"
SUCCESS_MARKER = "Example Domain"

PROMPT = (
    "Fetch %s using a web fetch / browse / web search tool (not memory). "
    "In your final answer, quote the exact visible title or main heading "
    "text from the live page. It must include the words Example Domain. "
    "Do not invent the title if the fetch fails; say FETCH_FAILED instead."
) % EXAMPLE_URL


VARIANTS: List[Dict[str, Any]] = [
    {
        "name": "A_ask_noforce",
        "flags": ["--trust", "--mode", "ask"],
        "note": "current harness worker argv",
    },
    {
        "name": "B_ask_force",
        "flags": ["--trust", "--mode", "ask", "--force"],
        "note": "ask + force auto-approve",
    },
    {
        "name": "C_ask_sandbox_disabled",
        "flags": ["--trust", "--mode", "ask", "--sandbox", "disabled"],
        "note": "ask + sandbox disabled",
    },
    {
        "name": "D_print_force",
        "flags": ["--trust", "--force"],
        "note": "print mode (no --mode ask) + force",
    },
    {
        "name": "E_print_force_sandbox_disabled",
        "flags": ["--trust", "--force", "--sandbox", "disabled"],
        "note": "print + force + sandbox disabled",
    },
    {
        "name": "F_print_only",
        "flags": ["--trust"],
        "note": "print + trust only (baseline agent mode)",
    },
    {
        "name": "G_plan_force",
        "flags": ["--trust", "--mode", "plan", "--force"],
        "note": "plan mode + force",
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
    raise SystemExit("cursor-agent / cursor not on PATH")


def require_api_key() -> None:
    if not os.environ.get("CURSOR_API_KEY", "").strip():
        raise SystemExit(
            "CURSOR_API_KEY unset; run via: "
            "zsh -lic 'python3 CLI_test/run_cursor_web_probes.py'"
        )


def classify(result_text: str) -> Dict[str, Any]:
    text = result_text or ""
    lower = text.lower()
    return {
        "has_success_marker": SUCCESS_MARKER in text,
        "fetch_failed_token": "FETCH_FAILED" in text,
        "user_rejected": "user rejected" in lower,
        "blocked": "blocked" in lower or "rejected" in lower,
        "mentions_example_com": "example.com" in lower,
        "result_prefix": text[:400],
    }


def run_variant(
    variant: Dict[str, Any],
    *,
    agent_argv: Sequence[str],
    model: str,
    run_dir: Path,
    env: Dict[str, str],
) -> Dict[str, Any]:
    name = str(variant["name"])
    argv = [
        *agent_argv,
        "-p",
        *list(variant["flags"]),
        "--output-format",
        "json",
        "--model",
        model,
        "--workspace",
        str(LAB),
        PROMPT,
    ]
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
    stdout_path = run_dir / (name + ".stdout.json")
    stderr_path = run_dir / (name + ".stderr.txt")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    parsed: Optional[Dict[str, Any]] = None
    parse_error = None
    result_text = ""
    is_error = None
    try:
        value = json.loads(stdout.strip()) if stdout.strip() else None
        if isinstance(value, dict):
            parsed = value
            result_text = str(value.get("result") or "")
            is_error = value.get("is_error")
        else:
            parse_error = "stdout JSON was not an object"
            result_text = stdout
    except json.JSONDecodeError as exc:
        parse_error = str(exc)
        result_text = stdout

    verdict = classify(result_text)
    passed = bool(verdict["has_success_marker"]) and not bool(is_error)
    redacted = list(argv)
    for index, item in enumerate(redacted):
        if item == PROMPT:
            redacted[index] = "<prompt-sha256:%s>" % sha256_bytes(
                PROMPT.encode("utf-8")
            )
    metadata = {
        "schema_version": 1,
        "variant": name,
        "note": variant.get("note"),
        "flags": list(variant["flags"]),
        "model_requested": model,
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "parse_error": parse_error,
        "is_error": is_error,
        "passed": passed,
        "verdict": verdict,
        "argv": redacted,
        "stdout_path": str(stdout_path.relative_to(ROOT)),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
    }
    (run_dir / (name + ".metadata.json")).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe Cursor Agent CLI web fetch argv variants."
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only named variant(s).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    require_api_key()
    agent_argv = resolve_agent_argv()
    variants = VARIANTS
    if args.only:
        wanted = set(args.only)
        variants = [item for item in VARIANTS if item["name"] in wanted]
        missing = sorted(wanted - {item["name"] for item in variants})
        if missing:
            raise SystemExit("Unknown variant(s): %s" % ", ".join(missing))

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    results = [
        run_variant(
            variant,
            agent_argv=agent_argv,
            model=args.model,
            run_dir=run_dir,
            env=dict(os.environ),
        )
        for variant in variants
    ]
    winners = [item["variant"] for item in results if item["passed"]]
    manifest = {
        "schema_version": 1,
        "model_requested": args.model,
        "prompt_sha256": sha256_bytes(PROMPT.encode("utf-8")),
        "success_marker": SUCCESS_MARKER,
        "url": EXAMPLE_URL,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "winners": winners,
        "variants": results,
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
    # Lab probe: exit 0 even if some variants fail; winners drive the fix.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
