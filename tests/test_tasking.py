import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.store import load_repository
from pure_tate.tasking import mathematics_tasks, research_tasks, review_tasks


class TaskingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _target, cls.sources, cls.claims, _edges = load_repository()

    def test_research_task_is_always_available(self):
        tasks = research_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["target"], "RED-0001")

    def test_mathematics_tasks_refuse_blocked_gate(self):
        with mock.patch("pure_tate.tasking.stage_two_ready", return_value=False):
            with self.assertRaises(RuntimeError):
                mathematics_tasks(self.config, self.claims, self.sources)

    def test_mathematics_tasks_available_when_ready(self):
        tasks = mathematics_tasks(self.config, self.claims, self.sources)
        self.assertEqual(len(tasks), 35)

    def test_unlocked_queue_covers_every_case_and_approach(self):
        with mock.patch("pure_tate.tasking.stage_two_ready", return_value=True):
            tasks = mathematics_tasks(self.config, self.claims, self.sources)
        self.assertEqual(len(tasks), 35)
        cases = {
            (task["target"]["g"], task["target"]["n"]) for task in tasks
        }
        self.assertEqual(
            cases,
            {(3, 12), (5, 8), (6, 6), (7, 4), (8, 0), (8, 1), (8, 2)},
        )
        self.assertEqual(len({task["approach"] for task in tasks}), 5)

    @staticmethod
    def _complete_attempt(attempt_id: str = "ATT-0001", **overrides):
        """An attempt the harness derives as complete."""
        attempt = {
            "id": attempt_id,
            "status": "proposed",
            "engine": "prover",
            "gap_markers": [],
            "claims": [{"statement": "A lemma.", "status": "proved"}],
            "completion_attestation": {
                "no_undischarged_dependencies": True,
                "not_reduction_only": True,
            },
        }
        attempt.update(overrides)
        return attempt

    def test_incomplete_attempt_gets_one_triage_pass(self):
        # Completeness is derived, so an attempt carrying a gap earns a single
        # triage pass no matter what status string it wrote.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "proof" / "attempts"
            attempts.mkdir(parents=True)
            (attempts / "ATT-0001.json").write_text(
                json.dumps(
                    self._complete_attempt(
                        status="claimed_complete", gap_markers=["a gap"]
                    )
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.tasking.ROOT", root):
                tasks = review_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["review_pass"], 1)
        self.assertTrue(all(task["phase"] == "review" for task in tasks))

    def test_review_task_carries_the_attempt_packet_binding(self):
        # Review tasks are gated on packet identity like every other campaign
        # turn. Without the binding hash the reviewer falls back to the
        # pre-binding migration table and every review is judged stale, which
        # leaves attempts unable to earn their two passes.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "proof" / "attempts"
            attempts.mkdir(parents=True)
            (attempts / "ATT-0001.json").write_text(
                json.dumps(
                    self._complete_attempt(
                        campaign_id="C66-001",
                        campaign_revision=6,
                        subproblem_id="C66-FULL",
                        packet_binding_sha256="b" * 64,
                    )
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.tasking.ROOT", root), mock.patch(
                "pure_tate.campaigns.packet_binding_matches", return_value=True
            ), mock.patch(
                "pure_tate.campaigns.campaign_route_policy_errors",
                return_value=[],
            ):
                tasks = review_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["packet_binding_sha256"], "b" * 64)

    def test_complete_attempt_earns_second_pass_despite_proposed_label(self):
        # Regression: a gap-free, fully proved attempt that labelled itself
        # "proposed" used to be capped at one review pass and could therefore
        # never be verified, stalling every subproblem depending on it.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "proof" / "attempts"
            reviews = root / "proof" / "reviews"
            attempts.mkdir(parents=True)
            reviews.mkdir(parents=True)
            (attempts / "ATT-0001.json").write_text(
                json.dumps(self._complete_attempt()), encoding="utf-8"
            )
            (reviews / "REV-0001.json").write_text(
                json.dumps(
                    {
                        "id": "REV-0001",
                        "attempt_id": "ATT-0001",
                        "review_pass": 1,
                        "verdict": "confirmed",
                        "reviewer_engine": "reviewer-a",
                        "context_revision": 2,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.tasking.ROOT", root):
                tasks = review_tasks()
        self.assertEqual([task["review_pass"] for task in tasks], [2])

    def test_claimed_complete_gets_second_pass_only_after_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "proof" / "attempts"
            reviews = root / "proof" / "reviews"
            attempts.mkdir(parents=True)
            reviews.mkdir(parents=True)
            (attempts / "ATT-0001.json").write_text(
                json.dumps(
                    self._complete_attempt(status="claimed_complete")
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.tasking.ROOT", root):
                first = review_tasks()
                self.assertEqual([task["review_pass"] for task in first], [1])
                (reviews / "REV-0001.json").write_text(
                    json.dumps(
                        {
                            "id": "REV-0001",
                            "attempt_id": "ATT-0001",
                            "review_pass": 1,
                            "verdict": "confirmed",
                            "reviewer_engine": "reviewer-a",
                            "context_revision": 2,
                        }
                    ),
                    encoding="utf-8",
                )
                second = review_tasks()
        self.assertEqual([task["review_pass"] for task in second], [2])

    def test_incomplete_triage_ends_review_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempts = root / "proof" / "attempts"
            reviews = root / "proof" / "reviews"
            attempts.mkdir(parents=True)
            reviews.mkdir(parents=True)
            (attempts / "ATT-0001.json").write_text(
                json.dumps({"id": "ATT-0001", "status": "proposed"}),
                encoding="utf-8",
            )
            (reviews / "REV-0001.json").write_text(
                json.dumps(
                    {
                        "id": "REV-0001",
                        "attempt_id": "ATT-0001",
                        "review_pass": 1,
                        "verdict": "incomplete",
                        "reviewer_engine": "reviewer-a",
                        "context_revision": 2,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.tasking.ROOT", root):
                tasks = review_tasks()
        self.assertEqual(tasks, [])


if __name__ == "__main__":
    unittest.main()
