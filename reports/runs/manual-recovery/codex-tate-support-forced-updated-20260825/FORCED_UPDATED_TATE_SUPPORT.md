# C66-TATE-SUPPORT forced resolution after REV-0178

This is a principal-investigator forced turn for `C66-TATE-SUPPORT` only.  The
goal is to prove or disprove the exact theorem in `TASK.json` for the named
ATT-0120 target subquotient `T_Z`; it is not a request to prove `RED-0001` or
to assemble complementary terms.

Return a complete, gap-free `proof` or `disproof` artifact with
`status: claimed_complete`, no gap markers, and the exact theorem statement
from `TASK.json`.  Do not substitute cohomology of a family base, atlas,
product model, standalone support, or a source class whose image in `T` has
not been proved nonzero.

You must first read the supplied fresh evidence `ATT-0128` and `REV-0178`.
REV-0178 confirms the useful localization lemmas but identifies two hard
stops: the residual dimensions 9 through 16 are undischarged, and the
abelian-ninefold model cannot be represented as one affine stratum in the
peeling construction.  Do not repeat either defect.

Before finalizing, dispatch two controller-mediated Cursor-Grok workers in
parallel on distinct narrow, load-bearing checks. The controller uses the
configured Cursor backend only; workers are assistive and their reports are
not proof. Continue either worker as often as useful: forced-proof worker
rounds are unbounded until this task's overall timeout. Do not request xAI
Grok workers.

The target-interface fields must name the verified ATT-0120 interface and the
top-level `dependency_claim_ids` must include every ATT-0120 claim named in
`target_interface_reference.interface_claim_ids`.  The final artifact must
be mathematically honest: a conditional criterion or an explicitly open
antecedent cannot be presented as a resolution.  If no complete proof or
interface-surviving disproof is obtained, state that in the artifact rather
than manufacturing completion; the harness will reject a false completeness
claim.

Public search may be used only for ordinary background, never to determine
whether this exact problem is open.  Set `exact_problem_web_search_used` to
false.  Return exactly one JSON object and no surrounding prose.
