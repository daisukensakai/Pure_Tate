# Focused (6,6) mathematics campaign

Work only on the assigned subproblem and exact target. Use the balanced tetragonal
Casnati–Ekedahl geometry in the packet and aim for the weakest sufficient theorem.

Respect the subproblem DAG. `TASK.json` lists `blocked_dependencies` and
`dependency_artifacts`. A task is executable only when `blocked_dependencies` is
empty. When `dependency_artifacts` is non-empty, read every supplied dependency
attempt and both of its confirmation reviews, and cite their artifact IDs when
using them. Do not infer, recreate, or strengthen a dependency whose verified
artifacts are absent.

Campaign proof turns always receive mathematical working context: a primary file
and usually an extended file. Before drafting, you **must** read the primary
file end-to-end (use your read tool on the path listed in the execution
contract). Prefer the primary file; use the extended file only for overflow.
Neither is a substitute for proof:

- Established facts may be used directly.
- Candidate ideas must be proved independently before they carry any weight. A
  row marked as carried from a superseded packet is a candidate, whatever it
  says about itself.
- Mathematical constraints record routes already shown not to work. They may
  appear in the primary file or the extended file; constraints in either file
  still bind. Do not walk them again, and do not present one as new.
- Frontier obligations / dependencies to resolve are open mathematical gaps, not
  proved inputs. Aim your theorem at advancing those, not re-deriving settled
  constraints.
- Reusable computations are pinned by SHA-256; a finite computation can motivate
  a claim but never establishes a universal one.

State one exact theorem. Separate proved steps, source-backed inputs, computational
hypotheses, and gaps. Finite experiments cannot close a proof. Address the applicable
failed routes listed by the task; do not silently reuse them. A counterexample lane
must show survival in the exact target, not merely locate non-Tate geometry.

If genuinely new evidence reopens a blocked route, record it in `new_inputs` with
the canonical `route`, a nonempty `evidence` explanation, and
`evidence_claim_ids` naming source-verified or cross-checked claims already admitted
through the research gate. A free-form citation or renamed method does not reopen a
blocked route.

Return exactly one JSON artifact.
