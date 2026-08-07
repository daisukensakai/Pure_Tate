#!/usr/bin/env python3
"""Principal-override: archive failed ATT-0049 forced-proof, reserve ATT-0050,
recreate the exact Claude cwd, resume session, optionally ingest the artifact.

Append-only w.r.t. existing harness artifacts. Never deletes source files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pure_tate.agents import (  # noqa: E402
    _extract_claude_stream,
    _validate_artifact,
    assemble_prompt,
    build_isolated_context,
)
from pure_tate.campaigns import campaign_packet_record, load_campaign  # noqa: E402
from pure_tate.paired import (  # noqa: E402
    attach_working_context,
    forced_task,
    working_context_records,
)
from pure_tate.run_lifecycle import (  # noqa: E402
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import ROOT as HARNESS_ROOT  # noqa: E402
from pure_tate.store import atomic_write_json  # noqa: E402

assert ROOT == HARNESS_ROOT

SESSION_ID = "e60cc354-480d-44c6-939f-ed7be7abdeec"
ORIG_CWD = Path(
    "/private/var/folders/r_/40tyr0nj6zn_yqb74rw_351c0000gn/T/"
    "pure-tate-agent-ubwi95od"
)
SESSION_JSONL = (
    Path.home()
    / ".claude/projects"
    / "-private-var-folders-r--40tyr0nj6zn-yqb74rw-351c0000gn-T-pure-tate-agent-ubwi95od"
    / f"{SESSION_ID}.jsonl"
)
PARENT_TRACE = ROOT / "research/paired-traces/TRACE-0026.json"
PARENT_LEDGER = ROOT / (
    "reports/runs/RUN-C66-001-20260806T234413727508Z-16366.json"
)
PARENT_RESERVATION = ROOT / "reports/runs/reservations/ATT-0049.json"
RUN_ID = "MANUAL-RECOVER-ATT0049-20260807"


def _ts() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def phase_archive(vault: Path) -> Dict[str, Any]:
    vault.mkdir(parents=True, exist_ok=True)
    copies = {}
    for label, src in [
        ("TRACE-0026.json", PARENT_TRACE),
        ("session.jsonl", SESSION_JSONL),
        ("run-ledger.json", PARENT_LEDGER),
        ("ATT-0049.reservation.json", PARENT_RESERVATION),
    ]:
        if not src.is_file():
            raise FileNotFoundError("missing source for archive: %s" % src)
        dest = vault / label
        if dest.exists():
            # never overwrite an existing archive copy with different content
            if _sha256(dest) != _sha256(src):
                raise RuntimeError("archive conflict: %s already exists with different content" % dest)
        else:
            shutil.copy2(src, dest)
        copies[label] = {
            "source": str(src),
            "archive": str(dest.relative_to(ROOT)),
            "sha256": _sha256(dest),
            "bytes": dest.stat().st_size,
        }

    ledger = json.loads(PARENT_LEDGER.read_text(encoding="utf-8"))
    step3 = None
    for event in ledger.get("events", []):
        if isinstance(event, dict) and event.get("step") == 3:
            step3 = event
            break
    (vault / "step3-event.json").write_text(
        json.dumps(step3, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "created_at": _ts(),
        "override": "principal_investigator_manual_session_resume",
        "policy": "append_only_no_deletes",
        "parent_attempt_id": "ATT-0049",
        "parent_trace_id": "TRACE-0026",
        "parent_session_id": SESSION_ID,
        "orig_cwd": str(ORIG_CWD),
        "copies": copies,
        "note": (
            "Archives are redundant safety copies. Originals remain in place. "
            "ATT-0049 stays spent; recovery writes a new attempt slot."
        ),
    }
    atomic_write_json(vault / "MANIFEST.json", manifest)
    (vault / "PRESERVED.md").write_text(
        "\n".join(
            [
                "# Preserved sources (not deleted)",
                "",
                "- Official stream: `research/paired-traces/TRACE-0026.json`",
                "- Claude session: `%s`" % SESSION_JSONL,
                "- Run ledger: `%s`" % PARENT_LEDGER.relative_to(ROOT),
                "- Spent reservation: `reports/runs/reservations/ATT-0049.json`",
                "- Double-confirmed lemma: `proof/attempts/ATT-0048.json` + REV-0091/0092",
                "",
                "This vault holds copies only. Recovery continues into a **new** attempt id.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def phase_reserve(vault: Path) -> Dict[str, Any]:
    artifact_id, reservation_path = reserve_prefixed_artifact(
        ROOT / "proof" / "attempts", "ATT", RUN_ID
    )
    record = json.loads(reservation_path.read_text(encoding="utf-8"))
    record.update(
        {
            "task_id": "TASK-C66-001-FORCED-FULL",
            "parent_trace_id": "TRACE-0026",
            "parent_session_id": SESSION_ID,
            "override": "principal_investigator_manual_session_resume",
            "vault": str(vault.relative_to(ROOT)),
        }
    )
    atomic_write_json(reservation_path, record)
    shutil.copy2(reservation_path, vault / (artifact_id + ".reservation.json"))
    info = {
        "artifact_id": artifact_id,
        "reservation": str(reservation_path.relative_to(ROOT)),
        "run_id": RUN_ID,
        "reserved_at": record.get("reserved_at"),
    }
    atomic_write_json(vault / "RESERVATION.json", info)
    return info


def build_task() -> Dict[str, Any]:
    campaign = load_campaign("C66-001")
    packet = campaign_packet_record("C66-001")
    task = forced_task(campaign, packet, working_context_records(campaign))
    return attach_working_context(task, campaign)


def phase_workspace(vault: Path, artifact_id: str) -> Dict[str, Any]:
    task = build_task()
    ORIG_CWD.mkdir(parents=True, exist_ok=True)
    files = build_isolated_context(task, ORIG_CWD)
    # Make workspace contents non-writable for the model posture (best-effort).
    for path in ORIG_CWD.rglob("*"):
        if path.is_file():
            mode = path.stat().st_mode
            path.chmod(mode & ~0o222)

    resume_prompt = "\n".join(
        [
            "CONTINUATION AFTER INFRASTRUCTURE FAILURE (principal override).",
            "",
            "Your previous turn was interrupted by API Error: Unable to connect to API",
            "(ConnectionRefused) after laptop sleep. The official stream is TRACE-0026.",
            "The prior attempt slot ATT-0049 is closed. You must finish into a NEW slot.",
            "",
            "You are resumed in the same isolated read-only task workspace as before.",
            "Continue your mathematical work. Do not restart from zero if you already",
            "have context; re-read files only as needed.",
            "",
            "Required first action if not already complete: read end-to-end via Read:",
            "proof/packets/generated/paired-working-context/WORKING-864c30eef5a1fdd9.md",
            "",
            "Hard contract for the final artifact:",
            "- Exactly one JSON object matching proof/CAMPAIGN_ATTEMPT_TEMPLATE.json",
            "- id must be exactly: %s" % artifact_id,
            "- engine must be exactly: claude",
            "- result_type is proof or disproof",
            "- status is claimed_complete",
            "- no gap markers",
            "- completion_attestation with resolves_exact_target true,",
            "  no_undischarged_dependencies true, not_reduction_only true,",
            "  no_problem_status_claim true, exact_problem_web_search_used false",
            "- Use the exact theorem statement from the campaign packet",
            "",
            "Public web may be used only for ordinary mathematical background or named",
            "theorems, not to search a solution of this exact problem or to decide",
            "openness. Do not claim the problem is open.",
            "",
            "Final message: exactly one JSON object, no Markdown fences, no prose",
            "before or after it.",
            "",
            "Supplied files in this workspace:",
            "\n".join("- " + f for f in files),
            "",
        ]
    )
    prompt_path = vault / "RESUME_PROMPT.txt"
    prompt_path.write_text(resume_prompt, encoding="utf-8")
    atomic_write_json(vault / "TASK.snapshot.json", task)
    listing = sorted(
        str(p.relative_to(ORIG_CWD)) for p in ORIG_CWD.rglob("*") if p.is_file()
    )
    meta = {
        "cwd": str(ORIG_CWD),
        "files": files,
        "workspace_listing": listing,
        "artifact_id": artifact_id,
        "resume_prompt": str(prompt_path.relative_to(ROOT)),
        "packet_sha256": task.get("packet_sha256"),
        "packet_binding_sha256": task.get("packet_binding_sha256"),
        "working_context": task.get("working_context"),
    }
    atomic_write_json(vault / "WORKSPACE.json", meta)
    return meta


def phase_launch(vault: Path, artifact_id: str, dry_run: bool) -> Dict[str, Any]:
    prompt = (vault / "RESUME_PROMPT.txt").read_text(encoding="utf-8")
    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = vault / ("%s.resume.stderr.txt" % artifact_id)
    console_path = vault / ("%s.resume.console.log" % artifact_id)
    pid_path = vault / ("%s.resume.pid" % artifact_id)

    env = dict(os.environ)
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "64000"

    cmd = [
        "claude",
        "-p",
        prompt,
        "--resume",
        SESSION_ID,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--permission-mode",
        "bypassPermissions",
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
        "--effort",
        "max",
    ]
    launch = {
        "cmd": cmd[:3] + ["<RESUME_PROMPT>"] + cmd[4:],
        "cwd": str(ORIG_CWD),
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
        "session_id": SESSION_ID,
        "artifact_id": artifact_id,
        "dry_run": dry_run,
        "started_at": _ts(),
    }
    atomic_write_json(vault / "LAUNCH.json", launch)
    if dry_run:
        return launch

    stdout_f = stdout_path.open("w", encoding="utf-8")
    stderr_f = stderr_path.open("w", encoding="utf-8")
    console_f = console_path.open("w", encoding="utf-8")
    console_f.write("CMD %s\nCWD %s\n" % (" ".join(cmd[:2] + ["…"] + cmd[4:]), ORIG_CWD))
    console_f.flush()
    proc = subprocess.Popen(
        cmd,
        cwd=str(ORIG_CWD),
        env=env,
        stdout=stdout_f,
        stderr=stderr_f,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid) + "\n", encoding="utf-8")
    launch["pid"] = proc.pid
    launch["status"] = "running"
    atomic_write_json(vault / "LAUNCH.json", launch)
    # Detach: do not wait here. Caller / ingest phase waits.
    stdout_f.close()
    stderr_f.close()
    console_f.write("PID %s started_at %s\n" % (proc.pid, launch["started_at"]))
    console_f.close()
    return launch


def phase_ingest(vault: Path, artifact_id: str) -> Dict[str, Any]:
    stdout_path = vault / ("%s.resume.stdout.jsonl" % artifact_id)
    if not stdout_path.is_file() or stdout_path.stat().st_size == 0:
        raise RuntimeError("resume stdout missing or empty: %s" % stdout_path)
    raw = stdout_path.read_text(encoding="utf-8", errors="replace")
    task = build_task()
    output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
    if output.exists():
        raise RuntimeError("refusing to overwrite existing %s" % output)

    receipt: Dict[str, Any] = {
        "artifact_id": artifact_id,
        "session_id": SESSION_ID,
        "parent_trace_id": "TRACE-0026",
        "override": "principal_investigator_manual_session_resume",
        "ingested_at": _ts(),
        "stdout_sha256": _sha256(stdout_path),
        "stdout_bytes": stdout_path.stat().st_size,
    }
    try:
        artifact = _extract_claude_stream(raw)
    except Exception as exc:
        receipt["status"] = "extract_failed"
        receipt["error"] = str(exc)
        atomic_write_json(vault / "RECEIPT.json", receipt)
        reservation = ROOT / "reports/runs/reservations" / (artifact_id + ".json")
        spend_artifact_reservation(
            reservation,
            reason="manual_session_resume_extract_failed",
            trace_id="TRACE-0026",
            task_id="TASK-C66-001-FORCED-FULL",
        )
        return receipt

    id_rewritten = False
    if artifact.get("id") == "ATT-0049":
        artifact["id"] = artifact_id
        id_rewritten = True
    if artifact.get("id") != artifact_id:
        receipt["status"] = "id_mismatch"
        receipt["error"] = "artifact id %r expected %r" % (
            artifact.get("id"),
            artifact_id,
        )
        receipt["raw_id"] = artifact.get("id")
        atomic_write_json(vault / "RECEIPT.json", receipt)
        spend_artifact_reservation(
            ROOT / "reports/runs/reservations" / (artifact_id + ".json"),
            reason="manual_session_resume_id_mismatch",
            trace_id="TRACE-0026",
            task_id="TASK-C66-001-FORCED-FULL",
        )
        return receipt

    if artifact.get("engine") != "claude":
        artifact["engine"] = "claude"

    try:
        _validate_artifact("mathematics", task, artifact, output, "claude")
    except Exception as exc:
        receipt["status"] = "validation_failed"
        receipt["error"] = str(exc)
        # keep extracted payload for audit, not as official attempt
        atomic_write_json(vault / ("%s.extracted.invalid.json" % artifact_id), artifact)
        atomic_write_json(vault / "RECEIPT.json", receipt)
        spend_artifact_reservation(
            ROOT / "reports/runs/reservations" / (artifact_id + ".json"),
            reason="manual_session_resume_validation_failed",
            trace_id="TRACE-0026",
            task_id="TASK-C66-001-FORCED-FULL",
        )
        return receipt

    artifact["observable_trace_id"] = "TRACE-0026"
    artifact["observable_trace_sha256"] = _sha256(PARENT_TRACE)
    artifact["recovery"] = {
        "classification": "manual_session_resume",
        "principal_override": True,
        "parent_attempt_id": "ATT-0049",
        "parent_trace_id": "TRACE-0026",
        "parent_session_id": SESSION_ID,
        "resume_stdout": str(stdout_path.relative_to(ROOT)),
        "id_rewritten_from_att0049": id_rewritten,
        "recovered_at": _ts(),
        "protect_from_overwrite": True,
        "reason": (
            "Principal investigator ordered manual Claude session resume after "
            "ConnectionRefused; new attempt slot preserves prior work without "
            "deleting outputs."
        ),
    }
    for field in (
        "paired_turn_kind",
        "paired_problem_key",
        "paired_theorem_sha256",
        "paired_attempt_policy_revision",
    ):
        if field in task:
            artifact[field] = task[field]

    atomic_write_json(output, artifact)
    receipt["status"] = "success"
    receipt["output"] = str(output.relative_to(ROOT))
    receipt["artifact_sha256"] = _sha256(output)
    receipt["result_type"] = artifact.get("result_type")
    receipt["attempt_status"] = artifact.get("status")
    receipt["id_rewritten_from_att0049"] = id_rewritten
    atomic_write_json(vault / "RECEIPT.json", receipt)
    spend_artifact_reservation(
        ROOT / "reports/runs/reservations" / (artifact_id + ".json"),
        reason="manual_session_resume_success",
        trace_id="TRACE-0026",
        task_id="TASK-C66-001-FORCED-FULL",
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vault",
        default="reports/runs/manual-recovery/ATT-0049-to-0050-20260807",
    )
    parser.add_argument(
        "--phase",
        choices=("prepare", "launch", "ingest", "all-prepare", "status"),
        default="prepare",
        help="prepare=archive+reserve+workspace; launch=start claude; ingest=write ATT",
    )
    parser.add_argument("--dry-run-launch", action="store_true")
    args = parser.parse_args()
    vault = ROOT / args.vault
    vault.mkdir(parents=True, exist_ok=True)

    if args.phase in {"prepare", "all-prepare"}:
        print("ARCHIVE", flush=True)
        phase_archive(vault)
        res_path = vault / "RESERVATION.json"
        if res_path.is_file():
            info = json.loads(res_path.read_text(encoding="utf-8"))
            print("RESERVATION_EXISTING", info["artifact_id"], flush=True)
        else:
            print("RESERVE", flush=True)
            info = phase_reserve(vault)
            print("RESERVED", info["artifact_id"], flush=True)
        print("WORKSPACE", flush=True)
        meta = phase_workspace(vault, info["artifact_id"])
        print("WORKSPACE_OK", meta["cwd"], "files", len(meta["files"]), flush=True)
        print("PREPARE_DONE", info["artifact_id"], flush=True)
        return 0

    if args.phase == "launch":
        info = json.loads((vault / "RESERVATION.json").read_text(encoding="utf-8"))
        launch = phase_launch(vault, info["artifact_id"], dry_run=args.dry_run_launch)
        print(json.dumps(launch, indent=2), flush=True)
        return 0

    if args.phase == "ingest":
        info = json.loads((vault / "RESERVATION.json").read_text(encoding="utf-8"))
        receipt = phase_ingest(vault, info["artifact_id"])
        print(json.dumps(receipt, indent=2), flush=True)
        return 0 if receipt.get("status") == "success" else 2

    if args.phase == "status":
        for name in (
            "MANIFEST.json",
            "RESERVATION.json",
            "WORKSPACE.json",
            "LAUNCH.json",
            "RECEIPT.json",
        ):
            path = vault / name
            print(name, "OK" if path.is_file() else "missing")
        if (vault / "RESERVATION.json").is_file():
            aid = json.loads((vault / "RESERVATION.json").read_text())["artifact_id"]
            out = ROOT / "proof/attempts" / (aid + ".json")
            print("attempt", aid, "exists" if out.is_file() else "absent")
            stdout = vault / ("%s.resume.stdout.jsonl" % aid)
            print(
                "stdout",
                stdout.stat().st_size if stdout.is_file() else 0,
                "bytes",
            )
            pid_path = vault / ("%s.resume.pid" % aid)
            if pid_path.is_file():
                pid = int(pid_path.read_text().strip())
                alive = True
                try:
                    os.kill(pid, 0)
                except OSError:
                    alive = False
                print("pid", pid, "alive" if alive else "dead")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
