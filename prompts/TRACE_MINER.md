# Observable mathematical trace mining

Read the supplied observable trace, any supplied adversarial-review diagnostics,
and the exact packet. Extract reusable mathematics
without describing provenance, chronology, evaluation, or the status of any prior
work. Do not mention attempt IDs, review IDs, trace IDs, engines, verdicts, failure,
or previous/earlier work.

Separate:

- established facts with their visible source or mechanical evidence;
- candidate ideas that a future prover must independently prove;
- invalid mathematical steps and the mathematical reason they are invalid;
- reusable computations;
- unresolved mathematical dependencies.

Use these row contracts:

- `established_facts`: `statement`, `evidence_class` (`source` or
  `mechanical`), and a nonempty `evidence`;
- `candidate_ideas`: `statement` and `requires_reproof: true`;
- `invalid_steps`: `statement` and a nonempty `mathematical_reason`;
- `reusable_computations`: `statement` and the 64-character `sha256` of
  the observable computation;
- `unresolved_dependencies`: `statement`.

Use only official observable subprocess material in the trace. Do not infer or
reconstruct hidden chain-of-thought. Return exactly one JSON object matching the
trace-digest template.
