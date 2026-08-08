import io
import json
import os
import unittest
from unittest.mock import patch

from pure_tate import qwen_worker


def _sse_body(events):
    """Build an OpenAI-compatible SSE body from dict events or raw strings."""
    lines = []
    for event in events:
        if event == "[DONE]":
            lines.append("data: [DONE]\n")
        elif isinstance(event, str):
            lines.append("data: %s\n" % event)
        else:
            lines.append("data: %s\n" % json.dumps(event))
        lines.append("\n")
    return "".join(lines).encode("utf-8")


class _StreamResponse:
    status = 200

    def __init__(self, body: bytes):
        self._buf = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def readline(self):
        return self._buf.readline()

    def read(self):
        return self._buf.read()


class _JsonResponse:
    status = 200

    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._raw


class QwenWorkerTests(unittest.TestCase):
    def test_request_body_includes_reasoning_effort(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": '{"ok":true}',
                                }
                            }
                        ],
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=None):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch.object(qwen_worker, "_stream_enabled", return_value=False), patch(
            "pure_tate.qwen_worker.urllib.request.urlopen", side_effect=fake_urlopen
        ), patch.object(qwen_worker, "_emit"):
            qwen_worker._request(
                api_key="test-key",
                model="qwen3.8-max",
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                max_tokens=100,
                thinking_budget=1024,
                reasoning_effort="xhigh",
            )
        self.assertEqual(captured["body"]["model"], "qwen3.8-max")
        self.assertEqual(captured["body"]["reasoning_effort"], "xhigh")
        self.assertTrue(captured["body"]["enable_thinking"])
        self.assertNotIn("thinking_budget", captured["body"])

    def test_response_timeout_defaults_to_three_hours(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QWEN_RESPONSES_TIMEOUT", None)
            self.assertEqual(qwen_worker._responses_timeout(), 10_800)

    def test_response_timeout_is_capped_at_three_hours(self):
        with patch.dict(os.environ, {"QWEN_RESPONSES_TIMEOUT": "99999"}):
            self.assertEqual(qwen_worker._responses_timeout(), 10_800)

    def test_stream_enabled_defaults_on(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QWEN_STREAM", None)
            self.assertTrue(qwen_worker._stream_enabled())

    def test_stream_can_be_disabled(self):
        with patch.dict(os.environ, {"QWEN_STREAM": "0"}):
            self.assertFalse(qwen_worker._stream_enabled())

    def test_chat_stream_reassembles_content_and_tool_calls(self):
        body = _sse_body(
            [
                {
                    "id": "chatcmpl-1",
                    "choices": [
                        {
                            "delta": {
                                "role": "assistant",
                                "reasoning_content": "plan ",
                            }
                        }
                    ],
                },
                {
                    "choices": [
                        {"delta": {"reasoning_content": "tools"}}
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {
                                            "name": "read_file",
                                            "arguments": "",
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": '{"path":"a.txt"}'
                                        },
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                },
                "[DONE]",
            ]
        )
        events = []
        with patch.object(qwen_worker, "_emit", side_effect=events.append):
            payload = qwen_worker._consume_chat_sse(
                _StreamResponse(body), stage="final_round_1"
            )
        message = payload["choices"][0]["message"]
        self.assertEqual(message.get("reasoning_content"), "plan tools")
        self.assertEqual(message.get("content"), "")
        self.assertEqual(len(message["tool_calls"]), 1)
        self.assertEqual(message["tool_calls"][0]["id"], "call-1")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(
            message["tool_calls"][0]["function"]["arguments"],
            '{"path":"a.txt"}',
        )
        types = [event["type"] for event in events]
        self.assertIn("thought", types)
        self.assertIn("tool_call", types)
        self.assertIn("end", types)

    def test_chat_stream_emits_text_deltas(self):
        body = _sse_body(
            [
                {
                    "id": "chatcmpl-2",
                    "choices": [{"delta": {"content": '{"ok":'}}],
                },
                {
                    "choices": [
                        {"delta": {"content": "true}"}, "finish_reason": "stop"}
                    ]
                },
                {"usage": {"total_tokens": 9}},
                "[DONE]",
            ]
        )
        events = []
        with patch.object(qwen_worker, "_emit", side_effect=events.append):
            payload = qwen_worker._consume_chat_sse(
                _StreamResponse(body), stage="final_round_1"
            )
        self.assertEqual(payload["choices"][0]["message"]["content"], '{"ok":true}')
        text = "".join(
            event["data"] for event in events if event.get("type") == "text"
        )
        self.assertEqual(text, '{"ok":true}')

    def test_responses_stream_reassembles_output_text(self):
        body = _sse_body(
            [
                {
                    "type": "response.created",
                    "response": {"id": "resp-9", "status": "in_progress"},
                },
                {
                    "type": "response.output_text.delta",
                    "delta": "short ",
                },
                {
                    "type": "response.output_text.delta",
                    "delta": "docket",
                },
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp-9",
                        "status": "completed",
                        "output": [
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "short docket",
                                    }
                                ],
                            }
                        ],
                        "usage": {"total_tokens": 12},
                    },
                },
            ]
        )
        events = []
        with patch.object(qwen_worker, "_emit", side_effect=events.append):
            payload = qwen_worker._consume_responses_sse(
                _StreamResponse(body), stage="web_evidence_round_1"
            )
        self.assertEqual(payload["id"], "resp-9")
        self.assertEqual(qwen_worker._responses_text(payload), "short docket")
        text = "".join(
            event["data"] for event in events if event.get("type") == "text"
        )
        self.assertEqual(text, "short docket")

    def test_web_evidence_is_bounded_and_uses_required_reasoning(self):
        body = _sse_body(
            [
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp-1",
                        "status": "completed",
                        "output_text": "docket",
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {"type": "output_text", "text": "docket"}
                                ],
                            }
                        ],
                    },
                }
            ]
        )
        with patch.dict(os.environ, {"QWEN_STREAM": "1"}), patch(
            "pure_tate.qwen_worker.urllib.request.urlopen",
            return_value=_StreamResponse(body),
        ) as open_url, patch.object(qwen_worker, "_emit"):
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
        self.assertTrue(body["stream"])
        self.assertEqual(body["tool_choice"], "auto")
        self.assertEqual(
            open_url.call_args.args[0].headers["X-dashscope-session-cache"],
            "enable",
        )
        self.assertEqual(
            open_url.call_args.kwargs["timeout"],
            qwen_worker.WEB_EVIDENCE_TIMEOUT_SECONDS,
        )

    def test_web_evidence_nonstream_fallback(self):
        with patch.dict(os.environ, {"QWEN_STREAM": "0"}), patch(
            "pure_tate.qwen_worker.urllib.request.urlopen",
            return_value=_JsonResponse({"id": "resp-1", "output_text": "docket"}),
        ) as open_url, patch.object(qwen_worker, "_emit"):
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
        self.assertNotIn("stream", body)

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
        ) as request, patch.object(qwen_worker, "_emit"):
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
        ) as request, patch.object(qwen_worker, "_emit"):
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
        ) as final, patch.object(qwen_worker, "_emit"):
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
        ) as final, patch.object(qwen_worker, "_emit"):
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
