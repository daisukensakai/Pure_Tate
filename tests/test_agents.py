import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.agents import (
    _engine_argv,
    _codex_controller_settings,
    _codex_controller_transcript,
    _parse_codex_controller_decision,
    _run_codex_controller,
    _extract_json_object,
    _failure_detail,
    _normalize_inferred_pairs,
    _normalize_source_references,
    _validate_review_verdict_consistency,
    _validate_artifact,
    assemble_prompt,
    build_isolated_context,
    engine_inventory,
    run_task,
)
from pure_tate.tasking import research_tasks


class AgentAdapterTests(unittest.TestCase):
    def _run_controller_fixture(
        self,
        decisions,
        worker_results,
        *,
        max_requests=4,
        retry_limit=1,
    ):
        """Run a controller turn with deterministic Codex and Grok stand-ins."""
        from pure_tate.grok_workers import DispatchLog, WorkerSession

        class FakeProcess:
            returncode = 0
            stdout = "controller turn completed"
            stderr = ""

        class FakePool:
            def __init__(self, **_kwargs):
                self.dispatched_count = 0

            def dispatch(self, _prompt, _description, wait=True):
                self.dispatched_count += 1
                status, payload = worker_results.pop(0)
                return {
                    "worker_id": "W-fixture-%d" % self.dispatched_count,
                    "status": status,
                    "result_text": payload if status == "completed" else "",
                    "error": payload if status != "completed" else "",
                }

            def shutdown(self, **_kwargs):
                return None

        calls = []

        def fake_run(command, **_kwargs):
            calls.append(command)
            path = Path(command[command.index("-o") + 1])
            path.write_text(decisions.pop(0), encoding="utf-8")
            return FakeProcess()

        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            log = DispatchLog(context / "logs", session_id="SESS-controller")
            session = WorkerSession(
                enabled=True,
                max_workers=4,
                allow_web=False,
                family="openai",
                results_dir=context / "workers",
                dispatch_log=log,
            )
            with mock.patch(
                "pure_tate.agents.run_captured_process", side_effect=fake_run
            ), mock.patch("pure_tate.grok_workers.GrokWorkerPool", FakePool):
                try:
                    process = _run_codex_controller(
                        task={"phase": "research"},
                        context=context,
                        context_files=["TASK.json"],
                        expected_artifact_id="RAUD-TEST",
                        phase="research",
                        workers=session,
                        settings={
                            "max_requests": max_requests,
                            "retry_limit": retry_limit,
                            "max_attempts": 8,
                            "max_result_chars": 12000,
                        },
                        task_timeout=60,
                        inactivity=None,
                        abort_patterns=None,
                        activity_streams=None,
                        progress_callback=None,
                    )
                except Exception as exc:  # noqa: BLE001 - returned for assertion
                    process = exc
            events = [
                json.loads(line)
                for line in (context / "logs" / "sessions" / "SESS-controller" / "events.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
        return process, calls, events

    def test_research_context_excludes_claim_database(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = build_isolated_context(
                research_tasks()[0], Path(directory)
            )
            self.assertIn("data/target.json", copied)
            self.assertIn("data/sources.jsonl", copied)
            self.assertIn("research/RED-0001.statement.json", copied)
            self.assertFalse((Path(directory) / "data" / "claims.jsonl").exists())

    def test_engine_inventory_pins_latest_models(self):
        by_id = {item["id"]: item for item in engine_inventory()}
        self.assertEqual(by_id["claude"]["model"], "claude-opus-5")
        self.assertEqual(by_id["codex"]["model"], "gpt-5.6-sol")
        self.assertEqual(by_id["grok"]["model"], "grok-4.5")
        self.assertEqual(by_id["qwen"]["model"], "qwen3.7-max")
        self.assertTrue(by_id["claude"]["web_access"])
        self.assertTrue(by_id["grok"]["web_access"])
        self.assertFalse(by_id["codex"]["web_access"])
        self.assertTrue(by_id["qwen"]["web_access"])

    def test_codex_argv_is_read_only(self):
        command = _engine_argv(
            "codex", "prompt", Path("/tmp/pure-tate-last-message")
        )
        self.assertIn("read-only", command)
        self.assertIn('approval_policy="never"', command)
        self.assertIn("gpt-5.6-sol", command)

    def test_codex_controller_settings_are_bounded(self):
        settings = _codex_controller_settings(
            {
                "codex_controller_workers": {
                    "enabled": True,
                    "max_requests": 99,
                    "retry_limit": 99,
                    "max_attempts": 99,
                    "max_result_chars": 1,
                }
            }
        )
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["max_requests"], 4)
        self.assertEqual(settings["retry_limit"], 1)
        self.assertEqual(settings["max_attempts"], 8)
        self.assertEqual(settings["max_result_chars"], 500)

    def test_codex_controller_decision_and_transcript_validation(self):
        decision = _parse_codex_controller_decision(
            json.dumps(
                {
                    "action": "dispatch",
                    "request": {
                        "request_id": "check-A",
                        "description": "Check a lemma",
                        "prompt": "Read the supplied packet and check the lemma.",
                    },
                }
            ),
            set(),
        )
        self.assertEqual(decision["request_id"], "check-A")
        with self.assertRaisesRegex(ValueError, "duplicated"):
            _parse_codex_controller_decision(
                json.dumps(
                    {
                        "action": "dispatch",
                        "request": {
                            "request_id": "check-A",
                            "description": "Repeat",
                            "prompt": "Repeat",
                        },
                    }
                ),
                {"check-A"},
            )
        transcript = _codex_controller_transcript(
            [
                {
                    "request_id": "check-A",
                    "description": "Check a lemma",
                    "status": "completed",
                    "attempts": 1,
                    "worker_ids": ["W-1"],
                    "result": "abcdefgh",
                },
                {
                    "request_id": "check-B",
                    "description": "Check another lemma",
                    "status": "failed",
                    "attempts": 2,
                    "worker_ids": ["W-2", "W-3"],
                    "error": "timeout",
                },
            ],
            4,
        )
        self.assertIn('"result": "abcd"', transcript)
        self.assertIn('"error": "timeout"', transcript)

    def test_codex_controller_feeds_worker_result_to_next_decision(self):
        from pure_tate.grok_workers import DispatchLog, WorkerSession

        class FakeProcess:
            returncode = 0

            def __init__(self, stdout):
                self.stdout = stdout
                self.stderr = ""

        class FakePool:
            def __init__(self, **_kwargs):
                self.dispatched_count = 0

            def dispatch(self, _prompt, _description, wait=True):
                self.dispatched_count += 1
                return {
                    "worker_id": "W-controller-1",
                    "status": "completed",
                    "result_text": "worker-result-for-next-decision",
                }

            def shutdown(self, **_kwargs):
                return None

        outputs = [
            json.dumps(
                {
                    "action": "dispatch",
                    "request": {
                        "request_id": "worker-1",
                        "description": "Check the key step",
                        "prompt": "Check the key step.",
                    },
                }
            ),
            json.dumps({"action": "finalize", "request": None}),
            '{"final":true}',
        ]

        def fake_run(command, **_kwargs):
            path = Path(command[command.index("-o") + 1])
            path.write_text(outputs.pop(0), encoding="utf-8")
            return FakeProcess('{"type":"turn.completed"}')

        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            log = DispatchLog(context / "logs", session_id="SESS-controller")
            session = WorkerSession(
                enabled=True,
                max_workers=4,
                allow_web=False,
                family="openai",
                results_dir=context / "workers",
                dispatch_log=log,
            )
            with mock.patch(
                "pure_tate.agents.run_captured_process", side_effect=fake_run
            ) as run_mock, mock.patch(
                "pure_tate.grok_workers.GrokWorkerPool", FakePool
            ):
                process = _run_codex_controller(
                    task={"phase": "research"},
                    context=context,
                    context_files=["TASK.json"],
                    expected_artifact_id="RAUD-TEST",
                    phase="research",
                    workers=session,
                    settings={
                        "max_requests": 4,
                        "retry_limit": 1,
                        "max_attempts": 8,
                        "max_result_chars": 12000,
                    },
                    task_timeout=60,
                    inactivity=None,
                    abort_patterns=None,
                    activity_streams=None,
                    progress_callback=None,
                )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(run_mock.call_count, 3)
        second_prompt = run_mock.call_args_list[1].args[0][-1]
        self.assertIn("worker-result-for-next-decision", second_prompt)
        for call in run_mock.call_args_list:
            argv = call.args[0]
            self.assertIn("read-only", argv)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
            self.assertFalse(any("mcp_servers" in part for part in argv))

    def test_codex_controller_retries_and_reports_exhaustion(self):
        dispatch = json.dumps(
            {
                "action": "dispatch",
                "request": {
                    "request_id": "retry-me",
                    "description": "Retry this focused check",
                    "prompt": "Check the requested lemma.",
                },
            }
        )
        process, calls, events = self._run_controller_fixture(
            [dispatch, json.dumps({"action": "finalize", "request": None}), "{}"],
            [("failed", "first timeout"), ("failed", "second timeout")],
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(len(calls), 3)
        self.assertIn("second timeout", calls[1][-1])
        self.assertIn("controller_retry", [event["event"] for event in events])
        self.assertIn("controller_worker_exhausted", [event["event"] for event in events])

    def test_codex_controller_retry_can_succeed(self):
        dispatch = json.dumps(
            {
                "action": "dispatch",
                "request": {
                    "request_id": "recover",
                    "description": "Recover the check after one failure",
                    "prompt": "Check the requested lemma.",
                },
            }
        )
        process, _calls, events = self._run_controller_fixture(
            [dispatch, json.dumps({"action": "finalize", "request": None}), "{}"],
            [("failed", "temporary error"), ("completed", "recovered result")],
        )
        self.assertEqual(process.returncode, 0)
        names = [event["event"] for event in events]
        self.assertIn("controller_retry", names)
        self.assertIn("controller_worker_finished", names)
        self.assertNotIn("controller_worker_exhausted", names)

    def test_codex_controller_four_round_cap_and_zero_round_finalization(self):
        decisions = []
        for index in range(4):
            decisions.append(
                json.dumps(
                    {
                        "action": "dispatch",
                        "request": {
                            "request_id": "round-%d" % index,
                            "description": "Round %d" % index,
                            "prompt": "Do check %d." % index,
                        },
                    }
                )
            )
        decisions.append("{}")
        process, calls, events = self._run_controller_fixture(
            decisions,
            [("completed", "ok")] * 4,
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(len(calls), 5)
        self.assertEqual(
            [event["event"] for event in events].count("controller_request_accepted"), 4
        )
        self.assertIn("controller_forced_finalization", [event["event"] for event in events])

        process, calls, events = self._run_controller_fixture(
            ["{}"], [], max_requests=0
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(len(calls), 1)
        self.assertIn("controller_forced_finalization", [event["event"] for event in events])

    def test_codex_controller_invalid_decision_fails_closed_and_is_logged(self):
        process, calls, events = self._run_controller_fixture(
            [json.dumps({"action": "dispatch", "request": None})], []
        )
        self.assertIsInstance(process, ValueError)
        self.assertEqual(len(calls), 1)
        self.assertIn("controller_decision_invalid", [event["event"] for event in events])

    def test_claude_argv_pins_opus_5(self):
        command = _engine_argv("claude", "prompt")
        self.assertIn("--model", command)
        self.assertEqual(command[command.index("--model") + 1], "claude-opus-5")

    def test_grok_argv_pins_model_and_can_disable_web(self):
        command = _engine_argv("grok", "prompt")
        self.assertIn("-m", command)
        self.assertEqual(command[command.index("-m") + 1], "grok-4.5")
        self.assertIn("--permission-mode", command)
        self.assertEqual(
            command[command.index("--permission-mode") + 1], "dontAsk"
        )
        self.assertIn("--always-approve", command)
        self.assertIn("--max-turns", command)
        self.assertIn("--tools", command)
        tools = command[command.index("--tools") + 1]
        self.assertEqual(
            set(tools.split(",")),
            {"read_file", "grep", "list_dir"},
        )
        self.assertNotIn("spawn_subagent", tools.split(","))
        self.assertIn("--disallowed-tools", command)
        denied = command[command.index("--disallowed-tools") + 1]
        self.assertEqual(
            set(denied.split(",")),
            {"run_terminal_command", "write", "web_fetch", "web_search", "open_page"},
        )
        self.assertIn("--disable-web-search", command)

        with mock.patch(
            "pure_tate.agents.load_engines",
            return_value={
                "grok": {
                    "binary": "grok",
                    "family": "grok",
                    "model": "grok-4.5",
                    "web_access": False,
                }
            },
        ):
            offline = _engine_argv("grok", "prompt")
        self.assertIn("--disable-web-search", offline)
        offline_tools = offline[offline.index("--tools") + 1]
        self.assertEqual(
            set(offline_tools.split(",")), {"read_file", "grep", "list_dir"}
        )

    def test_grok_argv_with_workers_uses_bypass_and_mcp_meta_tools(self):
        from pure_tate.grok_workers import WorkerSession
        from pathlib import Path

        session = WorkerSession(
            enabled=True,
            max_workers=4,
            allow_web=False,
            family="grok",
            results_dir=Path("/tmp/pure-tate-workers"),
            server_command=["uv", "run", "--with", "mcp", "python", "x"],
        )
        command = _engine_argv("grok", "prompt", workers=session)
        self.assertEqual(
            command[command.index("--permission-mode") + 1], "bypassPermissions"
        )
        tools = set(command[command.index("--tools") + 1].split(","))
        self.assertTrue({"read_file", "grep", "list_dir", "search_tool", "use_tool"}.issubset(tools))
        self.assertNotIn("spawn_subagent", tools)
        self.assertNotIn("run_terminal_command", tools)
        self.assertNotIn("write", tools)

    def test_claude_argv_with_workers_attaches_mcp(self):
        from pure_tate.grok_workers import WorkerSession
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            mcp_path = Path(directory) / "mcp.json"
            mcp_path.write_text("{}", encoding="utf-8")
            session = WorkerSession(
                enabled=True,
                max_workers=4,
                allow_web=False,
                family="claude",
                results_dir=Path(directory) / "workers",
                mcp_config_path=mcp_path,
                server_command=["uv", "run", "python", "x"],
            )
            command = _engine_argv("claude", "prompt", workers=session)
        self.assertEqual(
            command[command.index("--permission-mode") + 1], "bypassPermissions"
        )
        self.assertIn("--mcp-config", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertIn(
            "mcp__grok-workers__dispatch_grok_worker",
            command,
        )
        self.assertIn("Bash", command[command.index("--disallowedTools") :])

    def test_grok_text_envelope_is_unwrapped(self):
        raw = json.dumps(
            {
                "stopReason": "EndTurn",
                "sessionId": "abc",
                "text": '{"id":"RAUD-0002","verdict":"agree"}',
            }
        )
        value = _extract_json_object(raw)
        self.assertEqual(value["id"], "RAUD-0002")
        self.assertEqual(value["verdict"], "agree")

    def test_grok_cancelled_envelope_raises(self):
        raw = json.dumps(
            {
                "stopReason": "Cancelled",
                "sessionId": "abc",
                "text": "partial work without json",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            _extract_json_object(raw)
        self.assertIn("Cancelled", str(ctx.exception))

    def test_grok_cancelled_envelope_recovers_final_json(self):
        raw = json.dumps(
            {
                "stopReason": "Cancelled",
                "sessionId": "abc",
                "text": (
                    "Done.\n"
                    '{"id":"RAUD-0002","verdict":"agree","reviewer_engine":"grok"}'
                ),
            }
        )
        value = _extract_json_object(raw)
        self.assertEqual(value["id"], "RAUD-0002")
        self.assertEqual(value["verdict"], "agree")

    def test_campaign_review_prompt_forbids_confirmed_with_adverse_checks(self):
        task = {
            "id": "TASK-V-ATT-0001-P1",
            "phase": "review",
            "campaign_id": "C66-001",
            "prompt": "prompts/ADVERSARY.md",
            "inputs": [],
            "selected_engine": "claude",
        }
        prompt = assemble_prompt(task, [], "REV-0001", "claude")
        self.assertIn("confirmed verdict forbids", prompt.lower())
        self.assertIn("adverse structured check", prompt.lower())
        adversary = (Path(__file__).resolve().parents[1] / "prompts" / "ADVERSARY.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("confirmed` verdict forbids", adversary)
        self.assertIn("non-load-bearing", adversary)

    def test_prompt_requires_selected_engine_id(self):
        task = research_tasks()[0]
        prompt = assemble_prompt(task, ["TASK.json"], "RAUD-0001", "grok")
        self.assertIn("reviewer_engine field must be exactly: grok", prompt)
        self.assertIn("Never use run_terminal_command, write", prompt)
        self.assertIn("final message only", prompt)

    def test_json_envelope_is_unwrapped(self):
        value = _extract_json_object(
            '{"result":"{\\"id\\":\\"RAUD-0001\\"}"}'
        )
        self.assertEqual(value["id"], "RAUD-0001")

    def test_prose_wrapped_json_is_extracted(self):
        value = _extract_json_object(
            'Here is the audit.\n\n{"id": "RAUD-0001", "verdict": "agree"}\n'
        )
        self.assertEqual(value["id"], "RAUD-0001")
        self.assertEqual(value["verdict"], "agree")

    def test_latex_commands_that_look_like_json_escapes_are_preserved(self):
        raw = (
            '{"id":"ATT-0022","argument_markdown":'
            '"\\\\beta+\\\\frac{1}{2}+\\\\nu+\\\\rho+\\\\theta",'
            '"ordinary_newline":"first\\nsecond"}'
        )
        # Simulate the malformed model output, which contains single
        # backslashes before LaTeX commands but a legitimate JSON newline.
        malformed = raw.replace("\\\\beta", "\\beta").replace(
            "\\\\frac", "\\frac"
        ).replace("\\\\nu", "\\nu").replace("\\\\rho", "\\rho").replace(
            "\\\\theta", "\\theta"
        )
        value = _extract_json_object(malformed)
        self.assertEqual(
            value["argument_markdown"],
            r"\beta+\frac{1}{2}+\nu+\rho+\theta",
        )
        self.assertEqual(value["ordinary_newline"], "first\nsecond")

    def test_qwen_output_prefers_complete_outer_artifact(self):
        artifact = {
            "id": "ATT-0022",
            "target": {"g": 6, "n": 6},
            "argument_markdown": r"\Gamma and \omega",
        }
        malformed = json.dumps(artifact).replace(
            "\\\\Gamma", "\\Gamma"
        ).replace("\\\\omega", "\\omega")
        value = _extract_json_object(malformed)
        self.assertEqual(value["id"], "ATT-0022")
        self.assertEqual(value["target"], {"g": 6, "n": 6})
        self.assertEqual(value["argument_markdown"], r"\Gamma and \omega")

    def test_envelope_prose_and_object_pairs_normalize(self):
        raw = json.dumps(
            {
                "is_error": False,
                "result": (
                    "Audit complete.\n\n"
                    '{"id":"RAUD-0001","inferred_pairs":[{"g":3,"n":12},[5,8]]}'
                ),
            }
        )
        value = _extract_json_object(raw)
        pairs = _normalize_inferred_pairs(value["inferred_pairs"])
        self.assertEqual(pairs, [[3, 12], [5, 8]])

    def test_rate_limit_envelope_raises_clear_message(self):
        raw = json.dumps(
            {
                "is_error": True,
                "api_error_status": 429,
                "result": "You've hit your session limit · resets 3:20am (Asia/Tokyo)",
            }
        )
        with self.assertRaises(ValueError) as ctx:
            _extract_json_object(raw)
        self.assertIn("session limit", str(ctx.exception))

        detail = _failure_detail(1, "", raw)
        self.assertIn("session limit", detail)
        self.assertIn("exit 1", detail)

    def test_artifact_id_must_match_output_filename(self):
        task = research_tasks()[0]
        artifact = {
            "id": "RAUD-9999",
            "target_claim_id": "RED-0001",
            "verdict": "agree",
            "inferred_pairs": [],
            "source_ids": [],
            "locators_checked": [],
            "forward_citation_check_date": "2026-07-29",
            "reviewer_engine": "test",
            "independent": True,
        }
        with self.assertRaises(ValueError):
            _validate_artifact(
                "research",
                task,
                artifact,
                Path("research/audits/RAUD-0001.json"),
            )

    def test_validate_coerces_object_pairs(self):
        task = research_tasks()[0]
        artifact = {
            "id": "RAUD-0001",
            "target_claim_id": "RED-0001",
            "verdict": "agree",
            "inferred_pairs": [{"g": 3, "n": 12}, {"g": 5, "n": 8}],
            "source_ids": ["SRC-0001"],
            "locators_checked": ["loc"],
            "forward_citation_check_date": "2026-07-29",
            "reviewer_engine": "claude",
            "independent": True,
        }
        _validate_artifact(
            "research",
            task,
            artifact,
            Path("research/audits/RAUD-0001.json"),
            "claude",
        )
        self.assertEqual(artifact["inferred_pairs"], [[3, 12], [5, 8]])

    def test_source_identifiers_are_moved_without_erasing_provenance(self):
        artifact = {
            "source_claim_ids": ["THM-0005", "SRC-0004", "SRC-0004"],
            "source_ids": ["SRC-0002"],
        }
        _normalize_source_references(artifact)
        self.assertEqual(artifact["source_claim_ids"], ["THM-0005"])
        self.assertEqual(artifact["source_ids"], ["SRC-0002", "SRC-0004"])
        self.assertEqual(
            artifact["ingest_normalizations"][0]["rule"],
            "SOURCE-REFERENCE-SPLIT-0001",
        )

    def test_review_verdict_must_match_structured_checks(self):
        incomplete_without_adverse = {
            "verdict": "incomplete",
            "checked_claims": [{"verdict": "confirmed"}],
            "proof_dependency_checks": [{"verdict": "confirmed"}],
        }
        with self.assertRaisesRegex(ValueError, "failed or unresolved"):
            _validate_review_verdict_consistency(incomplete_without_adverse)
        incomplete_without_adverse["checked_claims"][0]["verdict"] = "failed"
        _validate_review_verdict_consistency(incomplete_without_adverse)

        confirmed_with_unresolved = {
            "verdict": "confirmed",
            "checked_claims": [{"verdict": "confirmed"}],
            "proof_dependency_checks": [
                {"dependency_id": "SRC-0002", "verdict": "unresolved"}
            ],
        }
        with self.assertRaisesRegex(
            ValueError, "confirmed review contains a failed or unresolved"
        ):
            _validate_review_verdict_consistency(confirmed_with_unresolved)
        confirmed_with_unresolved["proof_dependency_checks"][0][
            "verdict"
        ] = "confirmed"
        _validate_review_verdict_consistency(confirmed_with_unresolved)

    def test_run_task_surfaces_envelope_api_error(self):
        task = research_tasks()[0]
        envelope = json.dumps(
            {
                "is_error": True,
                "api_error_status": 429,
                "result": "You've hit your session limit",
            }
        )

        class FakeProcess:
            returncode = 0
            stdout = envelope
            stderr = ""

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "RAUD-0001.json"
            # Point output under the real audits dir constraint by mocking path check.
            with mock.patch(
                "pure_tate.agents._validate_output_path"
            ), mock.patch(
                "pure_tate.agents.shutil.which", return_value="/usr/bin/claude"
            ), mock.patch(
                "pure_tate.agents.run_captured_process", return_value=FakeProcess()
            ), mock.patch(
                "pure_tate.agents.atomic_write_json"
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    run_task(
                        task,
                        "claude",
                        Path("research/audits/RAUD-0001.json"),
                    )
        self.assertIn("session limit", str(ctx.exception))

    def test_run_task_accepts_grok_endturn_message_without_workspace_write(self):
        task = research_tasks()[0]
        artifact = {
            "id": "RAUD-0002",
            "target_claim_id": "RED-0001",
            "verdict": "agree",
            "inferred_pairs": [[3, 12]],
            "source_ids": ["SRC-0001"],
            "locators_checked": ["source locator"],
            "forward_citation_check_date": "2026-07-30",
            "reviewer_engine": "grok",
            "independent": True,
        }
        envelope = json.dumps(
            {
                "stopReason": "EndTurn",
                "sessionId": "session",
                "text": json.dumps(artifact),
            }
        )

        class FakeProcess:
            returncode = 0
            stdout = envelope
            stderr = ""

        with mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/grok"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", return_value=FakeProcess()
        ) as run_mock, mock.patch(
            "pure_tate.agents.atomic_write_json"
        ) as write_mock:
            result = run_task(
                task,
                "grok",
                Path("research/audits/RAUD-0002.json"),
            )
        self.assertEqual(result["id"], "RAUD-0002")
        self.assertEqual(write_mock.call_count, 2)
        self.assertEqual(
            write_mock.call_args_list[-1].args[0],
            Path("research/audits/RAUD-0002.json"),
        )
        command = run_mock.call_args.args[0]
        self.assertNotIn("write", command[command.index("--tools") + 1].split(","))
        self.assertIn(
            "write",
            command[command.index("--disallowed-tools") + 1].split(","),
        )


if __name__ == "__main__":
    unittest.main()
