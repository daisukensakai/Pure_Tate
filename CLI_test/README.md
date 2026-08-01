# CLI streaming experiments

This directory is an isolated compatibility lab for model CLIs. Nothing here is
loaded by the Pure Tate harness.

## Grok 4.5 worker pool (max 4)

Hard-capped Grok 4.5 helpers that parent agents can dispatch via MCP:

| File | Role |
|------|------|
| `grok_worker_pool.py` | Pool + hard caps (`max_concurrent=4`, `max_total=4`) |
| `grok_worker_mcp_sdk.py` | Official MCP SDK server for engine attachment |
| `grok_worker_mcp.py` | Minimal hand-rolled MCP (unit/debug) |
| `run_grok_worker_probes.py` | Offline + live probes |
| `GROK_WORKER_FINDINGS.md` | Gate results and harness recommendations |

```bash
python3 CLI_test/run_grok_worker_probes.py --offline
python3 CLI_test/run_grok_worker_probes.py --live
```

Results land under `results/grok_workers/`. **Do not** put `spawn_subagent` in
Grok `--tools` (allowlist collapse). Prefer MCP workers; see findings for the
Grok `bypassPermissions` requirement.

## Web access experiment

`run_web_access_probes.py` checks whether Grok, Claude, Codex, and Gemini can
use web search when tools are enabled (math-style optional use included). See
`WEB_ACCESS_FINDINGS.md` and `results/web_access/`.

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
