import json
import os
import unittest
from unittest.mock import patch

from pure_tate import qwen_worker


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"id":"resp-1","output_text":"docket"}'


class QwenWorkerTests(unittest.TestCase):
    def test_response_timeout_defaults_to_three_hours(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QWEN_RESPONSES_TIMEOUT", None)
            self.assertEqual(qwen_worker._responses_timeout(), 10_800)

    def test_response_timeout_is_capped_at_three_hours(self):
        with patch.dict(os.environ, {"QWEN_RESPONSES_TIMEOUT": "99999"}):
            self.assertEqual(qwen_worker._responses_timeout(), 10_800)

    def test_web_evidence_is_bounded_and_uses_required_reasoning(self):
        with patch(
            "pure_tate.qwen_worker.urllib.request.urlopen",
            return_value=_Response(),
        ) as open_url:
            result = qwen_worker._run_web_evidence(
                "find sources",
                {},
                api_key="test-key",
                model="qwen3.7-max",
                max_tokens=64_000,
                thinking_budget=16_384,
            )
        self.assertEqual(result, "docket")
        body = json.loads(open_url.call_args.args[0].data)
        self.assertEqual(body["max_output_tokens"], 6_000)
        self.assertTrue(body["enable_thinking"])
        self.assertEqual(
            body["thinking"]["budget_tokens"],
            qwen_worker.WEB_EVIDENCE_THINKING_BUDGET,
        )
        self.assertTrue(body["store"])
        self.assertEqual(body["tool_choice"], "auto")
        self.assertEqual(
            open_url.call_args.args[0].headers["X-dashscope-session-cache"],
            "enable",
        )
        self.assertEqual(
            open_url.call_args.kwargs["timeout"],
            qwen_worker.WEB_EVIDENCE_TIMEOUT_SECONDS,
        )

    def test_web_evidence_reserves_last_round_for_tool_free_synthesis(self):
        tool_call = {
            "id": "resp-tool",
            "output": [
                {
                    "type": "function_call",
                    "name": "read_file",
                    "call_id": "call-1",
                    "arguments": '{"path":"missing"}',
                }
            ],
        }
        final = {"id": "resp-final", "output_text": "short docket"}
        with patch(
            "pure_tate.qwen_worker._responses_request",
            side_effect=[tool_call, tool_call, final],
        ) as request:
            result = qwen_worker._run_web_evidence(
                "find sources",
                {},
                api_key="test-key",
                model="qwen3.7-max",
                max_tokens=64_000,
                thinking_budget=16_384,
            )
        self.assertEqual(result, "short docket")
        self.assertEqual(
            [call.kwargs["allow_tools"] for call in request.call_args_list],
            [True, True, False],
        )

    def test_final_stage_reserves_last_round_for_tool_free_synthesis(self):
        tool_message = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path":"missing"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        final = {"choices": [{"message": {"content": '{"ok":true}'}}]}
        with patch(
            "pure_tate.qwen_worker._request",
            side_effect=[tool_message, tool_message, final],
        ) as request:
            result = qwen_worker._run_without_web(
                "produce final artifact",
                {},
                api_key="test-key",
                model="qwen3.7-max",
                allow_grok=False,
                max_tokens=64_000,
                thinking_budget=16_384,
                max_tool_rounds=3,
            )
        self.assertEqual(result, '{"ok":true}')
        self.assertTrue(request.call_args_list[0].kwargs["tools"])
        self.assertTrue(request.call_args_list[1].kwargs["tools"])
        self.assertTrue(request.call_args_list[2].kwargs["tools"])
        self.assertEqual(
            [call.kwargs["tool_choice"] for call in request.call_args_list],
            ["auto", "auto", "none"],
        )

    def test_web_task_uses_docket_then_three_final_rounds(self):
        with patch("pure_tate.qwen_worker._api_key", return_value="test-key"), patch(
            "pure_tate.qwen_worker._allowlist", return_value={}
        ), patch(
            "pure_tate.qwen_worker._run_web_evidence", return_value="short sources"
        ), patch(
            "pure_tate.qwen_worker._run_without_web", return_value='{"ok": true}'
        ) as final:
            result = qwen_worker.run(
                "produce final artifact",
                [],
                model="qwen3.7-max",
                allow_grok=True,
                allow_web=True,
                max_tokens=64_000,
                thinking_budget=16_384,
            )
        self.assertEqual(result, '{"ok": true}')
        self.assertIn("short sources", final.call_args.args[0])
        self.assertTrue(final.call_args.kwargs["allow_grok"])
        self.assertEqual(final.call_args.kwargs["max_tool_rounds"], 3)

    def test_web_timeout_falls_forward_to_final_stage(self):
        with patch("pure_tate.qwen_worker._api_key", return_value="test-key"), patch(
            "pure_tate.qwen_worker._allowlist", return_value={}
        ), patch(
            "pure_tate.qwen_worker._run_web_evidence",
            side_effect=RuntimeError("timed out"),
        ), patch(
            "pure_tate.qwen_worker._run_without_web", return_value='{"ok": true}'
        ) as final:
            result = qwen_worker.run(
                "produce final artifact",
                [],
                model="qwen3.7-max",
                allow_grok=True,
                allow_web=True,
                max_tokens=64_000,
                thinking_budget=16_384,
            )
        self.assertEqual(result, '{"ok": true}')
        self.assertIn("bounded and unavailable", final.call_args.args[0])
        self.assertIn("timed out", final.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
