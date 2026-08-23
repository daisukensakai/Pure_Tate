import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pure_tate.agents import _engine_argv, _validate_artifact, run_task
from pure_tate.campaigns import load_campaign, write_campaign_packet
from pure_tate.paired import (
    EXTENDED_BUDGET_BYTES,
    POLICY_REVISION,
    PRIMARY_BUDGET_BYTES,
    PRIMARY_CAP_DEPENDENCY_ROWS,
    PRIMARY_SECTION_HEADINGS,
    PRIMARY_TITLE,
    PRIMARY_PREAMBLE,
    _allocate_tiers,
    _digest_rows,
    _is_packet_redundant,
    _packet_tokens,
    _rank_tuple,
    _render_tier,
    _safe_math_rows,
    _statement_core,
    attach_working_context,
    dry_run_preview,
    forced_task,
    is_primary_working_context_path,
    model_visible_task,
    pair_state,
    problem_key,
    working_context_paths,
    working_context_records,
)
from pure_tate.store import ROOT

LEDGER_DIRS = (ROOT / "proof" / "attempts", ROOT / "proof" / "reviews")


def _ledger_entries():
    """Artifacts currently present in the live proof ledger."""
    return {
        path
        for directory in LEDGER_DIRS
        if directory.is_dir()
        for path in directory.glob("*.json")
    }


class PairedAttemptPolicyTests(unittest.TestCase):
    def setUp(self):
        self.campaign = load_campaign("C66-001")
        self.packet = write_campaign_packet("C66-001")
        self.task = forced_task(self.campaign, self.packet, [])
        self._ledger_before = _ledger_entries()

    def tearDown(self):
        # Tests must never target the live ledger: artifacts under proof/ gate
        # campaign_mathematics_tasks, case_verified and audit_proofs, so a stray
        # fixture changes real campaign gating. Remove any leak and fail loudly.
        leaked = sorted(_ledger_entries() - self._ledger_before)
        for path in leaked:
            path.unlink()
        if leaked:
            self.fail(
                "test wrote into the live proof ledger: %s"
                % ", ".join(str(path.relative_to(ROOT)) for path in leaked)
            )

    def full_artifact(self):
        return {
            "schema_version": 3,
            "id": "ATT-9999",
            "task_id": self.task["id"],
            "campaign_id": "C66-001",
            "campaign_revision": 4,
            "subproblem_id": "C66-FULL",
            "lane": "full-resolution",
            "result_type": "proof",
            "target_claim_id": "RED-0001",
            "context_revision": 2,
            "packet_id": self.task["packet_id"],
            "packet_path": self.task["input_packet"],
            "packet_sha256": self.task["packet_sha256"],
            "target": self.task["target"],
            "theorem_statement": self.campaign[
                "paired_attempt_policy"
            ]["exact_theorem"],
            "theorem_scope": {"g": 6, "n": 6},
            "summary": "Complete exact proof.",
            "argument_markdown": "A complete argument.",
            "claims": [{"statement": "Exact conclusion.", "status": "proved"}],
            "proof_dependencies": [],
            "experiment_ids": [],
            "experiment_uses": [],
            "novelty_claims": [],
            "gap_markers": [],
            "failed_approaches_addressed": [],
            "methods_used": [],
            "new_inputs": [],
            "completion_attestation": {
                "resolves_exact_target": True,
                "no_undischarged_dependencies": True,
                "not_reduction_only": True,
                "no_problem_status_claim": True,
                "exact_problem_web_search_used": False,
            },
            "status": "claimed_complete",
            "source_claim_ids": [],
            "engine": "grok",
        }

    def test_model_task_strips_scheduler_state(self):
        task = {
            **self.task,
            "paired_scheduler_state": "standard_ready",
            "paired_source_engine": "grok",
            "selected_engine": "grok",
        }
        visible = model_visible_task(task)
        rendered = str(visible).lower()
        self.assertNotIn("scheduler", rendered)
        self.assertNotIn("fallback", rendered)
        self.assertNotIn("previous-attempt", rendered)
        self.assertNotIn("paired_source_engine", visible)
        self.assertNotIn("selected_engine", visible)

    def test_forced_contract_accepts_only_complete_exact_result(self):
        output = ROOT / "proof" / "attempts" / "ATT-9999.json"
        artifact = self.full_artifact()
        _validate_artifact(
            "mathematics", self.task, artifact, output, "grok"
        )
        for field, value, message in (
            ("result_type", "lemma", "proof or disproof"),
            ("gap_markers", ["gap"], "gap marker"),
            (
                "claims",
                [{"statement": "A claim.", "status": "proved_with_gap"}],
                "proved_with_gap",
            ),
            (
                "completion_attestation",
                {
                    "resolves_exact_target": True,
                    "no_undischarged_dependencies": False,
                    "not_reduction_only": True,
                    "no_problem_status_claim": True,
                    "exact_problem_web_search_used": False,
                },
                "no_undischarged_dependencies",
            ),
        ):
            invalid = copy.deepcopy(artifact)
            invalid[field] = value
            with self.assertRaisesRegex(ValueError, message):
                _validate_artifact(
                    "mathematics", self.task, invalid, output, "grok"
                )

    def test_status_is_derived_by_the_harness_not_the_model(self):
        # A prover's own `status` string is advisory. The harness recomputes it
        # from the artifact's structured content, so a complete attempt cannot
        # lock itself out of its second review pass by mislabelling itself.
        output = ROOT / "proof" / "attempts" / "ATT-9999.json"
        complete = self.full_artifact()
        complete["status"] = "proposed"
        _validate_artifact("mathematics", self.task, complete, output, "grok")
        self.assertEqual(complete["status"], "claimed_complete")

        incomplete = self.full_artifact()
        incomplete["claims"] = [
            {"statement": "An admitted input.", "status": "source_backed"}
        ]
        incomplete["status"] = "claimed_complete"
        task = {
            key: value
            for key, value in self.task.items()
            if key != "paired_turn_kind"
        }
        _validate_artifact("mathematics", task, incomplete, output, "grok")
        self.assertEqual(incomplete["status"], "proposed")

    def test_forced_math_enables_web_tools_for_supporting_lookup(self):
        # Forced-proof / mathematics expose web tools; exact-problem search is
        # an attestation/honesty contract, not argv offline enforcement.
        for engine in ("claude", "codex"):
            argv = _engine_argv(
                engine,
                "prove the theorem",
                Path("/tmp/paired-last-message"),
                phase="mathematics",
            )
            joined = " ".join(argv)
            if engine == "grok":
                self.assertNotIn("--disable-web-search", argv)
                tools = argv[argv.index("--tools") + 1]
                self.assertIn("web_search", tools.split(","))
                self.assertIn("web_fetch", tools.split(","))
            if engine == "claude":
                self.assertIn("WebSearch", joined)
                self.assertIn("WebFetch", joined)

    def test_dry_run_shows_one_conditional_pair_per_engine(self):
        with mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "forced_untried"},
        ):
            preview = dry_run_preview(
                self.campaign,
                self.packet,
                ["claude", "codex"],
                12,
            )
        self.assertEqual(len(preview), 4)
        for index, engine in enumerate(
            ["claude", "codex"]
        ):
            forced = preview[index * 2]
            fallback = preview[index * 2 + 1]
            self.assertEqual(forced["engine"], engine)
            self.assertEqual(forced["phase"], "forced-proof")
            self.assertEqual(fallback["engine"], engine)
            self.assertEqual(fallback["phase"], "standard-fallback")
            self.assertEqual(
                fallback["condition"],
                "only_after_substantive_forced_failure",
            )

    def test_dry_run_standard_ready_is_executable_fallback(self):
        with mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "standard_ready"},
        ):
            preview = dry_run_preview(
                self.campaign,
                self.packet,
                ["claude"],
                4,
            )
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]["phase"], "standard-fallback")
        self.assertEqual(preview[0]["engine"], "claude")
        self.assertEqual(preview[0]["condition"], "always")

    def test_dry_run_trace_mining_names_independent_miner(self):
        with mock.patch(
            "pure_tate.paired.pair_state",
            return_value={"state": "standard_trace_mining"},
        ):
            preview = dry_run_preview(
                self.campaign,
                self.packet,
                ["claude"],
                4,
                review_engines=["grok", "claude"],
                escalation_order=["grok", "qwen"],
            )
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]["phase"], "trace-mining")
        self.assertEqual(preview[0]["condition"], "always")
        # Miner must differ from the source paired engine.
        self.assertEqual(preview[0]["source_engine"], "claude")
        self.assertEqual(preview[0]["engine"], "grok")
        self.assertNotEqual(preview[0]["engine"], preview[0]["source_engine"])

    def test_digest_rendering_rejects_provenance(self):
        with self.assertRaisesRegex(ValueError, "leaks provenance"):
            _safe_math_rows(
                [{"statement": "The previous attempt used ATT-0017."}]
            )
        self.assertEqual(
            _safe_math_rows([{"statement": "The determinant has rank five."}]),
            ["The determinant has rank five."],
        )

    @staticmethod
    def _digest():
        return {
            "established_facts": [
                {
                    "statement": "deg(W_5)=16.",
                    "evidence_class": "mechanical",
                    "evidence": "Arithmetic.",
                },
                {
                    "statement": "The splitting is balanced.",
                    "evidence_class": "source",
                    "evidence": "Packet locator.",
                },
            ],
            "candidate_ideas": [{"statement": "Z is nonempty."}],
            "invalid_steps": [
                {
                    "statement": "Conclude nonemptiness from chi(L)=1.",
                    "mathematical_reason": "The divisor may be non-reduced.",
                }
            ],
            "reusable_computations": [
                {"statement": "2d-16=26.", "sha256": "a" * 64}
            ],
            "unresolved_dependencies": [{"statement": "Compare Fitting ideals."}],
        }

    def test_stale_source_facts_demote_but_mechanical_ones_survive(self):
        fresh = {
            row["statement"]: row
            for row in _digest_rows(self._digest(), 1, fresh=True)
        }
        self.assertEqual(
            {row["section"] for row in fresh.values() if "deg(W_5)" in row["statement"]},
            {"established"},
        )
        stale = _digest_rows(self._digest(), 1, fresh=False)
        by_section = {}
        for row in stale:
            by_section.setdefault(row["section"], []).append(row["statement"])
        # Arithmetic does not depend on the packet text and stays established.
        self.assertTrue(
            any("deg(W_5)" in item for item in by_section["established"])
        )
        # A source-evidenced fact leans on packet findings and becomes a
        # candidate that must be reproved.
        self.assertFalse(
            any("balanced" in item for item in by_section["established"])
        )
        demoted = [
            item for item in by_section["candidate"] if "balanced" in item
        ]
        self.assertEqual(len(demoted), 1)
        self.assertIn("superseded packet", demoted[0])
        # A refuted step stays refuted; its reason is self-contained.
        self.assertEqual(len(by_section["invalid"]), 1)
        # Sha-pinned computations survive unchanged.
        self.assertEqual(len(by_section["computation"]), 1)

    def test_tier_budgets_are_respected_and_eviction_cascades(self):
        rows = [
            {
                "section": "candidate",
                "statement": "Candidate %d. %s" % (index, "x" * 400),
                "fresh": False,
                "rank_key": "candidate",
                "rank": _rank_tuple(
                    "candidate",
                    packet_redundant=False,
                    fresh=False,
                    reinforced=False,
                    ordinal=index,
                ),
                "dedup_key": "candidate:%d" % index,
                "demoted": False,
                "force_archive": False,
                "packet_redundant": False,
            }
            for index in range(600)
        ]
        tiers = _allocate_tiers(rows)
        self.assertLessEqual(
            sum(len(("- " + row["statement"] + "\n").encode()) for row in tiers["primary"]),
            PRIMARY_BUDGET_BYTES,
        )
        self.assertLessEqual(
            sum(len(("- " + row["statement"] + "\n").encode()) for row in tiers["extended"]),
            EXTENDED_BUDGET_BYTES,
        )
        # Nothing is silently dropped: every row lands in exactly one tier.
        self.assertEqual(
            len(tiers["primary"]) + len(tiers["extended"]) + len(tiers["archive"]),
            len(rows),
        )
        self.assertTrue(tiers["archive"])
        # Low-value candidates cannot monopolize primary.
        self.assertLessEqual(
            sum(1 for row in tiers["primary"] if row["section"] == "candidate"),
            12,
        )

    @staticmethod
    def _row(
        section,
        statement,
        *,
        rank_key=None,
        fresh=True,
        ordinal=1,
        force_archive=False,
        packet_redundant=False,
        demoted=False,
        reinforced=False,
    ):
        if rank_key is None:
            rank_key = (
                "established_source" if section == "established" else section
            )
        return {
            "section": section,
            "statement": statement,
            "fresh": fresh,
            "ordinal": ordinal,
            "rank_key": rank_key,
            "rank": _rank_tuple(
                rank_key,
                packet_redundant=packet_redundant,
                fresh=fresh,
                reinforced=reinforced,
                ordinal=ordinal,
            ),
            "dedup_key": "%s:%s" % (section, statement.lower()),
            "demoted": demoted,
            "force_archive": force_archive,
            "packet_redundant": packet_redundant,
            "reinforced": reinforced,
        }

    def test_primary_prefers_constraints_over_dependencies(self):
        rows = []
        for index in range(40):
            rows.append(
                self._row(
                    "invalid",
                    "Bad inference %d with a substantial mathematical reason block."
                    % index
                    + (" y" * 20),
                    ordinal=index,
                )
            )
        for index in range(30):
            rows.append(
                self._row(
                    "dependency",
                    "Open obligation %d that restates the subproblem graph." % index
                    + (" z" * 20),
                    ordinal=index,
                )
            )
        rows.sort(key=lambda item: item["rank"])
        tiers = _allocate_tiers(rows, primary_budget=20_000, extended_budget=10_000)
        primary_deps = [
            row for row in tiers["primary"] if row["section"] == "dependency"
        ]
        primary_invalid = [
            row for row in tiers["primary"] if row["section"] == "invalid"
        ]
        self.assertLessEqual(len(primary_deps), PRIMARY_CAP_DEPENDENCY_ROWS)
        self.assertGreater(len(primary_invalid), len(primary_deps))
        # Remaining constraints should overflow to extended before archive.
        ext_invalid = [
            row for row in tiers["extended"] if row["section"] == "invalid"
        ]
        arch_invalid = [
            row for row in tiers["archive"] if row["section"] == "invalid"
        ]
        if any(row["section"] == "invalid" for row in rows if row not in tiers["primary"]):
            self.assertGreaterEqual(len(ext_invalid), len(arch_invalid))

    def test_force_archive_dependencies_skip_injected_tiers(self):
        rows = [
            self._row(
                "dependency",
                "Stale open gap from an old digest.",
                ordinal=1,
                force_archive=True,
                fresh=False,
            ),
            self._row(
                "dependency",
                "Fresh frontier obligation from the latest digest.",
                ordinal=3,
                force_archive=False,
                fresh=True,
            ),
            self._row(
                "invalid",
                "Do not equate geometric points with Fitting ideals.",
                ordinal=3,
            ),
        ]
        tiers = _allocate_tiers(rows, primary_budget=5000, extended_budget=5000)
        self.assertEqual(
            [row["statement"] for row in tiers["archive"]],
            ["Stale open gap from an old digest."],
        )
        injected = tiers["primary"] + tiers["extended"]
        self.assertTrue(
            any("Fresh frontier" in row["statement"] for row in injected)
        )
        self.assertFalse(
            any("Stale open gap" in row["statement"] for row in injected)
        )

    def test_packet_redundant_sorts_worse_than_unique(self):
        unique = self._row(
            "established",
            "A unique mechanical identity of the evaluation matrix.",
            rank_key="established_source",
            packet_redundant=False,
            ordinal=1,
        )
        redundant = self._row(
            "established",
            "A packet-redundant restatement of an adjudicated finding.",
            rank_key="established_source",
            packet_redundant=True,
            ordinal=2,
        )
        self.assertLess(unique["rank"], redundant["rank"])
        packet = (
            "FND-0063 evaluation fails iff O_C(Gamma) isomorphic to "
            "W_5 tensor omega_C^{-1} on balanced covers."
        )
        self.assertTrue(
            _is_packet_redundant(
                "FND-0063 evaluation fails iff O_C(Gamma) isomorphic to "
                "W_5 tensor omega_C^{-1} on balanced covers of genus six curves.",
                packet.lower(),
                _packet_tokens(packet),
            )
        )
        self.assertFalse(
            _is_packet_redundant(
                "Fitting ideal of the universal evaluation equals the identity section ideal.",
                packet.lower(),
                _packet_tokens(packet),
            )
        )

    def test_dedup_strips_evidence_suffixes(self):
        left = "deg(W_5)=16 [evidence: mechanical; Arithmetic from RR.]"
        right = "deg(W_5)=16 [evidence: source; Packet FND-0062.]"
        self.assertEqual(_statement_core(left), _statement_core(right))

    def test_primary_render_orders_constraints_before_established(self):
        text = _render_tier(
            PRIMARY_TITLE,
            PRIMARY_PREAMBLE,
            [
                self._row("established", "A fact."),
                self._row("invalid", "A bad step.", rank_key="invalid"),
                self._row("dependency", "An open gap."),
            ],
            headings=PRIMARY_SECTION_HEADINGS,
        )
        frontier_at = text.index("## Frontier obligations")
        constraints_at = text.index("## Mathematical constraints")
        established_at = text.index("## Established facts")
        self.assertLess(frontier_at, constraints_at)
        self.assertLess(constraints_at, established_at)

    def test_ledger_audit_reads_both_working_context_shapes(self):
        legacy = {"path": "a.md", "sha256": "a" * 64}
        self.assertEqual(working_context_paths(legacy), [legacy])
        tiered = {
            "primary": {"path": "p.md", "sha256": "b" * 64},
            "extended": {"path": "e.md", "sha256": "c" * 64},
            "archive": {"path": "r.md", "sha256": "d" * 64},
            "stats": {"rows_total": 3},
        }
        self.assertEqual(
            [item["path"] for item in working_context_paths(tiered)],
            ["p.md", "e.md", "r.md"],
        )

    def test_attach_working_context_injects_primary_and_is_idempotent(self):
        records = working_context_records(self.campaign)
        self.assertGreaterEqual(len(records), 1)
        primary_path = records[0]["path"]
        self.assertTrue(is_primary_working_context_path(primary_path))
        self.assertFalse(
            is_primary_working_context_path(
                "proof/packets/generated/paired-working-context/WORKING-EXT-abc.md"
            )
        )
        base = {
            "id": "TASK-C66-M-001",
            "phase": "mathematics",
            "campaign_id": self.campaign["id"],
            "input_artifacts": [],
        }
        once = attach_working_context(base, self.campaign)
        paths = [
            item["path"]
            for item in once["input_artifacts"]
            if isinstance(item, dict)
        ]
        self.assertIn(primary_path, paths)
        self.assertTrue(
            any(
                Path(path).name.startswith("WORKING-EXT-") for path in paths
            )
        )
        self.assertTrue(
            any(
                Path(path).name.startswith("WORKING-ARCHIVE-") for path in paths
            )
        )
        self.assertIn("working_context", once)
        self.assertEqual(once["working_context"]["primary"]["path"], primary_path)
        self.assertIn("archive", once["working_context"])
        twice = attach_working_context(once, self.campaign)
        self.assertEqual(
            [item["path"] for item in twice["input_artifacts"]],
            paths,
        )
        primary_only = attach_working_context(
            {"id": "TASK-X", "input_artifacts": []},
            self.campaign,
            include_extended=False,
        )
        self.assertEqual(len(primary_only["input_artifacts"]), 1)
        self.assertTrue(
            is_primary_working_context_path(
                primary_only["input_artifacts"][0]["path"]
            )
        )

    def test_problem_key_tracks_packet_identity_not_content(self):
        key = problem_key(self.campaign)
        self.assertEqual(len(key), 64)
        self.assertEqual(self.campaign["paired_attempt_policy"]["revision"], POLICY_REVISION)
        # Adjudicating a finding rewrites the packet's findings section. That
        # must not mint a new problem key: doing so orphaned the ledger and
        # reset every engine's pair state to untried, respending a forced proof.
        with mock.patch(
            "pure_tate.campaigns.campaign_packet_record",
            side_effect=[
                {"packet_sha256": "a" * 64},
                {"packet_sha256": "b" * 64},
            ],
        ):
            self.assertEqual(
                problem_key(self.campaign), problem_key(self.campaign)
            )
        # A changed packet identity is a genuinely different problem.
        with mock.patch(
            "pure_tate.campaigns.campaign_packet_binding_sha256",
            side_effect=["a" * 64, "b" * 64],
        ):
            self.assertNotEqual(
                problem_key(self.campaign), problem_key(self.campaign)
            )

    def test_external_state_machine_opens_exactly_one_fallback(self):
        def event_for(_campaign, _engine, event_type):
            if event_type == "forced_substantive_rejected":
                return {"trace_id": "TRACE-0001"}
            return None

        with mock.patch(
            "pure_tate.paired.load_artifacts", return_value=[]
        ), mock.patch("pure_tate.paired._event", side_effect=event_for):
            self.assertEqual(
                pair_state(self.campaign, "grok")["state"],
                "forced_trace_mining",
            )

        def ready_event(_campaign, _engine, event_type):
            values = {
                "forced_substantive_rejected": {"trace_id": "TRACE-0001"},
                "forced_digest_written": {"digest_id": "DIGEST-0001"},
            }
            return values.get(event_type)

        with mock.patch(
            "pure_tate.paired.load_artifacts", return_value=[]
        ), mock.patch("pure_tate.paired._event", side_effect=ready_event):
            self.assertEqual(
                pair_state(self.campaign, "grok")["state"],
                "standard_ready",
            )

        def exhausted_event(_campaign, _engine, event_type):
            values = {
                "forced_substantive_rejected": {"trace_id": "TRACE-0001"},
                "forced_digest_written": {"digest_id": "DIGEST-0001"},
                "standard_substantive_rejected": {"trace_id": "TRACE-0002"},
                "standard_digest_written": {"digest_id": "DIGEST-0002"},
            }
            return values.get(event_type)

        with mock.patch(
            "pure_tate.paired.load_artifacts", return_value=[]
        ), mock.patch("pure_tate.paired._event", side_effect=exhausted_event):
            self.assertEqual(
                pair_state(self.campaign, "grok")["state"],
                "pair_exhausted",
            )

    def test_infrastructure_progress_is_mined_before_retry(self):
        def infrastructure_event(_campaign, _engine, event_type):
            if event_type == "forced-proof_infrastructure_failure":
                return {"trace_id": "TRACE-0099"}
            return None

        with mock.patch(
            "pure_tate.paired.load_artifacts", return_value=[]
        ), mock.patch(
            "pure_tate.paired._event", side_effect=infrastructure_event
        ), mock.patch(
            "pure_tate.paired._event_for_trace", return_value=None
        ):
            state = pair_state(self.campaign, "claude")
            self.assertEqual(state["state"], "infrastructure_trace_mining")
            self.assertEqual(state["retry_turn"], "forced-proof")

        with mock.patch(
            "pure_tate.paired.load_artifacts", return_value=[]
        ), mock.patch(
            "pure_tate.paired._event", side_effect=infrastructure_event
        ), mock.patch(
            "pure_tate.paired._event_for_trace",
            return_value={"digest_id": "DIGEST-0099"},
        ):
            self.assertEqual(
                pair_state(self.campaign, "claude")["state"],
                "forced_untried",
            )

    def test_substantive_invalid_output_is_traced_but_not_written(self):
        incomplete = self.full_artifact()
        # Incompleteness has to be structural: a status string alone no longer
        # decides it, because the harness derives status from the content.
        incomplete["gap_markers"] = ["residual comparison unproved"]
        process = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "text": json.dumps(incomplete),
                    "stopReason": "endTurn",
                    "sessionId": "official-session-envelope",
                }
            ),
            stderr="",
        )
        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory)
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/grok"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", return_value=process
        ):
            from pure_tate.paired import SubstantiveAttemptError

            # Fresh slot: never target an on-disk ledger path.
            output = Path(directory) / "ATT-9999.json"
            with self.assertRaises(SubstantiveAttemptError):
                run_task(self.task, "grok", output)
            traces = list(Path(directory).glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text())
            self.assertIn("complete resolution", trace["validation_error"])
            self.assertFalse(output.exists())

    def test_backend_error_creates_infrastructure_trace_without_artifact(self):
        process = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "is_error": True,
                    "api_error_status": "status: 503",
                    "result": "backend unavailable",
                }
            ),
            stderr="",
        )
        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory)
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/grok"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", return_value=process
        ):
            from pure_tate.paired import PairedInfrastructureError

            # Fresh slot: never target an on-disk ledger path.
            output = Path(directory) / "ATT-9999.json"
            with self.assertRaisesRegex(
                PairedInfrastructureError, "backend unavailable"
            ):
                run_task(self.task, "grok", output)
            traces = list(Path(directory).glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text())
            self.assertEqual(trace["classification"], "parse_failure")
            self.assertIn("backend unavailable", trace["validation_error"])
            self.assertFalse(output.exists())

    def test_nonzero_stream_preserves_partial_claude_progress(self):
        partial = json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {
                        "type": "text_delta",
                        "text": "Provisional lemma: the boundary map vanishes.",
                    },
                },
            }
        )
        process = SimpleNamespace(
            returncode=1,
            stdout=partial,
            stderr="response exceeded output token maximum",
        )
        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory)
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/claude"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", return_value=process
        ):
            from pure_tate.paired import PairedInfrastructureError

            # Fresh slot: never target an on-disk ledger path.
            output = Path(directory) / "ATT-9999.json"
            with self.assertRaises(PairedInfrastructureError):
                run_task(self.task, "claude", output)
            traces = list(Path(directory).glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text())
            self.assertEqual(trace["classification"], "infrastructure")
            self.assertIn("Provisional lemma", trace["observable_stdout"])
            self.assertFalse(output.exists())

    def test_ordinary_nonzero_stream_preserves_partial_claude_progress(self):
        from pure_tate.paired import ObservableInfrastructureError

        task = copy.deepcopy(self.task)
        task["phase"] = "mathematics"
        task["subproblem_id"] = "C66-GEO-COMP"
        task["lane"] = "geometry"
        for key in list(task):
            if key.startswith("paired_"):
                task.pop(key)
        partial = json.dumps(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_delta",
                    "delta": {
                        "type": "text_delta",
                        "text": "Stacky monodromy repair in progress.",
                    },
                },
            }
        )
        process = SimpleNamespace(
            returncode=1,
            stdout=partial,
            stderr="session limit reached",
        )
        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory)
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/claude"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", return_value=process
        ):
            output = Path(directory) / "ATT-9998.json"
            with self.assertRaises(ObservableInfrastructureError) as raised:
                run_task(task, "claude", output)
            traces = list(Path(directory).glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text())
            self.assertEqual(trace["classification"], "infrastructure")
            self.assertEqual(trace["turn_kind"], "mathematics")
            self.assertIn("Stacky monodromy", trace["observable_stdout"])
            self.assertIn("session limit", trace["observable_stderr"])
            self.assertEqual(raised.exception.trace_id, trace["id"])
            self.assertFalse(output.exists())

    def test_ordinary_watchdog_preserves_partial_output(self):
        from pure_tate.paired import ObservableInfrastructureError
        from pure_tate.process_runner import ProcessWatchdogError

        task = copy.deepcopy(self.task)
        task["phase"] = "mathematics"
        task["subproblem_id"] = "C66-GEO-COMP"
        task["lane"] = "geometry"
        for key in list(task):
            if key.startswith("paired_"):
                task.pop(key)
        failure = ProcessWatchdogError(
            "inactivity timeout",
            600.0,
            "Partial scheme-atlas descent argument.",
            "",
        )
        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory)
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/claude"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", side_effect=failure
        ):
            output = Path(directory) / "ATT-9998.json"
            with self.assertRaises(ObservableInfrastructureError):
                run_task(task, "claude", output)
            traces = list(Path(directory).glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text())
            self.assertEqual(trace["classification"], "infrastructure")
            self.assertEqual(trace["turn_kind"], "mathematics")
            self.assertIn("scheme-atlas descent", trace["observable_stdout"])
            self.assertIn("inactivity timeout", trace["validation_error"])
            self.assertFalse(output.exists())

    def test_review_validation_failure_preserves_observable_trace(self):
        from pure_tate.agents import run_task
        from pure_tate.campaigns import campaign_packet_record
        from pure_tate.paired import ArtifactValidationError
        from pure_tate.targets import CONTEXT_REVISION

        packet = campaign_packet_record("C66-001")
        attempt = {
            "id": "ATT-9997",
            "engine": "codex",
            "campaign_id": "C66-001",
            "campaign_revision": self.campaign["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "target": self.task["target"],
            "theorem_statement": self.campaign["paired_attempt_policy"][
                "exact_theorem"
            ],
            "packet_path": packet["packet_path"],
        }
        body = {
            "schema_version": 3,
            "id": "REV-9997",
            "review_task_id": "TASK-V-ATT-9997-P1",
            "review_pass": 1,
            "attempt_id": "ATT-9997",
            "campaign_id": "C66-001",
            "campaign_revision": self.campaign["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "context_revision": CONTEXT_REVISION,
            "packet_id": packet["packet_id"],
            "packet_sha256": packet["packet_sha256"],
            "target": self.task["target"],
            "theorem_statement": attempt["theorem_statement"],
            "verdict": "confirmed",
            "reviewer_engine": "grok",
            "independent": True,
            "checked_claims": [
                {
                    "claim_id": "CLM-X",
                    "result": "refuted",
                    "note": "Adverse check retained under a confirmed verdict.",
                }
            ],
            "proof_dependency_checks": [],
            "strongest_attack": "Preserved attack body " + ("X" * 1000),
            "finding_candidates": [
                {
                    "key": "synthetic-adverse",
                    "statement": "Synthetic finding for review-trace coverage.",
                }
            ],
            "created_on": "2026-07-31",
        }
        process = SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "text": json.dumps(body),
                    "stopReason": "endTurn",
                    "sessionId": "review-trace-envelope",
                }
            ),
            stderr="",
        )
        task = {
            "id": "TASK-V-ATT-9997-P1",
            "phase": "review",
            "review_pass": 1,
            "target_attempt_id": "ATT-9997",
            "context_revision": CONTEXT_REVISION,
            "packet_id": packet["packet_id"],
            "packet_sha256": packet["packet_sha256"],
            "target": self.task["target"],
            "prover_engine": "codex",
            "excluded_reviewer_engines": ["codex"],
            "prompt": "prompts/ADVERSARY.md",
            "input_attempt": "proof/attempts/ATT-0020.json",
            "input_packet": packet["packet_path"],
            "campaign_id": "C66-001",
            "campaign_revision": self.campaign["campaign_revision"],
            "subproblem_id": "C66-FULL",
            "theorem_statement": attempt["theorem_statement"],
        }
        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory)
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/grok"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", return_value=process
        ), mock.patch(
            "pure_tate.agents._validate_task_packet", return_value=None
        ), mock.patch(
            "pure_tate.agents.build_isolated_context", return_value=["TASK.json"]
        ):
            # Fresh slot: never target an on-disk ledger path.
            output = Path(directory) / "REV-9997.json"
            with self.assertRaises(ArtifactValidationError) as raised:
                run_task(task, "grok", output)
            self.assertFalse(output.exists())
            traces = list(Path(directory).glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text(encoding="utf-8"))
            self.assertEqual(trace["classification"], "validation_failure")
            self.assertEqual(trace["turn_kind"], "review")
            self.assertEqual(raised.exception.trace_id, trace["id"])
            self.assertGreater(len(trace.get("observable_stdout") or ""), 1000)
            self.assertEqual(trace["parsed_artifact"]["id"], "REV-9997")
            self.assertIn(
                "Preserved attack body",
                trace["parsed_artifact"]["strongest_attack"],
            )

    def test_codex_final_file_is_parsed_while_jsonl_progress_is_traced(self):
        artifact = self.full_artifact()
        artifact["engine"] = "codex"
        progress = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "reasoning",
                    "text": "Derived a boundary-map identity.",
                },
            }
        )

        def fake_process(command, **_kwargs):
            final_path = Path(command[command.index("-o") + 1])
            final_path.write_text(json.dumps(artifact), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout=progress, stderr="")

        with tempfile.TemporaryDirectory(
            dir=ROOT / "research"
        ) as directory, mock.patch(
            "pure_tate.paired.TRACE_DIR", Path(directory) / "traces"
        ), mock.patch(
            "pure_tate.agents._validate_output_path"
        ), mock.patch(
            "pure_tate.agents.shutil.which", return_value="/usr/bin/codex"
        ), mock.patch(
            "pure_tate.agents.run_captured_process", side_effect=fake_process
        ), mock.patch(
            "pure_tate.agents._codex_controller_settings",
            return_value={
                "enabled": False,
                "max_requests": 0,
                "retry_limit": 0,
                "max_attempts": 1,
                "max_result_chars": 500,
            },
        ):
            output = Path(directory) / "ATT-9999.json"
            result = run_task(self.task, "codex", output)
            self.assertEqual(result["id"], "ATT-9999")
            traces = list((Path(directory) / "traces").glob("TRACE-*.json"))
            self.assertEqual(len(traces), 1)
            trace = json.loads(traces[0].read_text())
            self.assertIn("boundary-map identity", trace["observable_stdout"])
            self.assertEqual(trace["parsed_artifact"]["id"], "ATT-9999")

    def test_mathematics_trace_recovery_refuses_overwrite_and_uses_new_slot(self):
        from pure_tate.paired import (
            recover_attempt_from_trace,
            unrecovered_validation_traces,
        )
        from pure_tate.tasking import campaign_mathematics_tasks

        base = campaign_mathematics_tasks("C66-001")[0]
        artifact = self.full_artifact()
        artifact["id"] = "ATT-8801"
        artifact["engine"] = "claude"
        artifact["task_id"] = base["id"]
        artifact["subproblem_id"] = base["subproblem_id"]
        artifact["lane"] = base.get("lane", artifact["lane"])
        # Deliberately omit compact target keys; recovery validation coerces them.
        artifact["target"] = {
            key: value
            for key, value in base["target"].items()
            if key not in {"compact_cohomology_degree", "compact_tate_type"}
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            traces = root / "traces"
            attempts = root / "attempts"
            recoveries = root / "recoveries.json"
            traces.mkdir()
            attempts.mkdir()
            trace_id = "TRACE-8801"
            (traces / (trace_id + ".json")).write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": trace_id,
                        "campaign_id": "C66-001",
                        "task_id": base["id"],
                        "engine": "claude",
                        "turn_kind": "mathematics",
                        "packet_sha256": base["packet_sha256"],
                        "packet_binding_sha256": base.get(
                            "packet_binding_sha256"
                        ),
                        "classification": "validation_failure",
                        "validation_error": "target mismatch",
                        "parsed_artifact": artifact,
                        "observable_stdout": json.dumps(artifact),
                        "observable_stderr": "",
                        "source_boundary": (
                            "Official subprocess output only; no provider-private "
                            "session files or hidden chain-of-thought."
                        ),
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch("pure_tate.paired.TRACE_DIR", traces), mock.patch(
                "pure_tate.paired.RECOVERY_LEDGER_PATH", recoveries
            ), mock.patch(
                "pure_tate.paired.ROOT", root
            ), mock.patch(
                "pure_tate.paired.record_event", return_value={}
            ):
                pending = unrecovered_validation_traces("C66-001")
                self.assertEqual([item["trace_id"] for item in pending], [trace_id])
                output = attempts / "ATT-8801.json"
                receipt = recover_attempt_from_trace(trace_id, output)
                self.assertEqual(receipt["artifact_id"], "ATT-8801")
                self.assertTrue(output.is_file())
                recovered = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(
                    recovered["target"]["compact_cohomology_degree"],
                    base["target"]["compact_cohomology_degree"],
                )
                self.assertTrue(recovered["recovery"]["protect_from_overwrite"])
                with self.assertRaises(ValueError) as raised:
                    recover_attempt_from_trace(trace_id, output)
                self.assertIn("refusing to overwrite", str(raised.exception))
                # After recovery the trace is no longer pending.
                self.assertEqual(unrecovered_validation_traces("C66-001"), [])


class DigestAttributionTests(unittest.TestCase):
    def setUp(self):
        self.campaign = load_campaign("C66-001")

    def test_math_task_map_and_ancestors(self):
        from pure_tate.paired import (
            ancestor_subproblem_ids,
            math_task_subproblem_map,
        )

        mapping = math_task_subproblem_map(self.campaign)
        self.assertEqual(mapping["TASK-C66-M-001"]["subproblem_id"], "C66-GEO-Z")
        self.assertEqual(mapping["TASK-C66-M-009"]["subproblem_id"], "C66-COMP-RANK")
        self.assertEqual(mapping["TASK-C66-M-010"]["subproblem_id"], "C66-COMP-COMP")
        ancestors = ancestor_subproblem_ids(self.campaign, "C66-GEO-COMP")
        self.assertEqual(
            ancestors, {"C66-GEO-COMP", "C66-GEO-H0", "C66-GEO-Z"}
        )

    def test_forced_and_standard_trace_attribution(self):
        from pure_tate.paired import (
            FULL_LANE,
            FULL_SUBPROBLEM_ID,
            _attribution_from_trace,
        )

        forced = _attribution_from_trace(
            {
                "id": "TRACE-X",
                "task_id": "TASK-C66-001-FORCED-FULL",
                "turn_kind": "forced-proof",
                "parsed_artifact": None,
            },
            self.campaign,
        )
        self.assertEqual(forced["source_subproblem_id"], FULL_SUBPROBLEM_ID)
        self.assertEqual(forced["source_lane"], FULL_LANE)

        standard = _attribution_from_trace(
            {
                "id": "TRACE-Y",
                "task_id": "TASK-C66-M-008",
                "turn_kind": "standard-fallback",
                "parsed_artifact": {
                    "id": "ATT-0063",
                    "subproblem_id": "C66-COMP-RANK",
                    "lane": "computation",
                },
            },
            self.campaign,
        )
        self.assertEqual(standard["source_subproblem_id"], "C66-COMP-RANK")
        self.assertEqual(standard["confidence"], "artifact")

        by_task = _attribution_from_trace(
            {
                "id": "TRACE-Z",
                "task_id": "TASK-C66-M-001",
                "turn_kind": "standard-fallback",
                "parsed_artifact": None,
            },
            self.campaign,
        )
        self.assertEqual(by_task["source_subproblem_id"], "C66-GEO-Z")
        self.assertEqual(by_task["confidence"], "task_id")

    def test_backfill_sidecar_recovers_past_digests(self):
        from pure_tate.paired import (
            DIGEST_ATTRIBUTION_PATH,
            backfill_digest_attributions,
            digest_source_attribution,
            load_digest_attribution_sidecar,
        )

        before = (
            DIGEST_ATTRIBUTION_PATH.read_text(encoding="utf-8")
            if DIGEST_ATTRIBUTION_PATH.is_file()
            else None
        )
        try:
            result = backfill_digest_attributions(self.campaign)
            self.assertGreaterEqual(result["recovered"], 1)
            sidecar = load_digest_attribution_sidecar()
            self.assertIn("DIGEST-0001", sidecar["digests"])
            self.assertEqual(
                sidecar["digests"]["DIGEST-0001"]["source_subproblem_id"],
                "C66-FULL",
            )
            attr = digest_source_attribution(
                {"id": "DIGEST-0002", "campaign_id": "C66-001"},
                self.campaign,
            )
            self.assertEqual(attr["source_subproblem_id"], "C66-GEO-Z")
        finally:
            if before is None and DIGEST_ATTRIBUTION_PATH.is_file():
                DIGEST_ATTRIBUTION_PATH.unlink()
            elif before is not None:
                DIGEST_ATTRIBUTION_PATH.write_text(before, encoding="utf-8")


class CellWorkingContextTests(unittest.TestCase):
    def setUp(self):
        self.campaign = load_campaign("C66-001")

    def test_sibling_candidates_skip_primary(self):
        from pure_tate.paired import _allocate_tiers, _rank_tuple

        rows = [
            {
                "section": "invalid",
                "statement": "Campaign-wide blocked inference with reason.",
                "fresh": True,
                "ordinal": 1,
                "rank_key": "invalid",
                "rank": _rank_tuple(
                    "invalid",
                    packet_redundant=False,
                    fresh=True,
                    reinforced=False,
                    ordinal=1,
                    cell_relevance=0,
                ),
                "dedup_key": "invalid:campaign",
                "demoted": False,
                "force_archive": False,
                "packet_redundant": False,
                "source_subproblem_id": "C66-FULL",
                "cell_relevance": 0,
                "primary_eligible": True,
            },
            {
                "section": "candidate",
                "statement": (
                    "Sibling-only rank-drop ideal conjecture with no lexical "
                    "overlap to geometry components."
                ),
                "fresh": True,
                "ordinal": 2,
                "rank_key": "candidate",
                "rank": _rank_tuple(
                    "candidate",
                    packet_redundant=False,
                    fresh=True,
                    reinforced=False,
                    ordinal=2,
                    cell_relevance=3,
                ),
                "dedup_key": "candidate:sibling",
                "demoted": False,
                "force_archive": False,
                "packet_redundant": False,
                "source_subproblem_id": "C66-COMP-RANK",
                "cell_relevance": 3,
                "primary_eligible": False,
            },
            {
                "section": "candidate",
                "statement": (
                    "Geometry component and stabilizer cover behavior for GEO-COMP."
                ),
                "fresh": True,
                "ordinal": 3,
                "rank_key": "candidate",
                "rank": _rank_tuple(
                    "candidate",
                    packet_redundant=False,
                    fresh=True,
                    reinforced=False,
                    ordinal=3,
                    cell_relevance=0,
                ),
                "dedup_key": "candidate:geo",
                "demoted": False,
                "force_archive": False,
                "packet_redundant": False,
                "source_subproblem_id": "C66-GEO-COMP",
                "cell_relevance": 0,
                "primary_eligible": True,
            },
        ]
        tiers = _allocate_tiers(rows, primary_budget=20_000, extended_budget=10_000)
        primary_keys = {row["dedup_key"] for row in tiers["primary"]}
        self.assertIn("invalid:campaign", primary_keys)
        self.assertIn("candidate:geo", primary_keys)
        self.assertNotIn("candidate:sibling", primary_keys)
        overflow = {row["dedup_key"] for row in tiers["extended"] + tiers["archive"]}
        self.assertIn("candidate:sibling", overflow)

    def test_cell_merge_budget_and_path(self):
        from pure_tate.paired import merge_working_context

        merged = merge_working_context(self.campaign, "C66-GEO-COMP")
        self.assertLessEqual(
            merged["stats"]["bytes_primary"], PRIMARY_BUDGET_BYTES
        )
        self.assertIn("C66-GEO-COMP", merged["primary"]["path"])
        self.assertEqual(merged["subproblem_id"], "C66-GEO-COMP")
        primary = (ROOT / merged["primary"]["path"]).read_text(encoding="utf-8")
        self.assertIn("C66-GEO-COMP", primary.splitlines()[0])

    def test_attach_scopes_ordinary_cell(self):
        task = {
            "id": "TASK-C66-M-003",
            "phase": "mathematics",
            "campaign_id": self.campaign["id"],
            "subproblem_id": "C66-GEO-COMP",
            "lane": "geometry",
            "input_artifacts": [],
        }
        attached = attach_working_context(task, self.campaign)
        primary = attached["working_context"]["primary"]["path"]
        self.assertIn("C66-GEO-COMP", primary)
        self.assertEqual(
            attached["working_context"].get("subproblem_id"), "C66-GEO-COMP"
        )


class IsolatedContextRepoTests(unittest.TestCase):
    def test_mathematics_workspace_links_repo(self):
        from pure_tate.agents import build_isolated_context
        from pure_tate.paired import attach_working_context

        campaign = load_campaign("C66-001")
        packet = write_campaign_packet("C66-001")
        task = {
            "id": "TASK-C66-M-003",
            "phase": "mathematics",
            "campaign_id": campaign["id"],
            "campaign_revision": campaign["campaign_revision"],
            "subproblem_id": "C66-GEO-COMP",
            "lane": "geometry",
            "input_packet": packet["packet_path"],
            "input_artifacts": [],
            "prompt": "prompts/CAMPAIGN_MATHEMATICS.md",
        }
        task = attach_working_context(task, campaign)
        with tempfile.TemporaryDirectory(prefix="pure-tate-ctx-") as directory:
            destination = Path(directory)
            files = build_isolated_context(task, destination)
            self.assertIn("repo", files)
            self.assertIn("CONTEXT-INDEX.md", files)
            repo = destination / "repo"
            self.assertTrue(repo.is_symlink() or repo.exists())
            if repo.is_symlink():
                self.assertEqual(repo.resolve(), ROOT.resolve())
            self.assertTrue((destination / "CONTEXT-INDEX.md").is_file())
            self.assertTrue((destination / "TASK.json").is_file())
