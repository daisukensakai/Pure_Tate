# LATT-0010 — advisory adversarial checks (claude)

**Not a countable review.** `claude` is a declared contributing prover engine for
`LATT-0010` (`prover_engines: ["claude","codex"]`), so the harness correctly
rejects a confirming review from this engine. These files are evidence only.

They extend the two countermodels in `../LREV-0011-attacks/`, which established
logical independence for the critical-line and BFP routes. Together the four now
cover every open-range route.

## Route independence (stronger than the artifact's NC42–NC45)

`NC42`–`NC45` in `LATT-0010/Model.lean` establish **assembly sensitivity**: deleting a
route's disjunct from the open predicate falsifies the target at a pair only that route
covers. They do not re-prove that the remaining axioms still hold, so they do not by
themselves establish **logical independence**. These countermodels do.

| file | deleted axiom | route | obligation | target falsified at |
|---|---|---|---|---|
| `../LREV-0011-attacks/AttackOneMarking.lean` | `critical_endpoint_vanishes_one_marking` | critical line | `OBL-01` | `(6,6)` |
| `../LREV-0011-attacks/AttackBFP.lean` | `bfp_whole_open_bm_vanishes_above_critical_line` | above line | `OBL-09` | `(7,8)` |
| `AttackBelowLine.lean` | `open_bm_vanishes_below_critical_line` | below line | `OBL-02` | `(6,0)` |
| `AttackPublishedRange.lean` | `published_open_bm_tate_below_zero_range` | published | `OBL-02` | `(3,0)` |

Each proves three theorems: the other 33 campaign axioms still hold, the deleted axiom
genuinely fails, and the target predicate is false at the named pair. `(6,0)` also
exercises the `n = 0` Looijenga clause of the Ionel premise.

## Variant soundness

`VariantSoundness.lean` checks that `NC42`–`NC45` are not testing straw predicates.
For each of the four `openTateWithout*Model` variants it proves the variant implies
`openTateModel` (no smuggled extra route), and for two of them that restoring the
deleted disjunct recovers the full predicate exactly.

## Reproduce

    elan run leanprover/lean4:v4.32.1 lean AttackBelowLine.lean
    elan run leanprover/lean4:v4.32.1 lean AttackPublishedRange.lean
    elan run leanprover/lean4:v4.32.1 lean VariantSoundness.lean

All theorems report `does not depend on any axioms`, except
`attack3_refutes_ax15`, which uses `propext` via `simp`.
