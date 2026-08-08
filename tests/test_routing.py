import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.agents import (
    _engine_argv,
    _extract_claude_stream,
    _extract_grok_stream,
    _extract_json_object,
    _grok_observable_stream,
    _subprocess_env,
    engine_inventory,
)
from pure_tate.driver import drive
from pure_tate.routing import (
    high_tier_chain_order,
    high_tier_chain_state,
    load_routing_config,
    next_escalation_engine,
    next_rotation_engine,
    record_high_tier_dispatch,
    select_prover_for_cell,
    select_reviewer,
)
from pure_tate.store import ROOT, load_repository
from pure_tate.tasking import mathematics_tasks


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = load_routing_config()
        cls.config, _target, cls.sources, cls.claims, _edges = load_repository()
        cls.tasks = mathematics_tasks(cls.config, cls.claims, cls.sources)

    def test_routing_config_pins_ladders(self):
        self.assertEqual(
            self.routing["prover_rotation"],
            ["grok", "claude", "grok", "codex", "grok", "qwen"],
        )
        self.assertEqual(
            self.routing["escalation_order"],
            ["grok", "qwen"],
        )
        self.assertEqual(
            self.routing["high_tier_chain_engines"], ["claude", "codex"]
        )
        self.assertIn("qwen", self.routing["engines"])

    def test_engine_inventory_includes_qwen(self):
        by_id = {item["id"]: item for item in engine_inventory()}
        self.assertEqual(by_id["qwen"]["model"], "qwen3.8-max")
        self.assertEqual(by_id["qwen"]["family"], "qwen")
        self.assertTrue(by_id["qwen"]["web_access"])

    def test_qwen_argv_uses_local_scoped_adapter(self):
        command = _engine_argv(
            "qwen", "prompt", phase="finding-audit", context_files=["TASK.json"]
        )
        self.assertEqual(command[command.index("--model") + 1], "qwen3.8-max")
        self.assertEqual(
            command[command.index("--reasoning-effort") + 1], "xhigh"
        )
        self.assertIn(str(ROOT / "pure_tate" / "qwen_worker.py"), command)
        self.assertEqual(command[command.index("--context-file") + 1], "TASK.json")
        self.assertIn("--allow-web", command)

    def test_codex_web_phases_enable_live_search(self):
        command = _engine_argv(
            "codex", "prompt", Path("/tmp/pure-tate-last-message"), phase="finding-audit"
        )
        self.assertIn("--search", command)

    def test_grok_uses_fixture_verified_streaming_json(self):
        command = _engine_argv("grok", "prompt")
        self.assertEqual(
            command[command.index("--output-format") + 1],
            "streaming-json",
        )
        basic = (
            ROOT / "CLI_test" / "results" / "basic.stdout.jsonl"
        ).read_text(encoding="utf-8")
        read_tool = (
            ROOT / "CLI_test" / "results" / "read_tool.stdout.jsonl"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _extract_grok_stream(basic),
            {
                "probe": "basic",
                "ok": True,
                "latex": r"\Gamma and \omega_C",
            },
        )
        self.assertEqual(
            _extract_grok_stream(read_tool)["marker"],
            "PURE_TATE_GROK_STREAM_MARKER_20260731",
        )
        observable = _grok_observable_stream(read_tool)
        self.assertNotIn('"type": "thought"', observable)
        self.assertIn('"type": "text"', observable)
        self.assertIn('"type": "end"', observable)

    def test_grok_stream_error_is_clear(self):
        with self.assertRaisesRegex(ValueError, "Not signed in"):
            _extract_grok_stream(
                '{"type":"error","message":"Not signed in"}\n'
            )

    def test_claude_uses_streaming_and_pinned_output_cap(self):
        command = _engine_argv("claude", "prompt")
        self.assertEqual(
            command[command.index("--output-format") + 1], "stream-json"
        )
        self.assertIn("--include-partial-messages", command)
        self.assertIn("--verbose", command)
        env = _subprocess_env(
            "claude", {"max_output_tokens": 64000}
        )
        self.assertEqual(env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "64000")

    def test_claude_stream_extracts_final_json(self):
        artifact = '{"id":"ATT-0099","engine":"claude"}'
        stream = "\n".join(
            [
                '{"type":"system","subtype":"init","session_id":"abc"}',
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "text", "text": artifact}
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "result",
                        "subtype": "success",
                        "is_error": False,
                        "result": artifact,
                    }
                ),
            ]
        )
        self.assertEqual(
            _extract_claude_stream(stream),
            {"id": "ATT-0099", "engine": "claude"},
        )

    def test_json_object_extracts_direct_qwen_artifact(self):
        artifact = _extract_json_object(
            '{"id": "ATT-0001", "engine": "qwen"}'
        )
        self.assertEqual(artifact["id"], "ATT-0001")

    def test_rotation_sequence(self):
        rotation = self.routing["prover_rotation"]
        expected = ["grok", "claude", "grok", "codex", "grok", "qwen"]
        actual = [next_rotation_engine(i, rotation) for i in range(6)]
        self.assertEqual(actual, expected)
        self.assertEqual(next_rotation_engine(6, rotation), "grok")

    def test_retry_escalation_ladder(self):
        escalation = self.routing["escalation_order"]
        self.assertEqual(next_escalation_engine([], escalation), "grok")
        self.assertEqual(
            next_escalation_engine(["grok"], escalation), "qwen"
        )
        self.assertEqual(
            next_escalation_engine(
                ["grok", "qwen"], escalation,
                high_tier_order=["claude", "codex"],
            ),
            "claude",
        )
        self.assertEqual(
            next_escalation_engine(
                ["grok", "qwen", "claude"], escalation,
                high_tier_order=["claude", "codex"],
            ),
            "codex",
        )
        self.assertIsNone(
            next_escalation_engine(
                ["grok", "qwen", "claude", "codex"], escalation,
                high_tier_order=["claude", "codex"],
            )
        )
        self.assertEqual(
            next_escalation_engine(
                ["codex"], escalation,
                high_tier_order=["claude", "codex"],
            ),
            "claude",
        )

    def test_reviewer_skips_only_prover_and_used(self):
        escalation = self.routing["escalation_order"]
        self.assertEqual(
            select_reviewer("grok", [], escalation), "qwen"
        )
        self.assertEqual(
            select_reviewer("claude", [], escalation), "grok"
        )
        first = select_reviewer("grok", [], escalation)
        second = select_reviewer("grok", [first], escalation)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, "grok")
        self.assertNotEqual(second, "grok")
        self.assertEqual(
            {first, second},
            {"qwen", "claude"},
        )

    def test_high_tier_orders_alternate_by_chain_and_keep_pending_slots(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "pure_tate.routing.HIGH_TIER_LEDGER",
            Path(directory) / "high-tier-turns.json",
        ):
            first = high_tier_chain_order("proof:A")
            second = high_tier_chain_order("proof:B")
            self.assertEqual(first, ["claude", "codex"])
            self.assertEqual(second, ["codex", "claude"])
            record_high_tier_dispatch("proof:A", "claude")
            self.assertEqual(
                high_tier_chain_state("proof:A")["pending"], ["codex"]
            )

    def test_unavailable_first_high_tier_slot_is_deferred_not_substituted(self):
        engine = select_prover_for_cell(
            0,
            ["grok", "qwen"],
            self.routing["prover_rotation"],
            self.routing["escalation_order"],
            allowed=["codex"],
            chain_id="proof:deferred",
            persist_chain=False,
        )
        # Preferred high-tier slot is claude (unavailable); do not substitute
        # codex.  Escalation is blocked, but the cell may still open a fresh
        # rotation start restricted to the allowlist.
        self.assertEqual(engine, "codex")

    def test_exhausted_ladder_falls_back_to_fresh_rotation(self):
        rotation = self.routing["prover_rotation"]
        escalation = self.routing["escalation_order"]
        used = ["grok", "qwen", "claude", "codex"]
        # Ladder itself is still exhausted (forward-only).
        self.assertIsNone(
            next_escalation_engine(
                used,
                escalation,
                high_tier_order=["claude", "codex"],
            )
        )
        # Cell selection opens a fresh rotation start by ordinal.
        self.assertEqual(
            select_prover_for_cell(
                0,
                used,
                rotation,
                escalation,
                chain_id="proof:fresh-rotation",
                persist_chain=False,
            ),
            "grok",
        )
        self.assertEqual(
            select_prover_for_cell(
                1,
                used,
                rotation,
                escalation,
                chain_id="proof:fresh-rotation",
                persist_chain=False,
            ),
            "claude",
        )
        # Allowlist can restrict the fresh rotation start.
        self.assertEqual(
            select_prover_for_cell(
                0,
                used,
                rotation,
                escalation,
                allowed=["claude", "grok"],
                chain_id="proof:fresh-rotation-pool",
                persist_chain=False,
            ),
            "grok",
        )

    def test_driver_dry_run_follows_explicit_rotation_pool(self):
        with mock.patch(
            "pure_tate.driver.review_tasks", return_value=[]
        ), mock.patch(
            "pure_tate.driver._current_math_attempt_count", return_value=0
        ), mock.patch(
            "pure_tate.driver._current_attempt_engines_by_task", return_value={}
        ):
            result = drive(
                6,
                prover_engines=["grok", "claude", "codex", "qwen"],
                review_engines=["grok", "claude", "codex", "qwen"],
                dry_run=True,
            )
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["executed_steps"], 6)
        engines = [event["engine"] for event in result["events"]]
        self.assertEqual(
            engines, ["grok", "claude", "grok", "codex", "grok", "qwen"]
        )
        self.assertEqual(
            len({event["task_id"] for event in result["events"]}), 6
        )
        task_map = {task["id"]: task for task in self.tasks}
        approaches = {
            task_map[event["task_id"]]["approach_id"]
            for event in result["events"]
        }
        self.assertGreaterEqual(len(approaches), 5)
        self.assertEqual(result["stop_reason"], "step_limit")


if __name__ == "__main__":
    unittest.main()
