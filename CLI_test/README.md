# CLI streaming experiments

This directory is an isolated compatibility lab for model CLIs. Nothing here is
loaded by the Pure Tate harness.

## Grok streaming experiment

`run_grok_streaming_tests.py` runs two bounded, read-only probes:

1. `basic`: no tools; returns a small structured JSON object containing LaTeX.
2. `read_tool`: permits only `read_file`; reads `read_fixture.txt` and returns
   its marker in structured JSON.

Every probe stores:

- exact argv with the prompt replaced by its SHA-256;
- raw stdout JSONL;
- raw stderr;
- exit code and elapsed time;
- SHA-256 hashes;
- a structural summary of the observed event stream.

No production adapter is changed based on an undocumented assumption. A Grok
stream parser may be integrated only after these raw fixtures pass deterministic
replay tests.

Run:

```bash
python3 CLI_test/run_grok_streaming_tests.py
```

## Gemini 503 experiment

`run_gemini_503_probe.py` compares the configured `gemini-3.5-flash` route
with a `gemini-3-flash-preview` control using both a direct API request and the
headless CLI's `stream-json` mode. It captures stderr retries incrementally,
stops the process group after three 503 attempts, and requires a genuine
assistant message plus a terminal success event.

Run from this directory:

```bash
python3 run_gemini_503_probe.py
```

See `GEMINI_503_FINDINGS.md` for the current diagnosis. Every execution is
preserved below `results/gemini_503/<timestamp>/`.
