# Exact theorem proof or disproof

Prove or disprove the exact theorem stated in the supplied campaign packet.
Return a complete, gap-free argument resolving the exact target.

Do not return only a reduction, a partial result, an isolated lemma, a conditional
route, a summary of effort, an explanation of difficulty, or a statement about
whether the problem is open. Public-web solution search is not part of this task.
Use the supplied primary-source background and any supplied mathematical working
context. Candidate ideas in working context must be proved independently.

The result must have `result_type` equal to `proof` or `disproof`, `status` equal
to `claimed_complete`, no gap markers, and the exact theorem statement from the
packet. Every structured claim must have status `proved`.

Include:

```json
{
  "completion_attestation": {
    "resolves_exact_target": true,
    "no_undischarged_dependencies": true,
    "not_reduction_only": true,
    "no_problem_status_claim": true,
    "exact_problem_web_search_used": false
  }
}
```

Return exactly one JSON proof artifact and no surrounding prose.
