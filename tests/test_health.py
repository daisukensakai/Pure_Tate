import unittest
from unittest import mock

from pure_tate.health import (
    audit_engine_health,
    eligible_engine_pool,
    engine_health_is_attested,
)


class EngineHealthTests(unittest.TestCase):
    def test_missing_health_receipt_fails_closed(self):
        with mock.patch(
            "pure_tate.health.load_engine_health", return_value=None
        ):
            self.assertFalse(engine_health_is_attested("qwen"))

    def test_non_live_health_is_read_only(self):
        with mock.patch(
            "pure_tate.health.load_engine_health",
            return_value={
                "schema_version": 1,
                "engine": "qwen",
                "status": "pass",
                "level": "artifact",
            },
        ):
            value = audit_engine_health("qwen", live=False)
        self.assertEqual(value["status"], "pass")

    def test_paid_pool_excludes_failed_attested_engine(self):
        with mock.patch(
            "pure_tate.health.engine_health_state",
            side_effect=lambda engine, phase: (
                "fail" if engine == "qwen" else "not_required"
            ),
        ):
            self.assertEqual(
                eligible_engine_pool(
                    ["grok", "qwen", "codex"],
                    "mathematics",
                    dry_run=False,
                ),
                ["grok", "codex"],
            )
            self.assertEqual(
                eligible_engine_pool(
                    ["grok", "qwen", "codex"],
                    "mathematics",
                    dry_run=True,
                ),
                    ["grok", "qwen", "codex"],
            )
