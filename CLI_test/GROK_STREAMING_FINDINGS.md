# Grok 4.5 streaming-json findings

Date: 2026-07-31

## Probe results

- `basic`: exit 0, 45 valid JSONL events, stdout SHA-256
  `1d18aa7bc0b170daad3b597912d4d68fe10688dc2f4583e476c39d4ce61386aa`.
- `read_tool`: exit 0, 111 valid JSONL events, stdout SHA-256
  `a54fa155494140f87276512bd21ee557d888ff25f75ac83c4cbf339e7ab2ee80`.
- Production adapter health probe: pass, stdout SHA-256
  `b7ce8e0e289f874f25b72ac73773f6a42a6c76534ee811738c18f5a0cb4d25a4`.

## Observed schema

Successful streams contain:

- `{"type":"thought","data":"..."}` token deltas;
- `{"type":"text","data":"..."}` token deltas;
- one terminal `{"type":"end", ...}` event with `stopReason`, usage, cost,
  session, and request metadata.

Authentication failures contain:

- `{"type":"error","message":"..."}`.

The read-only tool probe did not expose separate tool-call or tool-result events.
It emitted text before the requested JSON object, so concatenated `text` deltas
must be passed through the existing largest-object extractor.

## Integration boundary

- Production parsing uses only concatenated `text` deltas.
- `thought` deltas are excluded from proof traces and trace-miner inputs.
- `text`, `end`, and `error` events are retained as the observable trace.
- The former single-result Grok envelope remains supported as a backward
  compatibility fallback for historical traces.
- Gemini settings and parsing were not changed.

