# Referee report — Revision 2 of the Liu input for `M_{5,8}`

## VERDICT

**INCOMPLETE**

I found no error in Revision 2 and no counterexample to any of the four claims; on the merits I believe all four are true. But two load-bearing steps are *asserted rather than argued* in `PROOF.md`, one of them inside the flagship repair (§2.5), and one of them (§2.1) is supported by a slogan that is not a valid argument. Both are fillable — I give complete fills below with locators — but they are not filled in the document under review, and one of them creates a hidden forward dependency that the document's own ordering conceals. That is short of the `CONFIRMED` bar as stated.

---

## CLAIM CHECKS

**1. `A^*(M_{5,8}) = R^*(M_{5,8})` — NOT ESTABLISHED AS WRITTEN; judged true.**
The three-stratum excision argument (`PROOF.md` §4) is correct in structure and every external citation checks out. It fails to close only because `[M_\omega]` tautological (§2.1) rests on an invalid multiplicity argument, and because the isomorphism `M_\omega\cong W` (§2.5), which the repair for §2.1 needs, is not completed.

**2. `M_{5,8}` has CKgP — NOT ESTABLISHED AS WRITTEN; judged true.**
The permanence chain is right and the two additions Liu omits (CL Lemma 3.6 for the gerbe; the affine-bundle justification for `BG`) are correctly identified and correctly applied. Same dependency on §2.5: CKgP of `M_\omega` is obtained *only* through `M_\omega\cong W\subset G(3,\mathcal E)`, so §2.5 is not optional here.

**3. `W_{24}H^{24}(M_{5,8};\mathbf Q)=0` — CONDITIONALLY CORRECT.**
Given claims 1–2, §6 is correct and I have no objection to it. CLP Lemma 4.3 and Ionel Theorem 0.1 are quoted accurately and used at exactly their stated strength. The claim inherits the status of claims 1–2 and nothing worse.

**4. `W_{-16}H^{\mathrm{BM}}_{16}(M_{5,8};\mathbf Q)=0` — CORRECT given claim 3.**
`\dim_{\mathbf C}M_{5,8}=3\cdot5-3+8=20`; `2d-i=40-16=24`; the Tate twist `(20)` shifts weight by `-40`, so weight `24` ↦ weight `-16`. Deligne's bound (weights on `H^k` of smooth `X` lie in `[k,2k]`) makes `-16` genuinely the bottom weight. Dimension, weight and twist are all right. No gap here.

---

## STRONGEST ATTACK

**The attack:** §2.1 concludes that `[M_\omega]` is tautological from Porteous. Porteous (Fulton, *Intersection Theory*, Thm. 14.4(c); Eisenbud–Harris Thm. 12.4) returns the class of the *determinantal scheme*, which in expected codimension is a positive cycle `\sum_j m_j[Z_j]` supported on the locus. If `M_\omega` had two codimension-4 components with `m_1\ne m_2`, tautologicality of `\sum m_j[Z_j]` would **not** give tautologicality of `[M_\omega]=\sum_j[Z_j]`. `PROOF.md`'s justification — "Rational coefficients absorb determinantal multiplicity" (line 134) — is not an argument; it is only valid if the cycle is a single multiple of `[M_\omega]`, i.e. if `M_\omega` is irreducible, and irreducibility is never asserted anywhere in the document.

**Does it survive?** No — but only because of §2.5, which §2.1 does not cite. Fill: by §2.5, `M_\omega\cong W`, an open substack of `G(3,\mathcal E)`, a Grassmann bundle over `V'\subset(\mathbf P F)^7` over `BG`. `G=\mathbf G_a^4\rtimes\mathrm{GL}_4` is connected, so `BG` is irreducible; `(\mathbf P F)^7` is an iterated projective bundle over it, hence irreducible; `V'` is a nonempty open in it (Liu p. 11, evaluation (12)), hence irreducible; `G(3,\mathcal E)` is a Grassmann bundle over `V'`, hence irreducible; `W` is a nonempty open, hence irreducible. So `M_\omega` is irreducible, Porteous gives `m[M_\omega]` with `m\in\mathbf Z_{>0}`, and division by `m` over `\mathbf Q` is legitimate.

**What this costs Revision 2:** §2.1 is presented as self-contained and is placed *before* §2.5, but as repaired it is logically downstream of §2.5. The same is true of the smoothness of `M_\omega` invoked at line 272 ("Because `M_\omega` is smooth, `i^*` is a ring map"), which is nowhere proved except via §2.5. So §2.5 is load-bearing three times over — for `A^*(M_\omega)`, for CKgP of `M_\omega`, and (silently) for §2.1 and §2.6 — and it is the one section whose conclusion is asserted.

---

## REPAIR ADJUDICATION

**(a) Normalized sequence (10) vs. Liu's displayed formula for Corollary 3.6 — COMPLETE AND CORRECT.**
Liu's proof of Corollary 3.6 (`liu.txt:701–702`) writes `c(G)=c(f_*\omega_f)/c(L)`, which by Whitney on (9) (`liu.txt:513`) is `c(G')`, not `c(G)`, since `G=L^\vee\otimes G'`. From the normalized sequence (10) (`liu.txt:516`), `0\to\mathcal O\to L^\vee\otimes f_*\omega_f\to G\to0`, Whitney gives `c(G)=c(L^\vee\otimes f_*\omega_f)` exactly as `PROOF.md` §2.3 states. It suffices: `c_1(L)=2\psi_i` (Liu Prop. 3.5, `liu.txt:673–699`, whose proof I checked — `N^\vee_{D_i}=\sigma_i^*\omega_f` gives `c_1(L)=2\psi_i`) and the `\lambda_j` are tautological, so every `c_j(G)` is a polynomial in restrictions of tautological classes. The slip is harmless because `c(G')` is tautological too. I independently confirmed the normalization is not cosmetic: it is exactly what makes `M_\omega\to BG` exist, since dualizing (10) gives `0\to G^\vee\to L\otimes f_*\omega_f^\vee\to\mathcal O\to0`, matching `0\to F\to F'\to\mathcal O\to 0` on `BG` (`liu.txt:588–603`).

**(b) `\mu_5`-gerbe descent of CKgP by CL Lemma 3.6 — COMPLETE AND CORRECT, and genuinely necessary.**
CL Lemma 3.6 (`cl.txt:749–752`) states precisely what is needed and is proved by the isomorphism of Chow rings of all products. Liu's Corollary 3.9 (`liu.txt:752–753`) cites CL Lemmas 3.3, 3.4, 3.5, 3.7, 3.8 — Lemma 3.6 is indeed absent. Since the stratification is of `M_{5,8}` by `U_8` (not by `M'_{5,8}`), CKgP of `U_8` and not of `M'_{5,8}` is what Lemma 3.4 consumes, so this is a real omission in Liu correctly supplied here. Base change of a `\mu_5`-gerbe along `U_n\to B\mathrm{PGL}_5` is a `\mu_5`-gerbe (Liu p. 3, `liu.txt:122–128`); over `\mathbf C` the band is finite.

**(c) `B\mathrm{GL}_4\to BG` as a representable `\mathbf A^4`-bundle — COMPLETE AND CORRECT.**
`G` is Liu's `\{[[1,0],[*,\mathrm{GL}_4]]\}` (`liu.txt:588–600`), so `G\cong\mathbf G_a^4\rtimes\mathrm{GL}_4` and `B\mathrm{GL}_4=[G/\mathrm{GL}_4\,/\,G]=[\mathbf A^4/G]\to BG` is a torsor under a vector bundle, i.e. an affine bundle. CL Lemma 3.5 (`cl.txt:738–748`) then transfers CKgP from `B\mathrm{GL}_4` (Lemma 3.8(1), `cl.txt:763–772`) to `BG`. The direction matters and `PROOF.md` picks the right one: `BG\to B\mathrm{GL}_4` is *not* an affine bundle (its fibre is `B\mathbf G_a^4`), so Liu's `h` cannot be used. One correction to `PROOF.md`'s framing: Liu *does* cite CL Lemma 3.5 in Corollary 3.9; what Liu omits is the justification, offering only the ordinary Chow-ring isomorphism `A^*(BG)\cong A^*(B\mathrm{GL}_4)` (`liu.txt:666–667`). `PROOF.md`'s parenthetical observation about Liu's Proposition 4.3 dropping Lemma 3.5 (`liu.txt:869` vs `liu.txt:752–753`) is factually correct and is good evidence.

**(d) The family inverse for Liu Proposition 3.3, `PROOF.md` §2.5 — SUBSTANTIALLY CORRECT, WRITE-UP INCOMPLETE.**
This is the section the prompt asks me to press hardest, so in detail.

*What is right, and is a genuine advance over Liu.* Liu's Proposition 3.3 (`liu.txt:630–658`) constructs only `M_\omega\to G(3,\mathcal E)` and then asserts "Furthermore, `M_\omega` is isomorphic to an open locus `W` in `G(3,\mathcal E)`", describing `W` as the nets whose base locus is a complete intersection. **Liu's `W` is strictly too big.** On the locus where the universal hyperplane `\mathbf P F` is tangent to `C` at some `p_i` (`i\le7`), the residual point `p_8` coincides with `p_i`, and `(C;p_1,\dots,p_8)` is *not* an object of `M_{5,8}`. Revision 2's `W` (line 231) adds exactly the missing condition "`p_8` is disjoint from those seven sections". `PROOF.md` never flags that this corrects Liu rather than merely amplifying him; it should.

*Verification I performed.* All steps check out:
- `S\subset b_\omega^*\mathcal E` is legitimate and `\mathrm{rk}\,\mathcal E=15-7=8` (`liu.txt:618–628`); surjectivity of (12) on the image of `b_\omega` needs Lemma 3.2, and Lemma 3.2 applies because `C\cap H` is cut out in `H\cong\mathbf P^3` by the three restricted quadrics, which stay independent (a quadric containing `H` would be `H\cup H'`, forcing the nondegenerate `C` into a hyperplane) and cut out length `8=2^3`, hence a complete intersection.
- The seven sections lie on `C` by the defining property of `\mathcal E`; they are automatically pairwise disjoint on `V'`, since coincident points make (12) non-surjective — `PROOF.md`'s remark at line 246 is correct.
- `C\cap\mathbf P F` is automatically a relative Cartier divisor of degree 8 wherever `C` is a smooth complete intersection, since `(Q_1,Q_2,Q_3)` is saturated and contains no linear form, so no fibre lies in `H`. The "finite flat of degree 8" clause in `W` is therefore redundant but harmless.
- The residual `C\cap\mathbf P F-\sum_{i=1}^{7}p_i` is effective Cartier of degree 1 on a smooth relative curve, hence a section `p_8`. `\mathcal O(\sum_{i=1}^8p_i)=\mathcal O_C(1)=\omega_C`, so the object lies in `M_\omega`, and `C` smooth complete intersection of three quadrics in `\mathbf P^4` is automatically canonical, non-hyperelliptic and non-trigonal.
- Automorphisms do match: `G\to\mathrm{Stab}_{\mathrm{PGL}_5}(H)` is an isomorphism (normalize the scalar), and any `g` fixing `S` and `p_1,\dots,p_7` preserves `C` and `H`, hence fixes the residual `p_8`.

*The round trip, which `PROOF.md` asserts (line 236: "This is the inverse of Liu's map") but does not verify.* I verified it. On `W`, `\omega_{\mathbf P F'/BG}=\gamma'^*\det F'\otimes\mathcal O(-5)` and `\det N_{C/\mathbf P F'}=\det\mathcal S^\vee\otimes\mathcal O(6)`, so `\omega_f=j^*\mathcal O(1)\otimes f^*(\det F'\otimes\det\mathcal S^\vee)` and `f_*\omega_f=F'^\vee\otimes\det F'\otimes\det\mathcal S^\vee`. The trivialization of `F'/F` makes `\mathbf P F\in|\mathcal O_{\mathbf P F'}(1)|` a *canonical section*, so `\sum_i\sigma_i=j^*\mathbf P F` and `L=f_*\omega_f(-\sum\sigma_i)=\det F'\otimes\det\mathcal S^\vee`. Hence `L^\vee\otimes f_*\omega_f=F'^\vee` and `G=F^\vee`, i.e. sequence (10) recovers `0\to\mathcal O\to F'^\vee\to F^\vee\to0` on the nose, and `G^\vee=F` exactly as Liu states (`liu.txt:601–603`). The composite `W\to M_\omega\to G(3,\mathcal E)` is therefore the identity, and the other composite is the identity by construction. **With this computation added, §2.5 is a complete open immersion of stacks.** Without it, it is not.

*Where §2.5 fails as written.* Three things:
1. The round trip above is asserted, not computed. The one-line stand-in — "Sequence (10) trivializes `F'/F`" (line 239) — names the right mechanism but does not exhibit it.
2. The closing sentence, "the monomorphism is an open immersion of smooth stacks" (line 241), is a non-sequitur as stated: a monomorphism of smooth stacks of equal dimension is an open immersion only via miracle flatness (source Cohen–Macaulay, target regular, quasi-finite ⟹ flat; flat monomorphism locally of finite type ⟹ open immersion), which is not invoked. Worse, it uses smoothness of `M_\omega`, which in this document is available *only* as a consequence of `M_\omega\cong W`. Read as an independent proof, it is circular; read as a redundant remark after the inverse is constructed, it is fine — but the document does not say which.
3. Step 4 (line 224) attributes the residual-divisor construction to Lemma 3.2. Lemma 3.2 is needed for `\mathcal E` to be a bundle at all; the residual construction needs only disjointness. Misattribution, not an error.

**Adjudication: incomplete, and fillable exactly as above.**

**(e) Localization/gluing across `U_8`, `M_\omega`, `M^3_{5,8}`, incl. CL Lemma 9.9 — COMPLETE AND CORRECT.**
CL Lemma 9.9 (`cl.txt:1960–1963`): `g\ge4`, `n\le g+7`; at `(5,8)`, `8\le12` ✓, and it delivers both CKgP of `M^3_{5,8}` and tautologicality of all classes supported on it — both of which are used. The hyperelliptic input is CL Theorem 6.1 with `n\le2g+6=16` (`cl.txt:1156, 1964`) ✓. Liu's Corollary 3.9 does not list it ✓. One factual correction to `PROOF.md` line 284: Liu does not state this "only in the 'Idea of the proof'" — Liu also cites CL Lemma 9.9 explicitly in the proof of Corollary 2.11 (`liu.txt:451`), for `M_{5,7}`. The substantive point (absent from Corollary 3.9's citation list) stands. The two excision sequences (§4) and CL Lemma 3.4 (`cl.txt:726–737`) are applied correctly to the locally closed stratification `U_8\sqcup M_\omega\sqcup M^3_{5,8}`.

**(f) Porteous on `M_{5,8}\setminus M^3_{5,8}` — CORRECT AS A CHOICE, INCOMPLETE AS AN ARGUMENT.**
Restricting is legitimate and the codimension claim is right: `M_\omega` is the rank-`\le4` locus of a map of ranks `5\to8`, expected codimension `(5-4)(8-4)=4`; `\dim M_\omega=12+4=16` in a 20-dimensional ambient. The side remark that the global degeneracy locus has strictly higher-codimension pieces over lower gonality is also correct (trigonal: `11+4=15`, codim 5; hyperelliptic: `9+4=13`, codim 7). The Porteous *index* repair is right: with `e=5,f=8,k=4` the class is `\Delta^{f-k}_{e-k}=\Delta^4_1`, a `1\times1` determinant, i.e. `c_4(F-E)` — which is exactly Liu's displayed degree-4 expression (`liu.txt:496–506`); Liu's `\Delta^1_4` is a transposition of symbols only. What fails is the multiplicity step, as in STRONGEST ATTACK. Also: line 129 says each fibre of `M_\omega\to M_5\setminus M^3_5` "is an open in `|\omega_C|=\mathbf P^4`"; it is a finite cover of one (ordered points). Dimension unaffected.

**(g) Ionel as cohomological vanishing only — COMPLETE AND CORRECT.**
Ionel Theorem 0.1 (`ionel.txt:28–29`): for `g\ge2`, any product of degree at least `g` of descendant or tautological classes vanishes in `H^*(M_{g,n};\mathbf Q)`. `PROOF.md` uses it at `g=5`, degree 12, only on the cycle-class image, and states explicitly that Chow vanishing of `R^{12}` is neither used nor claimed (lines 330–337). That is the correct and honest reading; Ionel says herself that a Chow-level statement would require an algebro-geometric proof of degeneration formula (1.23) (`ionel.txt:64–66`). The generation claim needed — `R^*(M_{5,8})` generated by `\psi` and `\kappa`, with `\lambda` a `\kappa`-polynomial on the open stack — is correct (Liu Def. 1.1, `liu.txt:36–39`), so `R^{12}` is spanned by degree-12 monomials, each killed by Ionel. The pairing with CLP Lemma 4.3 is exactly right, and the sentence "Both halves are needed" (line 339) is a fair statement of the logic.

**(h) CLP Lemma 4.3, Grassmann presentations, BM dimension/weight/twist — CORRECT.**
CLP Lemma 4.3 (`clp.txt:615–625`) is quoted verbatim in content, including the hypothesis "open substack of a smooth proper Deligne–Mumford stack over `\mathbf C`" — satisfied by `M_{5,8}\subset\overline{\mathcal M}_{5,8}`. Degreewise it gives `A^{12}\twoheadrightarrow W_{24}H^{24}` ✓. The Grassmann/projective-bundle chain for `U_8` (§1.4) is correct: `B\mathrm{SL}_5` (CL 3.8(2)) → `(\mathbf P V)^n` (CL 3.7 iterated, a projective bundle being `G(1,-)`) → `V_n` (CL 3.3) → `G(3,\mathcal E)` (CL 3.7) → `X` (CL 3.3) → `U_8` (CL 3.6). Liu's dimension check reproduced at `PROOF.md` lines 88–91 is right (`-24+4n+3(12-n)=12+n`), as is `-20+21+15=16` at line 243. BM: see claim 4.

**(i) Liu Lemma 3.8 sign — COMPLETE AND CORRECT; `-\psi_i` is right, `3\psi_i` is wrong.**
I verified this independently of `PROOF.md`'s reasoning. Under `\mathbf P K=\mathrm{Proj}(\mathrm{Sym}^\bullet K^\vee)` (Liu p. 2, `liu.txt:87`), `\mathcal O(-1)\subset\pi^*K` is tautological, so `\mathcal O_{\mathbf P(K\otimes L)}(1)=\mathcal O_{\mathbf P K}(1)\otimes\pi^*L^\vee`. Geometrically: `p_i` corresponds to the line `\sigma_i^*\omega_f^\vee\subset f_*\omega_f^\vee`; inside `G^\vee=L\otimes G'^\vee` it is `L\otimes\sigma_i^*\omega_f^\vee`; its dual is `L^\vee\otimes\sigma_i^*\omega_f`, giving `c_1=\psi_i-2\psi_i=-\psi_i`. Liu's `\otimes a^*L` at `liu.txt:740` should be `\otimes a^*L^\vee`, yielding `3\psi_i` instead of `-\psi_i`. Harmless for tautologicality, as `PROOF.md` says, but it must not be propagated. Correctly handled.

**(j) Not repaired, and it should be: Liu Proposition 2.5.** Revision 2 demands a family inverse for Proposition 3.3 and then accepts Proposition 2.5 (`liu.txt:209–224, 320–346`) at face value in §1.2 — but Proposition 2.5 ends with the same unproved "Therefore, `M'_{5,n}` is isomorphic to `X`", and it is equally load-bearing (it is the sole support for `A^*(U_8)=R^*(U_8)` and for CKgP of `U_8`). Here the inverse genuinely is immediate — a point of `X` *is* a smooth canonical genus-5 curve with `n` marked points, the points are distinct because `V_n` excludes the diagonal, and no extra point must be manufactured, so Liu's `X` is not too big the way Liu's `W` is (and on `V_8` the condition `\omega_C\not\cong\mathcal O(\sum p_i)` is automatic by Proposition 2.1, `liu.txt:165–171`). So this is a documentation gap, not a mathematical one — but by Revision 2's own declared standard it is an unexplained asymmetry.

---

## LOCATORS

Line numbers refer to the extracted `.txt` files in `tmp/liu-audit/`.

- **Liu, arXiv:2509.02950v1** (`liu-2509.02950v1.txt`): Def. 1.1 `:26–39`; Def. 1.2 (CKgP) `:44–48`; convention `\mathbf P K` `:87`; characteristic `:91–92`; `M'_{5,n}` Cartesian square `:122–128`; Prop. 2.1 `:165–198`; `\mathcal E` and `V_n` `:202–208`; Prop. 2.5 `:209–224`, seq. (3) `:226–230`, seq. (5) `:300–310`, open `X` and minors (6) `:320–338`, conclusion `:341–346`; Lemma 2.7 `:352–390`; Lemma 2.8 `:391–432`; Cor. 2.9 `:433`; Cor. 2.11 (cites CL 9.9) `:435–457`; `M_\omega` defined `:468–480`; Prop. 3.1 + Porteous `\Delta^1_4` and display (8) `:481–507`; seqs. (9),(10) `:513–516`; Lemma 3.2 `:521–583`; `G` matrix form `:588–600`; `G^\vee\leftrightarrow F` `:601–603`; eval. (12) and `V'` `:618–628`; Prop. 3.3 `:630–658`; comp. (13) and `A^*(BG)\cong A^*(B\mathrm{GL}_4)` `:659–668`; Cor. 3.4 `:669–672`; Prop. 3.5 `:673–699`; Cor. 3.6 (`c(G)=c(f_*\omega_f)/c(L)`) `:700–703`; Lemma 3.7 `:704–716`; Lemma 3.8 (`\otimes a^*L`, `3\psi_i`) `:717–749`; Cor. 3.9 citation list `:750–753`; §4 group with no unipotent radical `:782–795`; Prop. 4.3 citation list `:867–869`.
- **Canning–Larson, arXiv:2208.02357** (`canning-larson-2208.02357.txt`): Def. 3.1 `:709–713`; Lemma 3.3 `:718–725`; Lemma 3.4 `:726–737`; Lemma 3.5 `:738–748`; Lemma 3.6 `:749–752`; Lemma 3.7 `:753–762`; Lemma 3.8 `:763–778`; Lemma 3.11 `:806–807`; Theorem 6.1 `:1156`; Lemma 9.9 `:1960–1992`.
- **Canning–Larson–Payne, arXiv:2307.08830** (`clp-2307.08830.txt`): Thm. 4.2(3)–(6) `:605–609`; Lemma 4.3 statement `:615–625`, proof `:629–667`; Table 1 `:675–678`.
- **Ionel, math/9908060v2** (`ionel-math9908060.txt`): abstract `:8–11`; Theorem 0.1 `:28–29`; Chow-level caveat `:64–66`.
- **Manuscript** `paper/degree16_genus_le7.tex`: Liu input and the two "harmless points" `:406–450`; Prop. Ionel–Looijenga `:455–474`; Cor. "The Liu input" `:476–499`; use in the main table `:134–141`.
- **Under review**: `tmp/liu-repaired/PROOF.md` §1.2 `:84–98`, §1.3 `:100–111`, §1.4 `:113–117`, §2.1 `:123–141`, §2.2 `:143–154`, §2.3 `:156–178`, §2.4 `:180–197`, §2.5 `:199–254`, §2.6 `:256–274`, §3 `:278–286`, §4 `:290–301`, §5 `:305–314`, §6 `:318–340`, §7 `:344–358`.

---

## REQUIRED CHANGES

**In `PROOF.md` (blocking):**

1. **§2.5 — complete the round trip.** Add the computation that `\omega_f=j^*\mathcal O(1)\otimes f^*(\det F'\otimes\det\mathcal S^\vee)`, hence `L=\det F'\otimes\det\mathcal S^\vee`, hence `L^\vee\otimes f_*\omega_f=F'^\vee` and `G=F^\vee`, so that sequence (10) built from the family over `W` reproduces the `BG`-datum `0\to F\to F'\to\mathcal O\to0` (Liu `:601–603`) and both composites are identities. Delete or demote the sentence "the monomorphism is an open immersion of smooth stacks" (line 241); if it is kept, state miracle flatness and note that it cannot be the source of the smoothness it presupposes.
2. **§2.1 — replace the multiplicity slogan.** State that `M_\omega` is irreducible (proof: §2.5 plus connectedness of `G`, as in STRONGEST ATTACK above), then invoke Fulton Thm. 14.4(c) to get `m[M_\omega]` with `m\in\mathbf Z_{>0}` and divide over `\mathbf Q`. Add a forward reference making the dependency of §2.1 on §2.5 explicit, or move §2.5 before §2.1.
3. **§2.6 — prove or cite smoothness of `M_\omega`.** Line 272 uses it; the only available source is §2.5. Say so.
4. **§2.5 — say that Liu's `W` is wrong, not merely underspecified.** State that the condition `p_8\notin\{p_1,\dots,p_7\}` (equivalently, `\mathbf P F` not tangent to `C` at a marked point) is *missing* from Liu's `W` (`liu.txt:656–658`), and that without it `W` contains points with no preimage in `M_{5,8}`.

**In `PROOF.md` (non-blocking, but required for the document to be accurate):**

5. §2.5 step 4 (line 224): Lemma 3.2 is what makes `\mathcal E` locally free of rank 8; the residual construction needs only disjointness. Fix the attribution. Also note that the "finite flat of degree 8" clause is automatic (`(Q_1,Q_2,Q_3)` saturated ⟹ `C` nondegenerate).
6. §3 line 284: Liu also cites CL Lemma 9.9 in the proof of Corollary 2.11 (`liu.txt:451`); the accurate claim is that it is absent from Corollary 3.9's citation list, not from the paper.
7. §2.4: make clear that Liu *does* cite CL Lemma 3.5 in Corollary 3.9; the repair supplies the missing justification (the representable `\mathbf A^4`-bundle), not a missing citation.
8. §1.2/§2.5: apply Revision 2's own standard to Liu Proposition 2.5 — state the inverse `X\to M'_{5,n}`, note that `V_n` excludes the diagonal and that `\omega_C\not\cong\mathcal O(\sum p_i)` on `V_8` is automatic by Proposition 2.1, and note that `\pi_1(W)` is closed because `\pi_1` is proper.
9. §2.1 line 129: a fibre of `M_\omega\to M_5\setminus M^3_5` is a finite cover of an open in `|\omega_C|`, not an open in it.
10. §1.1/§1.3: `M'_{5,n}` is defined by the Cartesian square, so its objects carry a *trivialized* determinant, not merely `c_1(V)=0`; and CL Lemma 3.6 needs no "unobstructedness" (line 51).

**In `paper/degree16_genus_le7.tex` (before this dependency is honest):**

11. Lines 406–450 currently cite Liu Corollary 3.9 as the input and describe the additions as "two harmless points … compressed in the preprint". That is not a fair description of the record. The manuscript must cite the repaired argument, and must state at least: (i) that Liu's Proposition 3.3 supplies no inverse and that the open locus there is stated incorrectly (missing `p_8\ne p_i`), together with the family inverse; (ii) CL Lemma 3.6 for the gerbe (already present, line 446–449 — keep); (iii) the affine-bundle justification for `BG` (already present, lines 426–431 — keep, but say Liu cites Lemma 3.5 without justifying it); (iv) CL Lemma 9.9 as an input not listed in Corollary 3.9 (partially present at line 420 — strengthen).
12. Line 422–423, "The Chow–Künneth assertion can likewise be read directly from the presentations in Liu's Propositions 2.5 and 3.3", must go. Proposition 3.3's presentation is exactly the step that does not stand as written.
13. Record the Lemma 3.8 sign (`-\psi_i`, not `3\psi_i`) and the Porteous index (`\Delta^4_1`), with the note that neither affects the conclusion, so that no downstream work propagates them.
14. Say in the text that arXiv:2509.02950v1 is unrefereed and that the manuscript's `M_{5,8}` row rests on a repaired version of it, not on Corollary 3.9 as printed.
