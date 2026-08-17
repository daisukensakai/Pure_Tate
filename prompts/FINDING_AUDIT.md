# Independent finding audit

Resolve the assigned finding against primary sources and cross-checked claims.
Search live literature when the task requires it. State its exact mathematical scope,
evidence class, contradictions, and whether it should remain candidate, be promoted,
be merged, or be retired. Return exactly one JSON artifact.

Before reading the general packet or findings backlog, inspect every supplied
originating attempt and review named by the assigned finding's
`source_attempt_ids` and `source_review_ids`. These are mandatory first reads.
Do not promote, retire, or retain an attempt-specific finding without checking
the exact contested passage in those artifacts.

Always provide `adjudicated_statement`: the exact statement that may enter future
proof packets if promoted. Include every hypothesis introduced by the audit and
apply any wording corrections discovered during review; never promote the original
candidate text unchanged when your audit narrows or corrects it.

`source_records` is only for independently retrieved public HTTP(S) sources.
Use one of the accepted source types: `journal`, `preprint`, `survey`,
`repository`, `author-page`, `citation-index`, `encyclopedia`, `reference`, or
`other-primary`. Do not put packet paths, attempt paths, review paths, `file:`
URLs, or other local evidence in `source_records`; inspect supplied originating
attempts and reviews directly and discuss that local evidence in
`contradiction_resolution`. Cite at least one genuinely public source and report
its fetched-content SHA-256.
