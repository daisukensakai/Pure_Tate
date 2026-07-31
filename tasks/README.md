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
`--review-engines` act as allowlists while preserving ladder order. Gemini is
available for mathematics and review (`web_access: false`); research still requires
a web-enabled engine.

## Grok headless policy

Grok uses native snake-case tool ids, not Claude-compatible names. The current
headless adapter permits only `read_file`, `grep`, and `list_dir`; it excludes writes,
terminal commands, and web tools. Grok must return the artifact in its final message,
after which the harness validates and writes it.

Do not add an unrecognized tool id to `--tools`: current Grok releases may respond by
keeping the full toolset, which reintroduces headless permission cancellation when the
model later requests `write` or `run_terminal_command`.

## Gemini headless policy

Gemini runs with `--approval-mode plan` and `--skip-trust`, returning JSON via
`-o json`. Keep it read-only; the harness unwraps a top-level `response` envelope when
present.
