# LREV-0011 independence countermodels

Evidence for the `strongest_attack` section of `formal/reviews/LREV-0011.json`
(P1 adversarial review of `LATT-0009`, campaign `LG7D16-006`).

Both files reuse the attempt's own trusted prelude, `G7D16SignatureV5` shared
signature and model bodies verbatim, and change two things:

1. one campaign axiom is deleted from the model, and
2. the target predicate is replaced by an **assembly-tracking** one,
   `genus <= 2 ∨ homTateModel (compactHomologyIndex t.pair)`, so that a deleted
   route becomes observable at the target. (The attempt's own `Model.lean`
   defines the target as `t = compactH16Target t.pair ∧ IsStablePair t.pair ∧
   t.pair.genus <= 7`, which is insensitive to the assembly — see finding
   `LREV-0011-F04`.)

| file | deleted axiom | obligation | target falsified at |
|---|---|---|---|
| `AttackOneMarking.lean` | `critical_endpoint_vanishes_one_marking` | `G7D16-OBL-01` | `(6,6)` |
| `AttackBFP.lean` | `bfp_whole_open_bm_vanishes_above_critical_line` | `G7D16-OBL-09` | `(7,8)` |

Each file proves three axiom-free theorems: the other 33 campaign axioms still
hold, the deleted axiom genuinely fails, and the target predicate is false at
the named pair. Both attacks therefore **fail to break `LATT-0009`**, and in
failing they certify that the one-marking primitive-quotient derivation and the
Bergstrom-Faber-Payne premise are each independent and strictly load-bearing.

Reproduce with the campaign toolchain:

    elan run leanprover/lean4:v4.32.1 lean AttackOneMarking.lean
    elan run leanprover/lean4:v4.32.1 lean AttackBFP.lean

Expected output: three `does not depend on any axioms` lines per file, no errors.
