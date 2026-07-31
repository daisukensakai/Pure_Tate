import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.agents import _extract_gemini_stream
from pure_tate.health import (
    audit_engine_health,
    eligible_engine_pool,
    engine_health_is_attested,
)


class EngineHealthTests(unittest.TestCase):
    def test_gemini_stream_json_is_reassembled(self):
        stream = "\n".join(
            [
                '{"type":"init","session_id":"abc"}',
                '{"type":"message","role":"assistant","content":"{\\"probe\\":",'
                '"delta":true}',
                '{"type":"message","role":"assistant","content":"\\"basic\\",'
                '\\"ok\\":true}","delta":true}',
                '{"type":"result","status":"success"}',
            ]
        )
        self.assertEqual(
            _extract_gemini_stream(stream),
            {"probe": "basic", "ok": True},
        )

    def test_gemini_stream_recovers_latex_backslashes_and_prefers_outer_object(self):
        # Nested target-like object must not win when the outer attempt JSON
        # only fails because LaTeX used bare backslashes.
        body = (
            '{\n'
            '  "schema_version": 3,\n'
            '  "id": "ATT-9998",\n'
            '  "target": {"g": 6, "n": 6, "dimension": 21},\n'
            '  "summary": "Use $\\omega_C$ and $\\Gamma$.",\n'
            '  "status": "proposed"\n'
            '}'
        )
        # body above has real single backslashes before omega/Gamma once encoded
        # into the stream JSON string.
        stream = "\n".join(
            [
                '{"type":"init","session_id":"abc"}',
                json.dumps(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": body,
                        "delta": True,
                    }
                ),
                '{"type":"result","status":"success"}',
            ]
        )
        artifact = _extract_gemini_stream(stream)
        self.assertEqual(artifact.get("id"), "ATT-9998")
        self.assertEqual(artifact.get("schema_version"), 3)
        self.assertIn("\\omega_C", artifact["summary"])
        self.assertIn("\\Gamma", artifact["summary"])
        self.assertNotEqual(set(artifact.keys()), {"g", "n", "dimension"})
    def test_missing_health_receipt_fails_closed(self):
        with mock.patch(
            "pure_tate.health.load_engine_health", return_value=None
        ):
            self.assertFalse(engine_health_is_attested("gemini"))

    def test_non_live_health_is_read_only(self):
        with mock.patch(
            "pure_tate.health.load_engine_health",
            return_value={
                "schema_version": 1,
                "engine": "gemini",
                "status": "pass",
                "level": "artifact",
            },
        ):
            value = audit_engine_health("gemini", live=False)
        self.assertEqual(value["status"], "pass")

    def test_paid_pool_excludes_failed_attested_engine(self):
        with mock.patch(
            "pure_tate.health.engine_health_state",
            side_effect=lambda engine, phase: (
                "fail" if engine == "gemini" else "not_required"
            ),
        ):
            self.assertEqual(
                eligible_engine_pool(
                    ["grok", "gemini", "codex"],
                    "mathematics",
                    dry_run=False,
                ),
                ["grok", "codex"],
            )
            self.assertEqual(
                eligible_engine_pool(
                    ["grok", "gemini", "codex"],
                    "mathematics",
                    dry_run=True,
                ),
                ["grok", "gemini", "codex"],
            )
