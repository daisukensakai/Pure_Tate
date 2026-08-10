# Effort probes: Claude Max + Codex Sol Extra High

**Run:** `CLI_test/results/effort/20260803T133354383420Z`  
**Command:** `python3 CLI_test/run_effort_probes.py --timeout 180`  
**Verdict: GO for harness integration**

## Targets

| Engine | Model | Desired | CLI mapping |
|--------|-------|---------|-------------|
| Claude | `claude-opus-5` | Max | `--effort max` |
| Codex  | `gpt-5.6-sol` | Extra High | `-c model_reasoning_effort="xhigh"` |

## Results

### Claude Max
- **Status:** `pass_with_parse_warning` (exit 0; stream JSON parse heuristic missed the final object)
- **Elapsed:** ~3.7s
- **Evidence:**
  - Argv includes `--model claude-opus-5` and `--effort max`
  - Stream init reports `model: claude-opus-5`, `permissionMode: default`
  - Assistant text body was `{"probe": "effort", "ok": true, "answer": 2, "effort_hint": "unknown"}` (flag accepted; model does not always self-report effort)
  - Empty stderr; `is_error: false`, `stop_reason: end_turn`
- **Gate:** flag accepted by Claude Code 2.1.218 without error → safe to wire into harness.

### Codex Sol Extra High (`xhigh`)
- **Status:** `pass` (exit 0)
- **Elapsed:** ~30.3s
- **Evidence:**
  - Argv includes `-m gpt-5.6-sol` and `-c model_reasoning_effort="xhigh"`
  - Last message: `{"probe":"1+1","ok":true,"answer":2,"effort_hint":"xhigh"}`
  - Overrides user `~/.codex/config.toml` default (`model_reasoning_effort = "high"`) for this process
- **Noise:** models-manager timeout errors on stderr; non-fatal.

## Integration recommendation

1. Set `engines.claude.effort = "max"` and `effort_audit = "high"` in
   `data/engines.json`.
2. Set `engines.codex.model_reasoning_effort = "xhigh"` and
   `model_reasoning_effort_audit = "high"`.
3. In `pure_tate/agents.py` `_engine_argv`, emit proof effort for
   mathematics / forced-proof / standard-fallback, and audit effort for
   review / finding-audit / novelty / research / micro-research /
   trace-mining. Claude CLI has no `auto` effort level (`low|medium|high|xhigh|max`).

Do **not** use Codex `ultra` unless multi-agent is intentionally requested.

## Reproduce

```bash
python3 CLI_test/run_effort_probes.py
python3 CLI_test/run_effort_probes.py --engines claude
python3 CLI_test/run_effort_probes.py --engines codex --timeout 240
```
