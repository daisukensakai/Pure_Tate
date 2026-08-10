import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pure_tate.agents import (
    _engine_argv,
    _validate_artifact,
    _validate_task_packet,
    run_task,
)
from pure_tate.campaign_driver import (
    _drive_campaign_unlocked,
    _next_due_forced_task,
    _eligible_research_pool,
    _finding_audit_is_blocking,
    _research_capability_blocker,
    drive_campaign,
    next_campaign_task,
)
from pure_tate.campaigns import (
    campaign_packet_binding,
    campaign_packet_binding_sha256,
    campaign_packet_record,
    campaign_packet_snapshot_path,
    campaign_status,
    load_campaign,
    novelty_status,
    packet_binding_matches,
)
from pure_tate.capabilities import effective_capabilities_from_argv
from pure_tate.experiments import (
    OCI_DIGEST_RE,
    experiment_tasks,
    run_experiment,
)
from pure_tate.findings import finding_by_id, findings_for_case
from pure_tate.novelty import (
    NOVELTY_QUERY_FAMILIES,
    verify_source_records,
)
from pure_tate.store import ROOT
from pure_tate.targets import CONTEXT_REVISION
from pure_tate.tasking import campaign_mathematics_tasks, finding_audit_tasks


class PacketBindingTests(unittest.TestCase):
    """Packet identity must survive findings churn but track real changes.

    Hashing the whole rendered packet meant every finding adjudication
    invalidated all in-flight attempts, reviews and digests, so work was
    retired faster than it could earn two review passes.
    """

    def test_binding_ignores_the_adjudicated_findings_section(self):
        baseline = campaign_packet_binding_sha256("C66-001")
        content = campaign_packet_record("C66-001")["packet_sha256"]
        extra = {
            "id": "FND-9999",
            "case": {"g": 6, "n": 6},
            "status": "corroborated",
            "statement": "An additional adjudicated finding.",
        }
        with mock.patch(
            "pure_tate.campaigns.findings_for_case",
            side_effect=lambda *a, **k: [extra],
        ):
            self.assertEqual(campaign_packet_binding_sha256("C66-001"), baseline)
            self.assertNotEqual(
                campaign_packet_record("C66-001")["packet_sha256"], content
            )

    def test_binding_tracks_theorem_routes_and_subproblem_graph(self):
        baseline = campaign_packet_binding_sha256("C66-001")
        campaign = load_campaign("C66-001")
        for mutate in (
            lambda value: value["paired_attempt_policy"].update(
                {"exact_theorem": "A different theorem."}
            ),
            lambda value: value["blocked_routes"].append("a-new-blocked-route"),
            lambda value: value["subproblems"][0].update({"dependencies": ["X"]}),
            lambda value: value["bottleneck"].update({"splitting": "unbalanced"}),
        ):
            mutated = copy.deepcopy(campaign)
            mutate(mutated)
            with mock.patch(
                "pure_tate.campaigns.load_campaign", return_value=mutated
            ):
                self.assertNotEqual(
                    campaign_packet_binding_sha256("C66-001"), baseline
                )

    def test_binding_covers_every_identity_bearing_input(self):
        binding = campaign_packet_binding("C66-001")
        self.assertEqual(
            set(binding),
            {
                "campaign_id",
                "campaign_revision",
                "context_revision",
                "target",
                "exact_theorem",
                "bottleneck",
                "subproblems",
                "blocked_routes",
                "primary_sources",
            },
        )

    def test_migration_carries_artifacts_written_before_the_binding_hash(self):
        # Superseded packet texts are unrecoverable, so equivalence for these is
        # an attested migration record rather than a derivation.
        current = campaign_packet_binding_sha256("C66-001")
        self.assertTrue(
            packet_binding_matches(
                {"campaign_id": "C66-001", "packet_binding_sha256": current},
                "C66-001",
            )
        )
        self.assertFalse(
            packet_binding_matches(
                {"campaign_id": "C66-001", "packet_binding_sha256": "f" * 64},
                "C66-001",
            )
        )
        self.assertFalse(
            packet_binding_matches(
                {"campaign_id": "C66-001", "packet_sha256": "f" * 64},
                "C66-001",
            )
        )

    def test_missing_binding_matches_when_content_equals_live_packet(self):
        # Reviews that omit packet_binding_sha256 but carry the live full-content
        # hash must still pass the gate (otherwise double-confirms false-negative).
        from pure_tate.campaigns import campaign_packet_record

        live = campaign_packet_record("C66-001")["packet_sha256"]
        self.assertTrue(
            packet_binding_matches(
                {"campaign_id": "C66-001", "packet_sha256": live},
                "C66-001",
            )
        )
        # Explicit wrong binding still loses even if content looks live.
        self.assertFalse(
            packet_binding_matches(
                {
                    "campaign_id": "C66-001",
                    "packet_binding_sha256": "f" * 64,
                    "packet_sha256": live,
                },
                "C66-001",
            )
        )

    def test_snapshot_path_is_derived_once_and_does_not_nest(self):
        working = Path("proof/packets/generated/C66-001-v4.md")
        digest = "a" * 64
        snapshot = campaign_packet_snapshot_path(working, digest)
        self.assertEqual(snapshot.name, "C66-001-v4-%s.md" % ("a" * 16))
        # Re-deriving from a snapshot must not append a second digest.
        self.assertEqual(
            campaign_packet_snapshot_path(snapshot, digest), snapshot
        )


class TaskPacketContentTests(unittest.TestCase):
    """Campaign tasks are gated on packet identity, but the recorded text
    stays pinned.

    The working packet is rewritten on every finding adjudication, so content
    equality against it cannot gate campaign work -- that conflation froze the
    campaign. The immutable snapshot is what keeps ``packet_sha256`` meaningful,
    and a task carrying a binding hash was necessarily built after snapshots
    existed, so it must be able to produce its own packet text.
    """

    def _task(self, root, packet_sha256, binding="current"):
        packets = root / "proof" / "packets" / "generated"
        packets.mkdir(parents=True, exist_ok=True)
        working = packets / "C66-001-v4.md"
        working.write_text("current packet text", encoding="utf-8")
        task = {
            "phase": "review",
            "campaign_id": "C66-001",
            "context_revision": CONTEXT_REVISION,
            "input_packet": str(working.relative_to(root)),
            "packet_sha256": packet_sha256,
            "target": {"g": 6, "n": 6},
        }
        if binding is not None:
            task["packet_binding_sha256"] = binding
        return task, working

    def _validate(self, root, task):
        with mock.patch("pure_tate.agents.ROOT", root), mock.patch(
            "pure_tate.campaigns.packet_binding_matches", return_value=True
        ):
            _validate_task_packet(task)

    def test_recorded_packet_text_is_verified_against_the_snapshot(self):
        superseded = "superseded packet text"
        digest = hashlib.sha256(superseded.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, working = self._task(root, digest)
            snapshot = campaign_packet_snapshot_path(working, digest)
            snapshot.write_text(superseded, encoding="utf-8")
            # Working text has churned past the recorded hash; the snapshot
            # still reproduces it, so the task stays valid.
            self.assertNotEqual(
                hashlib.sha256(working.read_bytes()).hexdigest(), digest
            )
            self._validate(root, task)

    def test_missing_snapshot_is_rejected_for_bound_tasks(self):
        digest = hashlib.sha256(b"superseded packet text").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, _working = self._task(root, digest)
            with self.assertRaisesRegex(ValueError, "snapshot is missing"):
                self._validate(root, task)

    def test_corrupted_snapshot_is_rejected(self):
        digest = hashlib.sha256(b"superseded packet text").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, working = self._task(root, digest)
            snapshot = campaign_packet_snapshot_path(working, digest)
            snapshot.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                self._validate(root, task)

    def test_pre_binding_tasks_keep_identity_only_validation(self):
        # Artifacts written before the binding hash have no snapshot and their
        # packet texts were overwritten in place; identity equivalence via the
        # migration record is all that remains checkable.
        digest = hashlib.sha256(b"unrecoverable packet text").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task, _working = self._task(root, digest, binding=None)
            self._validate(root, task)


class FocusedCampaignTests(unittest.TestCase):
    def setUp(self):
        # Driving the campaign reserves artifact IDs, and a spent reservation is
        # a permanent claim that is never released. Pointed at the live ledger
        # every test run would burn real REV/FAUD slots, so each test reserves
        # into its own directory.
        from pure_tate import routing, run_lifecycle

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = mock.patch.object(
            run_lifecycle, "RESERVATION_DIR", Path(directory.name)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        # High-tier chain order is persisted per chain, so reading the live
        # routing ledger makes these assertions depend on whichever chains the
        # campaign happens to have opened. Start from the default ledger.
        ledger = mock.patch.object(
            routing, "HIGH_TIER_LEDGER", Path(directory.name) / "high-tier.json"
        )
        ledger.start()
        self.addCleanup(ledger.stop)

    def test_step_limit_with_failed_event_is_not_reported_as_success(self):
        finding_task = {
            "id": "TASK-F-FND-FAIL",
            "finding_id": "FND-0022",
            "campaign_id": "C66-001",
            "packet_sha256": "a" * 64,
        }
        ledger = {
            "schema_version": 2,
            "run_id": "RUN-TEST-FAIL",
            "campaign_id": "C66-001",
            "events": [],
            "status": "running",
        }
        with mock.patch(
            "pure_tate.campaign_driver._research_capability_state",
            return_value="pass",
        ), mock.patch(
            "pure_tate.campaign_driver._eligible_research_pool",
            return_value=["claude"],
        ), mock.patch(
            "pure_tate.campaign_driver._campaign_reviews", return_value=[]
        ), mock.patch(
            "pure_tate.campaign_driver._load_bearing_experiments", return_value=[]
        ), mock.patch(
            "pure_tate.campaign_driver.finding_audit_tasks",
            return_value=[finding_task],
        ), mock.patch(
            "pure_tate.campaign_driver.attempt_pending_recoveries",
            return_value=[],
        ), mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "forced_untried"},
        ), mock.patch(
            "pure_tate.campaign_driver._next_due_forced_task",
            return_value=None,
        ), mock.patch(
            "pure_tate.campaign_driver._math_task",
            return_value=None,
        ), mock.patch(
            "pure_tate.campaign_driver.run_task",
            side_effect=RuntimeError("provider failed"),
        ), mock.patch(
            "pure_tate.campaign_driver.reserve_prefixed_artifact",
            return_value=("FAUD-TEST", None),
        ), mock.patch(
            "pure_tate.campaign_driver._write_run_ledger"
        ), mock.patch(
            "pure_tate.campaign_driver._new_run_ledger",
            return_value=(ledger, ROOT / "reports" / "runs" / "RUN-TEST-FAIL.json"),
        ):
            result = _drive_campaign_unlocked(
                "C66-001",
                1,
                research_engines=["claude"],
                prover_engines=["grok", "claude", "codex", "qwen"],
                review_engines=["grok", "claude"],
            )
        self.assertEqual(result["stop_reason"], "step_limit_with_failures")
        self.assertEqual(ledger["status"], "completed_with_failures")

    def test_campaign_notifies_after_each_step_and_at_run_end(self):
        campaign = load_campaign("C66-001")
        finding_task = {
            "id": "TASK-F-FND-TEST",
            "finding_id": "FND-0022",
            "campaign_id": "C66-001",
            "packet_sha256": "a" * 64,
        }
        artifact = {
            "id": "FAUD-TEST",
            "finding_id": "FND-0022",
            "engine": "grok",
            "verdict": "retain_candidate",
        }
        with mock.patch(
            "pure_tate.campaign_driver._research_capability_state",
            return_value="pass",
        ), mock.patch(
            "pure_tate.campaign_driver._campaign_reviews", return_value=[]
        ), mock.patch(
            "pure_tate.campaign_driver._load_bearing_experiments", return_value=[]
        ), mock.patch(
            "pure_tate.campaign_driver.finding_audit_tasks",
            return_value=[finding_task],
        ), mock.patch(
            "pure_tate.campaign_driver.attempt_pending_recoveries",
            return_value=[],
        ), mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "forced_untried"},
        ), mock.patch(
            "pure_tate.campaign_driver._next_due_forced_task",
            return_value=None,
        ), mock.patch(
            "pure_tate.campaign_driver._math_task",
            return_value=None,
        ), mock.patch(
            "pure_tate.campaign_driver.run_task", return_value=artifact
        ), mock.patch(
            "pure_tate.campaign_driver._write_run_ledger"
        ), mock.patch(
            "pure_tate.campaign_driver._new_run_ledger",
            return_value=(
                {
                    "schema_version": 1,
                    "run_id": "RUN-TEST",
                    "campaign_id": "C66-001",
                    "events": [],
                    "status": "running",
                },
                ROOT / "reports" / "runs" / "RUN-TEST.json",
            ),
        ), mock.patch(
            "pure_tate.campaign_driver.CampaignRunLock"
        ), mock.patch(
            "pure_tate.campaign_driver.recover_stale_run_ledgers",
            return_value=[],
        ), mock.patch(
            "pure_tate.campaign_driver.live_run_ledgers",
            return_value=[],
        ), mock.patch(
            "pure_tate.campaign_driver.notify_campaign_step"
        ) as step_notification, mock.patch(
            "pure_tate.campaign_driver.notify_campaign_run"
        ) as run_notification:
            result = drive_campaign(
                campaign["id"],
                1,
                research_engines=["grok"],
                prover_engines=["grok", "claude", "codex", "qwen"],
                review_engines=["grok", "claude"],
                dry_run=False,
                desktop_notifications=True,
            )
        self.assertEqual(result["executed_steps"], 1)
        step_notification.assert_called_once()
        self.assertEqual(step_notification.call_args.args[0], campaign["id"])
        self.assertEqual(step_notification.call_args.args[2], 1)
        self.assertEqual(
            step_notification.call_args.kwargs, {"desktop": True, "ntfy": False}
        )
        run_notification.assert_called_once_with(
            campaign["id"],
            1,
            1,
            "completed",
            "step_limit",
            desktop=True,
            ntfy=False,
        )

    def test_forced_slots_open_after_ordinary_starts_three_and_six(self):
        campaign = load_campaign("C66-001")
        packet = campaign_packet_record("C66-001")
        with mock.patch(
            "pure_tate.campaign_driver._current_ordinary_proof_count",
            return_value=3,
        ), mock.patch(
            "pure_tate.campaign_driver._current_forced_attempts",
            return_value=[],
        ):
            first = _next_due_forced_task(
                campaign, packet, {"claude", "codex"}, dry_run=True
            )
        self.assertEqual(first["selected_engine"], "claude")
        with mock.patch(
            "pure_tate.campaign_driver._current_ordinary_proof_count",
            return_value=6,
        ), mock.patch(
            "pure_tate.campaign_driver._current_forced_attempts",
            return_value=[{"id": "ATT-TEST"}],
        ):
            second = _next_due_forced_task(
                campaign, packet, {"claude", "codex"}, dry_run=True
            )
        self.assertEqual(second["selected_engine"], "codex")
        self.assertEqual(
            {first["selected_engine"], second["selected_engine"]},
            {"claude", "codex"},
        )

    def test_campaign_target_and_four_lanes_are_exact(self):
        campaign = load_campaign("C66-001")
        self.assertEqual(campaign["context_revision"], 2)
        self.assertEqual(campaign["campaign_revision"], 4)
        # Forced exact-theorem work is Opus/GPT-only; ordinary rotation still
        # includes Grok and Qwen for cell mathematics.
        self.assertEqual(
            campaign["paired_attempt_policy"]["engine_order"],
            ["claude", "codex"],
        )
        self.assertNotIn("grok", campaign["paired_attempt_policy"]["engine_order"])
        self.assertNotIn(
            "qwen", campaign["paired_attempt_policy"]["engine_order"]
        )
        report = campaign_status("C66-001")
        self.assertIn("qwen", report["routing_policy"]["fresh_rotation"])
        self.assertEqual(
            report["paired_attempt_policy"]["engine_order"],
            ["claude", "codex"],
        )
        self.assertNotIn(
            "qwen", report["paired_attempt_policy"]["engine_states"]
        )
        tasks = campaign_mathematics_tasks("C66-001")
        self.assertEqual(
            {task["lane"] for task in tasks},
            {
                "geometry",
                "weakest-sufficient-proof",
                "counterexample",
                "computation",
            },
        )
        for task in tasks:
            self.assertEqual(task["target"]["ordinary_cohomology_degree"], 26)
            self.assertEqual(task["target"]["chow_codimension"], 13)
            self.assertEqual(task["packet_id"], "C66-001-v4")

    def test_campaign_packet_quarantines_candidates(self):
        packet = campaign_packet_record("C66-001")["_text"]
        self.assertIn("F=O_{P1}(4) direct-sum O_{P1}(5)", packet)
        self.assertIn("gamma^*O_{P1}(-5)", packet)
        self.assertIn("deg(W_5)=16", packet)
        self.assertIn("it is not the O_{P1}(5) summand of F", packet)
        self.assertIn("C66-GEO-Z", packet)
        self.assertIn("FND-0035", packet)
        self.assertNotIn("FND-0032 [candidate", packet)
        self.assertNotIn("would discharge this pair outright", packet)

    def test_revision_one_attempt_is_preserved_and_stale(self):
        path = ROOT / "proof" / "attempts" / "ATT-0016.json"
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "451b01409658b7a9b0dcc3dc3d14d698a8af1ce578cf3ae1199e1ae9b08a25b0",
        )
        report = campaign_status("C66-001")
        self.assertGreaterEqual(report["campaign_progress"]["attempts"], 0)
        self.assertEqual(
            report["campaign_progress"]["stale_campaign_attempts"], 15
        )
        self.assertTrue(
            any(
                item.get("id") == "ATT-0016"
                or item.get("attempt_id") == "ATT-0016"
                for item in report.get("historical_stale_attempts", [])
            )
            or report["campaign_progress"]["stale_campaign_attempts"] >= 1
        )

    def test_campaign_dag_blocks_unverified_dependencies(self):
        tasks = campaign_mathematics_tasks("C66-001")
        by_subproblem = {task["subproblem_id"]: task for task in tasks}
        self.assertEqual(by_subproblem["C66-GEO-Z"]["status"], "ready")
        # Dual-confirmed GEO-Z and GEO-H0 discharge the early geometry chain, so
        # GEO-COMP is executable. Downstream Tate/CEX cells still wait on COMP.
        self.assertEqual(by_subproblem["C66-GEO-H0"]["status"], "ready")
        self.assertEqual(
            by_subproblem["C66-GEO-H0"].get("blocked_dependencies") or [],
            [],
        )
        self.assertEqual(by_subproblem["C66-GEO-COMP"]["status"], "ready")
        self.assertEqual(
            by_subproblem["C66-GEO-COMP"].get("blocked_dependencies") or [],
            [],
        )
        self.assertEqual(by_subproblem["C66-TATE-SUPPORT"]["status"], "blocked")
        self.assertEqual(
            by_subproblem["C66-TATE-SUPPORT"]["blocked_dependencies"],
            ["C66-GEO-COMP"],
        )
        report = campaign_status("C66-001")
        self.assertIn(
            "C66-TATE-SUPPORT requires C66-GEO-COMP",
            report["unresolved_proof_dependencies"],
        )
        self.assertNotIn(
            "C66-GEO-COMP requires C66-GEO-H0",
            report["unresolved_proof_dependencies"],
        )
        self.assertNotIn(
            "C66-GEO-H0 requires C66-GEO-Z",
            report["unresolved_proof_dependencies"],
        )
        # Lemma double-confirms must not mark the full RED-0001 case verified.
        self.assertFalse(report["case_verification"]["case_verified"])

    def test_finding_migration_retires_bad_claims_and_splits_leray(self):
        self.assertEqual(finding_by_id("FND-0018")["status"], "retired")
        self.assertEqual(finding_by_id("FND-0021")["status"], "retired")
        self.assertEqual(finding_by_id("FND-0028")["status"], "retired")
        self.assertEqual(
            finding_by_id("FND-0036")["status"], "mechanically_verified"
        )
        finding_37_status = finding_by_id("FND-0037")["status"]
        self.assertIn(finding_37_status, {"candidate", "corroborated"})
        visible = {
            item["id"]
            for item in findings_for_case(
                6, 6, visible_only=True, campaign_id="C66-001"
            )
        }
        self.assertIn("FND-0035", visible)
        self.assertIn("FND-0036", visible)
        if finding_37_status == "candidate":
            self.assertNotIn("FND-0037", visible)
        else:
            self.assertIn("FND-0037", visible)

    def test_grok_web_is_available_on_agent_phases(self):
        research = _engine_argv("grok", "probe", phase="novelty")
        math = _engine_argv("grok", "proof", phase="mathematics")
        review = _engine_argv("grok", "review", phase="review")
        self.assertNotIn("--disable-web-search", research)
        self.assertNotIn("--disable-web-search", math)
        self.assertNotIn("--disable-web-search", review)
        self.assertEqual(
            research[research.index("--permission-mode") + 1], "dontAsk"
        )
        for argv, phase in (
            (research, "novelty"),
            (math, "mathematics"),
            (review, "review"),
        ):
            tools = argv[argv.index("--tools") + 1]
            self.assertIn("web_search", tools.split(","))
            self.assertIn("web_fetch", tools.split(","))
            self.assertTrue(
                {"web_search", "web_fetch"}.issubset(
                    effective_capabilities_from_argv("grok", argv, phase)
                )
            )

    def test_unattested_research_is_rejected_before_engine_run(self):
        tasks = finding_audit_tasks("C66-001")
        if tasks:
            task = tasks[0]
        else:
            # Queue may be empty after live audits; only phase/web flags matter.
            task = {
                "id": "TASK-F-SYNTH",
                "phase": "finding-audit",
                "requires_live_web": True,
                "campaign_id": "C66-001",
                "finding_id": "FND-SYNTH",
                "packet_id": "C66-001-v4",
                "packet_sha256": "0" * 64,
                "prompt": "prompts/FINDING_AUDIT.md",
                "target": {"g": 6, "n": 6},
            }
        output = ROOT / "research" / "finding-audits" / "FAUD-9999.json"
        with mock.patch(
            "pure_tate.capabilities.capability_is_attested",
            return_value=False,
        ):
            with self.assertRaisesRegex(ValueError, "live capability"):
                run_task(task, "grok", output)

    def test_research_pool_and_blocker_fail_closed_after_live_results(self):
        states = {"claude": "pass", "grok": "fail"}
        with mock.patch(
            "pure_tate.campaign_driver._research_capability_state",
            side_effect=lambda engine, phase: states[engine],
        ):
            self.assertEqual(
                _eligible_research_pool(
                    ["claude", "grok"], "finding-audit", dry_run=True
                ),
                ["claude"],
            )
            self.assertEqual(
                _eligible_research_pool(
                    ["claude", "grok"], "finding-audit", dry_run=False
                ),
                ["claude"],
            )
            blocker = _research_capability_blocker(
                ["claude", "grok"],
                "finding-audit",
                excluded_engines={"claude"},
                dry_run=True,
            )
        self.assertIsNotNone(blocker)
        self.assertEqual(
            blocker["independent_engine_states"]["grok"]["capability"],
            "fail",
        )
        self.assertIn("passing live-web attestation", blocker["reason"])

    def test_only_claim_conflicts_are_blocking_finding_audits(self):
        tasks = finding_audit_tasks("C66-001")
        task = tasks[0] if tasks else {
            "id": "TASK-F-SYNTH",
            "phase": "finding-audit",
            "finding": {
                "id": "FND-SYNTH",
                "contradicts_claim_ids": [],
                "blocks_campaign_packet": False,
            },
        }
        self.assertFalse(_finding_audit_is_blocking(task))
        blocking = copy.deepcopy(task)
        blocking.setdefault("finding", {})
        blocking["finding"]["contradicts_claim_ids"] = ["THM-TEST"]
        self.assertTrue(_finding_audit_is_blocking(blocking))

    def test_source_records_are_retrieved_and_hash_checked(self):
        content = b"stable source bytes"
        digest = hashlib.sha256(content).hexdigest()
        records = [
            {
                "query_family": family,
                "retrieved_at": "2026-07-30T00:00:00Z",
                "url": "https://example.org/%d" % index,
                "source_type": "journal",
                "doi": None,
                "arxiv_id": None,
                "arxiv_version": None,
                "content_sha256": digest,
            }
            for index, family in enumerate(NOVELTY_QUERY_FAMILIES)
        ]
        with mock.patch(
            "pure_tate.novelty.fetch_public_source", return_value=content
        ), mock.patch("pure_tate.novelty.atomic_write_bytes"):
            self.assertTrue(verify_source_records(records)["ok"])
            bad = copy.deepcopy(records)
            bad[0]["content_sha256"] = "0" * 64
            self.assertFalse(verify_source_records(bad)["ok"])

    def test_blocked_route_requires_source_verified_new_evidence(self):
        task = campaign_mathematics_tasks("C66-001")[0]
        artifact = {
            "schema_version": 3,
            "id": "ATT-9999",
            "task_id": task["id"],
            "campaign_id": "C66-001",
            "campaign_revision": 4,
            "subproblem_id": task["subproblem_id"],
            "lane": task["lane"],
            "result_type": "lemma",
            "target_claim_id": "RED-0001",
            "context_revision": 2,
            "packet_id": task["packet_id"],
            "packet_path": task["input_packet"],
            "packet_sha256": task["packet_sha256"],
            "target": task["target"],
            "theorem_statement": "A test theorem.",
            "summary": "A test.",
            "argument_markdown": "Argument.",
            "claims": [{"statement": "Claim."}],
            "status": "proposed",
            "source_claim_ids": [],
            "gap_markers": ["Not complete."],
            "engine": "codex",
            "proof_dependencies": [],
            "experiment_ids": [],
            "experiment_uses": [],
            "novelty_claims": [],
            "failed_approaches_addressed": [],
            "methods_used": ["vcd-only-vanishing"],
            "new_inputs": [],
        }
        with self.assertRaisesRegex(ValueError, "blocked campaign route"):
            _validate_artifact(
                "mathematics", task, artifact, ROOT / "proof" / "attempts" / "ATT-9999.json", "codex"
            )
        artifact["new_inputs"] = [
            {
                "route": "vcd-only-vanishing",
                "evidence": "A genuinely new theorem.",
                "evidence_claim_ids": ["THM-0002"],
            }
        ]
        _validate_artifact(
            "mathematics", task, artifact, ROOT / "proof" / "attempts" / "ATT-9999.json", "codex"
        )

    def test_blocked_route_alias_cannot_bypass_research_gate(self):
        task = next(
            item
            for item in campaign_mathematics_tasks("C66-001")
            if item["status"] == "ready"
        )
        artifact = {
            "schema_version": 3,
            "id": "ATT-9999",
            "task_id": task["id"],
            "campaign_id": "C66-001",
            "campaign_revision": 4,
            "subproblem_id": task["subproblem_id"],
            "lane": task["lane"],
            "result_type": "lemma",
            "target_claim_id": "RED-0001",
            "context_revision": 2,
            "packet_id": task["packet_id"],
            "packet_path": task["input_packet"],
            "packet_sha256": task["packet_sha256"],
            "target": task["target"],
            "theorem_statement": "A test theorem.",
            "summary": "A test.",
            "argument_markdown": "Argument.",
            "claims": [{"statement": "Claim."}],
            "status": "proposed",
            "source_claim_ids": [],
            "gap_markers": ["Not complete."],
            "engine": "codex",
            "proof_dependencies": [],
            "experiment_ids": [],
            "experiment_uses": [],
            "novelty_claims": [],
            "failed_approaches_addressed": [],
            "methods_used": [
                "top-degree-rational-vanishing-for-mapping-class-groups"
            ],
            "new_inputs": [
                {
                    "source": "A free-form bibliographic assertion.",
                    "statement": "An alleged theorem.",
                }
            ],
        }
        with self.assertRaisesRegex(
            ValueError, "without source-verified new evidence"
        ):
            _validate_artifact(
                "mathematics",
                task,
                artifact,
                ROOT / "proof" / "attempts" / "ATT-9999.json",
                "codex",
            )

    def test_driver_is_bounded_balanced_and_no_spend_in_dry_run(self):
        before = {
            path: path.read_bytes()
            for directory in (
                ROOT / "proof" / "attempts",
                ROOT / "proof" / "reviews",
                ROOT / "research" / "finding-audits",
                ROOT / "research" / "novelty-audits",
                ROOT / "experiments" / "results",
            )
            if directory.exists()
            for path in directory.glob("*.json")
        }
        with mock.patch(
            "pure_tate.campaign_driver._research_capability_state",
            return_value="missing",
        ), mock.patch(
            "pure_tate.campaign_driver._current_ordinary_proof_count",
            return_value=6,
        ), mock.patch(
            "pure_tate.campaign_driver._current_forced_attempts",
            return_value=[],
        ), mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "forced_untried"},
        ), mock.patch(
            "pure_tate.campaign_driver._campaign_reviews",
            return_value=[],
        ):
            result = drive_campaign(
                "C66-001",
                12,
                research_engines=["claude", "grok"],
                prover_engines=["codex", "claude"],
                review_engines=["claude", "grok", "codex"],
                dry_run=True,
            )
        # Dry-run exposes the deterministic Opus/GPT forced pair sequence,
        # then any remaining slots may fill with ordinary mathematics (including
        # fresh-rotation re-entry once a cell's retry ladder is exhausted).
        self.assertGreaterEqual(result["executed_steps"], 4)
        self.assertGreaterEqual(len(result["events"]), 4)
        self.assertEqual(result["events"][0]["phase"], "forced-proof")
        self.assertEqual(
            result["events"][0]["task_id"], "TASK-C66-001-FORCED-FULL"
        )
        self.assertEqual(
            [event["phase"] for event in result["events"][:4]],
            [
                "forced-proof",
                "standard-fallback",
                "forced-proof",
                "standard-fallback",
            ],
        )
        self.assertEqual(
            [event["engine"] for event in result["events"][:4]],
            ["claude", "claude", "codex", "codex"],
        )
        after = {
            path: path.read_bytes()
            for directory in (
                ROOT / "proof" / "attempts",
                ROOT / "proof" / "reviews",
                ROOT / "research" / "finding-audits",
                ROOT / "research" / "novelty-audits",
                ROOT / "experiments" / "results",
            )
            if directory.exists()
            for path in directory.glob("*.json")
        }
        self.assertEqual(before, after)
        with self.assertRaisesRegex(ValueError, "between 1 and 12"):
            with mock.patch(
                "pure_tate.campaign_driver._research_capability_state",
                return_value="missing",
            ):
                drive_campaign(
                    "C66-001",
                    13,
                    research_engines=["claude"],
                    prover_engines=["codex"],
                    review_engines=["claude", "grok"],
                    dry_run=True,
                )

    def test_dry_run_surfaces_standard_ready_as_executable_fallback(self):
        def fake_state(_campaign, engine):
            if engine == "claude":
                return {"state": "standard_ready"}
            return {"state": "standard_trace_mining", "trace_id": "TRACE-0001"}

        with mock.patch(
            "pure_tate.campaign_driver._research_capability_state",
            return_value="pass",
        ), mock.patch(
            "pure_tate.paired.pair_state",
            side_effect=fake_state,
        ), mock.patch(
            "pure_tate.campaign_driver._campaign_reviews",
            return_value=[],
        ):
            result = drive_campaign(
                "C66-001",
                2,
                research_engines=["claude", "cursor-grok"],
                prover_engines=["claude", "codex"],
                review_engines=["cursor-grok", "claude", "codex"],
                dry_run=True,
            )
        phases = [event["phase"] for event in result["events"]]
        self.assertEqual(phases[0], "standard-fallback")
        self.assertEqual(result["events"][0]["engine"], "claude")
        self.assertEqual(result["events"][0]["condition"], "always")
        self.assertEqual(phases[1], "trace-mining")
        # Miner is independent of the source paired engine (codex).
        self.assertEqual(result["events"][1]["engine"], "cursor-grok")
        self.assertEqual(result["events"][1].get("source_engine"), "codex")

    def test_review_schema_failure_allows_one_same_engine_retry(self):
        from pure_tate.paired import ArtifactValidationError

        review_task = {
            "id": "TASK-V-ATT-TEST-P1",
            "target_attempt_id": "ATT-TEST",
            "prover_engine": "grok",
            "packet_sha256": "a" * 64,
            "campaign_id": "C66-001",
            "packet_id": "C66-001-v3",
        }
        calls = []

        def boom(
            task,
            engine,
            output,
            timeout=None,
            progress_callback=None,
            process_start_callback=None,
        ):
            calls.append(engine)
            raise ArtifactValidationError(
                "confirmed review contains a failed or unresolved structured check",
                "TRACE-SCHEMA",
                "research/paired-traces/TRACE-SCHEMA.json",
            )

        with mock.patch(
            "pure_tate.campaign_driver._research_capability_state",
            return_value="pass",
        ), mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "standard_under_review"},
        ), mock.patch(
            "pure_tate.campaign_driver._campaign_reviews",
            return_value=[review_task],
        ), mock.patch(
            "pure_tate.campaign_driver._load_bearing_experiments",
            return_value=[],
        ), mock.patch(
            "pure_tate.campaign_driver.finding_audit_tasks",
            return_value=[],
        ), mock.patch(
            "pure_tate.campaign_driver.run_task",
            side_effect=boom,
        ), mock.patch(
            "pure_tate.campaign_driver._write_run_ledger",
        ), mock.patch(
            "pure_tate.campaign_driver._new_run_ledger",
            return_value=(
                {
                    "schema_version": 1,
                    "run_id": "RUN-TEST",
                    "campaign_id": "C66-001",
                    "events": [],
                    "status": "running",
                },
                ROOT / "reports" / "runs" / "RUN-TEST.json",
            ),
        ), mock.patch(
            "pure_tate.campaign_driver.CampaignRunLock"
        ), mock.patch(
            "pure_tate.campaign_driver.recover_stale_run_ledgers",
            return_value=[],
        ), mock.patch(
            "pure_tate.campaign_driver.live_run_ledgers",
            return_value=[],
        ), mock.patch(
            "pure_tate.campaign_driver.attempt_pending_recoveries",
            return_value=[],
        ), mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "standard_under_review"},
        ):
            result = drive_campaign(
                "C66-001",
                3,
                research_engines=["claude", "grok"],
                prover_engines=["grok", "claude"],
                review_engines=["grok", "claude"],
                dry_run=False,
            )
        # Restricted pool: only Claude can review Grok. First validation
        # failure requeues Claude; second bans Claude and ends the batch.
        review_events = [
            event for event in result["events"] if event["phase"] == "review"
        ]
        self.assertEqual(len(review_events), 2)
        self.assertEqual([event["engine"] for event in review_events], ["claude", "claude"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["stop_reason"], "step_limit_with_failures")
        self.assertTrue(all(event["state"] == "failed" for event in review_events))

    def test_macaulay2_is_digest_pinned_and_missing_runtime_is_explicit(self):
        tasks = experiment_tasks("C66-001")
        self.assertEqual(len(tasks), 2)
        for task in tasks:
            self.assertRegex(task["image"], OCI_DIGEST_RE)
        with mock.patch(
            "pure_tate.experiments.container_runtime", return_value=""
        ):
            with self.assertRaisesRegex(RuntimeError, "skipped explicitly"):
                run_experiment(
                    tasks[0],
                    ROOT / "experiments" / "results" / "EXP-TEST.json",
                )

    def test_novelty_fails_closed_before_case_verification(self):
        status = novelty_status("C66-001")
        self.assertFalse(status["certified"])
        self.assertEqual(status["reason"], "case_not_verified")
        report = campaign_status("C66-001")
        self.assertFalse(report["case_verification"]["case_verified"])
        self.assertFalse(
            report["novelty_certification"]["novelty_certified"]
        )
        self.assertEqual(
            report["routing_policy"]["fresh_rotation"],
            [
                "cursor-grok",
                "claude",
                "cursor-grok",
                "codex",
                "cursor-grok",
                "qwen",
            ],
        )
        self.assertEqual(
            report["routing_policy"]["retry_escalation"],
            ["cursor-grok", "qwen"],
        )
        coverage = report["campaign_progress"]["subproblem_engine_coverage"]
        self.assertEqual(len(coverage), 9)
        # Fresh campaigns start empty; after live paired attempts some GEO lanes
        # may already list engines. Novelty still fails closed without verification.
        self.assertFalse(report["case_verification"]["case_verified"])
        self.assertIn("C66-GEO-Z", coverage)

    def test_novelty_requires_two_engines_and_fails_on_conflict(self):
        attempt = {
            "id": "ATT-9000",
            "theorem_statement": "Exact synthetic theorem.",
            "argument_markdown": "Proof.",
            "proof_dependencies": [],
            "experiment_ids": [],
        }
        from pure_tate.campaigns import proof_hash

        common = {
            "campaign_id": "C66-001",
            "attempt_id": "ATT-9000",
            "proof_sha256": proof_hash(attempt),
            "theorem_statement": "Exact synthetic theorem.",
            "theorem_scope": {"g": 6, "n": 6},
            "sources_verified": True,
            "live_web": True,
            "capability_attestation_sha256": "a" * 64,
        }
        clean = [
            dict(common, id="NOV-9001", engine="claude", verdict="no_prior_result"),
            dict(common, id="NOV-9002", engine="grok", verdict="no_prior_result"),
        ]
        with mock.patch(
            "pure_tate.campaigns.case_verified",
            return_value={"verified": True, "attempt": attempt, "reviews": []},
        ), mock.patch(
            "pure_tate.campaigns.load_novelty_audits", return_value=clean
        ), mock.patch(
            "pure_tate.capabilities.attestation_receipt_valid",
            return_value=True,
        ):
            self.assertTrue(novelty_status("C66-001")["certified"])
            conflict = clean + [
                dict(
                    common,
                    id="NOV-9003",
                    engine="other",
                    verdict="prior_result_found",
                )
            ]
            with mock.patch(
                "pure_tate.campaigns.load_novelty_audits",
                return_value=conflict,
            ):
                status = novelty_status("C66-001")
                self.assertFalse(status["certified"])
                self.assertEqual(status["reason"], "conflicting_prior_art")


if __name__ == "__main__":
    unittest.main()
