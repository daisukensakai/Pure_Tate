import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from pure_tate.grok_workers import (
    DEFAULT_MAX_TOTAL,
    DispatchLog,
    GrokWorkerPool,
    PoolError,
    WorkerRecord,
    WorkerSession,
    apply_workers_to_argv,
    ensure_dispatch_log_dir,
    max_grok_workers_from_config,
    mcp_server_command,
    prepare_worker_session,
    record_parent_mcp_events,
    sha256_text,
    utc_now_iso,
)


class GrokWorkerPoolTests(unittest.TestCase):
    def test_max_config_defaults_and_disable(self):
        self.assertEqual(max_grok_workers_from_config({}), DEFAULT_MAX_TOTAL)
        self.assertEqual(
            max_grok_workers_from_config({"max_grok_workers": 4}), 4
        )
        self.assertEqual(
            max_grok_workers_from_config({"max_grok_workers": 99}), 4
        )
        self.assertEqual(
            max_grok_workers_from_config({"grok_workers_enabled": False}), 0
        )
        self.assertEqual(
            max_grok_workers_from_config({"max_grok_workers": 0}), 0
        )

    def test_total_budget_hard_cap(self):
        def runner(*, prompt, description, worker_id, pool):
            return WorkerRecord(
                worker_id=worker_id,
                description=description,
                prompt_sha256=sha256_text(prompt),
                status="completed",
                created_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                returncode=0,
                result_text="ok",
            )

        pool = GrokWorkerPool(
            max_concurrent=4, max_total=4, runner=runner
        )
        for i in range(4):
            result = pool.dispatch("p-%d" % i, "t%d" % i)
            self.assertEqual(result["status"], "completed")
        with self.assertRaises(PoolError) as ctx:
            pool.dispatch("overflow", "x")
        self.assertEqual(ctx.exception.code, "budget_exhausted")

    def test_concurrent_pool_full(self):
        pool = GrokWorkerPool(max_concurrent=4, max_total=10)
        gate = threading.Event()
        entered = threading.Event()
        count = {"n": 0}
        lock = threading.Lock()

        def gated_run(worker_id, prompt, timeout_seconds):
            with lock:
                count["n"] += 1
                if count["n"] >= 4:
                    entered.set()
            gate.wait(timeout=5)
            with pool._lock:
                rec = pool._workers[worker_id]
                rec.status = "completed"
                rec.finished_at = utc_now_iso()
                rec.returncode = 0
                pool._live = sum(
                    1
                    for item in pool._workers.values()
                    if item.status in {"queued", "running"}
                )

        pool._run_worker = gated_run  # type: ignore[method-assign]
        ids = []
        for i in range(4):
            meta = pool.dispatch("p-%d" % i, "c%d" % i, wait=False)
            ids.append(meta["worker_id"])
        self.assertTrue(entered.wait(timeout=2))
        with self.assertRaises(PoolError) as ctx:
            pool.dispatch("fifth", "x", wait=False)
        self.assertEqual(ctx.exception.code, "pool_full")
        gate.set()
        for wid in ids:
            pool.await_worker(wid, timeout_seconds=2)

    def test_prepare_worker_session_claude_and_grok(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            claude = prepare_worker_session(
                context,
                family="claude",
                max_workers=4,
                allow_web=False,
            )
            # May be None if grok binary missing in CI; skip soft.
            if claude is None:
                self.skipTest("grok binary unavailable")
            self.assertTrue(claude.enabled)
            self.assertIsNotNone(claude.mcp_config_path)
            self.assertTrue(claude.mcp_config_path.is_file())

            grok = prepare_worker_session(
                context / "g",
                family="grok",
                max_workers=4,
            )
            self.assertIsNotNone(grok)
            self.assertIsNotNone(grok.grok_home)
            self.assertTrue((grok.grok_home / "config.toml").is_file())
            self.assertIn("GROK_HOME", grok.env_updates)
            self.assertIn("UV_CACHE_DIR", grok.env_updates)

            disabled = prepare_worker_session(
                context, family="claude", max_workers=0
            )
            self.assertIsNone(disabled)

            gemini = prepare_worker_session(
                context, family="gemini", max_workers=4
            )
            self.assertIsNone(gemini)

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

            def runner(*, prompt, description, worker_id, pool):
                return WorkerRecord(
                    worker_id=worker_id,
                    description=description,
                    prompt_sha256=sha256_text(prompt),
                    status="completed",
                    created_at=utc_now_iso(),
                    finished_at=utc_now_iso(),
                    returncode=0,
                    result_text='{"ok":true}',
                )

            pool = GrokWorkerPool(
                max_concurrent=4,
                max_total=4,
                dispatch_log=dlog,
                runner=runner,
            )
            result = pool.dispatch("do work", "unit", wait=True)
            self.assertEqual(result["status"], "completed")

            with self.assertRaises(PoolError):
                # exhaust remaining budget with more dispatches then reject
                for i in range(3):
                    pool.dispatch("more-%d" % i, "u")
                pool.dispatch("overflow", "x")

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
