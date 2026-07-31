# Independent degree-16 reduction audit

Work in a clean context. Derive the residual list first. Only afterwards open
`research/RED-0001.statement.json` and compare your residual pairs to that
statement. Do not treat the global target conjecture as the audit target.

1. Verify the current publication/arXiv status of every load-bearing source.
2. Reconstruct the boundary exact-sequence induction used at degree 14.
3. Substitute degree 16 and enumerate every finite base pair from the stated inequalities.
4. Discharge cases only with source-verified theorems of matching scope.
5. Distinguish CKgP, tautological Chow, algebraic generation, and pure Hodge–Tate.
6. Compare your residual list with the `RED-0001` statement.
7. Record agreement or the exact discrepancy, with theorem/page locators.

Output rules:

- Return exactly one JSON object matching `research/audits/AUDIT_TEMPLATE.json`.
- No prose before or after the JSON object.
- `inferred_pairs` must be a list of `[g, n]` integer pairs, e.g. `[[3, 12], [5, 8]]`.
- `reviewer_engine` must be the engine id from `TASK.json` (for example `claude`).
- `verdict` is `agree` exactly when your residual list matches the `RED-0001`
  statement as the still-open finite obstruction; otherwise `disagree`.
- An open global conjecture is expected. Do not set `disagree` merely because
  degree 16 remains unresolved after the reduction.
- Do not promote `RED-0001` yourself; promotion is a separate harness step.
