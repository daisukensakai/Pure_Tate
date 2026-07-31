# Mathematics phase

Stage 2 is unlocked: `RED-0001` is `cross_checked`.

Create independent attempts under `proof/attempts/` using `ATTEMPT_TEMPLATE.json`.
Do not overwrite competing attempts. Reviews belong under `proof/reviews/` and use
`REVIEW_TEMPLATE.json`.

A `verified` attempt requires:

- no gap markers;
- every supporting research claim at least `source_verified`;
- two independent confirmations from different engines;
- a strongest attack in every review.

Revision-1 artifacts `ATT-0001`–`ATT-0008` and their reviews are immutable historical
evidence. `proof/migrations/context-v2.json` records their byte hashes and marks them
`stale_context` under `TARGET-DUALITY-0001`; they cannot complete revision-2 cells.
New attempt IDs begin at `ATT-0009`, and new review IDs begin at `REV-0016`.

Only `corroborated` and `mechanically_verified` rows from `proof/findings.jsonl` enter
future packets. Single-review conclusions remain `candidate`.

The initial approach families are listed in `prompts/MATHEMATICS.md`.

```bash
python3 -m pure_tate packet --claim RED-0001
python3 -m pure_tate tasks --phase mathematics --write
python3 -m pure_tate agent-run \
  --manifest tasks/generated/mathematics.json \
  --task-id TASK-M-0001 \
  --engine grok \
  --output proof/attempts/ATT-0009.json
```
