import unittest

from pure_tate.cli import build_parser


class CliTests(unittest.TestCase):
    def test_ntfy_defaults_to_local_configuration_and_can_be_disabled(self):
        parser = build_parser()
        base = [
            "drive",
            "--steps",
            "1",
            "--campaign",
            "C66-001",
            "--prover-engines",
            "grok",
            "claude",
            "--review-engines",
            "grok",
            "claude",
        ]
        self.assertIsNone(parser.parse_args(base).notify_ntfy)
        self.assertFalse(
            parser.parse_args(base + ["--no-notify-ntfy"]).notify_ntfy
        )

    def test_operational_commands_are_registered(self):
        parser = build_parser()
        for argv, command in (
            (["fetch-source", "SRC-0001"], "fetch-source"),
            (["extract-source", "SRC-0001"], "extract-source"),
            (["corpus-search", "boundary"], "corpus-search"),
            (["corpus-audit"], "corpus-audit"),
            (["research-audit"], "research-audit"),
            (["attest-finding-sources", "--dry-run"], "attest-finding-sources"),
            (["tasks", "--phase", "research"], "tasks"),
            (["tasks", "--phase", "review"], "tasks"),
            (["engines"], "engines"),
            (
                [
                    "agent-run",
                    "--manifest",
                    "tasks.json",
                    "--task-id",
                    "TASK-R-0001",
                    "--engine",
                    "claude",
                    "--output",
                    "research/audits/RAUD-0001.json",
                ],
                "agent-run",
            ),
        ):
            self.assertEqual(parser.parse_args(argv).command, command)


if __name__ == "__main__":
    unittest.main()
