## VERDICT

CONFIRMED

The four claims are correct after one mandatory local correction: Revision 3 dualizes \(\det F'\) incorrectly in §2.5. The corrected adjunction computation gives the same normalized bundles, so the round trip and all downstream conclusions survive. No unresolved load-bearing gap remains.

## CLAIM CHECKS

1. \(A^*(\mathcal M_{5,8})=R^*(\mathcal M_{5,8})\): **confirmed.** The three-stratum argument works: \(U_8\), the corrected exceptional stratum \(M_\omega\cong W\), and \(M^3_{5,8}\). Excision plus push–pull is valid.

2. \(\mathcal M_{5,8}\) has CKgP: **confirmed.** CKgP descends across the \(\mu _5\)-gerbe; \(B\mathrm{GL}_4\to BG\) is the required affine bundle; and Canning–Larson Lemma 3.4 glues the three CKgP strata.

3. \(W_{24}H^{24}(\mathcal M_{5,8};\mathbf Q)=0\): **confirmed.** CLP Lemma 4.3 makes lowest-weight cohomology algebraic; Claim 1 makes its source tautological; Ionel kills every codimension-12 tautological monomial because \(12\ge5\).

4. \(W_{-16}H^{\mathrm{BM}}_{16}(\mathcal M_{5,8};\mathbf Q)=0\): **confirmed.** For \(d=20\),
   \[
   H^{\mathrm{BM}}_{16}\cong H^{24}(20),
   \]
   and twisting lowers weights by \(40\), sending weight \(24\) to weight \(-16\).

## STRONGEST ATTACK

The strongest attack is Liu Proposition 3.3: Liu neither constructs a family inverse nor defines the correct open \(W\). His stated open includes smooth nets for which the hyperplane is tangent at one of \(p_1,\dots ,p_7\), making the residual \(p_8\) collide with that marking.

Revision 3 correctly removes this locus and constructs \(p_8\) as the degree-one residual Cartier divisor. Its displayed adjunction formula is nevertheless false under Liu’s convention. The correct formulas are
\[
\omega_{\mathbf P F'/BG}
 =\mathcal O(-5)\otimes\gamma'^*(\det F')^\vee,
\]
\[
\omega_f
 =j^*\mathcal O(1)\otimes
 f^*((\det F')^\vee\otimes\det\mathcal S^\vee).
\]
Consequently
\[
f_*\omega_f
 =F'^\vee\otimes(\det F')^\vee\otimes\det\mathcal S^\vee,
\qquad
L=(\det F')^\vee\otimes\det\mathcal S^\vee.
\]
The erroneous determinant cancels, leaving
\[
L^\vee\otimes f_*\omega_f=F'^\vee,\qquad G=F^\vee.
\]

The relative Koszul resolution also gives \(f_*\mathcal O_C(1)=F'^\vee\) and recovers the original rank-three net as \(f_*I_C(2)=\mathcal S\). Thus both composites are identities, compatibly with base change and automorphisms. The attack does not survive this correction. Liu’s projectivization convention is confirmed by [Stacks Project, §27.21](https://stacks.math.columbia.edu/tag/01OA).

## REPAIR ADJUDICATION

- **Normalized sequence (10): complete.** The correct formula is
  \[
  c(G)=c(L^\vee\otimes f_*\omega_f),
  \]
  whereas Liu’s Corollary 3.6 displays the formula for \(G'\).

- **\(\mu _5\)-gerbe descent: complete.** Canning–Larson Lemma 3.6 applies to every product with a test stack, which is exactly what CKgP requires.

- **\(B\mathrm{GL}_4\to BG\): complete.** For \(G=\mathbf G_a^4\rtimes\mathrm{GL}_4\), base change classifies reductions to the Levi and is the torsor \(P/\mathrm{GL}_4\), an affine-space bundle modelled on the associated rank-four vector bundle. Lemma 3.5 applies in this direction.

- **Liu Proposition 2.5 inverse: complete.** \(V_n\) excludes diagonals because evaluation at two coincident markings cannot be surjective. The universal smooth three-quadric intersection, its sections, and the \(B\mathrm{SL}_5\)-datum give the inverse in families.

- **Liu Proposition 3.3 inverse: complete after correcting the determinant dual above.** The residual construction is base-change compatible; the corrected \(W\) excludes \(p_8=p_i\); Koszul and adjunction recover both the net and the \(BG\)-reduction.

- **Irreducibility and Porteous: complete.** \(BG\), \((\mathbf PF)^7\), \(V'\), and \(G(3,\mathcal E)\) are irreducible. The corrected \(W\) is nonempty—for a general smooth intersection of three quadrics, a transverse hyperplane gives eight distinct points—and hence irreducible. Fulton 14.4(c) gives the natural degeneracy cycle; with irreducible support it is \(m[M_\omega]\), \(m>0\), so division over \(\mathbf Q\) is legitimate. See the [official Chapter 14 description](https://link.springer.com/book/10.1007/978-1-4612-1700-8).

- **Lemma 9.9 and gluing: complete.** At \((5,8)\), \(8\le5+7\). Lemma 3.4 and the two excision sequences give the claimed global statements.

- **CLP plus Ionel: complete.** Ionel is used only in cohomology, not to assert Chow vanishing.

- **Borel–Moore conversion: complete.** Dimension, cohomological degree, Tate twist, and weight shift are all correct.

- **Liu Lemma 3.8 sign: Revision 3 is correct.** The class is \(-\psi_i\), not \(3\psi_i\).

## LOCATORS

- Liu: convention p. 2; gerbe pp. 3–4; Proposition 2.5 pp. 5–7; Corollary 2.9 p. 8; sequences (9)–(10) p. 9; Lemma 3.2 pp. 9–10; Proposition 3.3 pp. 11–12; Corollary 3.6 p. 12; Lemma 3.8 and Corollary 3.9 p. 13. SHA-256 matches the supplied value. :codex-file-citation{path="/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/liu-codex-rev3-20260901/workspace/tmp/liu-audit/liu-2509.02950v1.pdf" purpose="source"}

- Canning–Larson: Definition 3.1 and Lemmas 3.3–3.8, pp. 9–10; analogous unipotent-radical affine bundle, p. 18; Lemma 9.9, p. 33. :codex-file-citation{path="/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/liu-codex-rev3-20260901/workspace/tmp/liu-audit/canning-larson-2208.02357.pdf" purpose="source"}

- CLP: Lemma 4.3 and proof, pp. 12–13. :codex-file-citation{path="/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/liu-codex-rev3-20260901/workspace/tmp/liu-audit/clp-2307.08830.pdf" purpose="source"}

- Ionel: definitions and Theorem 0.1, p. 1, especially the explicit distinction between cohomological and possible Chow vanishing. :codex-file-citation{path="/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/liu-codex-rev3-20260901/workspace/tmp/liu-audit/ionel-math9908060.pdf" purpose="source"}

- Revision 3 error: [PROOF.md §2.5](/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/liu-codex-rev3-20260901/workspace/tmp/liu-repaired/PROOF.md:287).

- Manuscript’s present dependency: [degree16_genus_le7.tex](/Users/ken/Desktop/Work/exploratory/Pure_Tate/reports/runs/manual-recovery/liu-codex-rev3-20260901/workspace/paper/degree16_genus_le7.tex:406).

## REQUIRED CHANGES

1. Replace every \(\det F'\) in PROOF.md §2.5’s adjunction, pushforward, and \(L\)-formulas by \((\det F')^\vee\).

2. State explicitly that the relative Koszul resolution gives
   \(f_*\mathcal O_C(1)=F'^\vee\) and recovers \(\mathcal S= f_*I_C(2)\); this closes both round trips rather than leaving one “by construction.”

3. Add the explicit nonemptiness argument for \(W\) before invoking irreducibility.

4. In the manuscript, do not cite Liu Corollary 3.9 as sufficient or describe only “two harmless points.” Incorporate or cite the corrected family inverse, corrected \(W\), irreducibility/Porteous argument, gerbe descent, affine-bundle argument, and Lemma 9.9 gluing. Until that is done, the manuscript’s citation trail understates the actual dependency.
