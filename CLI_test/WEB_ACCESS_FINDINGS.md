# Web access CLI probes — findings

**Run (rescored):** `CLI_test/results/web_access/20260801T032058126793Z`  
**Probe runner:** `CLI_test/run_web_access_probes.py`  
**Date:** 2026-08-01

## Verdicts

| Engine | Smoke (must search) | Optional math | Verdict |
|--------|---------------------|---------------|---------|
| Grok (`grok-4.5`) | pass (answer 2, tool used) | pass (answer 10, no web) | **pass** |
| Claude (`claude-opus-5`) | pass | pass | **pass** |
| Codex (`gpt-5.6-sol`, read-only sandbox) | pass (stream `web_search` item) | n/a | **pass** |
| Gemini (`gemini-3.5-flash`) | pass in **both** `plan` and `yolo` via `google_web_search` | n/a | **pass** |

Initial classifier failures were **parser issues** (stream deltas / nested envelopes), not missing web capability. After engine-specific reassembly, all four engines completed the helium web-search smoke correctly.

## Working argv patterns

### Grok
- Include `web_search,web_fetch` in `--tools`
- Do **not** pass `--disable-web-search`
- Keep write/shell denied; `dontAsk` + `--always-approve` OK for headless
- Stream: reassemble `{"type":"text","data":...}` chunks for final JSON

### Claude
- `--allowedTools Read Grep Glob WebSearch WebFetch`
- Stream: final `type=result` envelope field `result` holds JSON string

### Codex
- Existing harness `codex exec --sandbox read-only ... --json` is enough
- Web search appears as stream items `type: web_search`; final answer in `agent_message`
- No extra web flag required in this probe

### Gemini
- Harness-style `--approval-mode plan` **can** invoke `google_web_search` (not blocked by plan mode in this probe)
- `--approval-mode yolo` also works
- Stream: assistant `message` content may arrive as deltas; reassemble before JSON parse

## Harness recommendations

1. **Enable web tools on all agent phases** for Grok and Claude (math, review, trace-mining, research family)—not only `WEB_PHASES`.
2. **Codex / Gemini:** no argv change required for web availability beyond current headless shapes; declare web on math/review if we want inventory honesty (optional; Codex/Gemini research remains non-web-declared historically).
3. Keep **research/finding-audit/novelty** live capability attestation fail-closed.
4. Forced-proof: enable tools; keep soft `exact_problem_web_search_used: false` (exact-problem search ban deferred).
5. Do not require new math-phase attestation for every turn.

## Deferred

- Enforcement that agents must not web-search the *exact* campaign theorem (only supporting math).
