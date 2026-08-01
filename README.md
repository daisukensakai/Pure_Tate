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
python3 -m pure_tate engine-health --engine gemini --live --level artifact
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
isolated, read-only workspace containing only phase-approved inputs:

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
attempt, its exact packet, and the adversarial rubric. Revision-2 tasks pin the
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
Gemini). Retries escalate `grok → gemini → codex → claude`. Reviews walk the same
escalation order, skipping only the prover and already-used reviewers.

Remove `--dry-run` only when the displayed portfolio is intended. Pending current
reviews run before new mathematics. A `proposed` attempt receives one independent
triage review. An `incomplete` or `refuted` verdict closes that review cycle. Only an
attempt that declares `claimed_complete` and passes its first review receives a second
confirmation pass; the two confirmations must use engines distinct from each other
and from the prover.

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

Campaign `C66-001` keeps target context revision 2 and uses campaign revision 3.
Its packet focuses on the balanced tetragonal Casnati–Ekedahl failure locus and
coordinates geometry, weakest-sufficient-proof, counterexample, and computation
lanes. Revision 2 fixes the CE convention
`W_5=(O_{P(E^vee)}(2) tensor gamma^*O(-5))|_C`, preserves the revision-1
attempt byte-for-byte as stale context, and enforces the subproblem DAG. Revision 3
adds paired exact-theorem turns. For each theorem and packet revision, engines
escalate Grok → Codex → Claude on the forced exact-theorem ladder. Each of those
engines first receives one isolated, offline, completion-focused
proof-or-disproof task. Only a substantive unsuccessful result opens one
same-engine standard-method turn; infrastructure failures do not consume the
first slot. Gemini is not on the forced ladder; it still participates in ordinary
subproblem mathematics when `prover_rotation` selects it.

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
  --prover-engines grok claude codex gemini \
  --review-engines grok gemini codex claude \
  --dry-run
```

Remove `--dry-run` only after the listed research engines have passed live audits
for both finding-audit and novelty phases. Once any live audit exists, dry-run
also fails closed: failed or unattested engines are excluded, and an independence
requirement that leaves no passing web engine reports `capability_failure` with
the blocking task and engine states. Macaulay2 experiments use a
digest-pinned `linux/amd64` OCI image, run without network, and require a second
byte-hash-matching execution before a universal computation can support a proof.

Gemini mathematics and review turns additionally require a current artifact-level
health receipt. The health command runs bounded basic, file-reading, and synthetic
review probes without writing proof artifacts:

```bash
python3 -m pure_tate engine-health \
  --engine gemini \
  --live \
  --level artifact \
  --timeout 180 \
  --inactivity-timeout 60
```

Paid routing excludes a Gemini engine whose receipt is missing or failed; dry-run
keeps it in the proposed rotation while displaying the failed state. Agent subprocesses
run in their own process groups, emit activity to a durable campaign run ledger under
`reports/runs/`, and are terminated on total timeout, inactivity, interruption, or a
configured repeated fatal error such as backend `503`.

A campaign dry run displays both members of every conditional pair and marks the
standard turn as conditional. It spends nothing and does not claim that the
conditional turn has executed.

The report exposes `case_verified` and `novelty_certified` separately. The former
requires a gap-free exact theorem and two cross-engine confirmations. The latter is
available only after two distinct live-web audits of the exact theorem and proof
hash find no covering prior result. This is a harness certification, not a guarantee
against unpublished or undiscoverable work.
