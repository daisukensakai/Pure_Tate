# Handoff: Make Gemini CLI reliable for Pure Tate agent turns

Date: 2026-07-30  
Workspace: `/Users/ken/Desktop/Work/exploratory/Pure_Tate`

## Objective

Diagnose and fix the Gemini execution path so `gemini-3.5-flash` can complete
bounded mathematics and review turns through the Pure Tate harness.

Do not modify mathematical proof artifacts while troubleshooting. A successful
fix must first pass the isolated engine-health probes described below.

## Current state

- Gemini CLI was upgraded from `0.52.0` to `0.53.0`.
- Authentication type in `~/.gemini/settings.json` is `gemini-api-key`.
- `GEMINI_API_KEY` is present in the environment. Do not print or persist it.
- A read-only request to the official model-list endpoint returned HTTP 200.
- The returned inventory explicitly included:
  - `models/gemini-2.5-flash`
  - `models/gemini-3-flash-preview`
  - `models/gemini-3.5-flash`
  - `models/gemini-3.6-flash`
- A minimal direct `gemini-3.5-flash:generateContent` request returned:

```json
{
  "error": {
    "code": 503,
    "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.",
    "status": "UNAVAILABLE"
  }
}
```

- Gemini CLI basic probes against both `gemini-3.5-flash` and
  `gemini-2.5-flash` also repeatedly returned `503`.
- CLI `0.53.0` did not resolve the failure.
- No Gemini or campaign child processes are currently running.

This establishes that the API key is valid and the configured model ID exists.
The immediate failure occurs during generation, before proof reasoning or file
tool use.

## Earlier behavior

Gemini was not always completely unavailable. Earlier session logs show
`gemini-3.5-flash` successfully producing model turns and invoking `read_file`.
Some sessions later stalled after several successful file reads. Therefore two
failure modes may need separate treatment:

1. backend `503` before the first model response;
2. a later stalled model turn after successful tool calls.

Example earlier session:

```text
~/.gemini/tmp/pure-tate-agent-8tq62rx8/chats/
session-2026-07-30T06-43-670c4350.jsonl
```

Example failed basic health session:

```text
~/.gemini/tmp/pure-tate-engine-health-qiemzppa/chats/
session-2026-07-30T11-56-c225ecc4.jsonl
```

## Harness execution path

Engine configuration:

```text
data/engines.json
```

Gemini command construction and stream parsing:

```text
pure_tate/agents.py
```

Bounded process runner:

```text
pure_tate/process_runner.py
```

Health probes and receipts:

```text
pure_tate/health.py
research/engine-health/latest-gemini.json
```

Campaign routing:

```text
pure_tate/campaign_driver.py
pure_tate/routing.py
```

Gemini is currently constructed approximately as:

```bash
GEMINI_SYSTEM_MD=data/gemini_system_minimal.md \
gemini \
  -p '<prompt>' \
  -m gemini-3.5-flash \
  -o stream-json \
  --approval-mode plan \
  --skip-trust
```

The harness:

- runs the CLI in a temporary isolated workspace;
- uses read-only plan mode;
- closes stdin;
- captures stdout and stderr continuously;
- starts a separate process group;
- terminates the whole group on timeout or interruption;
- uses `stream-json` output as heartbeat data;
- rejects malformed or incomplete final JSON;
- does not write a proof artifact unless validation succeeds.

Gemini configuration presently includes:

```json
{
  "max_task_seconds": 900,
  "inactivity_timeout_seconds": 300,
  "abort_stderr_pattern_counts": {
    "status: 503": 3
  },
  "requires_health_attestation": [
    "mathematics",
    "review"
  ]
}
```

Paid routing excludes Gemini while its artifact-level health receipt is failed
or missing. Dry runs retain its intended place in the routing ladder while
displaying the failed health state.

## Reproduction

Inspect the current receipt without making a request:

```bash
cd /Users/ken/Desktop/Work/exploratory/Pure_Tate
python3 -m pure_tate engine-health \
  --engine gemini \
  --level artifact
```

Run only the basic live response probe:

```bash
python3 -m pure_tate engine-health \
  --engine gemini \
  --live \
  --level basic \
  --timeout 90 \
  --inactivity-timeout 30
```

Run the complete health sequence:

```bash
python3 -m pure_tate engine-health \
  --engine gemini \
  --live \
  --level artifact \
  --timeout 180 \
  --inactivity-timeout 60
```

The complete sequence checks:

1. exact JSON response without tools;
2. reading two local files and combining their contents;
3. reading a synthetic task, packet, and attempt and returning a structured
   adversarial review.

It writes only health receipts under `research/engine-health/`; it never writes
an attempt or review.

A diagnostic-only model override is available:

```bash
python3 -m pure_tate engine-health \
  --engine gemini \
  --live \
  --level basic \
  --model gemini-2.5-flash \
  --timeout 90 \
  --inactivity-timeout 30
```

An override receipt does not attest the configured `gemini-3.5-flash` model.

## Questions to investigate

1. Why does a valid AI Studio API key receive model inventory successfully but
   generation returns persistent `503` across both 3.5 Flash and 2.5 Flash?
2. Is the key associated with a free, paid, suspended, region-limited, or
   otherwise deprioritized project whose generation traffic is routed
   differently from model listing?
3. Does Gemini CLI `0.53.0` apply a different endpoint, API version, routing
   tier, preview feature, or retry policy than the direct Generative Language
   API call?
4. Is `gemini-3.5-flash` intended to be accessed through a different model
   alias, API version, billing project, Vertex AI route, or thinking setting?
5. Can retry behavior fail fast on persistent backend `503` without treating
   repeated retry-stack stderr as useful model activity?
6. For the earlier post-tool stall, does `stream-json` omit an event or leave
   the CLI waiting on an approval, retry, telemetry flush, session save, or
   unfinished stream even under `--approval-mode plan`?
7. Does an empty `GEMINI_SYSTEM_MD` have any unsupported interaction with
   headless plan mode? Test with and without the override, but do not weaken
   read-only execution.
8. Are there official CLI diagnostics, debug exports, quota endpoints, project
   metadata, or response headers that can identify the serving tier and precise
   retry reason without exposing credentials?

## Requested repair

Prefer a documented Google-supported configuration. Possible fixes may include:

- correcting the authentication/project/billing configuration;
- selecting the correct officially supported model route;
- updating Gemini CLI configuration;
- improving detection and classification of backend errors;
- correcting stream parsing or process lifecycle handling;
- adding a declared fallback only if it records the actual model used and does
  not silently substitute a weaker model.

Do not:

- print, copy, hash, or persist the API key;
- change proof or review artifacts;
- disable read-only plan mode;
- remove packet validation;
- silently relabel another model as `gemini-3.5-flash`;
- treat a basic text response as sufficient evidence of a proper agent turn.

## Acceptance criteria

The repair is complete only when all of the following hold:

1. `gemini --version` and the effective authentication/model route are recorded
   without secrets.
2. The artifact-level health command exits zero.
3. Its receipt has `status: "pass"` and three passing checks: `basic`, `tools`,
   and `artifact`.
4. The receipt records `model: "gemini-3.5-flash"`.
5. A second independent artifact-level health run also passes.
6. No child Gemini process remains after either run.
7. `python3 -m unittest discover -s tests -p 'test_*.py'` passes.
8. `python3 -m pure_tate all` passes.
9. A paid campaign dry run reports Gemini health as `pass` and retains the
   configured routing order.

Only after these checks should Gemini be allowed to receive a real mathematics
or review task.

