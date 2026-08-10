import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.grok_workers import (
    DEFAULT_MAX_TOTAL,
    DEFAULT_MAX_WORKER_TURNS,
    DispatchLog,
    GrokWorkerPool,
    PoolError,
    WorkerRecord,
    WorkerSession,
    apply_workers_to_argv,
    build_worker_argv,
    ensure_dispatch_log_dir,
    extract_cli_session_id,
    extract_result_text,
    max_grok_workers_from_config,
    max_worker_turns_from_config,
    mcp_server_command,
    prepare_worker_session,
    record_parent_mcp_events,
    redact_argv,
    resolve_worker_backend,
    resolve_worker_model,
    sha256_text,
    utc_now_iso,
    worker_dispatch_parent_policy,
)


class GrokWorkerPoolTests(unittest.TestCase):
    def test_max_config_defaults_and_disable(self):
        self.assertEqual(max_grok_workers_from_config({}), DEFAULT_MAX_TOTAL)
        self.assertEqual(DEFAULT_MAX_TOTAL, 1)
        self.assertEqual(
            max_grok_workers_from_config({"max_grok_workers": 1}), 1
        )
        self.assertEqual(
            max_grok_workers_from_config({"max_grok_workers": 99}), 1
        )
        self.assertEqual(
            max_grok_workers_from_config({"grok_workers_enabled": False}), 0
        )
        self.assertEqual(
            max_grok_workers_from_config({"max_grok_workers": 0}), 0
        )
        self.assertEqual(
            max_worker_turns_from_config({}), DEFAULT_MAX_WORKER_TURNS
        )
        self.assertEqual(
            max_worker_turns_from_config({"max_worker_turns": 4}), 4
        )

    def test_total_budget_hard_cap(self):
        def runner(*, prompt, description, worker_id, pool, **_kwargs):
            return WorkerRecord(
                worker_id=worker_id,
                description=description,
                prompt_sha256=sha256_text(prompt),
                status="completed",
                created_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                returncode=0,
                result_text="ok",
                cli_session_id="sess-complete",
            )

        pool = GrokWorkerPool(
            max_concurrent=1, max_total=1, max_worker_turns=4, runner=runner
        )
        result = pool.dispatch("p-0", "t0")
        self.assertEqual(result["status"], "completed")
        with self.assertRaises(PoolError) as ctx:
            pool.dispatch("overflow", "x")
        self.assertEqual(ctx.exception.code, "budget_exhausted")

    def test_concurrent_pool_full(self):
        pool = GrokWorkerPool(max_concurrent=1, max_total=1, max_worker_turns=4)
        gate = threading.Event()
        entered = threading.Event()

        def gated_run(
            worker_id, prompt, timeout_seconds, resume_session_id=None
        ):
            entered.set()
            gate.wait(timeout=5)
            with pool._lock:
                rec = pool._workers[worker_id]
                rec.status = "completed"
                rec.finished_at = utc_now_iso()
                rec.returncode = 0
                rec.cli_session_id = "sess-live"
                pool._live = sum(
                    1
                    for item in pool._workers.values()
                    if item.status in {"queued", "running"}
                )

        pool._run_worker = gated_run  # type: ignore[method-assign]
        meta = pool.dispatch("p-0", "c0", wait=False)
        self.assertTrue(entered.wait(timeout=2))
        with self.assertRaises(PoolError) as ctx:
            pool.dispatch("second", "x", wait=False)
        self.assertEqual(ctx.exception.code, "budget_exhausted")
        gate.set()
        pool.await_worker(meta["worker_id"], timeout_seconds=2)

    def test_continue_turns_and_resume_argv(self):
        def runner(
            *,
            prompt,
            description,
            worker_id,
            pool,
            turn=1,
            resume_session_id=None,
        ):
            return WorkerRecord(
                worker_id=worker_id,
                description=description,
                prompt_sha256=sha256_text(prompt),
                status="completed",
                created_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                returncode=0,
                result_text="turn-%d" % turn,
                cli_session_id=resume_session_id or "sess-abc",
                turn_index=turn,
            )

        pool = GrokWorkerPool(
            max_concurrent=1,
            max_total=1,
            max_worker_turns=4,
            backend="cursor",
            runner=runner,
        )
        first = pool.dispatch("start", "t1")
        worker_id = first["worker_id"]
        self.assertEqual(first["turn_index"], 1)
        self.assertEqual(first["cli_session_id"], "sess-abc")
        for turn in (2, 3, 4):
            cont = pool.continue_worker(worker_id, "follow-%d" % turn, "c%d" % turn)
            self.assertEqual(cont["status"], "completed")
            self.assertEqual(cont["turn_index"], turn)
            self.assertEqual(cont["cli_session_id"], "sess-abc")
        with self.assertRaises(PoolError) as ctx:
            pool.continue_worker(worker_id, "too-many", "x")
        self.assertEqual(ctx.exception.code, "turns_exhausted")
        with self.assertRaises(PoolError) as ctx:
            pool.dispatch("another", "x")
        self.assertEqual(ctx.exception.code, "budget_exhausted")

        resume_argv = build_worker_argv(
            "delta",
            model="cursor-grok-4.5-high",
            backend="cursor",
            resume_session_id="sess-abc",
        )
        self.assertEqual(
            resume_argv[resume_argv.index("--resume") + 1], "sess-abc"
        )

    def test_continue_requires_session_id(self):
        def runner(*, prompt, description, worker_id, pool, **_kwargs):
            return WorkerRecord(
                worker_id=worker_id,
                description=description,
                prompt_sha256=sha256_text(prompt),
                status="completed",
                created_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                returncode=0,
                result_text="ok",
                cli_session_id=None,
            )

        pool = GrokWorkerPool(
            max_concurrent=1,
            max_total=1,
            max_worker_turns=4,
            backend="cursor",
            runner=runner,
        )
        first = pool.dispatch("start", "t1")
        with self.assertRaises(PoolError) as ctx:
            pool.continue_worker(first["worker_id"], "more", "c2")
        self.assertEqual(ctx.exception.code, "resume_unavailable")

    def test_parent_policy_mentions_continue(self):
        text = worker_dispatch_parent_policy(1, max_worker_turns=4)
        self.assertIn("continue_grok_worker", text)
        self.assertIn("4 conversational turns", text)
        self.assertIn("gap-fill", text)

    def test_extract_cli_session_id(self):
        fixture = (
            Path(__file__).resolve().parent.parent
            / "CLI_test"
            / "results"
            / "cursor_grok"
            / "20260810T015914Z"
            / "json_format.stdout.json"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            extract_cli_session_id(fixture),
            "4e906b1d-7a72-4dca-a18b-5b2aec8ede8e",
        )

    def test_prepare_worker_session_claude_and_grok(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            claude = prepare_worker_session(
                context,
                family="claude",
                max_workers=4,
                allow_web=False,
                worker_backend="xai",
            )
            # May be None if grok binary missing in CI; skip soft.
            if claude is None:
                self.skipTest("xAI grok binary unavailable")
            self.assertTrue(claude.enabled)
            self.assertIsNotNone(claude.mcp_config_path)
            self.assertTrue(claude.mcp_config_path.is_file())
            self.assertEqual(
                claude.env_updates.get("GROK_WORKER_BACKEND"), "xai"
            )

            grok = prepare_worker_session(
                context / "g",
                family="grok",
                max_workers=4,
                worker_backend="xai",
            )
            self.assertIsNotNone(grok)
            self.assertIsNotNone(grok.grok_home)
            self.assertTrue((grok.grok_home / "config.toml").is_file())
            self.assertIn("GROK_HOME", grok.env_updates)
            self.assertIn("UV_CACHE_DIR", grok.env_updates)

            disabled = prepare_worker_session(
                context, family="claude", max_workers=0, worker_backend="xai"
            )
            self.assertIsNone(disabled)

            qwen = prepare_worker_session(
                context, family="qwen", max_workers=4, worker_backend="xai"
            )
            self.assertIsNotNone(qwen)
            self.assertIsNone(qwen.mcp_config_path)

    def test_prepare_worker_session_cursor_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            with mock.patch(
                "pure_tate.grok_workers.worker_backend_available",
                return_value=True,
            ), mock.patch.dict(
                "os.environ", {"CURSOR_API_KEY": "crsr_test_key"}, clear=False
            ):
                session = prepare_worker_session(
                    context,
                    family="cursor",
                    max_workers=4,
                    worker_backend="cursor",
                    worker_model="cursor-grok-4.5-high",
                )
            self.assertIsNotNone(session)
            mcp = context / ".cursor" / "mcp.json"
            self.assertTrue(mcp.is_file())
            self.assertEqual(session.mcp_config_path, mcp)
            self.assertEqual(
                session.env_updates.get("GROK_WORKER_BACKEND"), "cursor"
            )
            self.assertEqual(
                session.env_updates.get("GROK_WORKER_MODEL"),
                "cursor-grok-4.5-high",
            )
            self.assertEqual(
                session.env_updates.get("CURSOR_API_KEY"), "crsr_test_key"
            )

            argv = apply_workers_to_argv(
                [
                    "cursor-agent",
                    "-p",
                    "--mode",
                    "ask",
                    "--model",
                    "cursor-grok-4.5-high",
                    "hello",
                ],
                "cursor",
                session,
            )
            self.assertIn("--approve-mcps", argv)
            self.assertEqual(argv[-1], "hello")

    def test_cursor_worker_argv_and_result_extract(self):
        argv = build_worker_argv(
            "worker prompt",
            model="cursor-grok-4.5-high",
            cwd=Path("/tmp/ws"),
            backend="cursor",
        )
        self.assertEqual(argv[0], "cursor-agent")
        self.assertEqual(argv[argv.index("--mode") + 1], "ask")
        self.assertNotIn("--force", argv)
        self.assertNotIn("--yolo", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertEqual(
            argv[argv.index("--model") + 1], "cursor-grok-4.5-high"
        )
        self.assertEqual(argv[argv.index("--workspace") + 1], "/tmp/ws")
        self.assertEqual(argv[-1], "worker prompt")
        redacted = redact_argv(argv, "worker prompt")
        self.assertTrue(redacted[-1].startswith("<prompt-sha256:"))
        self.assertEqual(redacted[argv.index("--mode") + 1], "ask")

        web_argv = build_worker_argv(
            "worker prompt",
            model="cursor-grok-4.5-high",
            cwd=Path("/tmp/ws"),
            backend="cursor",
            allow_web=True,
        )
        self.assertEqual(web_argv[web_argv.index("--mode") + 1], "ask")
        self.assertIn("--force", web_argv)
        self.assertLess(
            web_argv.index("--mode"), web_argv.index("--force")
        )
        self.assertLess(
            web_argv.index("--force"), web_argv.index("--output-format")
        )

        fixture = (
            Path(__file__).resolve().parent.parent
            / "CLI_test"
            / "results"
            / "cursor_grok"
            / "20260810T015914Z"
            / "json_format.stdout.json"
        ).read_text(encoding="utf-8")
        text = extract_result_text(fixture)
        self.assertIn('"probe":"json_format"', text)

        self.assertEqual(
            resolve_worker_backend({"grok_worker_backend": "cursor"}), "cursor"
        )
        self.assertEqual(
            resolve_worker_model(
                {
                    "grok_worker_backend": "cursor",
                    "grok_worker_model": "cursor-grok-4.5-high",
                },
                backend="cursor",
            ),
            "cursor-grok-4.5-high",
        )

    def test_prepare_controller_session_never_attaches_mcp(self):
        with tempfile.TemporaryDirectory() as directory:
            session = prepare_worker_session(
                Path(directory),
                family="openai",
                max_workers=4,
                attach_mcp=False,
                worker_backend="xai",
            )
            if session is None:
                self.skipTest("xAI grok binary unavailable")
            self.assertTrue(session.enabled)
            self.assertIsNone(session.mcp_config_path)
            self.assertIsNone(session.grok_home)
            self.assertIsNotNone(session.dispatch_log)

    def test_apply_workers_to_claude_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            mcp = Path(directory) / "mcp.json"
            mcp.write_text("{}", encoding="utf-8")
            session = WorkerSession(
                enabled=True,
                max_workers=4,
                allow_web=False,
                family="claude",
                results_dir=Path(directory) / "w",
                mcp_config_path=mcp,
                server_command=["uv", "run", "python", "x"],
            )
            base = [
                "claude",
                "-p",
                "hi",
                "--permission-mode",
                "default",
                "--allowedTools",
                "Read",
                "Grep",
                "--disallowedTools",
                "Bash",
            ]
            out = apply_workers_to_argv(base, "claude", session)
            self.assertEqual(
                out[out.index("--permission-mode") + 1], "bypassPermissions"
            )
            self.assertIn("mcp__grok-workers__dispatch_grok_worker", out)
            self.assertIn("mcp__grok-workers__continue_grok_worker", out)
            self.assertIn("--mcp-config", out)
            self.assertIn("--strict-mcp-config", out)

    def test_apply_workers_to_codex_argv_includes_session_environment(self):
        session = WorkerSession(
            enabled=True,
            max_workers=1,
            allow_web=False,
            family="openai",
            results_dir=Path("/tmp/pure-tate-workers"),
            server_command=["uv", "run", "python", "worker.py"],
            env_updates={
                "GROK_WORKER_RESULTS_DIR": "/tmp/pure-tate-workers",
                "GROK_WORKER_SESSION_ID": "SESS-test",
            },
        )
        out = apply_workers_to_argv(
            ["codex", "exec", "--json", "prompt"], "openai", session
        )
        override = out[out.index("-c") + 1]
        self.assertIn("mcp_servers.grok_workers=", override)
        self.assertIn("GROK_WORKER_RESULTS_DIR", override)
        self.assertIn("GROK_WORKER_SESSION_ID", override)

    def test_mcp_server_command_shape(self):
        cmd = mcp_server_command()
        self.assertGreaterEqual(len(cmd), 2)
        self.assertTrue(any("grok_workers.py" in part for part in cmd))
        self.assertIn("--no-project", cmd)
        self.assertIn("--serve-mcp", cmd)

    def test_dispatch_log_records_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            log_root = Path(directory) / "worker-dispatches"
            dlog = DispatchLog(
                log_root,
                session_id="SESS-testlog",
                parent={"engine": "grok", "task_id": "TASK-X"},
            )

            def runner(*, prompt, description, worker_id, pool, **_kwargs):
                return WorkerRecord(
                    worker_id=worker_id,
                    description=description,
                    prompt_sha256=sha256_text(prompt),
                    status="completed",
                    created_at=utc_now_iso(),
                    finished_at=utc_now_iso(),
                    returncode=0,
                    result_text='{"ok":true}',
                    cli_session_id="sess-log",
                )

            pool = GrokWorkerPool(
                max_concurrent=1,
                max_total=1,
                max_worker_turns=4,
                dispatch_log=dlog,
                runner=runner,
            )
            result = pool.dispatch("do work", "unit", wait=True)
            self.assertEqual(result["status"], "completed")

            with self.assertRaises(PoolError) as ctx:
                pool.dispatch("overflow", "x")
            self.assertEqual(ctx.exception.code, "budget_exhausted")

            events_path = log_root / "events.jsonl"
            self.assertTrue(events_path.is_file())
            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            types = [e["event"] for e in events]
            self.assertIn("dispatch", types)
            self.assertIn("worker_finished", types)
            self.assertIn("dispatch_rejected", types)
            session_meta = json.loads(
                (log_root / "sessions" / "SESS-testlog" / "session.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(session_meta["parent"]["task_id"], "TASK-X")
            self.assertEqual(
                (log_root / "latest.txt").read_text(encoding="utf-8").strip(),
                "SESS-testlog",
            )

    def test_ensure_dispatch_log_dir_creates_readme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = ensure_dispatch_log_dir(Path(directory) / "dispatches")
            self.assertTrue(root.is_dir())
            self.assertTrue((root / "README.md").is_file())

    def test_records_codex_client_side_mcp_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "worker-dispatches"
            session = WorkerSession(
                enabled=True,
                max_workers=1,
                allow_web=False,
                family="openai",
                results_dir=Path(directory) / "workers",
                env_updates={
                    "GROK_WORKER_LOG_DIR": str(root),
                    "GROK_WORKER_SESSION_ID": "SESS-client-cancel",
                },
            )
            DispatchLog(root, session_id="SESS-client-cancel").log("session_open")
            stdout = json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "mcp_tool_call",
                        "server": "grok_workers",
                        "tool": "dispatch_grok_worker",
                        "status": "failed",
                        "result": None,
                        "error": {"message": "user cancelled MCP tool call"},
                    },
                }
            )
            self.assertEqual(record_parent_mcp_events(session, stdout), 1)
            rows = [
                json.loads(line)
                for line in (root / "sessions" / "SESS-client-cancel" / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            attempt = [row for row in rows if row["event"] == "parent_mcp_attempt"]
            self.assertEqual(len(attempt), 1)
            self.assertEqual(attempt[0]["client_status"], "failed")
            self.assertEqual(attempt[0]["client_error"], "user cancelled MCP tool call")


if __name__ == "__main__":
    unittest.main()
