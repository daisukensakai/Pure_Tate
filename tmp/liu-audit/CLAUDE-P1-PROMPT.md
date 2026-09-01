# Independent mathematical review, pass 1

Act as a hostile but fair expert referee in intersection theory and the geometry of moduli spaces.  This is an independent first-pass review.  Do not rely on any prior AI review, campaign verdict, abstract, or authorial assertion.  Do not modify any file.

Read the following primary-source files in full where relevant:

- `tmp/liu-audit/liu-2509.02950v1.pdf` and its extracted text `tmp/liu-audit/liu-2509.02950v1.txt` (Yuhan Liu, arXiv:2509.02950v1, 3 September 2025; SHA-256 of the PDF `ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a`).
- `tmp/liu-audit/canning-larson-2208.02357.pdf` and `.txt`, used by Liu as reference [2].
- `tmp/liu-audit/clp-2307.08830.pdf` and `.txt`, especially Lemma 4.3.
- `tmp/liu-audit/ionel-math9908060.pdf` and `.txt`, especially Theorem 0.1.
- `paper/degree16_genus_le7.tex`, only to check how the result is used.

Audit the following exact dependency claim, over the complex numbers and with rational coefficients:

1. Liu's proof establishes both
   \[
   A^*(\mathcal M_{5,8})=R^*(\mathcal M_{5,8})
   \quad\text{and}\quad
   \mathcal M_{5,8}\text{ has the Chow--Kunneth generation property}.
   \]
   Do not treat Theorem 1.3 or Corollary 3.9 as self-validating.  Trace the proof through the independent locus, the exceptional canonical-divisor locus, localization, its generators, and the Canning--Larson lemmas invoked for the Chow--Kunneth property.  Check dimensions, degeneracy-locus formulas, gerbes/quotients, restriction and localization arguments, and whether every claimed generator is shown tautological.  Identify any missing hypothesis or unjustified step that could invalidate the result for `M_{5,8}`.  The characteristic restriction in Liu must be compared with the use over `C`.

2. If claim 1 is valid, check the downstream implication used in the manuscript:
   \[
   W_{24}H^{24}(\mathcal M_{5,8};\mathbf Q)=0.
   \]
   In particular, verify that Liu plus Canning--Larson--Payne Lemma 4.3 identifies the lowest-weight group with tautological cohomology, and that the relevant Ionel vanishing threshold applies in Chow codimension 12.  Then verify the equivalent Borel--Moore statement in degree 16, including dimension and Tate twist.

Give exact proposition/lemma/page locators.  Push the proof as hard as possible, including checking whether Liu's appeal to the Canning--Larson Chow--Kunneth lemmas actually applies to the stratification used.

The local source audit found four points that require an independent decision; do not accept the suggested repairs without checking them:

- In the proof of Liu's Corollary 3.6, the displayed formula `c(G)=c(f_*omega_f)/c(L)` is the formula for `G'`, whereas Liu defined `G=L^vee tensor G'`.  Check whether normalized sequence (10) really gives `c(G)=c(L^vee tensor f_*omega_f)` and whether this suffices for every Chern class used later.
- The passage from the auxiliary `mu_5`-gerbe `M'_{5,n}` to `U_n` appears to require Canning--Larson Lemma 3.6, although Liu's Corollary 3.9 does not list it.  Check that the gerbe and characteristic hypotheses make that lemma applicable.
- In the exceptional-locus construction, Liu says that `BG -> BGL_4` induces an isomorphism on ordinary Chow rings.  Determine whether this is enough for the Chow--Kunneth generation property, which is a universal product assertion, or whether a separate argument for the unipotent extension is missing.
- Corollary 3.9 compresses the localization across the lower-gonality, independent, and exceptional loci.  Check that pushforwards of all generators are tautological and that every stratum has the Chow--Kunneth property needed for the gluing lemma.

Return a concise report with these headings:

- `VERDICT`: exactly one of `CONFIRMED`, `INCOMPLETE`, or `REFUTED`.
- `CLAIM CHECKS`: separate determinations for the Chow-ring assertion, the Chow--Kunneth assertion, the lowest-weight consequence, and the Borel--Moore consequence.
- `STRONGEST ATTACK`: the most serious possible flaw and whether it survives scrutiny.
- `LOCATORS`: exact source locations used.
- `REQUIRED CHANGES`: what the manuscript must say to cite this dependency honestly.

Use `CONFIRMED` only if no unresolved load-bearing gap remains in the claims actually used by the manuscript.  A correct theorem statement in an unrefereed preprint is not by itself enough.
