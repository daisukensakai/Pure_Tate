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
            reservation.write_text(json.dumps({"run_id": run_id, "status": "reserved"}))
            with mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservation_dir
            ):
                recovered = run_lifecycle.recover_stale_run_ledgers("C66-TEST")
            result = json.loads(ledger_path.read_text())
            self.assertEqual(recovered, [run_id])
            self.assertEqual(result["status"], "abandoned")
            self.assertEqual(result["events"][0]["state"], "abandoned")
            self.assertFalse(reservation.exists())

    def test_stale_recovery_keeps_spent_reservations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "reports" / "runs"
            reservation_dir = run_dir / "reservations"
            run_dir.mkdir(parents=True)
            reservation_dir.mkdir()
            run_id = "RUN-C66-TEST-20260803T000000000000Z-99999998"
            ledger_path = run_dir / (run_id + ".json")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "campaign_id": "C66-TEST",
                        "parent_pid": 99999998,
                        "status": "running",
                        "events": [
                            {
                                "state": "running",
                                "task_id": "TASK-1",
                                "output": "proof/attempts/ATT-0007.json",
                                "trace_id": "TRACE-9",
                            }
                        ],
                    }
                )
            )
            reservation = reservation_dir / "ATT-0007.json"
            reservation.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "status": "reserved",
                        "artifact_id": "ATT-0007",
                        "trace_id": "TRACE-9",
                        "task_id": "TASK-1",
                    }
                )
            )
            with mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservation_dir
            ):
                recovered = run_lifecycle.recover_stale_run_ledgers("C66-TEST")
            self.assertEqual(recovered, [run_id])
            self.assertTrue(reservation.exists())
            spent = json.loads(reservation.read_text())
            self.assertEqual(spent["status"], "spent")
            self.assertEqual(spent["trace_id"], "TRACE-9")

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
            run_dir = root / "reports" / "runs"
            run_dir.mkdir(parents=True)
            with mock.patch.object(run_lifecycle, "ROOT", root), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservations
            ), mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir), mock.patch.object(
                run_lifecycle, "RECOVERY_LEDGER_PATH", root / "recoveries.json"
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

    def test_spent_reservation_is_never_reissued(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "proof" / "attempts"
            reservations = root / "reports" / "runs" / "reservations"
            run_dir = root / "reports" / "runs"
            run_dir.mkdir(parents=True)
            with mock.patch.object(run_lifecycle, "ROOT", root), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservations
            ), mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir), mock.patch.object(
                run_lifecycle, "RECOVERY_LEDGER_PATH", root / "recoveries.json"
            ):
                first, first_path = run_lifecycle.reserve_prefixed_artifact(
                    target, "ATT", "RUN-1"
                )
                self.assertEqual(first, "ATT-0001")
                run_lifecycle.spend_artifact_reservation(
                    first_path,
                    reason="validation_failure",
                    trace_id="TRACE-1",
                    task_id="TASK-1",
                )
                # Releasing a spent reservation is a no-op.
                run_lifecycle.release_artifact_reservation(first_path)
                self.assertTrue(first_path.exists())
                self.assertEqual(
                    json.loads(first_path.read_text())["status"], "spent"
                )
                second, second_path = run_lifecycle.reserve_prefixed_artifact(
                    target, "ATT", "RUN-2"
                )
                self.assertEqual(second, "ATT-0002")
                run_lifecycle.release_artifact_reservation(second_path)

    def test_historical_ledger_outputs_block_id_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "proof" / "attempts"
            reservations = root / "reports" / "runs" / "reservations"
            run_dir = root / "reports" / "runs"
            run_dir.mkdir(parents=True)
            (run_dir / "RUN-OLD.json").write_text(
                json.dumps(
                    {
                        "run_id": "RUN-OLD",
                        "events": [
                            {
                                "output": "proof/attempts/ATT-0040.json",
                                "state": "failed",
                            }
                        ],
                    }
                )
            )
            with mock.patch.object(run_lifecycle, "ROOT", root), mock.patch.object(
                run_lifecycle, "RESERVATION_DIR", reservations
            ), mock.patch.object(run_lifecycle, "RUN_LEDGER_DIR", run_dir), mock.patch.object(
                run_lifecycle, "RECOVERY_LEDGER_PATH", root / "recoveries.json"
            ):
                artifact_id, path = run_lifecycle.reserve_prefixed_artifact(
                    target, "ATT", "RUN-NEW"
                )
                self.assertEqual(artifact_id, "ATT-0041")
                run_lifecycle.release_artifact_reservation(path)


if __name__ == "__main__":
    unittest.main()
