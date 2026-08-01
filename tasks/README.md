# Task manifests

Task generation is phase-aware:

```bash
python3 -m pure_tate tasks --phase research --write
python3 -m pure_tate tasks --phase mathematics --write
python3 -m pure_tate tasks --phase review --write
```

Research tasks can always be generated. Mathematics tasks are refused until:

1. an independent `RAUD-*.json` audit agrees with the exact degree-16 case list;
2. every source and locator in that audit passes validation; and
3. `RED-0001` is explicitly promoted to `cross_checked`.

The generated JSON is an engine-neutral dispatch manifest. A task runner may give the
named prompt and inputs to any web-enabled research engine or reasoning engine, while
the resulting audit, attempt, or review remains a durable artifact in this repository.

The built-in `agent-run` adapter supports the engines declared in
`data/engines.json`. It constructs a temporary read-only context, captures a single JSON
result, checks its required fields and identifier, and writes only to the phase's
artifact directory.

Mathematics and review artifacts use schema version 2. Exact task linkage, context
revision, target dictionary, packet identity, and packet hash are mandatory. Use
`pure-tate board --write` for the 35-cell portfolio, `pure-tate next` for deterministic
selection, or `pure-tate drive` for bounded orchestration.

## Engine rotation and escalation

`data/engines.json` defines two ladders:

- `prover_rotation`: fresh first attempts cycle
  `grok → claude → grok → codex → grok → gemini`
- `escalation_order`: retries and reviewer conflict resolution walk
  `grok → gemini → codex → claude`

`drive` defaults to the full engine set. Optional `--prover-engines` /
`--review-engines` act as allowlists while preserving ladder order. Agent phases
(mathematics, review, forced-proof, trace-mining) expose web tools when the engine
supports them so models may look up supporting results; research still requires a
web-enabled, capability-attested engine. Gemini remains unattested for research.

## Grok headless policy

Grok uses native snake-case tool ids, not Claude-compatible names. The headless
adapter permits `read_file`, `grep`, `list_dir`, and on agent phases also
`web_search` / `web_fetch`; it excludes writes and terminal commands. Grok must
return the artifact in its final message, after which the harness validates and
writes it.

Do not add an unrecognized tool id to `--tools`: current Grok releases may respond by
keeping the full toolset, which reintroduces headless permission cancellation when the
model later requests `write` or `run_terminal_command`.

**Never** add `spawn_subagent` to Grok `--tools` — that collapses the allowlist and
reintroduces shell. Optional Grok 4.5 helpers use the MCP worker pool instead
(see below).

## Optional Grok 4.5 worker pool (max 4)

When `data/engines.json` has `grok_workers_enabled: true` (default) and
`max_grok_workers` ≤ 4, agent runs for Claude, Grok, and (best-effort) Codex
attach a session-scoped MCP server exposing:

- `dispatch_grok_worker` / `await_grok_worker` / `list_grok_workers` /
  `worker_pool_stats` / `cancel_grok_worker`

Hard caps: **4 concurrent** and **4 total** dispatches per parent task. Workers
are read-only `grok-4.5` processes with `--no-subagents`. The parent still owns
the durable JSON artifact.

Grok parents use `--permission-mode bypassPermissions` only when workers are
enabled (MCP `use_tool` fails under `dontAsk`); the read-only `--tools`
allowlist still denies write/shell. Config is session-scoped (temp dir /
ephemeral `GROK_HOME`); the harness never writes `~/.grok/config.toml`.

Disable with `"grok_workers_enabled": false` or `"max_grok_workers": 0`.
Gemini is not attached yet (no safe session MCP inject).

### Dispatch logs

Worker activity is written under `research/worker-dispatches/` (created on first
use). Temp task workspaces are deleted after each run; this folder is durable:

- `events.jsonl` — global append-only stream
- `sessions/<SESS-id>/session.json` — parent engine/task metadata
- `sessions/<SESS-id>/events.jsonl` — per-parent-session events
  (`session_open`, `dispatch`, `worker_started`, `worker_finished`,
  `dispatch_rejected`)
- `sessions/<SESS-id>/workers/` — durable worker stdout/stderr copies
- `latest.txt` — most recent session id

A `session_open` event is logged even when the parent never dispatches a worker,
so “available but unused” is auditable.

## Gemini headless policy

Gemini runs with `--approval-mode plan` and `--skip-trust`, returning JSON via
`-o json`. Keep it read-only; the harness unwraps a top-level `response` envelope when
present.
