import os
import sys
import tempfile
import unittest
from pathlib import Path

from pure_tate.process_runner import (
    ProcessWatchdogError,
    run_captured_process,
)


class ProcessRunnerTests(unittest.TestCase):
    def test_streams_output_and_reports_activity(self):
        activity = []
        with tempfile.TemporaryDirectory() as directory:
            result = run_captured_process(
                [
                    sys.executable,
                    "-c",
                    "import sys; print('out'); print('err', file=sys.stderr)",
                ],
                cwd=Path(directory),
                env=dict(os.environ),
                timeout=10,
                on_activity=lambda stream, size, elapsed: activity.append(
                    (stream, size)
                ),
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("out", result.stdout)
        self.assertIn("err", result.stderr)
        self.assertEqual({item[0] for item in activity}, {"stdout", "stderr"})

    def test_repeated_fatal_pattern_stops_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProcessWatchdogError) as caught:
                run_captured_process(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import sys,time;"
                            "sys.stderr.write('status: 503\\n'*3);"
                            "sys.stderr.flush();time.sleep(10)"
                        ),
                    ],
                    cwd=Path(directory),
                    env=dict(os.environ),
                    timeout=10,
                    abort_stderr_pattern_counts={"status: 503": 3},
                )
        self.assertIn("repeated stderr pattern", str(caught.exception))
