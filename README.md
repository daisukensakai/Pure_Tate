# Pure Tate research program

This repository is a source-audited research and proof harness for the target

$$
H^{16}(\overline{\mathcal M}_{g,n};\mathbb Q)
\cong \mathbb Q(-8)^{\oplus b_{16}}
$$

for every stable pair $(g,n)$. It enforces a hard boundary between:

1. **Research:** versioned sources → atomic claims → dependency graph → a certified
   finite obstruction.
2. **Mathematics:** small dependency-closed proof packets → independent attempts →
   adversarial reviews.

The canonical data is Git-friendly JSON/JSONL under `data/`. Reports and proof packets are
generated artifacts.

## Quick start

```bash
python3 -m pure_tate all
python3 -m unittest discover -s tests -v
```

Useful commands:

```bash
python3 -m pure_tate validate
python3 -m pure_tate audit
python3 -m pure_tate cases --degree 16
python3 -m pure_tate replay --degree 14
python3 -m pure_tate obstruction
python3 -m pure_tate packet --claim RED-0001
python3 -m pure_tate proof-audit
python3 -m pure_tate research-audit
python3 -m pure_tate stage
python3 -m pure_tate board --write
python3 -m pure_tate next --phase mathematics
python3 -m pure_tate next --phase micro-research
python3 -m pure_tate tasks --phase research --write
python3 -m pure_tate tasks --phase micro-research --write
python3 -m pure_tate engines
python3 -m pure_tate capability-audit --engines claude grok
python3 -m pure_tate engine-health --engine qwen --live --level artifact
python3 -m pure_tate campaign-status --campaign C66-001 --write
python3 -m pure_tate next --campaign C66-001 --phase forced-proof
```

`TARGET.md` is the human-readable scope contract. `data/target.json` is its
machine-readable counterpart.

For a local literature corpus, fetch and extract a pinned arXiv version:

```bash
python3 -m pure_tate fetch-source SRC-0002
python3 -m pure_tate extract-source SRC-0002
python3 -m pure_tate corpus-search "Equation 6.1 Table 1"
python3 -m pure_tate corpus-audit
```

The initial seven-pair reduction is `cross_checked` after independent Claude and Grok
research audits (`RAUD-0001`, `RAUD-0002`). Stage 2 mathematics is unlocked.

## Agent execution

Task manifests can be run through a configured headless engine. Each turn gets an
isolated, read-only workspace containing only phase-approved inputs.
High-tier engines run at elevated reasoning depth (validated in
`CLI_test/EFFORT_FINDINGS.md`): Claude uses `--effort max` on `claude-opus-5`,
and Codex uses `model_reasoning_effort=xhigh` (Extra High) on `gpt-5.6-sol`.


```bash
python3 -m pure_tate agent-run \
  --manifest tasks/generated/research.json \
  --task-id TASK-R-0001 \
  --engine claude \
  --output research/audits/RAUD-0001.json
```

Engine capabilities are phase-specific. Research dispatch checks that the generated
command really permits both web search and fetch and, for current live-web tasks,
requires a durable passing capability attestation. A declared capability alone is
not sufficient.
Mathematics receives only the dependency-closed packet; review receives only one proof
attempt, its exact packet, and the adversarial rubric. Agent phases (including
mathematics, review, and forced-proof) expose web tools so engines may look up
supporting results; research / finding-audit / novelty still require live web
capability attestation. Forced-proof may use public search only for ordinary
mathematical background or named theorems, not to seek a solution of the exact
problem or to decide openness (`exact_problem_web_search_used: false`). Revision-2 tasks pin the
Borel–Moore target, its dimension-dependent ordinary-cohomology realization, and the
packet SHA-256. The runner rejects missing, stale, or hash-mismatched packets before
invoking an engine.

The light driver uses the configured rotation and escalation ladders in
`data/engines.json`, but every run must explicitly name both the prover and reviewer
engine pools. This makes a paid run impossible through an implicit default:

```bash
python3 -m pure_tate drive \
  --steps 5 \
  --prover-engines grok claude \
  --review-engines claude codex \
  --dry-run
```

Fresh mathematics follows `prover_rotation` (Grok → Opus → Grok → GPT → Grok →
Qwen). Retries move forward within one proof chain: Grok → Qwen → the
chain-assigned Opus/GPT pair. Consecutive chains alternate Opus → GPT and
GPT → Opus; an unavailable high-tier slot remains pending rather than repeating
the available model. Reviews use the same base ladder while skipping the prover
and already-used reviewers.

Remove `--dry-run` only when the displayed portfolio is intended. Pending current
reviews run before new mathematics. A `proposed` attempt receives one independent
triage review. An `incomplete` or `refuted` verdict closes that review cycle. Only an
attempt that declares `claimed_complete` and passes its first review receives a second
confirmation pass; the two confirmations must use engines distinct from each other
and from the prover.

Live tasks default to a one-hour cap. Individual Grok helper workers are
separately capped at 20 minutes.

Mathematics attempts can isolate a narrow literature obstruction without reopening
the Stage-1 reduction. `all` writes those tasks to
`tasks/generated/micro-research.json`; run them individually with a web-enabled
engine:

```bash
python3 -m pure_tate agent-run \
  --manifest tasks/generated/micro-research.json \
  --task-id TASK-Q-0001 \
  --engine grok \
  --output research/followups/RF-0001.json
```

Reviewer findings stay `candidate` even when their machine keys match. Promotion,
retirement, and duplicate merging are explicit, audited actions:

```bash
python3 -m pure_tate finding-adjudicate \
  --finding FND-0014 \
  --action corroborate \
  --reason "Independent locator-level reviews establish the same obstruction."
```

## Focused `(6,6)` novelty campaign

Campaign `C66-001` keeps target context revision 2 and uses campaign revision 4.
Its packet focuses on the balanced tetragonal Casnati–Ekedahl failure locus and
coordinates geometry, weakest-sufficient-proof, counterexample, and computation
lanes. Revision 2 fixes the CE convention
`W_5=(O_{P(E^vee)}(2) tensor gamma^*O(-5))|_C`, preserves the revision-1
attempt byte-for-byte as stale context, and enforces the subproblem DAG. Revision 4
adds chain-scoped high-tier escalation and periodic forced exact-theorem turns.
After fresh ordinary proof starts 3 and 6 in each six-start cycle, the harness
queues one forced turn each for Opus and GPT in the active chain order. Grok and
Qwen never receive forced-proof work. A substantive unsuccessful forced result
opens one same-engine standard-method turn; infrastructure failures do not consume
the forced slot.

Observable subprocess output, tool records, computations, and review diagnostics are
quarantined as traces. An independent engine converts each trace into a
provenance-free mathematical working context; private provider reasoning is never
read. Candidates in that context remain unproved. A
downstream node is runnable only after every predecessor has a gap-free result
and two independent cross-engine confirmations. Generate all campaign manifests
and reports with:

```bash
python3 -m pure_tate all
python3 -m pure_tate capability-audit --engines claude grok --live
python3 -m pure_tate drive \
  --campaign C66-001 \
  --steps 12 \
  --research-engines claude grok \
  --prover-engines grok claude codex qwen \
  --review-engines grok qwen codex claude \
  --notify-desktop \
  --dry-run
```

On macOS, `--notify-desktop` sends a native notification after every completed
campaign step and a final run notification. It is best-effort: a notification
permission or AppleScript failure never interrupts proof work.

For phone alerts, install the free ntfy app and subscribe to the private topic
in `data/notifications.local.json` (copy the tracked example file first when
setting up another workspace). Once configured, campaign drives post the same
per-step and final notices automatically; use `--no-notify-ntfy` to disable them
for one drive. Unicode titles are RFC 2047 encoded for HTTP transport, and each
run ledger records the redacted per-channel delivery status and HTTP result. The
topic acts as the shared secret; never commit or share it.

Remove `--dry-run` only after the listed research engines have passed live audits
for both finding-audit and novelty phases. Once any live audit exists, dry-run
also fails closed: failed or unattested engines are excluded, and an independence
requirement that leaves no passing web engine reports `capability_failure` with
the blocking task and engine states. Macaulay2 experiments use a
digest-pinned `linux/amd64` OCI image, run without network, and require a second
byte-hash-matching execution before a universal computation can support a proof.

Qwen mathematics and review turns additionally require a current artifact-level
health receipt. The health command runs bounded basic, file-reading, and synthetic
review probes without writing proof artifacts:

```bash
python3 -m pure_tate engine-health \
  --engine qwen \
  --live \
  --level artifact \
  --timeout 180 \
  --inactivity-timeout 60
```

Qwen live-web turns use the Model Studio Responses API with `web_search` and
`web_extractor`. The Singapore Qwen3.7-Max endpoint requires thinking mode when
`web_extractor` is enabled, so the evidence stage uses a small 2,048-token thinking
budget. A task has at most six model calls total: three evidence-stage calls and
three final-artifact calls, with the last call of each stage forced tool-free for
synthesis. The web-evidence response window is one hour and the main Qwen response
window defaults to three hours (`QWEN_RESPONSES_TIMEOUT` may lower it). A web-stage
failure falls forward to the final stage rather than discarding the whole task.

Qwen provider calls stream by default (Server-Sent Events). The worker emits
JSONL progress events on stdout (`stage`, `text`, `thought`, `tool_call`,
`tool_result`, `heartbeat`, `end`) so the campaign inactivity watchdog sees
mid-request activity and partial tokens remain in observable traces if a step is
killed. Thought events are quarantined from proof traces the same way Grok
thoughts are. Set `QWEN_STREAM=0` only as an emergency non-streaming fallback.

Paid routing excludes a Qwen engine whose receipt is missing or failed; dry-run
keeps it in the proposed rotation while displaying the failed state. Agent subprocesses
run in their own process groups, emit activity to a durable campaign run ledger under
`reports/runs/`, and are terminated on total timeout, inactivity, interruption, or a
configured repeated fatal error such as backend `503`.

Live campaign drives hold an OS-backed per-campaign lease, so a second process cannot
select the same task or artifact while the first is active. Artifact IDs are reserved
atomically before dispatch. Each engine and Grok helper runs behind a parent-death
supervisor; if the drive or MCP owner disappears, the supervised process group is
terminated. The next drive marks any ledger left by a missing parent as `abandoned`
and releases its active (non-spent) reservations. Run ledgers record parent, supervisor,
engine PID, and process-group metadata for diagnosis. Qwen is excluded before dispatch
when neither `DASHSCOPE_API_KEY` nor `QWEN_API_KEY` is present.

### Artifact slots, recovery, and no rewrites (mandatory)

These rules are harness policy, not suggestions:

1. **Existing work is never rewritten.** Proof attempts, reviews, and other durable
   artifacts are append-only. The runner refuses to overwrite an on-disk artifact path.
2. **Reattempts always get a new slot.** Every live dispatch reserves a never-before-used
   `ATT-####` / `REV-####` / research ID. Numbers already claimed by files, active or
   *spent* reservations, run-ledger outputs, or recovery receipts are never reissued.
   After a paid turn produces an official trace, its reserved ID is permanently **spent**
   even if validation fails and no artifact file was written. Re-running the same task
   therefore cannot target the previous ID.
3. **Recovery before re-run.** If a paid turn fails validation or parsing but left an
   official observable trace, the harness **must attempt recovery** of that stream
   (identity-field coercion, re-parse, write into the reserved slot if still free)
   before spending another engine turn on the same task. Operators may also recover
   manually or with Grok:

   ```bash
   python3 -m pure_tate recover-trace --trace TRACE-0023
   # optional exclusive path if the original id is already occupied:
   python3 -m pure_tate recover-trace --trace TRACE-0023 --output proof/attempts/ATT-0041.json
   ```

   Live drives call recovery for pending validation-failure traces at start, and again
   immediately after a mid-batch validation failure, so a fixable schema mismatch does
   not burn another full paid attempt. Successful recovery is ledgered under
   `proof/paired-recoveries.json` with `protect_from_overwrite: true`.

Do not delete, rename-over, or hand-edit a recovered artifact to "make room" for a
re-run. If another attempt is still needed, reserve the next free ID.

A campaign dry run displays both members of every conditional pair and marks the
standard turn as conditional. It spends nothing and does not claim that the
conditional turn has executed.

The report exposes `case_verified` and `novelty_certified` separately. The former
requires a gap-free exact theorem and two cross-engine confirmations. The latter is
available only after two distinct live-web audits of the exact theorem and proof
hash find no covering prior result. This is a harness certification, not a guarantee
against unpublished or undiscoverable work.
