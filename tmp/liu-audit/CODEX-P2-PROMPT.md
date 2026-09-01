# Independent mathematical review, pass 2

Act as a second hostile but fair expert referee in intersection theory and moduli of curves.  This is an adjudicating review, not a summary.  Do not modify any file and do not rely on theorem statements or prior model confidence as evidence.

Read the same primary-source packet used in pass 1:

- `tmp/liu-audit/liu-2509.02950v1.pdf` and `.txt` (Yuhan Liu, arXiv:2509.02950v1, 3 September 2025; PDF SHA-256 `ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a`).
- `tmp/liu-audit/canning-larson-2208.02357.pdf` and `.txt`.
- `tmp/liu-audit/clp-2307.08830.pdf` and `.txt`.
- `tmp/liu-audit/ionel-math9908060.pdf` and `.txt`.
- `paper/degree16_genus_le7.tex`.
- The pass-1 Claude report supplied with this request.

Independently decide whether the manuscript may use, as an unconditional mathematical input over `C` with rational coefficients,

1. `A^*(M_{5,8})=R^*(M_{5,8})`;
2. the Chow--Kunneth generation property for `M_{5,8}`;
3. the consequence `W_24 H^24(M_{5,8};Q)=0`;
4. the equivalent vanishing `W_{-16} H_16^BM(M_{5,8};Q)=0`.

Trace Liu's argument rather than treating Corollary 3.9 as self-validating.  In particular, adjudicate all four pressure points listed in `CLAUDE-P1-PROMPT.md`: the `G` versus `G'` Chern formula; descent across the `mu_5`-gerbe; whether the use of `BG -> BGL_4` suffices for the universal Chow--Kunneth assertion; and localization/gluing across the lower-gonality, independent, and exceptional loci.  Check the expected codimension and Porteous step, the seven-point configuration lemma, the Grassmann-bundle presentations, and every dimension, weight, and twist in the downstream Hodge-theoretic implication.

Where the pass-1 report is right, explain why from the primary sources.  Where it is wrong or incomplete, say so explicitly.  A minor repair counts as adequate only if you can give a complete valid argument with exact source locators; otherwise classify the dependency as unresolved.

Return a concise report with these headings:

- `VERDICT`: exactly one of `CONFIRMED`, `INCOMPLETE`, or `REFUTED`.
- `P1 ADJUDICATION`: which pass-1 findings survive.
- `CLAIM CHECKS`: one determination for each of the four claims above.
- `LOAD-BEARING DETAILS`: exact arguments and locators for every repaired shorthand step.
- `MANUSCRIPT ACTION`: exact changes required before a Zenodo deposit.

Use `CONFIRMED` only if no unresolved load-bearing gap remains in the claims actually used by the manuscript.
