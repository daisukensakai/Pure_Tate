# Gemini 3.5 Flash 503 diagnosis

Diagnosed on 2026-08-01 JST with Gemini CLI `0.53.0`. No Pure Tate harness
files or configuration were changed.

## Result

`gemini-3.5-flash` is currently unavailable on the configured API-key route.
This is model-specific provider capacity failure, not a broken login, API key,
network path, CLI installation, or stream parser.

The focused control run established all of the following:

- A direct `generateContent` request to `gemini-3.5-flash` returned HTTP 503
  `UNAVAILABLE` with Google's high-demand message.
- The same API key and endpoint returned HTTP 200 for
  `gemini-3-flash-preview`.
- Gemini CLI initialized normally for `gemini-3.5-flash`, then printed retry
  failures to **stderr** with exponential/jittered backoff. It produced no
  assistant message and no terminal `result` event.
- The lab wrapper stopped the whole process group after the third 503, in about
  20 seconds.
- The identical CLI invocation using `gemini-3-flash-preview` completed in
  about three seconds with an assistant message and terminal success event.

Latest manifest:

`results/gemini_503/20260731T231133941627Z/manifest.json`

## Interactive-mode cross-check

The exact command `gemini --model gemini-3.5-flash` can appear healthy because
it renders the interactive UI before issuing a model request. In a live
interactive cross-check, the UI opened and displayed `gemini-3.5-flash`, but a
one-line prompt remained in `Thinking` for almost two minutes and never
returned an answer. The Gemini CLI's own exit summary reported six main-model
requests to `gemini-3.5-flash` with zero input and output tokens. A separate
`gemini-3.1-flash-lite` utility-summarizer request succeeded.

Thus UI startup is not a health receipt. If an interactive session does return
a substantive answer, inspect its exit summary: nonzero 3.5 output tokens show
that transient capacity recovered; output attributed to another model shows a
fallback. `--model` and `-m` are aliases and do not select different routes.

## Two diagnostic traps

1. Text-mode output is buffered, so retries can look like a completely silent
   hang. Use `stream-json` and monitor stderr as an activity/error stream.
2. Do not accept exit code zero or a raw substring match as success. The stream
   echoes the user prompt, and a process terminated during retry handling may
   still report code zero. Success requires an assistant response plus a
   terminal event whose `status` is `success`.

## Lab mitigation

`run_gemini_503_probe.py` now:

- preserves every run in a timestamped directory;
- captures stdout and stderr incrementally;
- aborts the process group after three explicit 503 retry lines;
- requires both an assistant message and a terminal success event;
- runs a healthy control model after the failure.

For production integration later, fail the Gemini health gate after three 503
attempts and do not consume a mathematical turn. Keep `gemini-3.5-flash`
disabled until both a direct probe and a CLI stream probe succeed. A temporary
switch to `gemini-3-flash-preview` is operationally viable, but it is a model
substitution and should be explicit rather than automatic.
