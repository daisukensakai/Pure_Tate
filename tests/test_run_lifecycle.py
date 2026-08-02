import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate import run_lifecycle


class RunLifecycleTests(unittest.TestCase):
    def test_campaign_lock_rejects_a_second_live_drive(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            run_lifecycle, "LOCK_DIR", Path(directory) / "locks"
        ):
            with run_lifecycle.CampaignRunLock("C66-TEST"):
                with self.assertRaises(run_lifecycle.CampaignAlreadyRunning):
                    with run_lifecycle.CampaignRunLock("C66-TEST"):
                        pass

    def test_recovery_marks_missing_parent_abandoned_and_releases_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "reports" / "runs"
            reservation_dir = run_dir / "reservations"
            run_dir.mkdir(parents=True)
            reservation_dir.mkdir()
            run_id = "RUN-C66-TEST-20260803T000000000000Z-99999999"
            ledger_path = run_dir / (run_id + ".json")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "campaign_id": "C66-TEST",
                        "parent_pid": 99999999,
                        "status": "running",
                        "events": [{"state": "running", "task_id": "TASK-1"}],
                    }
                )
            )
            reservation = reservation_dir / "FAUD-0001.json"
            reservation.write_text(json.dumps({"run_id": run_id}))
            with mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservation_dir
            ):
                recovered = run_lifecycle.recover_stale_run_ledgers("C66-TEST")
            result = json.loads(ledger_path.read_text())
            self.assertEqual(recovered, [run_id])
            self.assertEqual(result["status"], "abandoned")
            self.assertEqual(result["events"][0]["state"], "abandoned")
            self.assertFalse(reservation.exists())

    def test_live_parent_is_not_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "runs"
            run_dir.mkdir()
            run_id = "RUN-C66-TEST-20260803T000000000000Z-%d" % os.getpid()
            path = run_dir / (run_id + ".json")
            path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "campaign_id": "C66-TEST",
                        "parent_pid": os.getpid(),
                        "status": "running",
                        "events": [],
                    }
                )
            )
            with mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir):
                self.assertEqual(
                    run_lifecycle.live_run_ledgers("C66-TEST"), [run_id]
                )
                self.assertEqual(
                    run_lifecycle.recover_stale_run_ledgers("C66-TEST"), []
                )

    def test_artifact_reservations_are_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "research" / "finding-audits"
            reservations = root / "reports" / "runs" / "reservations"
            with mock.patch.object(run_lifecycle, "ROOT", root), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservations
            ):
                first, first_path = run_lifecycle.reserve_prefixed_artifact(
                    target, "FAUD", "RUN-1"
                )
                second, second_path = run_lifecycle.reserve_prefixed_artifact(
                    target, "FAUD", "RUN-2"
                )
                self.assertEqual((first, second), ("FAUD-0001", "FAUD-0002"))
                run_lifecycle.release_artifact_reservation(first_path)
                run_lifecycle.release_artifact_reservation(second_path)


if __name__ == "__main__":
    unittest.main()
