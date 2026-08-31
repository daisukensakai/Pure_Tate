#!/usr/bin/env python3
"""Grok P1 Lean faithfulness review of LATT-0002 / LC66-002 only."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import (
    _engine_argv,
    _extract_grok_stream,
    _subprocess_env,
    load_engines,
)
from pure_tate.lean_campaign import load_campaign, sha256_path, validate_review
from pure_tate.process_runner import ProcessWatchdogError, run_captured_process
from pure_tate.store import atomic_write_json, load_json

CAMPAIGN_ID = "LC66-002"
ATTEMPT_ID = "LATT-0002"
REVIEW_ID = "LREV-0003"
TASK_ID = "TASK-LV-LATT-0002-P1"
ENGINE = "grok"
TIMEOUT = 10800
VAULT = Path(__file__).resolve().parent
OUTPUT = ROOT / "formal" / "reviews" / (REVIEW_ID + ".json")
RUN_PATH = ROOT / "reports" / "runs" / "RUN-LC66-002-LATT-0002-GROK-P1.json"
PROMPT = "formal/dispatch/LREV-0003-grok-p1-latt0002.md"
CONTEXT_FILES = [
    PROMPT,
    "formal/prompts/REVIEW.md",
    "formal/templates/REVIEW_TEMPLATE.json",
    "formal/campaigns/LC66-002.json",
    "formal/TrustedC66Target.lean.inc",
    "formal/C66SeparatedSignature.lean.inc",
    "formal/attempts/LATT-0002-codex-repair-c66/manifest.json",
    "formal/attempts/LATT-0002-codex-repair-c66/Claim.lean",
    "formal/attempts/LATT-0002-codex-repair-c66/Model.lean",
    "formal/attempts/LATT-0002-codex-repair-c66/report.json",
    "proof/attempts/ATT-0136.json",
    "proof/reviews/REV-0187.json",
    "proof/reviews/REV-0188.json",
    "pure_tate/lean_campaign.py",
]


def _copy_context(destination: Path) -> list[str]:
    copied = []
    for relative in CONTEXT_FILES:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative)
    task = {
        "id": TASK_ID,
        "phase": "lean-review",
        "role": "independent-lean-faithfulness-reviewer",
        "campaign_id": CAMPAIGN_ID,
        "target_attempt_id": ATTEMPT_ID,
        "review_pass": 1,
        "reviewer_engine": ENGINE,
        "excluded_reviewer_engines": ["codex"],
        "prompt": PROMPT,
        "output": str(OUTPUT.relative_to(ROOT)),
        "status": "ready",
    }
    atomic_write_json(destination / "TASK.json", task)
    copied.append("TASK.json")
    return copied


def _coerce_identity(review: dict) -> dict:
    review = dict(review)
    review["schema_version"] = 1
    review["id"] = REVIEW_ID
    review["attempt_id"] = ATTEMPT_ID
    review["campaign_id"] = CAMPAIGN_ID
    review["review_pass"] = 1
    review["review_task_id"] = TASK_ID
    review["review_run_path"] = str(RUN_PATH.relative_to(ROOT))
    review["reviewer_engine"] = ENGINE
    review["independent"] = True
    return review


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("%s already exists" % OUTPUT)
    campaign = load_campaign(CAMPAIGN_ID)
    report_path = (
        ROOT / "formal" / "attempts" / "LATT-0002-codex-repair-c66" / "report.json"
    )
    launch = {
        "campaign_id": CAMPAIGN_ID,
        "target_attempt_id": ATTEMPT_ID,
        "task_id": TASK_ID,
        "engine": ENGINE,
        "review_id": REVIEW_ID,
        "status": "running",
    }
    atomic_write_json(VAULT / "LAUNCH.json", launch)
    workspace = Path(tempfile.mkdtemp(prefix="pure-tate-lrev-0003-"))
    try:
        copied = _copy_context(workspace)
        prompt = (
            (ROOT / PROMPT).read_text(encoding="utf-8").strip()
            + "\n\n# Execution contract\n\n"
            "You are in an isolated, read-only task workspace. Read TASK.json and "
            "the curated files listed below. Do not search outside this workspace. "
            "Do not read LATT-0001, LC66-001, LREV-0001, or LREV-0002.\n\n"
            + "\n".join("- " + item for item in copied)
            + "\n\nReturn exactly one JSON object matching "
            "formal/templates/REVIEW_TEMPLATE.json. Do not use Markdown fences. "
            "The JSON object's id must be exactly: %s\n"
            "The JSON object's reviewer_engine field must be exactly: %s\n"
            % (REVIEW_ID, ENGINE)
        )
        engines = load_engines()
        env = _subprocess_env("grok", engines[ENGINE])
        command = _engine_argv(
            ENGINE,
            prompt,
            phase="review",
            workspace=workspace,
        )
        process = run_captured_process(
            command,
            cwd=workspace,
            env=env,
            timeout=TIMEOUT,
            inactivity_timeout=3600,
            activity_streams=["stdout"],
        )
        raw = process.stdout or ""
        (VAULT / "stdout.jsonl").write_text(raw, encoding="utf-8")
        (VAULT / "stderr.txt").write_text(process.stderr or "", encoding="utf-8")
        if process.returncode != 0:
            raise RuntimeError(
                "grok exited %s: %s"
                % (process.returncode, (process.stderr or raw)[:2000])
            )
        review = _coerce_identity(_extract_grok_stream(raw))
        atomic_write_json(OUTPUT, review)
        review["_path"] = str(OUTPUT)
        receipt = {
            "schema_version": 1,
            "run_id": "RUN-LC66-002-LATT-0002-GROK-P1",
            "status": "completed",
            "events": [
                {
                    "phase": "lean-review",
                    "state": "completed",
                    "review_id": REVIEW_ID,
                    "target_attempt_id": ATTEMPT_ID,
                    "review_pass": 1,
                    "engine": ENGINE,
                    "task_id": TASK_ID,
                    "output": str(OUTPUT.relative_to(ROOT)),
                    "artifact_sha256": sha256_path(OUTPUT),
                }
            ],
        }
        atomic_write_json(RUN_PATH, receipt)
        check = validate_review(review, campaign, report_path)
        launch.update(
            {
                "status": "completed",
                "verdict": review.get("verdict"),
                "artifact_sha256": sha256_path(OUTPUT),
                "validation_errors": list(check.errors),
                "validation_warnings": list(check.warnings),
            }
        )
        atomic_write_json(VAULT / "LAUNCH.json", launch)
        print(json.dumps(launch, indent=2, sort_keys=True))
        return 0 if check.ok else 1
    except Exception as exc:
        launch["status"] = "failed"
        launch["error"] = str(exc)
        if not isinstance(exc, ProcessWatchdogError):
            launch["traceback"] = traceback.format_exc()
        atomic_write_json(VAULT / "LAUNCH.json", launch)
        print(json.dumps(launch, indent=2, sort_keys=True))
        return 1
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
