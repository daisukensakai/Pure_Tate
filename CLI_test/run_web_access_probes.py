#!/usr/bin/env python3
"""Isolated CLI probes: can each engine use web tools when enabled?

Nothing here is imported by pure_tate. Results land under
CLI_test/results/web_access/<timestamp>/.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "CLI_test"
RESULTS_ROOT = LAB / "results" / "web_access"
TIMEOUT_SECONDS = 180

HELIUM_PROMPT = (
    "You must use a web search tool at least once. Look up the atomic number of "
    "helium. Return exactly one JSON object and no Markdown fences or surrounding "
    "prose with keys probe, ok, answer, tool_used. Set probe to "
    '"web_search_smoke", ok to true, answer to the integer atomic number, and '
    "tool_used to true only if you actually invoked a web search or fetch tool."
)

MATH_OPTIONAL_PROMPT = (
    "State the degree of the canonical bundle omega_C on a smooth projective "
    "curve of genus 6 (answer should be 10). You may use web tools if helpful; "
    "they are optional. Return exactly one JSON object and no Markdown fences "
    "with keys probe, ok, answer, web_used. Set probe to "
    '"optional_web_math_style", ok to true, answer to the integer degree, and '
    "web_used to true only if you invoked a web search or fetch tool."
)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def timestamp_slug() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y%m%dT%H%M%S%fZ")
    )


def redacted_argv(argv: Sequence[str], prompt: str) -> List[str]:
    out = list(argv)
    digest = "<prompt-sha256:%s>" % sha256_bytes(prompt.encode("utf-8"))
    for flag in ("-p", "--prompt"):
        if flag in out:
            idx = out.index(flag)
            if idx + 1 < len(out):
                out[idx + 1] = digest
    # codex puts prompt as final positional
    if out and out[-1] == prompt:
        out[-1] = digest
    return out


def _object_from_text(blob: str) -> Optional[Dict[str, Any]]:
    start = blob.find("{")
    end = blob.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def extract_json_object(text: str, engine: str = "") -> Optional[Dict[str, Any]]:
    """Best-effort final JSON object from plain text or stream-json lines."""
    # Engine-specific stream reassembly first.
    if engine == "grok":
        parts: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("type") == "text"
                and isinstance(event.get("data"), str)
            ):
                parts.append(event["data"])
        obj = _object_from_text("".join(parts))
        if obj is not None:
            return obj
    if engine == "claude":
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("type") == "result"
                and isinstance(event.get("result"), str)
            ):
                obj = _object_from_text(event["result"])
                if obj is not None:
                    return obj
    if engine == "codex":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") if isinstance(event, dict) else None
            if (
                isinstance(item, dict)
                and item.get("type") == "agent_message"
                and isinstance(item.get("text"), str)
            ):
                obj = _object_from_text(item["text"])
                if obj is not None:
                    return obj
    if engine == "gemini":
        chunks: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("type") == "message"
                and event.get("role") == "assistant"
                and isinstance(event.get("content"), str)
            ):
                chunks.append(event["content"])
        obj = _object_from_text("".join(chunks))
        if obj is not None:
            return obj

    candidates: List[str] = []
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            if line.startswith("{"):
                try:
                    env = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(env, dict):
                    for key in ("result", "response", "text", "message", "content"):
                        inner = env.get(key)
                        if isinstance(inner, str) and "{" in inner:
                            candidates.append(inner)
                        elif isinstance(inner, dict) and "probe" in inner:
                            return inner
            continue
        if isinstance(value, dict):
            if "probe" in value:
                return value
            for key in ("result", "response", "text", "message", "content"):
                inner = value.get(key)
                if isinstance(inner, str) and "{" in inner:
                    candidates.append(inner)
                elif isinstance(inner, dict) and "probe" in inner:
                    return inner
    candidates.append(text)
    for blob in candidates:
        obj = _object_from_text(blob)
        if obj is not None:
            return obj
    return None


def tool_evidence(text: str, engine: str = "") -> Dict[str, Any]:
    lowered = text.lower()
    patterns = {
        "web_search": r"\bweb[_-]?search\b|websearch|google_web_search",
        "web_fetch": r"\bweb[_-]?fetch\b|webfetch",
        "open_page": r"\bopen_page\b",
        "browser": r"\bbrowser\b",
        "search_query": r"\bsearch_query\b|\"query\"\s*:",
        "tool_use_search": r'"type"\s*:\s*"web_search"|tool_name"\s*:\s*"google_web_search"',
    }
    hits = {
        name: bool(re.search(pat, lowered)) for name, pat in patterns.items()
    }
    # Structured stream evidence per engine.
    if engine == "codex":
        for line in text.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item") if isinstance(event, dict) else None
            if isinstance(item, dict) and item.get("type") == "web_search":
                hits["web_search"] = True
    if engine == "gemini":
        for line in text.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(event, dict)
                and event.get("type") == "tool_use"
                and "search" in str(event.get("tool_name", "")).lower()
            ):
                hits["web_search"] = True
    return {
        "any_web_signal": any(hits.values()),
        "signals": hits,
    }


def run_command(
    argv: List[str],
    *,
    prompt: str,
    out_dir: Path,
    name: str,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
        timed_out = False
        returncode = completed.returncode
        stdout_b = completed.stdout
        stderr_b = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = -1
        stdout_b = exc.stdout or b""
        stderr_b = exc.stderr or b""
    elapsed = time.monotonic() - started
    stdout = stdout_b.decode("utf-8", "replace") if isinstance(stdout_b, bytes) else str(stdout_b or "")
    stderr = stderr_b.decode("utf-8", "replace") if isinstance(stderr_b, bytes) else str(stderr_b or "")
    stdout_path = out_dir / (name + ".stdout.txt")
    stderr_path = out_dir / (name + ".stderr.txt")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    engine_hint = name.split("__", 1)[0] if "__" in name else ""
    parsed = extract_json_object(stdout, engine_hint) or extract_json_object(
        stderr, engine_hint
    )
    evidence = tool_evidence(stdout + "\n" + stderr, engine_hint)
    metadata = {
        "schema_version": 1,
        "name": name,
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "argv": redacted_argv(argv, prompt),
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 3),
        "stdout_path": str(stdout_path.relative_to(ROOT)),
        "stderr_path": str(stderr_path.relative_to(ROOT)),
        "stdout_sha256": sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(stderr.encode("utf-8")),
        "parsed_json": parsed,
        "tool_evidence": evidence,
        "binaries_present": {
            "grok": bool(shutil.which("grok")),
            "claude": bool(shutil.which("claude")),
            "codex": bool(shutil.which("codex")),
            "gemini": bool(shutil.which("gemini")),
        },
    }
    (out_dir / (name + ".metadata.json")).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def classify_smoke(meta: Dict[str, Any], *, expect_tool: bool) -> str:
    if meta.get("timed_out"):
        return "fail_timeout"
    parsed = meta.get("parsed_json") or {}
    answer = parsed.get("answer")
    ok_answer = answer == 2 or answer == "2"
    if meta.get("returncode") not in (0, None) and not ok_answer:
        # some CLIs return non-zero even with usable output
        if not parsed:
            return "fail"
    evidence = meta.get("tool_evidence") or {}
    tool_used_field = parsed.get("tool_used")
    if ok_answer and (
        (expect_tool and (tool_used_field is True or evidence.get("any_web_signal")))
        or (not expect_tool)
    ):
        if expect_tool and not (
            tool_used_field is True or evidence.get("any_web_signal")
        ):
            return "answer_ok_but_no_tool_evidence"
        return "pass"
    if ok_answer:
        return "answer_ok_but_no_tool_evidence"
    if parsed:
        return "fail_wrong_answer"
    return "fail"


def classify_math(meta: Dict[str, Any]) -> str:
    if meta.get("timed_out"):
        return "fail_timeout"
    parsed = meta.get("parsed_json") or {}
    answer = parsed.get("answer")
    if answer == 10 or answer == "10":
        return "pass"
    if parsed:
        return "fail_wrong_answer"
    if meta.get("returncode") == 0:
        return "fail_unparsed"
    return "fail"


def build_grok(prompt: str) -> List[str]:
    return [
        "grok",
        "-p",
        prompt,
        "--output-format",
        "streaming-json",
        "--max-turns",
        "12",
        "--permission-mode",
        "dontAsk",
        "--always-approve",
        "--tools",
        "read_file,grep,list_dir,web_search,web_fetch",
        "--disallowed-tools",
        "run_terminal_command,write,open_page",
        "-m",
        "grok-4.6",
    ]


def build_claude(prompt: str) -> List[str]:
    return [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--permission-mode",
        "default",
        "--allowedTools",
        "Read",
        "Grep",
        "Glob",
        "WebSearch",
        "WebFetch",
        "--disallowedTools",
        "Edit",
        "Write",
        "Bash",
        "--model",
        "claude-opus-5",
    ]


def build_codex(prompt: str) -> List[str]:
    # Mirror harness read-only sandbox; observe whether web is possible.
    return [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "-m",
        "gpt-5.6-sol",
        "--sandbox",
        "read-only",
        "-c",
        'approval_policy="never"',
        "--json",
        prompt,
    ]


def build_gemini(prompt: str, *, approval_mode: str) -> List[str]:
    return [
        "gemini",
        "-p",
        prompt,
        "-m",
        "gemini-3.5-flash",
        "-o",
        "stream-json",
        "--approval-mode",
        approval_mode,
        "--skip-trust",
    ]


def run_suite(run_dir: Path) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []

    def add(
        engine: str,
        probe: str,
        argv: List[str],
        prompt: str,
        classifier,
    ) -> None:
        name = "%s__%s" % (engine, probe)
        print("RUN", name, flush=True)
        meta = run_command(argv, prompt=prompt, out_dir=run_dir, name=name)
        meta["engine"] = engine
        meta["probe"] = probe
        meta["classification"] = classifier(meta)
        results.append(meta)
        print(
            "  ->",
            meta["classification"],
            "rc=",
            meta["returncode"],
            "elapsed=",
            meta["elapsed_seconds"],
            flush=True,
        )

    # Grok
    if shutil.which("grok"):
        add(
            "grok",
            "web_search_smoke",
            build_grok(HELIUM_PROMPT),
            HELIUM_PROMPT,
            lambda m: classify_smoke(m, expect_tool=True),
        )
        add(
            "grok",
            "optional_web_math_style",
            build_grok(MATH_OPTIONAL_PROMPT),
            MATH_OPTIONAL_PROMPT,
            classify_math,
        )
    else:
        results.append(
            {
                "engine": "grok",
                "probe": "missing_binary",
                "classification": "tools_unavailable",
            }
        )

    # Claude
    if shutil.which("claude"):
        add(
            "claude",
            "web_search_smoke",
            build_claude(HELIUM_PROMPT),
            HELIUM_PROMPT,
            lambda m: classify_smoke(m, expect_tool=True),
        )
        add(
            "claude",
            "optional_web_math_style",
            build_claude(MATH_OPTIONAL_PROMPT),
            MATH_OPTIONAL_PROMPT,
            classify_math,
        )
    else:
        results.append(
            {
                "engine": "claude",
                "probe": "missing_binary",
                "classification": "tools_unavailable",
            }
        )

    # Codex
    if shutil.which("codex"):
        add(
            "codex",
            "web_search_smoke",
            build_codex(HELIUM_PROMPT),
            HELIUM_PROMPT,
            lambda m: classify_smoke(m, expect_tool=True),
        )
    else:
        results.append(
            {
                "engine": "codex",
                "probe": "missing_binary",
                "classification": "tools_unavailable",
            }
        )

    # Gemini: plan (harness default) vs yolo
    if shutil.which("gemini"):
        add(
            "gemini",
            "web_search_smoke_plan",
            build_gemini(HELIUM_PROMPT, approval_mode="plan"),
            HELIUM_PROMPT,
            lambda m: classify_smoke(m, expect_tool=True),
        )
        add(
            "gemini",
            "web_search_smoke_yolo",
            build_gemini(HELIUM_PROMPT, approval_mode="yolo"),
            HELIUM_PROMPT,
            lambda m: classify_smoke(m, expect_tool=True),
        )
    else:
        results.append(
            {
                "engine": "gemini",
                "probe": "missing_binary",
                "classification": "tools_unavailable",
            }
        )

    by_engine: Dict[str, List[str]] = {}
    for item in results:
        by_engine.setdefault(str(item.get("engine")), []).append(
            str(item.get("classification"))
        )

    def engine_verdict(engine: str) -> str:
        classes = by_engine.get(engine, ["tools_unavailable"])
        if any(c == "pass" for c in classes):
            # Prefer smoke pass
            smoke = [
                item
                for item in results
                if item.get("engine") == engine
                and "web_search" in str(item.get("probe", ""))
            ]
            if smoke and any(s.get("classification") == "pass" for s in smoke):
                return "pass"
            if any(c == "pass" for c in classes):
                return "partial_pass"
        if any("unavailable" in c for c in classes):
            return "tools_unavailable"
        if any(c.startswith("fail") or c.startswith("answer_ok") for c in classes):
            if any(c == "answer_ok_but_no_tool_evidence" for c in classes):
                return "answer_ok_but_no_tool_evidence"
            return "fail"
        return "unknown"

    summary = {
        "schema_version": 1,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "engine_verdicts": {
            engine: engine_verdict(engine)
            for engine in ("grok", "claude", "codex", "gemini")
        },
        "results": results,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (RESULTS_ROOT / "latest.txt").write_text(
        str(run_dir.relative_to(ROOT)) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    run_dir = RESULTS_ROOT / timestamp_slug()
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = run_suite(run_dir)
    print(json.dumps(summary["engine_verdicts"], indent=2, sort_keys=True))
    print("manifest:", summary["run_dir"] + "/manifest.json")
    # Gate: Grok and Claude smoke should pass for Stage B.
    verdicts = summary["engine_verdicts"]
    ok = verdicts.get("grok") == "pass" and verdicts.get("claude") == "pass"
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
