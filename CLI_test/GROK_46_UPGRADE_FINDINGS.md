# Grok 4.6 upgrade gate

Date: 2026-08-13

## Cursor Agent: pass

Requested model: `cursor-grok-4.6-high`. The stream initialization identified
the model as `Cursor Grok 4.6 High`.

| Gate | Result | Evidence |
|---|---|---|
| Basic stream JSON and model identity | pass | `results/cursor_grok/20260813T102242Z/` |
| Read-only file tool and fixture marker | pass | `results/cursor_grok/20260813T105600Z/` |
| Single JSON result envelope | pass | `results/cursor_grok/20260813T110305Z/` |
| Web fetch with `--mode ask --force` | pass | `results/cursor_web/20260813T110649Z/` |

The first combined run passed `basic` and then stalled before the read-tool
probe completed. Re-running the remaining gates independently passed, so no
schema, tool-use, or web compatibility regression was observed.

Harness decision: upgrade the `cursor-grok` parent and the default Cursor Grok
worker model to `cursor-grok-4.6-high` without changing routing, permissions,
effort tier, or timeouts.

## xAI Grok Build: pass after balance restoration

`grok models` listed `grok-4.6` as the default and retained `grok-4.5` as an
available model. The first attempt stopped before inference with HTTP 402,
`Grok Build usage balance exhausted`:

- `results/grok_streaming/20260813T110845Z/basic.*`
- `results/grok_streaming/20260813T110845Z/read_tool.*`

After usage was restored, the complete xAI gate passed:

| Gate | Result | Evidence |
|---|---|---|
| Streaming JSON and reported `grok-4.6-build` usage | pass | `results/grok_streaming/20260813T114252Z/` |
| Read-only `read_file` call and fixture marker | pass | `results/grok_streaming/20260813T114252Z/` |
| Worker argv selects `grok-4.6` | pass | `results/grok_workers/20260813T114346712618Z/` |
| Production worker smoke | pass | `results/grok_workers/20260813T114823999413Z/` |
| Strict allowlist safety | pass | `results/grok_workers/20260813T114823999413Z/` |

Harness decision: upgrade the direct xAI engine and xAI worker default to
`grok-4.6`. Keep the Cursor parent and worker path on `cursor-grok-4.6-high`.
