# Validation repair (exact-string mismatch) findings

## Question

Can the harness feed validation feedback back into the same engine turn when
an artifact fails for **mechanical / exact-string** reasons, instead of ending
the turn and spending the artifact slot?

## Answer

**Yes.** Two layers:

1. **Free coerce** of harness-owned identity fields (id, engine, review
   identity, campaign review `theorem_statement`, finding-audit identity).
2. **One in-`run_task` repair call** when remaining failures are classified as
   mechanical, with a compact prompt that includes the previous JSON + error
   text. Same reserved output path; no second reservation.

Substantive failures (target contradictions, forced-proof incompleteness,
confirmed-review structure failures) are **not** retried.

## Offline probe results

```bash
python3 CLI_test/run_validation_retry_probes.py
```

Latest run: see `CLI_test/results/validation_retry/latest.txt`.

| Probe | Result |
|-------|--------|
| classifier | PASS |
| coerce_review_theorem | PASS |
| repair_prompt_shape | PASS |
| repair_loop (mock engine, missing field → repair) | PASS |
| no_retry_substantive (forced-proof incomplete) | PASS |

## Production hooks

| Piece | Location |
|-------|----------|
| Classifier / repair prompt / settings | `pure_tate/validation_repair.py` |
| Identity coerce | `pure_tate/agents.py` `_validate_artifact`, `_validate_finding_audit` |
| Repair loop | `pure_tate/agents.py` `run_task` |
| Unit tests | `tests/test_validation_repair.py` |

### Config (optional, in engines root JSON)

```json
"validation_repair": { "enabled": true, "retry_limit": 1 }
```

Defaults: enabled, limit 1 (capped at 2). Codex controller turns skip nested
repair (already multi-turn).

## Historical traces this would have changed

| Trace | Old outcome | New path |
|-------|-------------|----------|
| TRACE-0029 / TRACE-0030 | review hard-fail on paraphrased `theorem_statement` | **coerce** from task |
| TRACE-0022 | claims shape failure | mechanical → **one repair call** |
| Forced-proof incompleteness | substantive reject | **no repair** (unchanged) |

## Recommendations

- Keep repair limit at 1 in production; raise only if repair success rate is
  high and cost is acceptable.
- Do **not** coerce mathematics `theorem_statement` or contradictory `target`
  keys — those are authorial / mathematical content.
- Campaign-level same-engine retry for *new* slots remains a second line of
  defense after in-run repair is exhausted.
