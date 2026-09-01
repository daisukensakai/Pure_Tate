# Independent mathematical review of Revision 3 (Codex)

Act as a hostile but fair expert referee in intersection theory and moduli
of curves. This is an independent adversarial review of a *thrice-repaired
proposed proof*. It is not a review of a published theorem and not a vote
of confidence in any prior AI report. Do not rely on any prior AI review,
campaign verdict, abstract, or authorial assertion. Do not modify any file.

Read, in this order:

1. `tmp/liu-repaired/PROOF.md` — Revision 3 of the argument under review.
   Attack this.
2. `tmp/liu-repaired/claims.json` — the atomic claims.
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
cites Liu for a construction, trace that construction in the preprint.
Where `PROOF.md` supplies a repair, decide whether the repair is complete
and correct. A minor repair counts only if you can give a complete valid
argument with exact locators.

Do not cite, quote, or use any Claude, Qwen, or earlier Codex report.

Audit the following exact claims, over `\mathbf C` with rational coefficients:

1. `A^*(M_{5,8})=R^*(M_{5,8})`.
2. `M_{5,8}` has the Chow--Künneth generation property.
3. `W_{24}H^{24}(M_{5,8};\mathbf Q)=0`.
4. `W_{-16}H^{\mathrm{BM}}_{16}(M_{5,8};\mathbf Q)=0`.

Pressure points that must be independently decided (do not accept them
because they are labelled "repair"):

- Normalized sequence (10) versus the displayed formula for `G'` in Liu's
  Corollary 3.6.
- Descent of CKgP across the `\mu_5`-gerbe by Canning--Larson Lemma 3.6.
- Whether `B\mathrm{GL}_4\to BG` as a representable `\mathbf A^4`-bundle
  plus Lemma 3.5 yields CKgP of `BG`.
- The *family* inverse for Liu Proposition 3.3 in `PROOF.md` §2.5, including:
  the claim that Liu's `W` is too big; the residual section `p_8`; the
  adjunction computation
  `\omega_f=j^*\mathcal O(1)\otimes f^*(\det F'\otimes\det\mathcal S^\vee)`
  and the identification `L^\vee\otimes f_*\omega_f=F'^\vee`, `G=F^\vee`;
  and whether both composites are identities, so that `M_\omega\cong W` is
  now a complete isomorphism of stacks.
- The inverse for Liu Proposition 2.5 in §1.2.
- Irreducibility of `M_\omega` and Fulton Theorem 14.4(c) for the Porteous
  multiplicity in §2.6.
- Canning--Larson Lemma 9.9 at `(5,8)` and gluing by excision / Lemma 3.4.
- Ionel as cohomological vanishing of the cycle-class image of `R^{12}`.
- Borel--Moore dimension, weight, and twist.
- Liu Lemma 3.8 sign: `-\psi_i` versus `3\psi_i`.

Return a concise report with these headings:

- `VERDICT`: exactly one of `CONFIRMED`, `INCOMPLETE`, or `REFUTED`.
- `CLAIM CHECKS`: one determination for each of the four claims above.
- `STRONGEST ATTACK`: the most serious possible flaw in Revision 3 and
  whether it survives scrutiny.
- `REPAIR ADJUDICATION`: for each repair, complete / incomplete / wrong,
  with locators. Pay special attention to the round trip in §2.5 and to
  irreducibility in §2.6.
- `LOCATORS`: exact source locations used.
- `REQUIRED CHANGES`: what must change in `PROOF.md` (and then in the
  manuscript) before this dependency is honest.

Use `CONFIRMED` only if no unresolved load-bearing gap remains in the
claims actually used. A correct theorem statement in an unrefereed preprint
is not by itself enough.
