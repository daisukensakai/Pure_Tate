# Exact theorem proof or disproof

Prove or disprove the exact theorem stated in the supplied campaign packet.
Return a complete, gap-free argument resolving the exact target.

Do not return a reduction, partial result, isolated missing lemma, "better
effort" summary, or explanation of why the problem is difficult. Public search
may be used only for ordinary mathematical background or named theorems, not to
search a solution for this exact problem. Do not search the public web to
determine whether it is open, and do not answer that it is open.

Use the supplied primary-source background and any supplied mathematical working
context. Candidate ideas in working context must be proved independently. Set
`exact_problem_web_search_used` to false to attest that you did not use the web
to seek a solution of the exact theorem or to decide openness.

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

If genuinely new evidence reopens a blocked route named in the packet, record the
canonical `route`, a nonempty `evidence` explanation, and `evidence_claim_ids`
naming source-verified or cross-checked claims already admitted through the research
gate. A free-form citation or renamed method does not reopen a blocked route.

Return exactly one JSON proof artifact and no surrounding prose.
