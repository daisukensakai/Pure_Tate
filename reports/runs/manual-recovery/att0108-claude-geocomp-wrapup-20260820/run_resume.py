#!/usr/bin/env python3
"""Resume Claude GEO-COMP as a wrap-up: summarize progress, not forced proof.

ATT-0106/0107/0108 are spent. Same Claude session, new append-only ATT slot.
No Grok workers. No forced-completeness contract. No model fallback.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/Users/ken/Desktop/Work/exploratory/Pure_Tate")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pure_tate.agents import (  # noqa: E402
    _extract_claude_stream,
    _validate_artifact,
    build_isolated_context,
)
from pure_tate.campaign_driver import _new_run_ledger, _timestamp, _write_run_ledger
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.notifications import (  # noqa: E402
    notify_campaign_run,
    notify_campaign_step,
    send_desktop_notification,
    send_ntfy_notification_detailed,
)
from pure_tate.paired import (  # noqa: E402
    attach_working_context,
    write_observable_trace,
)
from pure_tate.run_lifecycle import (  # noqa: E402
    CampaignAlreadyRunning,
    CampaignRunLock,
    live_run_ledgers,
    recover_stale_run_ledgers,
    release_artifact_reservation,
    reserve_prefixed_artifact,
    spend_artifact_reservation,
)
from pure_tate.store import atomic_write_json  # noqa: E402
from pure_tate.tasking import campaign_mathematics_tasks  # noqa: E402
from pure_tate.validation_repair import expected_identity_values  # noqa: E402

CAMPAIGN_ID = "C66-001"
TASK_ID = "TASK-C66-M-003"
SUBPROBLEM_ID = "C66-GEO-COMP"
ENGINE = "claude"
FAILED_SLOT = "ATT-0108"
FAILED_TRACE = "TRACE-0069"
PRIOR_SPENT = ("ATT-0106", "ATT-0107", "ATT-0108")
SESSION_ID = "fd85bfb3-3fa5-487b-8827-4089aee6ec6e"
ORIG_CWD = Path(
    "/private/var/folders/r_/40tyr0nj6zn_yqb74rw_351c0000gn/T/pure-tate-agent-5_ddw7vi"
)
CLAUDE_PROJ = (
    Path.home()
    / ".claude/projects/-private-var-folders-r--40tyr0nj6zn-yqb74rw-351c0000gn-T-pure-tate-agent-5-ddw7vi"
)
SESSION_JSONL = CLAUDE_PROJ / ("%s.jsonl" % SESSION_ID)
VAULT = Path(__file__).resolve().parent
TIMEOUT = 10800
WRAPUP_PROMPT = (
    "reports/runs/manual-recovery/att0108-claude-geocomp-wrapup-20260820/"
    "WRAPUP_GEO_COMP.md"
)
OLD_WORKERS = ("W-a12a19e238c7", "W-6e3ad73aaa29")


def notify(title: str, message: str) -> None:
    print(
        "notify",
        {
            "desktop": send_desktop_notification(title, message),
            "ntfy": send_ntfy_notification_detailed(title, message),
        },
        flush=True,
    )


def main() -> int:
    if not SESSION_JSONL.is_file():
        raise SystemExit("missing Claude session %s" % SESSION_JSONL)
    for spent in PRIOR_SPENT:
        if (ROOT / "proof" / "attempts" / (spent + ".json")).exists():
            raise SystemExit("refusing: spent slot %s unexpectedly exists" % spent)

    packet = write_campaign_packet(CAMPAIGN_ID)
    campaign = load_campaign(CAMPAIGN_ID)
    matches = [
        task
        for task in campaign_mathematics_tasks(CAMPAIGN_ID)
        if task.get("id") == TASK_ID
    ]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one %s" % TASK_ID)
    task = attach_working_context(dict(matches[0]), campaign)
    if task.get("status") != "ready" or task.get("subproblem_id") != SUBPROBLEM_ID:
        raise RuntimeError(
            "%s not ready: status=%s subproblem=%s"
            % (TASK_ID, task.get("status"), task.get("subproblem_id"))
        )
    task["selected_engine"] = ENGINE
    task["prompt"] = WRAPUP_PROMPT
    task["paired_turn_kind"] = "mathematics"

    try:
        with CampaignRunLock(CAMPAIGN_ID):
            recover_stale_run_ledgers(CAMPAIGN_ID)
            active = live_run_ledgers(CAMPAIGN_ID)
            if active:
                raise CampaignAlreadyRunning(
                    "campaign %s has a live drive: %s" % (CAMPAIGN_ID, ", ".join(active))
                )

            ledger, ledger_path = _new_run_ledger(
                CAMPAIGN_ID, 1, ["claude", "grok"], [ENGINE], ["codex", "claude"]
            )
            run_id = ledger["run_id"]
            artifact_id, reservation_path = reserve_prefixed_artifact(
                ROOT / "proof" / "attempts", "ATT", run_id
            )
            if artifact_id in PRIOR_SPENT:
                raise RuntimeError("refusing to reuse spent %s" % artifact_id)
            output = ROOT / "proof" / "attempts" / (artifact_id + ".json")
            if output.exists():
                raise RuntimeError("refusing to overwrite %s" % output)
            task["output"] = str(output.relative_to(ROOT))

            session_archive = VAULT / "session.pre-resume.jsonl"
            if not session_archive.exists():
                shutil.copy2(SESSION_JSONL, session_archive)
            proj_copy = VAULT / "claude-project-copy"
            if CLAUDE_PROJ.exists() and not proj_copy.exists():
                shutil.copytree(CLAUDE_PROJ, proj_copy)

            if ORIG_CWD.exists():
                shutil.rmtree(ORIG_CWD)
            ORIG_CWD.mkdir(parents=True, exist_ok=True)
            copied = build_isolated_context(task, ORIG_CWD)
            (ORIG_CWD / "TASK.json").write_text(
                json.dumps(task, indent=2) + "\n", encoding="utf-8"
            )

            identity = expected_identity_values(
                "mathematics", task, artifact_id, ENGINE
            )
            identity_lines = []
            for key, value in identity.items():
                rendered = (
                    json.dumps(value, sort_keys=True, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else json.dumps(value, ensure_ascii=False)
                )
                identity_lines.append("- %s: %s" % (key, rendered))

            prompt = "\n".join(
                [
                    "WRAP-UP RESUME — record useful GEO-COMP progress; do not force a complete proof.",
                    "",
                    "The forced-turn completeness contract is cancelled for this resume.",
                    "",
                    "Your original turn for TASK-C66-M-003 / C66-GEO-COMP was interrupted",
                    "by a Claude session limit (TRACE-0067 / ATT-0106). Two later --resume",
                    "attempts (ATT-0107 / TRACE-0068, ATT-0108 / TRACE-0069) hit session",
                    "limits again and did no new mathematics. Official last stream:",
                    "research/paired-traces/%s.json." % FAILED_TRACE,
                    "You never emitted a JSON artifact.",
                    "",
                    "On the original turn you read the primary GEO-COMP working context,",
                    "dispatched two Grok workers in parallel (%s type-(ii) monodromy;"
                    % OLD_WORKERS[0],
                    "%s balanced base / component count), both completed, and began"
                    % OLD_WORKERS[1],
                    "the mathematics before the session died.",
                    "",
                    "Spent/failed slots ATT-0106, ATT-0107, and ATT-0108 are closed.",
                    "Do NOT reopen or overwrite them.",
                    "Finish into the NEW append-only slot: %s." % artifact_id,
                    "Same Claude session is resumed. Do not restart from zero.",
                    "",
                    "Old Grok workers are dead. Do NOT await, continue, or dispatch workers.",
                    "Wrap up from session memory and those reports.",
                    "",
                    "This wrap-up's job:",
                    "- Summarize findings and useful progress from this interrupted session.",
                    "- Produce one valid campaign attempt JSON (lemma, GEO-COMP, not RED-0001).",
                    "- Do NOT claim complete resolution of GEO-COMP.",
                    "- Prefer result_type lemma, honest gap_markers, unproved claims not marked proved.",
                    "- completion_attestation.resolves_exact_target must be false.",
                    "- Cite prior dual-confirmed artifacts by ID when restating them;",
                    "  only mark as new what this session actually added or sharpened.",
                    "- Keep remaining gaps explicit: exact type-(ii) image inside S_2 wr S_3;",
                    "  purely type-(ii) components; irreducibility of the balanced base;",
                    "  Aut/inertia and the map to M_{6,6}.",
                    "",
                    "Hard identity (copy exactly):",
                    *identity_lines,
                    "- Match proof/CAMPAIGN_ATTEMPT_TEMPLATE.json",
                    "- Final message: exactly one complete JSON object, no Markdown fences,",
                    "  no prose before or after it.",
                    "",
                    "Supplied files:",
                    *["- %s" % item for item in copied],
                    "- TASK.json (output retargeted to %s)" % artifact_id,
                    "",
                    "Do not re-read the packet or primary working context end-to-end.",
                    "",
                ]
            )
            prompt_path = VAULT / "RESUME_PROMPT.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
            atomic_write_json(VAULT / ("manifest-%s.json" % artifact_id), task)

            launch = {
                "note": (
                    "Claude --resume wrap-up after ATT-0108 session limit; same session; "
                    "new slot; NOT forced-proof; no Grok workers; summarize progress"
                ),
                "stamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                "campaign_id": CAMPAIGN_ID,
                "task_id": TASK_ID,
                "subproblem_id": SUBPROBLEM_ID,
                "engine": ENGINE,
                "failed_slot": FAILED_SLOT,
                "failed_trace": FAILED_TRACE,
                "session_id": SESSION_ID,
                "cwd": str(ORIG_CWD),
                "artifact_id": artifact_id,
                "output": str(output.relative_to(ROOT)),
                "reservation": str(reservation_path),
                "run_id": run_id,
                "run_ledger": str(ledger_path.relative_to(ROOT)),
                "resume_prompt": str(prompt_path.relative_to(ROOT)),
                "wrapup_prompt": WRAPUP_PROMPT,
                "forced_prompt": None,
                "packet_sha256": packet.get("packet_sha256"),
                "max_grok_workers": 0,
                "max_worker_turns": 0,
                "worker_session": None,
                "status": "running",
            }
            atomic_write_json(VAULT / "LAUNCH.json", launch)

            event = {
                "step": 1,
                "phase": "mathematics",
                "task_id": TASK_ID,
                "engine": ENGINE,
                "output": str(output.relative_to(ROOT)),
                "state": "running",
                "started_at": _timestamp(),
                "resume_of": FAILED_SLOT,
                "resume_session": SESSION_ID,
                "parent_trace": FAILED_TRACE,
                "pi_override": {
                    "wrapup": True,
                    "forced_prompt": None,
                    "max_grok_workers": 0,
                },
            }
            ledger["events"] = [event]
            _write_run_ledger(ledger_path, ledger)

            notify(
                "Pure Tate • Claude GEO-COMP wrap-up starting",
                "C66-001 • --resume %s\n%s -> %s wrap-up (%s closed)"
                % (SESSION_ID, TASK_ID, artifact_id, FAILED_SLOT),
            )

            stdout_path = VAULT / ("%s.resume.stdout.jsonl" % artifact_id)
            stderr_path = VAULT / ("%s.resume.stderr.txt" % artifact_id)
            env = dict(os.environ)
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
            argv = [
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
            try:
                with stdout_path.open("w", encoding="utf-8") as out_h, stderr_path.open(
                    "w", encoding="utf-8"
                ) as err_h:
                    proc = subprocess.run(
                        argv,
                        cwd=str(ORIG_CWD),
                        env=env,
                        stdout=out_h,
                        stderr=err_h,
                        check=False,
                        timeout=TIMEOUT,
                    )
                raw = stdout_path.read_text(encoding="utf-8", errors="replace")
                with stderr_path.open("a", encoding="utf-8") as err_h:
                    err_h.write("EXIT:%d\n" % proc.returncode)
                    err_h.write("OUT_BYTES:%d\n" % stdout_path.stat().st_size)
                event["activity_bytes"] = stdout_path.stat().st_size
                event["completed_at"] = _timestamp()
                event["returncode"] = proc.returncode

                if proc.returncode != 0 or not raw.strip():
                    raise RuntimeError(
                        "claude resume failed: exit=%s bytes=%s"
                        % (proc.returncode, stdout_path.stat().st_size)
                    )
                artifact = _extract_claude_stream(raw)
                _validate_artifact("mathematics", task, artifact, output, ENGINE)
                if output.exists():
                    raise RuntimeError("output appeared concurrently; abort")
                atomic_write_json(output, artifact)
                release_artifact_reservation(reservation_path)
                event["state"] = "completed"
                event["attempt_id"] = artifact.get("id")
                event["artifact_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                launch["result_status"] = artifact.get("status")
                launch["gap_count"] = len(artifact.get("gap_markers") or [])
            except Exception as exc:
                event["error"] = str(exc)
                event["state"] = "failed"
                event["completed_at"] = _timestamp()
                event["traceback"] = traceback.format_exc()
                launch["error"] = str(exc)
                try:
                    parsed = None
                    raw_for_trace = ""
                    if stdout_path.is_file():
                        raw_for_trace = stdout_path.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        try:
                            parsed = _extract_claude_stream(raw_for_trace)
                        except Exception:
                            parsed = None
                    if raw_for_trace.strip():
                        trace = write_observable_trace(
                            task,
                            ENGINE,
                            raw_for_trace,
                            stderr_path.read_text(encoding="utf-8", errors="replace")
                            if stderr_path.is_file()
                            else "",
                            parsed_artifact=parsed,
                            validation_error=str(exc),
                            classification="validation_failure",
                        )
                        event["trace_id"] = trace["id"]
                        event["trace_path"] = trace["path"]
                except Exception as trace_exc:
                    event["trace_write_error"] = str(trace_exc)
                spend_artifact_reservation(
                    reservation_path,
                    reason="resume_validation_or_agent_failure",
                    trace_id=event.get("trace_id"),
                    task_id=TASK_ID,
                )

            event["notification_delivery"] = notify_campaign_step(
                CAMPAIGN_ID, event, 1, desktop=True, ntfy=True
            )
            stop_reason = (
                "step_limit" if event.get("state") == "completed" else "engine_failure"
            )
            ledger["events"] = [event]
            ledger["status"] = (
                "completed" if event.get("state") == "completed" else "stopped"
            )
            ledger["stop_reason"] = stop_reason
            ledger["completed_at"] = _timestamp()
            ledger["executed_steps"] = 1
            ledger["run_notification_delivery"] = notify_campaign_run(
                CAMPAIGN_ID,
                1,
                1,
                ledger["status"],
                stop_reason,
                desktop=True,
                ntfy=True,
            )
            _write_run_ledger(ledger_path, ledger)
            launch["status"] = ledger["status"]
            launch["event_state"] = event.get("state")
            launch["stop_reason"] = stop_reason
            atomic_write_json(VAULT / "LAUNCH.json", launch)
            print(json.dumps(launch, indent=2, default=str), flush=True)
            return 0 if event.get("state") == "completed" else 1
    except CampaignAlreadyRunning as exc:
        notify("Pure Tate • GEO-COMP resume blocked", str(exc))
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
