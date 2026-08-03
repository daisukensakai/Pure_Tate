# Qwen hang diagnosis and streaming fix

Diagnosed on 2026-08-03; streaming fix landed the same day in the harness
(`pure_tate/qwen_worker.py`, agent/paired/health extraction).

## Historical hang shapes

| Run | Failure | Cause |
|-----|---------|-------|
| `RUN-C66-001-20260803T062926…` | inactivity 3600s, empty stderr | Silent blocking `urlopen` |
| `RUN-C66-001-20260802T233654…` | client read timeout | Long wait, then urllib timeout |
| `RUN-C66-001-20260802T133031…` | HTTP 504 `ResponseTimeout` ~300s | Provider stream idle limit |

## Root cause (pre-fix)

`qwen_worker` used non-streaming HTTP and wrote **nothing** until the full task
finished. With `inactivity_timeout_seconds=3600` and client waits up to 10800s,
a slow/stuck call was killed as a hang with no partial stdout.

## Fix

1. **SSE streaming** for Chat Completions and Responses (`stream: true`).
2. **JSONL stdout protocol** (Grok-shaped): `stage`, `heartbeat`, `thought`,
   `text`, `tool_call`, `tool_result`, `error`, `end` — flushed per event.
3. **First-byte heartbeats** every 15s until the first SSE payload.
4. **Harness extraction** via `_extract_qwen_stream` / `_qwen_observable_stream`
   (thoughts quarantined from proof traces).
5. Emergency: `QWEN_STREAM=0` forces non-stream requests (still emits one-shot
   text events when the response returns).

## Live verification (post-fix)

Worker suite after the fix:

- First stdout activity at **~0.1s** (stage event), not only at completion.
- Continuous text/thought events during generation.
- Direct worker invoke: 33 JSONL lines including stage, thought, tool_call,
  tool_result, text, end.

Probe:

```bash
python3 CLI_test/run_qwen_hang_probe.py --suite worker --wall 180
```

## Remaining provider risks (not local hangs)

- HTTP 504 `ResponseTimeout` (~300s server stream idle) can still fail a long
  quiet stage; streaming shortens false inactivity kills but cannot invent
  provider progress.
- Token-plan quota 429 remains an operational limit.

## Files

- `pure_tate/qwen_worker.py` — streaming transport + emits
- `pure_tate/agents.py` — stream extract / observable filter
- `pure_tate/paired.py`, `health.py`, `capabilities.py` — Qwen stream parse
- `tests/test_qwen_worker.py`, `tests/test_agents.py`
- `CLI_test/run_qwen_hang_probe.py`
