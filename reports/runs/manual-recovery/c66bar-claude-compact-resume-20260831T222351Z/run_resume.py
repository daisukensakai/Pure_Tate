#!/usr/bin/env python3
"""Resume Claude C58-COMPACT after ATT-0144 session-limit 429, new ATT slot.

Recreates the original Claude cwd, copies the isolated task context plus a
slim TRACE-0112 summary, reserves a fresh attempt id, and continues session
6d394240-b9f5-488a-8bd9-c3fe5dc1a28f. ATT-0144 stays spent.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
sys.path.insert(0, str(ROOT))

from pure_tate.agents import (  # noqa: E402
    _engine_argv,
    _extract_claude_stream,
    _subprocess_env,
    _validate_artifact,
    assemble_prompt,
    build_isolated_context,
    load_engines,
    load_engines_config,
)
from pure_tate.campaigns import campaign_status, load_campaign  # noqa: E402
from pure_tate.grok_workers import (  # noqa: E402
    max_grok_workers_from_config,
    max_worker_turns_from_config,
    merge_worker_env,
    prepare_worker_session,
    record_parent_mcp_events,
    resolve_worker_backend,
    resolve_worker_model,
)
from pure_tate.paired import attach_working_context, write_observable_trace  # noqa: E402
from pure_tate.process_runner import ProcessWatchdogError, run_captured_process  # noqa: E402
from pure_tate.run_lifecycle import (  # noqa: E402
    CampaignAlreadyRunning,
    CampaignRunLock,
    live_run_ledgers,
    recover_stale_run_ledgers,
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import atomic_write_json  # noqa: E402
from pure_tate.tasking import campaign_mathematics_tasks  # noqa: E402

CAMPAIGN_ID = "C66BAR-001"
SUBPROBLEM_ID = "C58-COMPACT"
SESSION_ID = "6d394240-b9f5-488a-8bd9-c3fe5dc1a28f"
PARENT_TRACE = "TRACE-0112"
PARENT_ATTEMPT = "ATT-0144"
ORIG_CWD = Path(
    "/private/var/folders/r_/40tyr0nj6zn_yqb74rw_351c0000gn/T/"
    "pure-tate-agent-rp38w_bp"
)
SESSION_JSONL = (
    Path.home()
    / ".claude/projects"
    / "-private-var-folders-r--40tyr0nj6zn-yqb74rw-351c0000gn-T-pure-tate-agent-rp38w-bp"
    / ("%s.jsonl" % SESSION_ID)
)
PARENT_TRACE_PATH = ROOT / "research/paired-traces/TRACE-0112.json"
PARENT_RESERVATION = ROOT / "reports/runs/reservations/ATT-0144.json"
VAULT = Path(__file__).resolve().parent
RUN_ID = VAULT.name
PROOF_DEPENDENCIES = ["ATT-0141", "ATT-0142"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _chmod_curated_readonly(root: Path) -> None:
    """Make curated copies non-writable without touching repo/ or grok-workers/."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in {"repo", "grok-workers"}
            and not (Path(dirpath) / name).is_symlink()
        ]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            path.chmod(path.stat().st_mode & ~0o222)


def _trace_summary(src: Path) -> Dict[str, Any]:
    record = json.loads(src.read_text(encoding="utf-8"))
    stdout = record.get("observable_stdout") or ""
    stderr = record.get("observable_stderr") or ""
    return {
        "id": record.get("id"),
        "task_id": record.get("task_id"),
        "engine": record.get("engine"),
        "campaign_id": record.get("campaign_id"),
        "classification": record.get("classification"),
        "validation_error": record.get("validation_error"),
        "parsed_artifact": record.get("parsed_artifact"),
        "created_at": record.get("created_at"),
        "packet_sha256": record.get("packet_sha256"),
        "packet_binding_sha256": record.get("packet_binding_sha256"),
        "session_id": SESSION_ID,
        "orig_cwd": str(ORIG_CWD),
        "stdout_bytes": len(stdout) if isinstance(stdout, str) else 0,
        "stderr_bytes": len(stderr) if isinstance(stderr, str) else 0,
        "note": (
            "Infrastructure 429 session-limit; no parsed_artifact. Do not mine "
            "this stream for a proof JSON object."
        ),
    }


def build_task() -> Dict[str, Any]:
    status = campaign_status(CAMPAIGN_ID)
    if status.get("structural_integrity") != "ready":
        raise RuntimeError("campaign structural integrity is not ready")
    campaign = load_campaign(CAMPAIGN_ID)
    matches = [
        item
        for item in campaign_mathematics_tasks(CAMPAIGN_ID)
        if item.get("subproblem_id") == SUBPROBLEM_ID
    ]
    if len(matches) != 1 or matches[0].get("status") != "ready":
        raise RuntimeError("%s is not uniquely ready" % SUBPROBLEM_ID)
    value = attach_working_context(dict(matches[0]), campaign)
    value["selected_engine"] = "claude"
    return value


def phase_archive() -> Dict[str, Any]:
    archive = VAULT / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    copies: Dict[str, Any] = {}
    for label, src in [
        ("TRACE-0112.json", PARENT_TRACE_PATH),
        ("session.jsonl", SESSION_JSONL),
        ("ATT-0144.reservation.json", PARENT_RESERVATION),
    ]:
        if not src.is_file():
            raise FileNotFoundError("missing archive source: %s" % src)
        dest = archive / label
        if not dest.exists():
            _copy_file(src, dest)
        copies[label] = {
            "source": str(src),
            "archive": str(dest.relative_to(ROOT)),
            "sha256": _sha256(dest),
            "bytes": dest.stat().st_size,
        }
    summary = _trace_summary(PARENT_TRACE_PATH)
    atomic_write_json(archive / "TRACE-0112.summary.json", summary)
    manifest = {
        "created_from": PARENT_ATTEMPT,
        "parent_trace_id": PARENT_TRACE,
        "parent_session_id": SESSION_ID,
        "orig_cwd": str(ORIG_CWD),
        "policy": "append_only_no_deletes",
        "copies": copies,
        "note": (
            "ATT-0144 stays spent. Recovery continues into a new attempt id. "
            "Session jsonl is archived here only; it is not copied into the "
            "isolated model workspace."
        ),
    }
    atomic_write_json(VAULT / "MANIFEST.json", manifest)
    return manifest


def phase_reserve() -> Dict[str, Any]:
    existing = VAULT / "RESERVATION.json"
    if existing.is_file():
        return json.loads(existing.read_text(encoding="utf-8"))
    artifact_id, reservation_path = reserve_prefixed_artifact(
        ROOT / "proof" / "attempts", "ATT", RUN_ID
    )
    record = json.loads(reservation_path.read_text(encoding="utf-8"))
    record.update(
        {
            "task_id": "TASK-C66-M-005",
            "parent_trace_id": PARENT_TRACE,
            "parent_session_id": SESSION_ID,
            "parent_attempt_id": PARENT_ATTEMPT,
            "override": "principal_investigator_manual_session_resume",
            "vault": str(VAULT.relative_to(ROOT)),
        }
    )
    atomic_write_json(reservation_path, record)
    _copy_file(reservation_path, VAULT / (artifact_id + ".reservation.json"))
    info = {
        "artifact_id": artifact_id,
        "reservation": str(reservation_path.relative_to(ROOT)),
        "run_id": RUN_ID,
        "reserved_at": record.get("reserved_at"),
    }
    atomic_write_json(existing, info)
    return info


def _extra_workspace_files(artifact_id: str) -> List[str]:
    extra: List[str] = []
    summary_rel = "research/paired-traces/TRACE-0112.summary.json"
    summary_path = ORIG_CWD / summary_rel
    atomic_write_json(summary_path, _trace_summary(PARENT_TRACE_PATH))
    extra.append(summary_rel)

    trace_rel = "research/paired-traces/TRACE-0112.json"
    _copy_file(PARENT_TRACE_PATH, ORIG_CWD / trace_rel)
    extra.append(trace_rel)

    resume_rel = "RESUME.md"
    (ORIG_CWD / resume_rel).write_text(
        "\n".join(
            [
                "# C58-COMPACT continuation",
                "",
                "The previous official stream is TRACE-0112. It is an infrastructure",
                "429 session-limit failure with no parsed_artifact. ATT-0144 is closed.",
                "Finish into the new slot %s." % artifact_id,
                "",
                "Do not mine TRACE-0112 for a proof JSON object. Continue the",
                "mathematical work from this session and the curated files.",
                "",
                "Hard contract:",
                "- id must be exactly `%s`" % artifact_id,
                "- engine must be exactly `claude`",
                "- proof_dependencies must be exactly %s" % json.dumps(PROOF_DEPENDENCIES),
                "- never put subproblem ids (C58-OPEN, C58-BOUNDARY, C66BAR-GRAPH) in proof_dependencies",
                "- use the C58-COMPACT theorem from TASK.json (target is (g,n)=(5,8))",
                "- this theorem does not conclude the campaign boundary-image theorem",
                "- final message: exactly one JSON object, no Markdown fences",
                "",
            ]
        ),
        encoding="utf-8",
    )
    extra.append(resume_rel)
    return extra


def phase_workspace(artifact_id: str) -> Dict[str, Any]:
    task = build_task()
    ORIG_CWD.mkdir(parents=True, exist_ok=True)
    files = build_isolated_context(task, ORIG_CWD)
    extra = _extra_workspace_files(artifact_id)
    files = list(files) + extra
    _chmod_curated_readonly(ORIG_CWD)

    continuation = "\n".join(
        [
            "CONTINUATION AFTER INFRASTRUCTURE FAILURE (principal override).",
            "",
            "Your previous turn was interrupted by API Error 429 session limit",
            "(resets 2:40am Asia/Tokyo). The official stream is TRACE-0112.",
            "It has no parsed_artifact. The prior attempt slot ATT-0144 is closed.",
            "You must finish into a NEW slot.",
            "",
            "You are resumed in the same isolated read-only task workspace as before.",
            "The original temp directory had been deleted; curated files have been",
            "recopied. Continue your mathematical work. Do not restart from zero if",
            "you already have context; re-read files only as needed.",
            "",
            "Required reads if not already complete:",
            "- TASK.json",
            "- RESUME.md",
            "- the primary working-context file listed in CONTEXT-INDEX.md",
            "- proof/attempts/ATT-0141.json and proof/attempts/ATT-0142.json",
            "",
            "Optional: research/paired-traces/TRACE-0112.summary.json. Do not mine",
            "TRACE-0112.json for a proof object.",
            "",
            "Hard contract for the final artifact:",
            "- Exactly one JSON object matching proof/CAMPAIGN_ATTEMPT_TEMPLATE.json",
            "- id must be exactly: %s" % artifact_id,
            "- engine must be exactly: claude",
            "- proof_dependencies must be exactly %s" % json.dumps(PROOF_DEPENDENCIES),
            "- result_type is proof or disproof",
            "- Use the exact theorem statement from TASK.json (C58-COMPACT, (5,8))",
            "- This theorem does not conclude the campaign boundary-image theorem",
            "- no gap markers if claimed_complete",
            "",
            "Public web may be used only for ordinary mathematical background or named",
            "theorems, not to search a solution of this exact problem or to decide",
            "openness. Do not claim the problem is open.",
            "",
            "Final message: exactly one JSON object, no Markdown fences, no prose",
            "before or after it.",
            "",
        ]
    )
    (VAULT / "CONTINUATION.txt").write_text(continuation, encoding="utf-8")
    prompt = assemble_prompt(task, files, artifact_id, "claude") + "\n\n" + continuation
    prompt_path = VAULT / "RESUME_PROMPT.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    atomic_write_json(VAULT / "TASK.snapshot.json", task)
    listing = sorted(
        str(path.relative_to(ORIG_CWD))
        for path in ORIG_CWD.rglob("*")
        if path.is_file() and "repo" not in path.relative_to(ORIG_CWD).parts
    )
    meta = {
        "cwd": str(ORIG_CWD),
        "files": files,
        "extra_files": extra,
        "workspace_listing": listing,
        "artifact_id": artifact_id,
        "resume_prompt": str(prompt_path.relative_to(ROOT)),
        "packet_sha256": task.get("packet_sha256"),
        "packet_binding_sha256": task.get("packet_binding_sha256"),
        "working_context": task.get("working_context"),
        "dependency_artifacts": task.get("dependency_artifacts"),
    }
    atomic_write_json(VAULT / "WORKSPACE.json", meta)
    return meta


def _insert_resume(command: List[str]) -> List[str]:
    out = list(command)
    if "--resume" in out:
        return out
    if len(out) >= 3 and out[1] == "-p":
        out[3:3] = ["--resume", SESSION_ID]
        return out
    out[1:1] = ["--resume", SESSION_ID]
    return out


def phase_launch(artifact_id: str) -> Dict[str, Any]:
    task = json.loads((VAULT / "TASK.snapshot.json").read_text(encoding="utf-8"))
    prompt = (VAULT / "RESUME_PROMPT.txt").read_text(encoding="utf-8")
    output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
    if output.exists():
        raise RuntimeError("refusing to overwrite existing %s" % output)
    reservation = ROOT / "reports/runs/reservations" / (artifact_id + ".json")
    stdout_path = VAULT / ("%s.resume.stdout.jsonl" % artifact_id)
    stderr_path = VAULT / ("%s.resume.stderr.txt" % artifact_id)
    console_path = VAULT / ("%s.resume.console.log" % artifact_id)
    files = json.loads((VAULT / "WORKSPACE.json").read_text(encoding="utf-8"))["files"]

    engines_root = load_engines_config()
    config = load_engines()["claude"]
    max_workers = max_grok_workers_from_config(engines_root)
    max_worker_turns = max_worker_turns_from_config(engines_root)
    workers = prepare_worker_session(
        ORIG_CWD,
        family="claude",
        max_workers=max_workers,
        allow_web=True,
        worker_model=str(
            resolve_worker_model(
                engines_root, backend=resolve_worker_backend(engines_root)
            )
        ),
        worker_timeout=min(int(config.get("max_task_seconds") or 10800), 3600),
        worker_backend=resolve_worker_backend(engines_root),
        max_worker_turns=max_worker_turns,
        parent_meta={
            "engine": "claude",
            "family": "claude",
            "phase": "mathematics",
            "task_id": task.get("id"),
            "output": str(output),
            "campaign_id": CAMPAIGN_ID,
            "parent_attempt_id": PARENT_ATTEMPT,
            "parent_trace_id": PARENT_TRACE,
            "resume_session_id": SESSION_ID,
            "worker_mode": "mcp",
        },
        attach_mcp=True,
    )
    workers_on = workers is not None and getattr(workers, "enabled", False)
    continuation = (VAULT / "CONTINUATION.txt").read_text(encoding="utf-8")
    prompt = assemble_prompt(
        task,
        files,
        artifact_id,
        "claude",
        workers_enabled=workers_on,
        max_workers=max_workers if workers_on else 0,
        max_worker_turns=max_worker_turns if workers_on else 0,
    )
    prompt = prompt + "\n\n" + continuation
    (VAULT / "RESUME_PROMPT.txt").write_text(prompt, encoding="utf-8")

    command = _engine_argv(
        "claude",
        prompt,
        phase="mathematics",
        workers=workers if workers_on else None,
        context_files=files,
        workspace=ORIG_CWD,
    )
    command = _insert_resume(command)
    env = merge_worker_env(_subprocess_env("claude", config), workers)
    timeout = int(config.get("max_task_seconds") or 10800)
    inactivity = config.get("inactivity_timeout_seconds")
    if not isinstance(inactivity, int) or inactivity <= 0:
        inactivity = 3600
    abort_patterns = config.get("abort_stderr_pattern_counts")
    if not isinstance(abort_patterns, dict):
        abort_patterns = None

    launch: Dict[str, Any] = {
        "campaign_id": CAMPAIGN_ID,
        "subproblem_id": SUBPROBLEM_ID,
        "artifact_id": artifact_id,
        "parent_attempt_id": PARENT_ATTEMPT,
        "parent_trace_id": PARENT_TRACE,
        "session_id": SESSION_ID,
        "cwd": str(ORIG_CWD),
        "status": "running",
        "workers_enabled": workers_on,
        "cmd": command[:2] + ["<RESUME_PROMPT>"] + command[3:],
    }
    atomic_write_json(VAULT / "LAUNCH.json", launch)
    console_path.write_text(
        "START %s %s %s resume %s\n" % (artifact_id, SUBPROBLEM_ID, RUN_ID, SESSION_ID),
        encoding="utf-8",
    )
    print(
        "LAUNCH %s cwd=%s resume=%s workers=%s" % (
            artifact_id, ORIG_CWD, SESSION_ID, workers_on
        ),
        flush=True,
    )

    event: Dict[str, Any] = {
        "state": "running",
        "artifact_id": artifact_id,
        "task_id": task.get("id"),
    }
    stdout = ""
    stderr = ""
    try:
        process = run_captured_process(
            command,
            cwd=ORIG_CWD,
            env=env,
            timeout=timeout,
            inactivity_timeout=inactivity,
            abort_stderr_pattern_counts=abort_patterns,
            activity_streams=["stdout"],
            on_process_start=lambda meta: (
                (VAULT / ("%s.resume.pid" % artifact_id)).write_text(
                    str(meta.get("child_pid") or meta.get("supervisor_pid") or "")
                    + "\n",
                    encoding="utf-8",
                ),
                launch.update({"process": meta}),
                atomic_write_json(VAULT / "LAUNCH.json", launch),
            ),
        )
        stdout = process.stdout or ""
        stderr = process.stderr or ""
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        record_parent_mcp_events(workers, stdout)
        if process.returncode != 0:
            raise RuntimeError(
                "Claude resume failed: exit=%s bytes=%s stderr=%s"
                % (
                    process.returncode,
                    len(stdout),
                    (stderr or "").strip()[:400],
                )
            )
        artifact = _extract_claude_stream(stdout)
        id_rewritten = False
        if artifact.get("id") == PARENT_ATTEMPT:
            artifact["id"] = artifact_id
            id_rewritten = True
        _validate_artifact("mathematics", task, artifact, output, "claude")
        trace = write_observable_trace(
            task,
            "claude",
            stdout,
            stderr,
            parsed_artifact=artifact,
        )
        artifact["observable_trace_id"] = trace["id"]
        artifact["observable_trace_sha256"] = trace["sha256"]
        artifact["recovery"] = {
            "classification": "manual_session_resume",
            "parent_attempt_id": PARENT_ATTEMPT,
            "parent_trace_id": PARENT_TRACE,
            "parent_session_id": SESSION_ID,
            "resume_stdout": str(stdout_path.relative_to(ROOT)),
            "id_rewritten_from_att0144": id_rewritten,
            "protect_from_overwrite": True,
            "reason": (
                "Principal investigator ordered manual Claude session resume "
                "after 429 session-limit on ATT-0144 / TRACE-0112; new attempt "
                "slot preserves prior work without deleting outputs."
            ),
        }
        atomic_write_json(output, artifact)
        spend_artifact_reservation(
            reservation,
            reason="manual_session_resume_success",
            trace_id=trace["id"],
            task_id=str(task.get("id") or ""),
        )
        event.update(
            {
                "state": "completed",
                "attempt_id": artifact_id,
                "trace_id": trace["id"],
                "result_status": artifact.get("status"),
                "result_type": artifact.get("result_type"),
                "id_rewritten_from_att0144": id_rewritten,
                "artifact_sha256": _sha256(output),
            }
        )
        launch["status"] = "completed"
        launch["trace_id"] = trace["id"]
        launch["output"] = str(output.relative_to(ROOT))
    except Exception as exc:
        event.update(
            {
                "state": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        launch["status"] = "failed"
        launch["error"] = str(exc)
        if stdout or stderr:
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
        try:
            trace_task = dict(task)
            if not trace_task.get("paired_turn_kind"):
                trace_task["paired_turn_kind"] = "mathematics"
            if isinstance(exc, ProcessWatchdogError):
                stdout = exc.stdout or stdout
                stderr = exc.stderr or stderr
                stdout_path.write_text(stdout, encoding="utf-8")
                stderr_path.write_text(stderr, encoding="utf-8")
            if stdout or stderr:
                trace = write_observable_trace(
                    trace_task,
                    "claude",
                    stdout,
                    stderr,
                    validation_error=str(exc),
                    classification="infrastructure",
                )
                event["trace_id"] = trace["id"]
                launch["trace_id"] = trace["id"]
                spend_artifact_reservation(
                    reservation,
                    reason="manual_session_resume_failure",
                    trace_id=trace["id"],
                    task_id=str(task.get("id") or ""),
                )
            else:
                spend_artifact_reservation(
                    reservation,
                    reason="manual_session_resume_failure",
                    task_id=str(task.get("id") or ""),
                )
        except Exception as spend_exc:
            event["spend_error"] = str(spend_exc)
    finally:
        atomic_write_json(VAULT / "LAUNCH.json", launch)
        atomic_write_json(VAULT / "RECEIPT.json", event)
        with console_path.open("a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (event["state"].upper(), json.dumps(event, default=str)))
            handle.write("DONE\n" if event["state"] == "completed" else "FAILED\n")
        print("DONE" if event["state"] == "completed" else "FAILED", flush=True)
        if event.get("error"):
            print(event["error"], flush=True)
    return event


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    recover_stale_run_ledgers(CAMPAIGN_ID)
    active = live_run_ledgers(CAMPAIGN_ID)
    if active:
        raise CampaignAlreadyRunning(", ".join(active))
    if phase in {"prepare", "all"}:
        print("ARCHIVE", flush=True)
        phase_archive()
        print("RESERVE", flush=True)
        info = phase_reserve()
        print("RESERVED", info["artifact_id"], flush=True)
        print("WORKSPACE", flush=True)
        meta = phase_workspace(info["artifact_id"])
        print(
            "WORKSPACE_OK",
            meta["cwd"],
            "files",
            len(meta["files"]),
            flush=True,
        )
        if phase == "prepare":
            return 0
    if phase in {"launch", "all"}:
        info = json.loads((VAULT / "RESERVATION.json").read_text(encoding="utf-8"))
        with CampaignRunLock(CAMPAIGN_ID):
            event = phase_launch(info["artifact_id"])
        return 0 if event.get("state") == "completed" else 1
    raise SystemExit("unknown phase %r" % phase)


if __name__ == "__main__":
    raise SystemExit(main())
