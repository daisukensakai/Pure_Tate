# Independent mathematical review, pass 1 (Qwen)

Act as a hostile but fair expert referee in intersection theory and the
geometry of moduli spaces. This is an independent first-pass review of a
*repaired proposed proof*, not of a published theorem and not of a prior
AI report. Do not rely on any prior AI review, campaign verdict, abstract,
or authorial assertion. Do not modify any file.

Read, in this order:

1. `tmp/liu-repaired/PROOF.md` — the argument under review. Attack this.
2. `tmp/liu-repaired/claims.json` — the atomic claims the argument asserts.
3. Primary sources, in full where relevant:
   - `tmp/liu-audit/liu-2509.02950v1.pdf` and `.txt` (Yuhan Liu,
     arXiv:2509.02950v1; PDF SHA-256
     `ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a`).
   - `tmp/liu-audit/canning-larson-2208.02357.pdf` and `.txt`.
   - `tmp/liu-audit/clp-2307.08830.pdf` and `.txt`, especially Lemma 4.3.
   - `tmp/liu-audit/ionel-math9908060.pdf` and `.txt`, especially Theorem 0.1.
4. `paper/degree16_genus_le7.tex`, only to check how the manuscript uses the
   result. The manuscript is not itself the proof under review.

Liu's Corollary 3.9 is unrefereed and is not an axiom. Where `PROOF.md`
cites Liu for a construction, trace that construction in the preprint. Where
`PROOF.md` supplies a repair, decide whether the repair is complete and
correct. A minor repair counts only if you can give a complete valid
argument with exact locators.

Audit the following exact claims, over `\mathbf C` with rational coefficients:

1. `A^*(M_{5,8})=R^*(M_{5,8})`.
2. `M_{5,8}` has the Chow--Künneth generation property.
3. `W_{24}H^{24}(M_{5,8};\mathbf Q)=0`.
4. `W_{-16}H^{\mathrm{BM}}_{16}(M_{5,8};\mathbf Q)=0`.

Pressure points that must be independently decided (do not accept them
because they are labelled "repair"):

- Normalized sequence (10) versus the displayed formula for `G'` in Liu's
  Corollary 3.6: does `c(G)=c(L^\vee\otimes f_*\omega_f)` hold, and does it
  suffice for later Chern classes?
- Descent of CKgP across the `\mu_5`-gerbe `M'_{5,8}\to U_8` by
  Canning--Larson Lemma 3.6.
- Whether `B\mathrm{GL}_4\to BG` being a representable `\mathbf A^4`-bundle
  (Canning--Larson Lemma 3.5) is what yields CKgP of `BG`, rather than the
  ordinary Chow-ring isomorphism Liu states.
- The inverse open immersion supplied for Liu's Proposition 3.3.
- Localization/gluing across `U_8`, `M_\omega`, and `M^3_{5,8}`, including
  Canning--Larson Lemma 9.9 at `(g,n)=(5,8)`.
- Expected codimension and Porteous; Lemma 3.2; Grassmann presentations;
  Ionel at Chow codimension 12; Borel--Moore dimension, weight, and twist.

Return a concise report with these headings:

- `VERDICT`: exactly one of `CONFIRMED`, `INCOMPLETE`, or `REFUTED`.
- `CLAIM CHECKS`: one determination for each of the four claims above.
- `STRONGEST ATTACK`: the most serious possible flaw in `PROOF.md` and
  whether it survives scrutiny.
- `REPAIR ADJUDICATION`: for each repair, complete / incomplete / wrong,
  with locators.
- `LOCATORS`: exact source locations used.
- `REQUIRED CHANGES`: what must change in `PROOF.md` (and then in the
  manuscript) before this dependency is honest.

Use `CONFIRMED` only if no unresolved load-bearing gap remains in the claims
actually used. A correct theorem statement in an unrefereed preprint is not
by itself enough. Do not cite or use any Claude report.
