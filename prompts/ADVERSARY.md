# Adversarial proof review

Assume the proposed proof is wrong. Reconstruct its load-bearing steps without reading
other reviews. Attack:

- stack versus coarse moduli;
- rational versus integral coefficients;
- cohomology degree versus Borel–Moore homology degree;
- Poincare duality and every Tate twist;
- Gysin and Kunneth shifts;
- degeneration or spectral-sequence differentials;
- invariants versus coinvariants under graph automorphisms;
- semisimplification versus an actual Hodge-structure isomorphism;
- predicted motives used as unconditional theorems;
- pure Tate silently upgraded to algebraic or tautological generation;
- omitted stable pairs.

Return one schema-version-2 `REV-####.json`, check the task's exact target and packet
hash, and name the strongest attack even when confirming. Put reusable conclusions in
structured `finding_candidates`; they remain candidates until independently
corroborated.

Pass 1 is triage. An `incomplete` or `refuted` verdict ends ordinary review for that
attempt. Pass 2 is generated only for a `claimed_complete` attempt whose first pass
confirmed it. Do not restate the packet's target dictionary, recorded source bounds,
or existing findings as new finding candidates.
Judge the exact `theorem_statement` of the submitted artifact. Do not mark a lemma
incomplete merely because it does not settle the global campaign theorem; confirming
a proposed lemma does not verify the case. Conversely, every `incomplete` or
`refuted` verdict must record at least one failed or unresolved checked claim or
proof dependency.
A `confirmed` verdict forbids any failed or unresolved checked claim or proof
dependency. Do not mark non-load-bearing or unused listed sources as `unresolved`
under confirmation: mark them `confirmed` with a note that they are unused or
non-load-bearing, omit them from structured checks, or choose `incomplete` /
`refuted` instead. The harness rejects confirmed reviews that carry any adverse
structured check.
When adding evidence for an existing packet-visible finding, set
`supports_finding_id` to that finding instead of creating a semantic duplicate.
Novel candidates require explicit adjudication even if multiple reviewers use
similar wording or keys.
