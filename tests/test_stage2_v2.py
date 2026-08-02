import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.agents import _validate_artifact, _validate_task_packet
from pure_tate.board import build_board
from pure_tate.driver import drive
from pure_tate.findings import findings_for_case
from pure_tate.packets import render_case_packet
from pure_tate.store import ROOT, load_repository
from pure_tate.targets import open_input_target
from pure_tate.tasking import mathematics_tasks, micro_research_tasks, review_tasks


class StageTwoRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _target, cls.sources, cls.claims, _edges = load_repository()
        cls.tasks = mathematics_tasks(cls.config, cls.claims, cls.sources)

    def test_target_formula_for_all_residual_cases(self):
        expected = [
            ((3, 12), 18, 20, 10),
            ((5, 8), 20, 24, 12),
            ((6, 6), 21, 26, 13),
            ((7, 4), 22, 28, 14),
            ((8, 0), 21, 26, 13),
            ((8, 1), 22, 28, 14),
            ((8, 2), 23, 30, 15),
        ]
        for (g, n), dimension, ordinary_degree, codimension in expected:
            target = open_input_target(g, n)
            self.assertEqual(target.dimension, dimension)
            self.assertEqual(target.open_bm_degree, 16)
            self.assertEqual(target.open_bm_weight, -16)
            self.assertEqual(target.open_bm_tate_type, "Q(8)")
            self.assertEqual(target.ordinary_cohomology_degree, ordinary_degree)
            self.assertEqual(target.ordinary_weight, ordinary_degree)
            self.assertEqual(target.poincare_twist, dimension)
            self.assertEqual(target.chow_codimension, codimension)
            self.assertEqual(
                target.ordinary_tate_type, "Q(-%d)" % codimension
            )

    def test_packets_are_revision_two_and_hash_matched(self):
        self.assertEqual(len(self.tasks), 35)
        for task in self.tasks:
            self.assertEqual(task["context_revision"], 2)
            self.assertEqual(task["packet_revision"], 2)
            path = ROOT / task["input_packet"]
            self.assertTrue(path.is_file())
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(actual, task["packet_sha256"])
            _validate_task_packet(task)

    def test_missing_or_hash_mismatched_packet_is_rejected(self):
        bad_hash = copy.deepcopy(self.tasks[0])
        bad_hash["packet_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            _validate_task_packet(bad_hash)
        missing = copy.deepcopy(self.tasks[0])
        missing["input_packet"] = "proof/packets/generated/DOES-NOT-EXIST.md"
        with self.assertRaises(ValueError):
            _validate_task_packet(missing)

    def test_generated_obstruction_has_no_old_open_target(self):
        text = (ROOT / "reports" / "generated" / "OBSTRUCTION.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("W_{16}H^{16}", text)
        self.assertIn("W_{-16}H^{BM}_{16}", text)

    def test_candidate_findings_stay_out_of_packets(self):
        packet = render_case_packet(5, 8, self.claims)
        self.assertNotIn("FND-0004", packet)
        self.assertIn("FND-0001", packet)
        corroborated = render_case_packet(7, 4, self.claims)
        self.assertIn("FND-0003", corroborated)
        visible = findings_for_case(5, 8, visible_only=True)
        self.assertNotIn("FND-0004", {item["id"] for item in visible})

    def test_wrong_ordinary_degree_is_rejected_before_write(self):
        task = self.tasks[0]
        artifact = {
            "schema_version": 2,
            "id": "ATT-0009",
            "task_id": task["id"],
            "target_claim_id": "RED-0001",
            "approach_id": task["approach_id"],
            "context_revision": 2,
            "packet_id": task["packet_id"],
            "packet_path": task["input_packet"],
            "packet_sha256": task["packet_sha256"],
            "target": copy.deepcopy(task["target"]),
            "summary": "summary",
            "argument_markdown": "argument",
            "claims": [{"id": "A1", "statement": "claim", "status": "open"}],
            "status": "proposed",
            "source_claim_ids": [],
            "gap_markers": ["gap"],
            "engine": "codex",
        }
        artifact["target"]["ordinary_cohomology_degree"] = 16
        with self.assertRaises(ValueError):
            _validate_artifact(
                "mathematics",
                task,
                artifact,
                ROOT / "proof" / "attempts" / "ATT-0009.json",
                "codex",
            )

    def test_informal_mathematics_status_is_rejected(self):
        task = self.tasks[0]
        artifact = {
            "schema_version": 2,
            "id": "ATT-0099",
            "task_id": task["id"],
            "target_claim_id": "RED-0001",
            "approach_id": task["approach_id"],
            "context_revision": 2,
            "packet_id": task["packet_id"],
            "packet_path": task["input_packet"],
            "packet_sha256": task["packet_sha256"],
            "target": task["target"],
            "summary": "summary",
            "argument_markdown": "argument",
            "claims": [{"id": "A1", "statement": "claim", "status": "open"}],
            "status": "incomplete",
            "source_claim_ids": [],
            "gap_markers": ["gap"],
            "engine": "codex",
        }
        with self.assertRaisesRegex(ValueError, "exact schema enum"):
            _validate_artifact(
                "mathematics",
                task,
                artifact,
                ROOT / "proof" / "attempts" / "ATT-0099.json",
                "codex",
            )

    def test_recorded_incomplete_triage_does_not_request_second_pass(self):
        tasks = review_tasks()
        queued = {
            (task["target_attempt_id"], task["review_pass"]) for task in tasks
        }
        self.assertNotIn(("ATT-0009", 2), queued)

    def test_local_obstructions_become_targeted_micro_research(self):
        with mock.patch("pure_tate.tasking._load_json_objects", return_value=[]):
            tasks = micro_research_tasks(self.claims)
        self.assertEqual(
            [task["question_id"] for task in tasks],
            ["MRQ-0001", "MRQ-0002"],
        )
        self.assertEqual(
            [(task["target"]["g"], task["target"]["n"]) for task in tasks],
            [(5, 8), (6, 6)],
        )
        for task in tasks:
            self.assertEqual(task["context_revision"], 2)
            _validate_task_packet(task)

    def test_completed_micro_research_question_is_not_requeued(self):
        completed = [{"question_id": "MRQ-0001", "context_revision": 2}]
        with mock.patch(
            "pure_tate.tasking._load_json_objects", return_value=completed
        ):
            tasks = micro_research_tasks(self.claims)
        self.assertEqual(
            [task["question_id"] for task in tasks],
            ["MRQ-0002"],
        )

    def test_legacy_artifacts_are_unchanged_and_stale(self):
        migration = json.loads(
            (
                ROOT / "proof" / "migrations" / "context-v2.json"
            ).read_text(encoding="utf-8")
        )
        for kind in ("attempts", "reviews"):
            for artifact_id, record in migration[kind].items():
                path = ROOT / "proof" / kind / (artifact_id + ".json")
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(actual, record["sha256"])
        board = build_board(self.config, self.claims, self.sources)
        self.assertEqual(board["cell_count"], 35)
        self.assertEqual(len(board["historical_stale_attempts"]), 8)

    def test_driver_dry_run_spends_nothing_and_does_not_repeat_cells(self):
        before_attempts = {
            path: path.read_bytes()
            for path in (ROOT / "proof" / "attempts").glob("ATT-*.json")
        }
        before_reviews = {
            path: path.read_bytes()
            for path in (ROOT / "proof" / "reviews").glob("REV-*.json")
        }
        result = drive(
            3,
            prover_engines=["codex"],
            review_engines=["claude", "grok", "qwen"],
            dry_run=True,
        )
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["executed_steps"], 3)
        self.assertEqual(
            len({item["task_id"] for item in result["events"]}), 3
        )
        engines = [item["engine"] for item in result["events"]]
        review_events = [
            item for item in result["events"] if item["phase"] == "review"
        ]
        if review_events:
            by_attempt = {}
            for item in review_events:
                attempt_id = item["task_id"].split("-P", 1)[0].replace(
                    "TASK-V-", ""
                )
                by_attempt.setdefault(attempt_id, []).append(item["engine"])
            for engines_for_attempt in by_attempt.values():
                self.assertEqual(
                    len(engines_for_attempt), len(set(engines_for_attempt))
                )
        math_events = [
            item for item in result["events"] if item["phase"] == "mathematics"
        ]
        if math_events:
            self.assertEqual(
                len({item["task_id"] for item in math_events}),
                len(math_events),
            )
        after_attempts = {
            path: path.read_bytes()
            for path in (ROOT / "proof" / "attempts").glob("ATT-*.json")
        }
        after_reviews = {
            path: path.read_bytes()
            for path in (ROOT / "proof" / "reviews").glob("REV-*.json")
        }
        self.assertEqual(before_attempts, after_attempts)
        self.assertEqual(before_reviews, after_reviews)
        self.assertEqual(len(engines), len(set(item["output"] for item in result["events"])))


if __name__ == "__main__":
    unittest.main()
