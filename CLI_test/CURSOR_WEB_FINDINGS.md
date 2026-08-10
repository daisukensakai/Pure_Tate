# Cursor Agent web-fetch findings

Date: 2026-08-10

Isolated lab for why Cursor Grok workers reported **User Rejected** on
`WebFetch` / `WebSearch` during Pure Tate finding audits
(`SESS-06bf1f7a8279`).

## Incident

Claude parent `TASK-F-FND-0116` dispatched cursor workers with
`allow_web=true` / model `cursor-grok-4.5-high`. Worker results still said
live retrieval was blocked:

- `WebFetch` / `WebSearch`: **User Rejected**
- Shell HTTP download: **Rejected**

Harness argv at the time (always, ignoring `allow_web`):

```bash
cursor-agent -p --trust --mode ask --output-format json \
  --model cursor-grok-4.5-high --workspace <tmp> "<prompt>"
```

## Root cause

Cursor Agent CLI has **no** `--tools` allowlist. Approval is mode + force:

| Factor | Effect |
|--------|--------|
| `--mode ask` | Read-only Q&A (keeps writes blocked) |
| missing `--force` / `--yolo` | Network/web tool calls require approval → headless **User Rejected** |
| `--sandbox disabled` alone | Does **not** fix rejection |

`build_cursor_worker_argv` also ignored `allow_web` (xAI path honors it;
cursor path returned early).

## Probe matrix

Runner: `CLI_test/run_cursor_web_probes.py`  
Run: `CLI_test/results/cursor_web/20260810T024922Z/`  
Prompt: fetch `https://example.com` and quote **Example Domain**.

| Variant | Flags | Pass |
|---------|-------|------|
| `A_ask_noforce` | `--trust --mode ask` (old harness) | **no** (`FETCH_FAILED`) |
| `B_ask_force` | `--trust --mode ask --force` | **yes** |
| `C_ask_sandbox_disabled` | ask + `--sandbox disabled` | **no** |
| `D_print_force` | `--trust --force` (no ask) | **yes** |
| `E_print_force_sandbox_disabled` | force + sandbox disabled | **yes** |
| `F_print_only` | `--trust` only | **no** |
| `G_plan_force` | `--mode plan --force` | **yes** |

**Winners all include `--force`.** Sandbox alone does not matter. Ask without
force fails exactly like the production workers.

## Fix (harness)

When web is allowed, keep `--mode ask` and add `--force`:

```bash
cursor-agent -p --trust --mode ask --force --output-format json \
  --model cursor-grok-4.5-high --workspace <tmp> "<prompt>"
```

Applied in:

- `pure_tate/grok_workers.py` — `build_cursor_worker_argv(..., allow_web=)`
- `pure_tate/agents.py` — parent `family == "cursor"` when `phase_allows_web`

When web is **not** allowed, omit `--force` so network tools stay approval-blocked.

## How to re-run

```bash
zsh -lic 'python3 CLI_test/run_cursor_web_probes.py'
zsh -lic 'python3 CLI_test/run_cursor_web_probes.py --only A_ask_noforce --only B_ask_force'
```
