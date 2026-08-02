import os
import json
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from pure_tate.process_runner import (
    ProcessWatchdogError,
    run_captured_process,
)


class ProcessRunnerTests(unittest.TestCase):
    def test_engine_is_terminated_when_harness_parent_disappears(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(__file__).resolve().parent.parent
            status = Path(directory) / "process.json"
            source = (
                "import json,os,sys;"
                "from pathlib import Path;"
                "from pure_tate.process_runner import run_captured_process;"
                "run_captured_process([sys.executable,'-c','import time;time.sleep(60)'],"
                "cwd=Path(sys.argv[1]),env=dict(os.environ),timeout=60,"
                "on_process_start=lambda value: Path(sys.argv[2]).write_text(json.dumps(value)))"
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(root)
            parent = subprocess.Popen(
                [sys.executable, "-c", source, directory, str(status)], env=env
            )
            engine_pid = None
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and not status.exists():
                    time.sleep(0.05)
                self.assertTrue(status.exists(), "supervisor did not report its child")
                engine_pid = int(json.loads(status.read_text())["engine_pid"])
                parent.kill()
                parent.wait(timeout=5)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    try:
                        os.kill(engine_pid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.1)
                else:
                    self.fail("engine survived the death of its harness parent")
            finally:
                if parent.poll() is None:
                    parent.kill()
                    parent.wait(timeout=5)
                if engine_pid is not None:
                    try:
                        os.killpg(engine_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_streams_output_and_reports_activity(self):
        activity = []
        process_metadata = []
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
                on_process_start=process_metadata.append,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("out", result.stdout)
        self.assertIn("err", result.stderr)
        self.assertEqual({item[0] for item in activity}, {"stdout", "stderr"})
        self.assertEqual(len(process_metadata), 1)
        self.assertIsInstance(process_metadata[0].get("engine_pid"), int)
        self.assertIsInstance(process_metadata[0].get("supervisor_pid"), int)
        self.assertNotEqual(
            process_metadata[0]["engine_pid"],
            process_metadata[0]["supervisor_pid"],
        )

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
