# C66-GEO-COMP wrap-up (not a forced proof)

This turn is a **session wrap-up**, not a forced complete resolution of
`C66-GEO-COMP`. The forced-turn contract is cancelled.

Write one campaign attempt JSON that records what this interrupted Claude
session actually established or usefully synthesized. Do not claim to have
closed GEO-COMP. Do not return `claimed_complete`. Do not empty `gap_markers`
unless that is honest.

Stay on the assigned subproblem `C66-GEO-COMP`. Do not resolve RED-0001.
Set `resolves_exact_target` to false. `result_type` is `lemma`. `status` will
be set by the harness from the content; write honest gaps and do not mark
unproved claims `proved`.

Public search may be used only for ordinary mathematical background. Set
`exact_problem_web_search_used` to false.

Prefer session memory and the two Grok worker reports already received on
the original turn (type-(ii) monodromy extraction; balanced base / component
count). Do not restart from zero. Do not re-read the packet or primary working
context end-to-end. Do not dispatch Grok workers.

Separate:

- facts already dual-confirmed in prior artifacts (cite ATT/REV/FND IDs; do
  not present them as new theorems of this wrap-up);
- useful progress, locators, or sharpened gap statements from this session;
- remaining GEO-COMP frontier (exact type-(ii) monodromy image; purely
  type-(ii) components; irreducibility of the balanced base; Aut/inertia and
  the map to `M_{6,6}`).

Return exactly one JSON object matching `proof/CAMPAIGN_ATTEMPT_TEMPLATE.json`
and no surrounding prose.
