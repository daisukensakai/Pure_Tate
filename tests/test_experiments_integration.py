import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pure_tate.experiments import (
    container_runtime,
    experiment_tasks,
    run_experiment,
)


def _runtime_usable() -> bool:
    runtime = container_runtime()
    if not runtime:
        return False
    try:
        result = subprocess.run(
            [runtime, "info"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


@unittest.skipUnless(
    _runtime_usable(),
    "Docker/Podman unavailable; deterministic Macaulay2 integration skipped explicitly",
)
class Macaulay2IntegrationTests(unittest.TestCase):
    def test_independent_reproduction_has_identical_stdout_hash(self):
        task = experiment_tasks("C66-001")[0]
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "EXP-INTEGRATION-run-0001.json"
            first = run_experiment(task, first_path, timeout=1800)
            reproduction_task = dict(task)
            reproduction_task["reproduction_of"] = str(first_path)
            reproduction_task["expected_stdout_sha256"] = first[
                "stdout_sha256"
            ]
            second_path = Path(directory) / "EXP-INTEGRATION-run-0002.json"
            second = run_experiment(
                reproduction_task, second_path, timeout=1800
            )
            self.assertTrue(second["reproduced"])
            self.assertEqual(
                first["stdout_sha256"], second["stdout_sha256"]
            )
            self.assertEqual(
                json.loads(second_path.read_text(encoding="utf-8"))[
                    "stdout_sha256"
                ],
                first["stdout_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
