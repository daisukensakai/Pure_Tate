# Lean campaign

`LC66-002` formalizes the exact `(6,6)` proof in `ATT-0136`. Lean is only the
deduction checker. It does not certify that an opaque carrier denotes the right
cohomology group or that an axiom accurately states a cited theorem. Those semantic
questions are enforced by two independent, hash-bound reviews.

The current attempt is `LATT-0003`. It preserves the separated closed/open carrier
proof of `LATT-0002` and replaces its overly collapsed consistency model: restriction,
Kunneth splitting, containment, polarizability, Tate quotient, and full Tate type now
have distinct concrete interpretations and explicit non-collapse witnesses. Its local
mechanical check passes. It remains a candidate pending the queued independent reviews
`LREV-0005` (Grok) and `LREV-0006` (Claude); neither review has been run.

The campaign is intentionally fail-closed:

- every attempt is bound to the exact `ATT-0136` SHA-256 and to
  `C66-EXACT-TARGET-V1`;
- the target index is a hash-pinned trusted Lean prelude, and the exported theorem must
  have the literal type `BMIsFiniteTateSum exactC66BMTarget`; attempts cannot replace
  the indexed `(6,6)` BM target with an arbitrary proposition;
- bare Lean 4 is pinned by `lean-toolchain`; imports, `sorry`, `admit`, unsafe or
  external code, and other proof escapes are rejected;
- every axiom must map to one of the nine proof obligations, every obligation must be
  represented, and every declared axiom must appear in `#print axioms`;
- `Model.lean` is mandatory as a consistency/non-collapse witness;
- a generated `report.json` binds the campaign, source proof, manifest, Lean source,
  model, toolchain, and exact axiom closure;
- “verified” requires two confirming reviews from distinct engines, both different
  from the prover. Each must bind every artifact hash and audit statement faithfulness,
  every axiom, the model witness, and a strongest attack. Each review must also be
  backed by a completed `lean-review` run receipt whose event binds its engine, task,
  output path, and artifact hash; self-asserted reviewer labels are rejected.

This is a local-check architecture, like the Hodge FLC tier. It verifies the assembly
over audited black boxes; it does not pretend to formalize the full theory of mixed
Hodge structures or moduli stacks in bare Lean.

## Workflow

1. Copy `formal/templates/attempt/` to a new immutable directory such as
   `formal/attempts/LATT-####-description/`. Never overwrite a competing or reviewed attempt.
2. Fill `manifest.json`, `Claim.lean`, and `Model.lean`.
3. Run `python3 -m pure_tate lean-check --attempt LATT-#### --campaign LC66-002 --write`.
4. Give `formal/prompts/REVIEW.md`, the source proof, campaign contract, attempt, and
   generated report to two independent reviewer engines. Store their artifacts as
   `formal/reviews/LREV-####.json` using the review template.
5. Run `python3 -m pure_tate lean-status --campaign LC66-002` and
   `python3 -m pure_tate lean-audit --campaign LC66-002`.

`lean-audit` accepts a campaign with no attempts as a warning, because scaffolding the
campaign must not create a fake formal verification. `lean-status` lists a verified
attempt only after all mechanical and independent semantic gates pass.
