import unittest
from unittest import mock

from pure_tate.health import (
    audit_engine_health,
    eligible_engine_pool,
    engine_health_is_attested,
    engine_runtime_issue,
    operational_engine_pool,
)


class EngineHealthTests(unittest.TestCase):
    def test_qwen_without_credentials_is_not_operational(self):
        config = {"binary": "python3", "family": "qwen"}
        with mock.patch.dict(
            "os.environ",
            {"DASHSCOPE_API_KEY": ""},
            clear=False,
        ):
            self.assertIn("API_KEY", engine_runtime_issue("qwen", config))
            with mock.patch(
                "pure_tate.health.load_engines", return_value={"qwen": config}
            ), mock.patch(
                "pure_tate.health.engine_health_state", return_value="not_required"
            ):
                self.assertEqual(
                    operational_engine_pool(["qwen"], "finding-audit"), []
                )

    def test_cursor_grok_without_credentials_is_not_operational(self):
        config = {"binary": "cursor-agent", "family": "cursor"}
        with mock.patch(
            "pure_tate.health.shutil.which", return_value="/usr/bin/cursor-agent"
        ), mock.patch.dict(
            "os.environ",
            {"CURSOR_API_KEY": ""},
            clear=False,
        ):
            self.assertIn(
                "CURSOR_API_KEY", engine_runtime_issue("cursor-grok", config)
            )

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
