# Mathematics-agent dispatch

Load `TASK.json` and its single revision-2 case packet. Use the exact target
dictionary, ordinary degree, Tate twist, and packet hash recorded there.

Attempt exactly one approach:

1. Extend CKgP or gonality-stratification geometry to the missing pointed case.
2. Prove only the weaker pure-weight Tate statement, without CKgP.
3. Give an exact point-count or equivariant-stratification computation.
4. Use the weight spectral sequence or decorated graph complex.
5. Search for a non-Tate motive that survives the compactification induction.

Output one schema-version-2 `ATT-####.json`; place the readable Markdown proof in
`argument_markdown`, make `claims` structured objects, and mark every gap explicitly.
The top-level `status` must be exactly one of `draft`, `proposed`,
`claimed_complete`, `refuted`, or `verified`. Use `proposed` for an incomplete
argument; informal values such as `partial`, `blocked`, or `incomplete` are invalid.
Do not claim completeness from an arithmetic prediction, a semisimplification, or a
tautological pairing computation whose perfectness was not proved.
