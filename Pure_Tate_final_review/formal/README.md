# Lean campaigns

The current genus-at-most-seven, degree-sixteen campaign is `LG7D16-007`, bound to
the revised manuscript proof `ATT-0149`. Its current attempt is `LATT-0010`, the
immutable successor to reviewed attempt `LATT-0009` addressing `LREV-0011`. The
critical endpoint `(5,8)` is treated by the same one-marking primitive-quotient route
as `(3,12)`, `(6,6)`, and `(7,4)`: the Lean data expose the strict virtual-
cohomological-dimension inequalities, the exact marking endpoint `7=c(5)`, and Ionel
codimension `11`. No separate genus-five Chow, CKgP, or Liu premise occurs in this
campaign. The direct published-range route is used only at `(4,10)`.

`LG7D16-007` pins shared signature `G7D16SignatureV5.lean.inc`. The target, trusted
prelude, and required theorem type are unchanged from `LG7D16-004`; what changed is
the axiom structure. The open Borel-Moore range is split into four disjoint guarded
regimes — above the critical line, exactly on it, below it, and the published range —
so the critical-line case is reachable only through `CriticalEndpointVanishes`, and the
general Ionel premise is independently load-bearing through the below-line regime.
Ionel and endpoint indices carry geometry and coefficients; the CLP Table 1 bound is
the shared `clpMarkingBound` function rather than a per-record datum; smooth-proper
purity is pinned to the canonical index up to its purity tag; the published-range
control is typed by the pair; and Bergstrom-Faber-Payne Proposition 2.1 has its own
whole-group carrier with a distinct bridge to the lowest-weight piece as obligation
`G7D16-OBL-09`.

`LATT-0010` replaces the assembly-insensitive target interpretation identified by
`LREV-0011-F04`. Its model target now depends on the complete boundary/open/purity
assembly. Four axiom-free countermodels (`NC42`--`NC45`) delete the critical-line,
Bergstrom--Faber--Payne, below-critical-line, and published-range routes one at a time
and refute the corresponding target pair, so route load-bearing is checked inside the
artifact rather than only by a reviewer. The model witness depends on no axioms.

The successor also records provenance conservatively. Its Claim is adopted from the
Claude-authored V5 deduction and its assembly-sensitive model is Codex-authored, so
the manifest lists both `claude` and `codex` in `prover_engines`. The harness excludes
every listed contributor from independent-review credit. `LATT-0010` is
nevertheless only a candidate until it receives two independent, hash-bound semantic
reviews. Lean checks deduction over the declared black boxes; it does not certify that
an opaque carrier denotes the intended cohomology group or that an axiom faithfully
states its cited theorem.

`LATT-0009` and `LREV-0011` remain unchanged as the reviewed predecessor. `LATT-0008`
also remains unchanged; its manifest's references to `LG7D16-005` and `LREV-0010` are
historical dangling references and are not dependencies of `LG7D16-007`. `LATT-0007`
and campaign `LG7D16-004` remain as the earlier predecessor. The exact
`(6,6)` campaign `LC66-002` and its current attempt `LATT-0003`
remain in the repository as a separate, narrower formalization.

The campaign is intentionally fail-closed:

- every attempt is bound to an exact source-proof SHA-256 and a campaign-specific
  claim contract;
- the target index is a hash-pinned trusted Lean prelude, and the exported theorem
  must have the literal type required by its campaign; an attempt cannot replace the
  indexed target with an arbitrary proposition;
- bare Lean 4 is pinned by `lean-toolchain`; imports, `sorry`, `admit`, unsafe or
  external code, and other proof escapes are rejected;
- every axiom must map to a campaign proof obligation, every obligation must be
  represented, and every declared axiom must appear in `#print axioms`;
- `Model.lean` is mandatory as a consistency/non-collapse witness;
- a generated `report.json` binds the campaign, source proof, manifest, Lean source,
  model, toolchain, and exact axiom closure;
- “verified” requires two confirming reviews from distinct engines, both different
  from every engine listed in the attempt's `prover_engines`. Each must bind every artifact hash and audit statement faithfulness,
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
3. Run `python3 -m pure_tate lean-check --attempt LATT-#### --campaign CAMPAIGN-ID --write`.
4. Give `formal/prompts/REVIEW.md`, the source proof, campaign contract, attempt, and
   generated report to two independent reviewer engines. Store their artifacts as
   `formal/reviews/LREV-####.json` using the review template.
5. Run `python3 -m pure_tate lean-status --campaign CAMPAIGN-ID` and
   `python3 -m pure_tate lean-audit --campaign CAMPAIGN-ID`.

`lean-audit` accepts a campaign with no attempts as a warning, because scaffolding the
campaign must not create a fake formal verification. `lean-status` lists a verified
attempt only after all mechanical and independent semantic gates pass.
