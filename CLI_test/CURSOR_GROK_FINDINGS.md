# Cursor Grok 4.5 Agent CLI findings

Date: 2026-08-10

Isolated lab for billing **Cursor** Grok 4.5 via the headless Agent CLI when the
xAI `grok` binary is out of credits. Nothing here is loaded by the Pure Tate
harness.

## Probe results

Run dir: `CLI_test/results/cursor_grok/20260810T015914Z/`

| Probe | Format | Exit | Elapsed | Init model | Notes |
|-------|--------|------|---------|------------|-------|
| `basic` | `stream-json` | 0 | ~21s | Cursor Grok 4.5 | Exact JSON in `result` |
| `read_tool` | `stream-json` | 0 | ~25s | Cursor Grok 4.5 | Read marker + latex recovered; extra tool calls |
| `json_format` | `json` | 0 | ~15s | (no init event) | Single terminal `result` object |

Requested slug: `cursor-grok-4.5-high`. Stream `system/init.model` displays as
`Cursor Grok 4.5` (not the slug). No silent fallback to another family observed.

Binary resolved: `/Users/ken/.local/bin/cursor-agent`.

## Working argv

```bash
cursor-agent -p --trust --mode ask \
  --output-format stream-json \
  --model cursor-grok-4.5-high \
  --workspace /path/to/Pure_Tate \
  "<prompt>"
```

For a single final envelope (no NDJSON):

```bash
cursor-agent -p --trust --mode ask \
  --output-format json \
  --model cursor-grok-4.5-high \
  --workspace /path/to/Pure_Tate \
  "<prompt>"
```

Auth: process env `CURSOR_API_KEY` only (never argv). Init events report
`apiKeySource: "env"`.

## Auth quirks

- `cursor-agent status` / `about` still say **Not logged in** when only the API
  key is set. That does **not** mean the key is invalid—`models` and live runs
  succeed.
- Non-login agent shells often lack `CURSOR_API_KEY` even when `~/.zshrc`
  exports it. Prefer `zsh -lic 'python3 CLI_test/run_cursor_grok_probes.py'`.
- `cursor-agent --list-models` / `models` lists slugs including:
  - `cursor-grok-4.5-high` (default for this lab)
  - `cursor-grok-4.5-medium` / `cursor-grok-4.5-low`
  - matching `*-fast` variants

Do **not** pass xAI’s `grok-4.5` slug to Cursor Agent; that is a different
provider (`grok` binary + `~/.grok`).

## Stream / JSON schema vs xAI Grok

Cursor Agent `stream-json` is **not** compatible with the xAI
`streaming-json` parser in `pure_tate/agents.py`.

| Cursor Agent | xAI `grok` |
|--------------|------------|
| `system` / `init` (model display name) | (no equivalent) |
| `user` echo | (no equivalent) |
| `thinking` / `delta` + `completed` | `thought` / `data` |
| `assistant` with `message.content[].text` | `text` / `data` deltas |
| `tool_call` started/completed (`readToolCall`, …) | tools often invisible in stream |
| terminal `result` / `success` + `usage` | terminal `end` |

Parsing notes for a future adapter:

1. Prefer the terminal `result.result` string for the final answer.
2. Strip or ignore `thinking` events for proof traces (same role as xAI
   `thought`).
3. `result.result` may concatenate intermediate assistant chatter before the
   final JSON (seen on `read_tool`). Reuse the existing largest-JSON-object
   extractor.
4. Official docs claim thinking is suppressed in print mode; this run still
   emitted `thinking` deltas under `stream-json`. Treat them as present.
5. `--output-format json` returns one object with the same terminal `result`
   shape and is simpler for fire-and-forget task completion.

## Tools under `--mode ask`

`--mode ask` is read-only enough for these probes (no `--force` / `--yolo`).

Observed tool keys on `read_tool`:

- `readToolCall` (successfully read `CLI_test/read_fixture.txt`)
- `grepToolCall`
- `globToolCall`

The agent also browsed nearby lab files (`README.md`, the probe script) beyond
the single requested fixture. There is **no** Grok-style
`--tools` / `--disallowed-tools` allowlist on Cursor Agent CLI. Constraint is
mode-based (`ask` / `plan`) plus omitting `--force`, not a fine-grained tool
ACL.

**Web fetch:** ask mode alone rejects `WebFetch` / `WebSearch` as
**User Rejected** in headless print mode. When workers/parents need live web,
keep `--mode ask` and add `--force` (see `CURSOR_WEB_FINDINGS.md`). Do not
enable `--force` for no-web workers unless intentional.

Shell / write were not exercised under ask without force; do not drop ask mode
for harness-like read-only tasks unless intentional.

## Credit / error signatures (for later failover)

Not exhaustively probed (key had quota). Practical detection points:

- Non-zero exit + stderr text (no well-formed JSON on `--output-format json`
  failure, per Cursor docs).
- Missing/invalid key: fail before spawn if `CURSOR_API_KEY` unset; otherwise
  expect auth-style stderr / non-zero exit.
- Stream without a terminal `result` / `success`, or `is_error: true`.
- Init `model` not containing `Grok` / not matching the requested Cursor Grok
  family → treat as wrong-model / silent fallback risk.

xAI credit exhaustion remains on the `grok` binary path; Cursor usage is a
separate pool behind this CLI.

## Harness integration (landed 2026-08-10)

Implemented in the Pure Tate harness (not only this lab):

- Parent engine id **`cursor-grok`** (`family: cursor`, binary `cursor-agent`,
  model `cursor-grok-4.5-high`) with Claude-compatible stream extract and
  thinking quarantine.
- Default `prover_rotation` / `escalation_order` use `cursor-grok` in place of
  xAI `grok`; the `grok` engine entry remains for manual `--engine grok`.
- Shared worker pool default backend is **`cursor`**
  (`grok_worker_backend` / `GROK_WORKER_BACKEND`). Claude, Codex, Qwen, and
  cursor-grok parents still call `dispatch_grok_worker` / `ask_grok`; workers
  spawn `cursor-agent --mode ask --output-format json`, and add `--force`
  when `allow_web` is true (required for WebFetch; see
  `CURSOR_WEB_FINDINGS.md`).
- Auth: `CURSOR_API_KEY` (never on argv). Runtime gate mirrors Qwen’s API-key
  check.

## Earlier recommendation (superseded by integration)

Prefer a **separate engine id** (e.g. `cursor-grok`) over transparent failover
inside `grok`:

- Different binary, auth, argv, stream schema, and tool control surface.
- Model slug differs (`cursor-grok-4.5-high` vs `grok-4.5`).
- Mixing them under one family would force dual parsers and dual health checks
  behind one name.

## How to re-run

```bash
zsh -lic 'python3 CLI_test/run_cursor_grok_probes.py'
zsh -lic 'python3 CLI_test/run_cursor_grok_probes.py --only basic'
```

Results land under `CLI_test/results/cursor_grok/<timestamp>/`;
`CLI_test/results/cursor_grok/latest.txt` points at the newest run.
