# Pure Tate — final review handoff

Self-contained snapshot of the genus-at-most-seven, degree-sixteen campaign
`LG7D16-007` and its current attempt `LATT-0010`, plus the manuscript it is bound to.
Repo-relative paths are preserved, so the harness resolves and runs here unchanged.

## Verify in one step

```bash
python3 -m pure_tate lean-check --attempt LATT-0010 --campaign LG7D16-007
```

Expected: `"result": "PASS"`, `lean_exit 0`, `model_exit 0`, empty `errors`, Lean
4.32.1, 36 declared axioms all used, model witness depending on no axioms. Requires
`elan` with `leanprover/lean4:v4.32.1`. Also reproducible here:

```bash
python3 -m pure_tate lean-status --campaign LG7D16-007
python3 -m unittest tests.test_lean_campaign
```

All 20 harness tests pass. The predecessor `LATT-0009` / `LG7D16-006` also still
verifies, and every file in this folder is byte-identical to its repository original.

## Current state

`LATT-0010` is a **candidate**, not verified. It passes every mechanical gate and has
**zero** independent semantic reviews. `lean-audit` fails closed, correctly.

Two reviews exist and neither counts:

| Review | Target | Verdict | Why it does not count |
|---|---|---|---|
| `formal/reviews/LREV-0011.json` | LATT-0009 | `incomplete` | engine `claude`; also no run receipt |
| `formal/reviews/LREV-0012.json` | LATT-0010 | `confirmed` | engine `claude`, a contributing prover; recorded at the PI's direction as an accepted **non-independent** P1 |

`LATT-0010` declares `prover_engines: ["claude", "codex"]` — its `Claim.lean` is the
Claude-authored V5 deduction adopted from `LATT-0008`, its `Model.lean` is
Codex-authored. **Neither `claude` nor `codex` can grant independence credit.** Eligible
engines: `grok`, `cursor-grok`, `qwen`.

Reaching `verified` needs two confirming reviews from distinct eligible engines, each
backed by a `lean-review` run receipt binding engine, task, output path and artifact
hash. `formal/dispatch/LREV-0013-qwen-p1-latt0010.md` is written and ready to hand off.

## The revision queue

These are the open items from the two reviews. None is a correctness defect — the
formalization was found faithful, and four countermodels certify that every open-range
route is logically independent and strictly load-bearing.

| Id | Severity | Item |
|---|---|---|
| `LREV-0012-N03` | medium | The harness cannot detect content reuse across attempts. `prover_engines` is optional, so a future attempt could copy another engine's `Claim.lean` and declare only itself. Automate the check done by hand: normalise the identifier comments, hash `Claim.lean`/`Model.lean`, compare against every prior attempt. |
| `LREV-0012-N01` | low | `review_policy.reviewers_must_differ_from_all_prover_engines` is in `LG7D16-007` but read by no code. Wire it up or drop it. |
| `LREV-0012-N02` | low | `derived_from_attempt_id` and `adopted_claim_prover_engine` are never validated. |
| `LREV-0012-N04` | low | `NC42`–`NC45` test assembly *sensitivity*, not axiom *independence*. Folding the countermodel pattern into `Model.lean` would move the stronger property inside the artifact. |
| `LREV-0011-F05` | info | `clpMarkingBound 0 = 0` where CLP Table 1 has `c(0) = ∞`. Unreachable and conservative. |
| `LREV-0011-F06` | info | The CLP primitive-quotient formula (Lemma 3.1(a) via the Petersen–Tavakol–Yin projector), Harer's vcd values and the coefficient-form vcd lemma have no separate carriers; they are folded into `critical_endpoint_vanishes_one_marking`. Within contract, but the largest un-itemized published input. |

## Evidence

`formal/reviews/LREV-0011-attacks/` and `formal/reviews/LATT-0010-claude-advisory/`
hold four independence countermodels — one per open-range route — and a
variant-soundness check confirming `NC42`–`NC45` are honest one-disjunct deletions
rather than straw predicates. Each has its own README and reproduces under the pinned
toolchain.

| Route | Deleted axiom | Target falsified at |
|---|---|---|
| critical line | `critical_endpoint_vanishes_one_marking` | (6,6) |
| above line | `bfp_whole_open_bm_vanishes_above_critical_line` | (7,8) |
| below line | `open_bm_vanishes_below_critical_line` | (6,0) |
| published | `published_open_bm_tate_below_zero_range` | (3,0) |

## Scope

This is a local-check architecture. Lean verifies the assembly over audited black
boxes; it does not certify that an opaque carrier denotes the intended cohomology
group, or that an axiom faithfully states its cited theorem. `formal/README.md` has the
full fail-closed policy.

## Layout

```
formal/          campaigns, attempts (0008/0009/0010 + predecessors), reviews,
                 templates, prompts, dispatch, hash-pinned preludes and signatures
proof/attempts/  ATT-0149 (source proof for LG7D16-007) + ATT-0136, ATT-0148
output/zenodo/   degree16_genus_le7_v2 — the hash-bound manuscript (.tex, .pdf)
paper/           working manuscript copy
pure_tate/       the validator, so PASS is reproducible rather than asserted
tests/           harness test suite
reports/runs/    review run receipts and the manual-recovery reports campaigns pin
```
