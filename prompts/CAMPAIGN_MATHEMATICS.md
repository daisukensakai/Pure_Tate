# Focused (6,6) mathematics campaign

Work only on the assigned subproblem and exact target. Use the balanced tetragonal
Casnati–Ekedahl geometry in the packet and aim for the weakest sufficient theorem.

Respect the subproblem DAG. `TASK.json` lists `blocked_dependencies` and
`dependency_artifacts`. A task is executable only when `blocked_dependencies` is
empty. Read every supplied dependency attempt and both confirmation reviews; cite
their artifact IDs when using them. Do not infer, recreate, or strengthen a
dependency whose verified artifacts are absent.

State one exact theorem. Separate proved steps, source-backed inputs, computational
hypotheses, and gaps. Finite experiments cannot close a proof. Address the applicable
failed routes listed by the task; do not silently reuse them. A counterexample lane
must show survival in the exact target, not merely locate non-Tate geometry.

Return exactly one JSON artifact.
