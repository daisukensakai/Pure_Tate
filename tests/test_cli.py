import unittest

from pure_tate.cli import build_parser


class CliTests(unittest.TestCase):
    def test_operational_commands_are_registered(self):
        parser = build_parser()
        for argv, command in (
            (["fetch-source", "SRC-0001"], "fetch-source"),
            (["extract-source", "SRC-0001"], "extract-source"),
            (["corpus-search", "boundary"], "corpus-search"),
            (["corpus-audit"], "corpus-audit"),
            (["research-audit"], "research-audit"),
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
