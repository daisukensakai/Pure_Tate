# Grok 4.5 worker pool findings (CLI_test)

**Latest controller Codex gate run:** `CLI_test/results/grok_workers/20260801T084319677265Z`
**Probe runner:** `CLI_test/run_grok_worker_probes.py`  
**Date:** 2026-08-01  
**Harness status:** integrated in `pure_tate/grok_workers.py` + `agents.py`
(see `data/engines.json` `max_grok_workers` / `grok_workers_enabled`)

## Goal

Claude and Grok may use their existing direct MCP dispatch. Codex instead uses
a controller-mediated, sequential path: safe read-only Codex decisions request
at most four Grok workers, and the harness dispatches one at a time.

## Verdicts

| Probe | Status | Notes |
|-------|--------|-------|
| `pool_unit_cap` | **pass** | Hard concurrent=4 and total=4 in-process |
| `mcp_unit_roundtrip` | **pass** | Hand-rolled JSON-RPC unit path |
| `worker_argv_shape` | **pass** | Workers: read-only tools, `--no-subagents`, `grok-4.5` |
| `worker_smoke` | **pass** (prior run) | Live single worker returns marker |
| `worker_parallel_4` | **pass** (prior run) | 4 live workers complete; 5th `budget_exhausted` |
| `allowlist_safety` | **pass** | Baseline allowlist safe; `spawn_subagent` in `--tools` **unsafe** |
| `native_spawn_optional` | **skip** | Native spawn via `--tools` collapses allowlist |
| `mcp_claude` | **pass** | Real worker artifacts + `CLAUDE-MCP` |
| `mcp_grok` | **pass** | Real worker artifacts; allowlist stays shell-free |
| `mcp_codex` | **pass** | Dedicated headless probe dispatches one real worker with a hard artifact gate |
| `mcp_codex_restricted` | **expected fail** | Codex emits the call but cancels it in its headless approval layer |
| `controller_codex` | **pass** | Safe Codex chose worker 2 after receiving worker 1; both outcomes and final marker are durable |
| `mcp_gemini` | **skip** | No safe session-scoped MCP inject without project/user settings |

**Stage B (harness) gate:** offline hard-cap + allowlist_safety + worker_smoke +
`mcp_claude` + `mcp_grok` + `mcp_codex` are green. Gemini needs follow-up.

## Architecture that works

```
Parent (Claude | Grok)
   │  MCP tools (dispatch / await / list)
   ▼
uv run --with mcp python CLI_test/grok_worker_mcp_sdk.py
   │  hard max_concurrent=4, max_total=4
   ▼
grok -p … -m grok-4.5   (read-only --tools, --no-subagents)
```

```
Codex (read-only, approval_policy=never, no MCP attachment)
   │  structured dispatch/finalize decision
   ▼
Harness controller (one live worker; 4 logical rounds, one retry each)
   ▼
Grok worker → durable outcome → next Codex decision or final Codex artifact
```

### Components (CLI_test only)

| File | Role |
|------|------|
| `grok_worker_pool.py` | Pool logic, hard caps, worker subprocess |
| `grok_worker_mcp.py` | Minimal hand-rolled MCP (unit tests / debug) |
| `grok_worker_mcp_sdk.py` | Official `mcp` SDK server (engine attachment) |
| `run_grok_worker_probes.py` | Offline + live probe runner |

Workers always:

- model `grok-4.5`
- `--tools read_file,grep,list_dir` (+ web only if configured)
- deny write/shell/open_page
- `--no-subagents` (no nested workers)

## Critical safety findings

### 1. Never put `spawn_subagent` in Grok `--tools`

Harness-safe baseline:

```
--tools read_file,grep,list_dir
```

exposes only those plus always-on MCP meta tools (`search_tool`, `use_tool`).

Adding `spawn_subagent` to `--tools` **collapses the allowlist**: shell
(`run_terminal_command`) reappears, and `spawn_subagent` itself often does
**not** appear. Native subagents are therefore **not** the harness path.

### 2. Grok MCP requires `bypassPermissions` (not `dontAsk`)

Under harness-like `--permission-mode dontAsk --always-approve`, Grok can
`search_tool` the MCP catalog, but `use_tool` ends `failed` and the turn is
`cancelled`.

Under `--permission-mode bypassPermissions` with the **same** strict
`--tools` allowlist, MCP `use_tool` succeeds and workers run. Shell/write stay
absent from `available_commands`.

**Harness implication:** Grok worker-enabled runs should switch permission mode
to `bypassPermissions` (or `auto`) while keeping the read-only tool allowlist.
Do not rely on `dontAsk` for MCP.

### 3. Official MCP SDK required for engine attach

Hand-rolled Content-Length JSON-RPC completed `initialize` but Grok/Claude did
not finish the session (protocol `2025-06-18` / newer).  
`uv run --with mcp python CLI_test/grok_worker_mcp_sdk.py` works end-to-end.

### 4. Session-scoped config only

- **Claude:** ephemeral `--mcp-config` JSON + `--strict-mcp-config`
- **Grok:** ephemeral `GROK_HOME` with linked `auth.json` + temp `config.toml`
- **Never** wrote `~/.grok/config.toml` or project harness settings

## Hard cap semantics

| Cap | Value | Enforcement |
|-----|-------|-------------|
| `max_concurrent` | 4 | Pool rejects with `pool_full` |
| `max_total` | 4 | Pool rejects with `budget_exhausted` |

Live `worker_parallel_4` observed 4 completions and a 5th
`budget_exhausted` (total budget hits before concurrent when all four
dispatches are admitted).

## Recommended harness argv (when Phase 2 is approved)

### Grok parent

- Keep `--tools read_file,grep,list_dir,search_tool,use_tool` (+ web if phase allows)
- Keep write/shell in `--disallowed-tools`
- Change `--permission-mode` from `dontAsk` → `bypassPermissions` when workers enabled
- Attach MCP via session-scoped config (temp `GROK_HOME` or equivalent), not user config
- MCP command: `uv run --with mcp python <repo>/CLI_test/grok_worker_mcp_sdk.py` (or vendored copy under `pure_tate/`)

### Claude parent

- `--mcp-config` ephemeral JSON for `grok-workers`
- `--allowedTools` include `mcp__grok-workers__dispatch_grok_worker` (and await/list/stats)
- Keep `Edit`/`Write`/`Bash` disallowed
- `--permission-mode bypassPermissions` worked in probes

### Codex / Gemini

- Direct Codex MCP requires `--dangerously-bypass-approvals-and-sandbox` for a
  noninteractive dispatch; that remains a diagnostic-only CLI probe. Production
  Codex has no MCP server, remains `--sandbox read-only` with
  `approval_policy="never"`, and requests workers through the controller.
- Gemini needs a session-scoped MCP inject that does not rewrite user settings

## Prompt contract (for later harness)

- Workers are **optional** assistive helpers
- Parent still returns the **single durable JSON artifact**
- At most 4 workers total per parent task (pool enforces)

## Run

```bash
# Offline only (no API)
python3 CLI_test/run_grok_worker_probes.py --offline

# Live probes (API keys / CLI auth required)
python3 CLI_test/run_grok_worker_probes.py --live

# Diagnostic-only direct Codex MCP gate (uses bypass; not production)
python3 CLI_test/run_grok_worker_probes.py --live --only mcp_codex

# Expected-red diagnosis: headless read-only Codex cancels before server receipt
python3 CLI_test/run_grok_worker_probes.py --live --only mcp_codex_restricted

# Production-safe controller: Codex requests two sequential workers, then synthesizes
python3 CLI_test/run_grok_worker_probes.py --live --only controller_codex
```

Results: `CLI_test/results/grok_workers/<timestamp>/`  
Pointer: `CLI_test/results/grok_workers/latest.txt`

## Explicit non-actions

- No edits to user Grok config
- No enabling native `spawn_subagent` in production allowlists
- No permanent project MCP registration
