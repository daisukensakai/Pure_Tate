import json
import unittest
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
    load_routing_config,
    next_escalation_engine,
    next_rotation_engine,
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
            ["grok", "claude", "grok", "codex", "grok", "gemini"],
        )
        self.assertEqual(
            self.routing["escalation_order"],
            ["grok", "gemini", "codex", "claude"],
        )
        self.assertIn("gemini", self.routing["engines"])

    def test_engine_inventory_includes_gemini(self):
        by_id = {item["id"]: item for item in engine_inventory()}
        self.assertEqual(by_id["gemini"]["model"], "gemini-3.5-flash")
        self.assertEqual(by_id["gemini"]["family"], "gemini")
        self.assertFalse(by_id["gemini"]["web_access"])

    def test_gemini_argv_is_plan_mode(self):
        command = _engine_argv("gemini", "prompt")
        self.assertEqual(command[command.index("-m") + 1], "gemini-3.5-flash")
        self.assertEqual(command[command.index("-o") + 1], "stream-json")
        self.assertEqual(
            command[command.index("--approval-mode") + 1], "plan"
        )
        self.assertIn("--skip-trust", command)

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

    def test_gemini_response_envelope_unwrap(self):
        artifact = _extract_json_object(
            '{"response": "{\\"id\\": \\"ATT-0001\\", \\"engine\\": \\"gemini\\"}",'
            ' "stats": {}}'
        )
        self.assertEqual(artifact["id"], "ATT-0001")
        nested = _extract_json_object(
            '{"response": {"id": "REV-0001", "reviewer_engine": "gemini"},'
            ' "session_id": "abc"}'
        )
        self.assertEqual(nested["id"], "REV-0001")

    def test_rotation_sequence(self):
        rotation = self.routing["prover_rotation"]
        expected = ["grok", "claude", "grok", "codex", "grok", "gemini"]
        actual = [next_rotation_engine(i, rotation) for i in range(6)]
        self.assertEqual(actual, expected)
        self.assertEqual(next_rotation_engine(6, rotation), "grok")

    def test_retry_escalation_ladder(self):
        escalation = self.routing["escalation_order"]
        self.assertEqual(next_escalation_engine([], escalation), "grok")
        self.assertEqual(
            next_escalation_engine(["grok"], escalation), "gemini"
        )
        self.assertEqual(
            next_escalation_engine(["grok", "gemini"], escalation), "codex"
        )
        self.assertEqual(
            next_escalation_engine(
                ["grok", "gemini", "codex"], escalation
            ),
            "claude",
        )
        self.assertIsNone(
            next_escalation_engine(
                ["grok", "gemini", "codex", "claude"], escalation
            )
        )

    def test_reviewer_skips_only_prover_and_used(self):
        escalation = self.routing["escalation_order"]
        self.assertEqual(
            select_reviewer("grok", [], escalation), "gemini"
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
            {"gemini", "codex"},
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
                prover_engines=["grok", "claude", "codex", "gemini"],
                review_engines=["grok", "claude", "codex", "gemini"],
                dry_run=True,
            )
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["executed_steps"], 6)
        engines = [event["engine"] for event in result["events"]]
        self.assertEqual(
            engines, ["grok", "claude", "grok", "codex", "grok", "gemini"]
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
