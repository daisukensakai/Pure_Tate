# Codex controller smoke test

This is a controller-mediated worker test, not a mathematics task.

On the first controller decision turn, return exactly a `dispatch` decision
for request id `first-check`; ask the worker to return exactly
`{"worker":"first","ok":true}`.

After the controller transcript reports `first-check` completed, return exactly
a `dispatch` decision for request id `second-check`; ask the worker to return
exactly `{"worker":"second","ok":true}` and mention that it follows the
first worker result.

After the controller transcript reports `second-check` completed, return
`finalize`. On the final synthesis turn return exactly:

`{"id":"CONTROLLER-SMOKE","controller_smoke":true}`
