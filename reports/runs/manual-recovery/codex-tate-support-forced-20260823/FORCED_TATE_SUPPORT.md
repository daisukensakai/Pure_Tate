# C66-TATE-SUPPORT forced complete resolution

This is a principal-investigator override of the ordinary campaign-mathematics
prompt. Keep the forced-turn contract below. The assigned target is the
subproblem `C66-TATE-SUPPORT`, not the campaign Hodge/Tate group RED-0001
and not `C66-TATE-ASSEMBLY`.

Prove or disprove the exact `C66-TATE-SUPPORT` theorem stated in `TASK.json` as
`exact_theorem`. Return a complete, gap-free argument that resolves
`C66-TATE-SUPPORT`: Tate type of the exact codimension-13 contribution
supported on the balanced evaluation-failure model `Z`.

Do not return a reduction, partial result, isolated missing lemma, "better
effort" summary, or explanation of why the problem is difficult. Do not leave
TATE-SUPPORT frontier obligations as `gap_markers`. In particular do not leave
the constant-coefficient corners (H-S)/(H-C), the remaining `S_6`-isotypics, or
the complementary non-simply-branched incidence as gaps. Keep working—using
both parallel Grok workers as needed—until the TATE-SUPPORT lemma is complete.

This lemma does **not** resolve the campaign exact target
`W_{-16}H^{BM}_{16}(M_{6,6};Q)`. Set `resolves_exact_target` to false. Do not
claim that the global kernel `K=ker(H^{16}(Mbar_{6,6};Q)->H^{16}(D;Q))` is
Z-supported Tate (FND-0168). Do not construct a closed embedding, Gysin map,
image, or support-exhaustion statement in `M_{6,6}` (that is
`C66-TATE-ASSEMBLY`). Respect FND-0164: compact-support Leray with
constructible coefficients does not inherit a top-weight vanishing proved only
for constant `Q`.

Public search may be used only for ordinary mathematical background or named
theorems, not to search a solution for this exact problem. Do not search the
public web to determine whether it is open, and do not answer that it is open.

Use the supplied primary-source background and any supplied mathematical working
context (primary and extended files). Prefer primary; constraints in either file
are hard stops—do not walk them again. Candidate ideas in working context must
be proved independently before use. Set `exact_problem_web_search_used` to false
to attest that you did not use the web to seek a solution of the exact theorem or
to decide openness.

The result must have `result_type` equal to `proof` or `disproof`, `status` equal
to `claimed_complete`, no gap markers, and the exact theorem statement from
`TASK.json`. Every structured claim must have status `proved`. Cite verified
dependency artifacts by ID when you use them.

Include:

```json
{
  "completion_attestation": {
    "resolves_exact_target": false,
    "no_undischarged_dependencies": true,
    "not_reduction_only": true,
    "no_problem_status_claim": true,
    "exact_problem_web_search_used": false
  }
}
```

If genuinely new evidence reopens a blocked route named in the packet, record the
canonical `route`, a nonempty `evidence` explanation, and `evidence_claim_ids`
naming source-verified or cross-checked claims already admitted through the research
gate. A free-form citation or renamed method does not reopen a blocked route.

Principal worker override (harness-enforced for this turn):

- You have two Grok worker identities. Dispatch both and let them run in
  parallel on distinct narrow TATE-SUPPORT sub-tasks (for example: constant-
  coefficient corners of the balanced 15-fold / universal curve versus the
  remaining `S_6`-isotypics under FND-0164).
- Each identity has a 256-turn continue budget. Treat that as unlimited for
  this session. Prefer spending turns over stopping short.
- You remain the mastermind. Workers read and extract; you prove and write
  the single final JSON artifact.

Return exactly one JSON proof artifact and no surrounding prose.
