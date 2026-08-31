# Compact (6,6) boundary-image mathematics campaign

Work only on the assigned subproblem and exact target. The campaign theorem is
the image of the degree-16 boundary map of `Mbar_{6,6}`, not the open residual
of `M_{6,6}` and not Casnati–Ekedahl tetragonal geometry.

Every normalized one-edge boundary component is stack-theoretic: use
`[Mbar_Gamma/Aut(Gamma)]`, not its ordered atlas alone. In particular, the
non-separating component is `[Mbar_{5,8}/S_2]`, with `S_2` exchanging the two
branches of the node. Cohomological contributions retain `Aut(Gamma)`
invariants and the determinant-edge convention.

Respect the subproblem DAG. `TASK.json` lists `blocked_dependencies` and
`dependency_artifacts`. A task is executable only when `blocked_dependencies` is
empty. When `dependency_artifacts` are non-empty, read every supplied dependency
attempt and both of its confirmation reviews, and cite their artifact IDs when
using them. Do not infer, recreate, or strengthen a dependency whose verified
artifacts are absent.

The complementary cokernel `W_{-16}H^{BM}_{16}(M_{6,6};Q)` is the `C66-001`
theorem, double-confirmed as `ATT-0136`. Do not re-prove it. Do not conclude
`H^{16}(Mbar_{6,6};Q) cong Q(-8)` unless the assigned exact theorem is that
compact statement; the campaign exact theorem is the boundary-image only.

Campaign proof turns receive a subproblem-scoped mathematical working context: a
primary file (about 60kb) and usually extended and archive overflow files. Before
drafting, you **must** read the primary file end-to-end (use your read tool on the
path listed in the execution contract). Prefer the primary file; use extended and
archive only for overflow. When you need more, search under `repo/` (full project)
or `CONTEXT-INDEX.md`. Neither working context nor searched repo material is a
substitute for proof:

- Established facts may be used directly.
- Candidate ideas must be proved independently before they carry any weight. A
  row marked as carried from a superseded packet is a candidate, whatever it
  says about itself.
- Mathematical constraints record routes already shown not to work. They may
  appear in the primary, extended, or archive file; constraints in any of them
  still bind if you rely on them. Do not walk them again, and do not present one
  as new.
- Frontier obligations / dependencies to resolve are open mathematical gaps, not
  proved inputs. Aim your theorem at advancing those, not re-deriving settled
  constraints.
- Reusable computations are pinned by SHA-256; a finite computation can motivate
  a claim but never establishes a universal one.
- Material found under `repo/` is not proved unless it is a verified dependency
  artifact listed in `TASK.json` or an established working-context fact.

State one exact theorem. If `TASK.json` contains a nonempty `exact_theorem`, that
is the assigned theorem to prove or disprove; do not replace it by a stronger
universally quantified packaging, and do not omit its excluded claims. Separate
proved steps, source-backed inputs, computational hypotheses, and gaps. Finite
experiments cannot close a proof. Address the applicable failed routes listed by
the task; do not silently reuse them. A counterexample lane must show survival in
the exact boundary-image, typically via the `Mbar_{5,8}` contribution after
the `S_2`/det operation, not merely locate non-Tate geometry of an unrelated
ordered atlas.

If genuinely new evidence reopens a blocked route, record it in `new_inputs` with
the canonical `route`, a nonempty `evidence` explanation, and
`evidence_claim_ids` naming source-verified or cross-checked claims already admitted
through the research gate. A free-form citation or renamed method does not reopen a
blocked route.

Return exactly one JSON artifact.
