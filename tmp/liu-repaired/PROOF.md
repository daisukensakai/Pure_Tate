# The Liu input for `M_{5,8}`, with explicit repairs

This is a proposed proof, not a referee report. Treat every step as unproved
until checked against the primary sources. Liu's Corollary 3.9 is an unrefereed
preprint statement and is not an axiom. The manuscript must cite this repaired
argument, not Corollary 3.9 alone.

Revision 3 incorporates the Claude Rev2 required fills: the round-trip
computation for Liu Proposition 3.3; the correction that Liu's open `W` is
too big; irreducibility of `M_\omega` before Porteous multiplicity; the
inverse for Proposition 2.5; and the citation/justification distinctions
for Canning--Larson Lemmas 3.5, 3.6, and 9.9.

## Exact theorem

Work throughout over `\mathbf C` with rational Chow groups and rational mixed
Hodge structures. Let `M_{5,8}` be the smooth moduli stack of smooth
8-pointed genus-5 curves. Then

\[
A^*(\mathcal M_{5,8})=R^*(\mathcal M_{5,8}),
\qquad
\mathcal M_{5,8}\ \text{has the Chow--Künneth generation property},
\]
and consequently
\[
W_{24}H^{24}(\mathcal M_{5,8};\mathbf Q)=0,
\qquad
W_{-16}H^{\mathrm{BM}}_{16}(\mathcal M_{5,8};\mathbf Q)=0.
\]

No statement about `M_{5,9}` is made. No Betti number is computed. No Chow
vanishing in codimension 12 is asserted.

## Source status

- Yuhan Liu, *On the Chow rings of the moduli spaces `M_{5,8}` and `M_{5,9}`*,
  arXiv:2509.02950v1, 3 September 2025, PDF SHA-256
  `ada191f5012a45d57640ef4333c6e64e218babdb22aee4579110e5d1f0c66d5a`.
  Unrefereed. We use only the `M_{5,8}` half (Liu §§2--3). Liu §4 on `M_{5,9}`
  is not an input.
- Samir Canning and Hannah Larson, arXiv:2208.02357v2 (JEMS 2024).
- Canning--Larson--Payne, arXiv:2307.08830v3 (Forum Math. Pi 2024).
- Ionel, arXiv:math/9908060v2, Theorem 0.1.

## Characteristic

Liu works over an algebraically closed field of characteristic not `2,3,5`
(Liu p. 3). Canning--Larson work in characteristic `0` or `>5`. CLP Lemma 4.3
is stated over `\mathbf C`. The use here is over `\mathbf C`, so every
characteristic hypothesis is strictly satisfied. Canning--Larson Lemma 3.6
needs a gerbe banded by a finite group; the band is `\mu_5` and we are in
characteristic zero, which is the stated hypothesis. No extra
"unobstructedness" is used.

## Notation

Liu's convention: for a vector bundle `K`, `\mathbf P K := \mathrm{Proj}(\mathrm{Sym}^\bullet K^\vee)`.
`U_n` is the independent locus in `M_{5,n}\setminus M^3_{5,n}` (marked points
impose independent conditions on quadrics in the canonical `\mathbf P^4`).
`M'_{5,n}` is the `\mu_5`-gerbe over `U_n` obtained by the Cartesian square
`M'_{5,n} \to U_n` over `B\mathrm{SL}_5 \to B\mathrm{PGL}_5` (Liu p. 3).
Objects of `M'_{5,n}` therefore carry a *trivialized* determinant of the
canonical `\mathbf P^4`, not merely `c_1(V)=0`.
`M_\omega := (M_{5,8}\setminus M^3_{5,8})\setminus U_8` is the exceptional
canonical-divisor locus (Liu p. 8).

CKgP is Canning--Larson Definition 3.1: for every finite-type stack `X`
admitting a stratification by global quotient stacks, the exterior product
`A^*(Y)\otimes A^*(X)\to A^*(Y\times X)` is surjective.

---

## 1. Independent locus

### 1.1 Geometry of `U_n`

A non-trigonal, non-hyperelliptic genus-5 curve is a complete intersection of
three quadrics in its canonical `\mathbf P^4` (Max Noether). Liu Proposition 2.1
(p. 4): `\deg(\mathcal O_C(-2)(\Gamma)\otimes\omega_C)=n-8`. Thus for `n\le 7`
the marked points automatically impose independent conditions on quadrics; at
`n=8` they fail if and only if `\omega_C\cong\mathcal O(\sum p_i)`; the `n=9`
base-point argument is as in Liu p. 4.

The ambient object over `U_n` is a `\mathbf P^4`-*fibration*, not necessarily a
projectivized vector bundle (Brauer obstruction). Passage to `M'_{5,n}`
rigidifies this to `\mathbf P V` with trivialized determinant.

### 1.2 Presentation and inverse (Liu Proposition 2.5)

Liu constructs a morphism `M'_{5,n}\to G(3,\mathcal E)` over an open `V_n` in
`(\mathbf P V)^n`, with smoothness of the relative complete intersection cut
out by the `3\times 3` Jacobian minors (Liu (6), p. 6). Write `X` for that
open in `G(3,\mathcal E)`. Dimension check:
`\dim B\mathrm{SL}_5=-24`, plus `4n` for `(\mathbf P V)^n`, plus
`3(12-n)` for `G(3,\mathcal E)` with `\mathrm{rk}\,\mathcal E=15-n`, total
`12+n=\dim M_{5,n}`.

**Inverse `X\to M'_{5,n}`.** A point of `X` *is* a net of quadrics on
`\mathbf P V` whose base locus is a smooth complete intersection curve `C`
together with `n` marked points on `C` coming from `V_n`. The points are
distinct because `V_n` excludes the diagonal. The complete intersection of
three quadrics in `\mathbf P^4` is a canonically embedded non-trigonal
non-hyperelliptic genus-5 curve, and the Cartesian square to `B\mathrm{SL}_5`
trivializes `\det V`. On `V_8`, the condition `\omega_C\not\cong\mathcal O(\sum p_i)`
is automatic by Proposition 2.1, so the image lands in `U_8` rather than in
`M_\omega`. No residual point has to be manufactured, and Liu's `X` is not
too big. Both composites are identities by construction, so
`M'_{5,n}\cong X` is an open immersion into a Grassmann bundle.

Lemma 2.7: `f_*\omega_f=\det(\mathcal S^\vee)\otimes V^\vee` with trivialized
determinant gives `\lambda_1=5c_1(\det\mathcal S^\vee)` and `c_{2,\ldots,5}(V)`
polynomial in `\lambda`; `c_1(\eta_i^*\mathcal O(1))=\psi_i-\lambda_1/5`.
Lemma 2.8: the displayed GRR term is `R^1 f_*\omega_f^{\otimes 2}`, which
vanishes by relative duality from `f_*\omega_f^\vee=0`. Corollary 2.9:
`A^*(U_n)` is tautological for `n\le 12`. In particular this holds at `n=8`.

### 1.3 Repair: `\mu_5`-gerbe descent for CKgP

Liu records `A^*(M'_{5,n})\cong A^*(U_n)` from the gerbe, but CKgP is a
universal product assertion, not a statement about ordinary Chow rings of a
single stack. Canning--Larson Lemma 3.6 (p. 10): if `\pi:Y\to Y'` is a gerbe
banded by a finite group, then `Y` has CKgP if and only if `Y'` does, because
pullback is an isomorphism on Chow rings of all products with test stacks `X`.
The band is `\mu_5`, finite, and we are in characteristic zero, so Lemma 3.6
applies. Thus CKgP for `M'_{5,8}` is equivalent to CKgP for `U_8`.

Liu's Corollary 3.9 cites Canning--Larson Lemmas 3.3, 3.4, 3.5, 3.7, 3.8
and does not list Lemma 3.6. The gerbe permanence must be cited explicitly.
(The stratification of `M_{5,8}` is by `U_8`, not by `M'_{5,8}`, so CKgP of
`U_8` is what Lemma 3.4 consumes.)

### 1.4 CKgP for `U_8`

`B\mathrm{SL}_5` has CKgP (Canning--Larson Lemma 3.8(2)). Permanence under
projective bundles / Grassmann bundles (Lemma 3.7), open restriction
(Lemma 3.3), and the gerbe (Lemma 3.6) gives CKgP for `U_8`.

---

## 2. Exceptional locus `M_\omega`

The identification `M_\omega\cong W` in §2.5 is load-bearing for the class
`[M_\omega]`, for smoothness of `M_\omega`, for `A^*(M_\omega)=R^*(M_\omega)`,
and for CKgP of `M_\omega`. It is proved before those consequences are used.

### 2.1 Expected dimension (Liu Proposition 3.1)

Work on the open stack `M_{5,8}\setminus M^3_{5,8}`, not on all of `M_{5,8}`.
On this open, `M_\omega` is the rank-`\le 4` locus of
`f_*\omega_f\to\bigoplus_{i=1}^8\sigma_i^*\omega_f` (`e=5`, `f=8`, `k=4`).
Expected Porteous codimension is `(e-k)(f-k)=4`. Each fibre of
`M_\omega\to M_5\setminus M^3_5` is a finite cover of an open in
`|\omega_C|=\mathbf P^4` (ordered 8-tuples summing to a canonical divisor),
so `\dim M_\omega=12+4=16` inside the 20-dimensional ambient, and the actual
codimension is 4. Porteous therefore applies on this open. Any lower-gonality
components of the *global* degeneracy locus on `M_{5,8}` have strictly higher
codimension (trigonal: `11+4=15`, codimension 5; hyperelliptic: `9+4=13`,
codimension 7) and do not affect the codimension-4 class on
`M_{5,8}\setminus M^3_{5,8}`.

Tautologicality of `[M_\omega]` is postponed to §2.6: it needs irreducibility
of `M_\omega`, which is a consequence of §2.5.

Porteous index repair (not used by the manuscript, recorded for honesty):
in the Eisenbud--Harris convention of their Theorem 12.4, the class is
`\Delta^4_1` (the degree-4 part), i.e. `c_4` of the virtual bundle. Liu writes
`\Delta^1_4` but displays the degree-4 expression that is actually needed.
Both symbols are tautological; the displayed formula is the correct one.

### 2.2 Seven-point configurations (Liu Lemma 3.2)

If eight points in `\mathbf P^3` are a complete intersection of three quadrics,
then the first seven impose independent conditions on quadrics. The residual
sequence (11) reduces this to plane-quadric independence of `\Delta` plus linear
general position of `\Sigma`. The exhaustive case analysis on the maximal plane
`H` (7, 6, 5, 4, or 3 points) yields exactly three failure modes: seven coplanar;
six on a plane conic; four collinear. In each, every quadric through the seven
points contains a plane, a conic, or a line, so the three quadrics cannot cut
out a complete intersection (Bézout plus the exclusion of four collinear points
in the conic case). Hence evaluation (12) is surjective on the image of `b_\omega`,
so `\mathcal E` is locally free of rank `8`, and `p_8` is uniquely determined
by `p_1,\ldots,p_7`.

### 2.3 Normalized sequence and Chern classes of `G`

Liu (9)--(10), p. 9:
\[
0\to L\to f_*\omega_f\to G'\to 0,
\qquad
L:=f_*\omega_f(-\sigma_1-\cdots-\sigma_8),
\]
and after tensoring by `L^\vee`,
\[
0\to\mathcal O\to L^\vee\otimes f_*\omega_f\to G\to 0,
\qquad
G:=L^\vee\otimes G'.
\]
Whitney on the normalized sequence gives
\[
c(G)=c(L^\vee\otimes f_*\omega_f).
\]
Liu's proof of Corollary 3.6 displays instead `c(G)=c(f_*\omega_f)/c(L)`, which
is the formula for `G'`. The normalized formula is the one needed. It is enough:
`c_1(L)` is tautological by Proposition 3.5 (`c_1(L)=2\psi_i` on `M_\omega`),
and Chern classes of the Hodge bundle are tautological, so every `c_j(G)` is
tautological. This is the content of Corollary 3.6 as repaired.

The normalization is also what makes `M_\omega\to BG` exist: dualizing (10)
gives `0\to G^\vee\to L\otimes f_*\omega_f^\vee\to\mathcal O\to 0`, matching
`0\to F\to F'\to\mathcal O\to 0` on `BG` (Liu p. 11).

### 2.4 Repair: `B\mathrm{GL}_4\to BG` and CKgP

Let `G=\mathbf G_a^4\rtimes\mathrm{GL}_4` be Liu's hyperplane stabilizer in
`\mathrm{PGL}_5` (Liu p. 11). The Levi inclusion `\mathrm{GL}_4\hookrightarrow G`
induces `B\mathrm{GL}_4\to BG`. As schemes of groups,
`G/\mathrm{GL}_4\cong\mathbf G_a^4`, with `G` acting by translations and the
adjoint linear action, so `B\mathrm{GL}_4\to BG` is a representable affine
bundle with fibre `\mathbf A^4`. Canning--Larson Lemma 3.5 (p. 9): an affine
bundle has CKgP if and only if the base does, because pullback is an isomorphism
on Chow rings of all products with test stacks. Thus CKgP of `B\mathrm{GL}_4`
(Lemma 3.8(1)) yields CKgP of `BG`.

The load-bearing fact is this representable `\mathbf A^4`-bundle together with
Lemma 3.5. Liu *does* cite Lemma 3.5 in Corollary 3.9; what is missing is the
justification. Liu states only that `h:BG\to B\mathrm{GL}_4` induces an
isomorphism of ordinary Chow rings (p. 12). That is the
`X=\mathrm{Spec}\,\mathbf C` case of Lemma 3.5 and is not by itself the CKgP.
The opposite map `BG\to B\mathrm{GL}_4` is not an affine bundle (its fibre is
`B\mathbf G_a^4`), so Liu's `h` cannot be used in that direction. (Liu knows
the distinction: in Proposition 4.3, where the stabilizer of `(H,p_9)` is a
Levi with no unipotent radical, he drops Lemma 3.5 from the citation list.)

### 2.5 Repair: family inverse for Liu Proposition 3.3

Liu maps `M_\omega\to G(3,\mathcal E)` by the universal property of the
Grassmannian (`S\subset b_\omega^*\mathcal E` of rank 3) and then writes:
"Furthermore, `M_\omega` is isomorphic to an open locus `W` in `G(3,\mathcal E)`"
with no inverse and with `W` described only as the nets whose base locus is a
complete intersection (Liu pp. 11--12).

**Liu's `W` is too big, not merely underspecified.** On the locus where the
universal hyperplane `\mathbf P F` is tangent to `C` at some marked point
`p_i` with `i\le 7`, the residual point `p_8` coincides with `p_i`, and
`(C;p_1,\ldots,p_8)` is not an object of `M_{5,8}`. The condition
`p_8\notin\{p_1,\ldots,p_7\}` is missing from Liu's open, and without it `W`
contains points with no preimage in `M_{5,8}`.

Both `A^*=R^*` on `M_\omega` and CKgP of `M_\omega` use an identification with
an open in a Grassmann bundle. We construct the inverse in families and check
both composites.

Write `G(3,\mathcal E)\to V'\subset(\mathbf P F)^7\to\mathbf P F\to BG` for
Liu's composition (13), and let `\mathbf P F'` be the universal `\mathbf P^4`
over `BG`. Over `G(3,\mathcal E)`:

1. The universal rank-3 subbundle `\mathcal S\subset\mathcal E` determines a
   relative net of quadrics on the pulled-back fibration `\mathbf P F'`. Let
   `C\subset\mathbf P F'` be the corresponding relative complete intersection.
2. The seven projections `(\mathbf P F)^7\to\mathbf P F` supply seven sections
   of `\mathbf P F` over `V'`, hence seven sections of `C` after restriction to
   the open where `C` is a smooth curve. They are pairwise disjoint on `V'`:
   coincident points make evaluation (12) non-surjective, so the diagonal
   misses `V'`.
3. Let `H` be the universal hyperplane `\mathbf P F\subset\mathbf P F'`.
   Because the net `(Q_1,Q_2,Q_3)` is saturated and contains no linear form,
   no fibre of `C` lies in `H`. Thus wherever `C` is a smooth complete
   intersection, `C\cap\mathbf P F` is automatically a relative Cartier
   divisor of degree `8` (finite flat of degree 8 is not an extra open
   condition).
4. Lemma 3.2 is what makes `\mathcal E` locally free of rank 8. The residual
   construction itself uses only disjointness: the seven given sections form a
   relative Cartier divisor of degree 7 inside `C\cap\mathbf P F`, and the
   residual is a relative Cartier divisor of degree 1, i.e. a section `p_8`
   of `C`.
5. Define `W\subset G(3,\mathcal E)` to be the open locus on which `C` is a
   smooth complete intersection curve and `p_8` is disjoint from the seven
   given sections.

On `W`, the complete intersection of three quadrics in a fibre `\mathbf P^4`
is a canonically embedded non-trigonal non-hyperelliptic genus-5 curve, and
`\mathcal O(\sum_{i=1}^8 p_i)=\mathcal O_C(1)=\omega_C`, so the family
`(C;p_1,\ldots,p_8)` is an object of `M_\omega`. This defines
`\iota:W\to M_\omega`.

**Round trip.** Write `\gamma':\mathbf P F'\to BG`. Under Liu's convention
`\mathbf P K=\mathrm{Proj}(\mathrm{Sym}^\bullet K^\vee)` one has
`\omega_{\mathbf P F'/BG}=\gamma'^*\det F'\otimes\mathcal O(-5)`. The
normal bundle of the relative complete intersection of three quadrics is
`N_{C/\mathbf P F'}=\mathcal S^\vee\otimes\mathcal O(2)`, so
`\det N=\det\mathcal S^\vee\otimes\mathcal O(6)`. Adjunction therefore gives
\[
\omega_f=j^*\mathcal O(1)\otimes f^*(\det F'\otimes\det\mathcal S^\vee),
\]
and pushing forward,
\[
f_*\omega_f=F'^\vee\otimes\det F'\otimes\det\mathcal S^\vee.
\]
The trivialization of `F'/F` makes `\mathbf P F\in|\mathcal O_{\mathbf P F'}(1)|`
a canonical section, so `\sum_i\sigma_i=j^*\mathbf P F` as Cartier divisors on
`C` and
\[
L=f_*\omega_f\Bigl(-\sum\sigma_i\Bigr)=\det F'\otimes\det\mathcal S^\vee.
\]
Hence `L^\vee\otimes f_*\omega_f=F'^\vee` and `G=F^\vee`: sequence (10) built
from the family over `W` reproduces the `BG`-datum
`0\to F\to F'\to\mathcal O\to 0` on the nose (Liu p. 11). The composite
`W\to M_\omega\to G(3,\mathcal E)` is therefore the identity. The other
composite is the identity by construction of `\iota`. Thus
`M_\omega\cong W` as stacks.

**Automorphisms.** The map `G\to\mathrm{Stab}_{\mathrm{PGL}_5}(H)` is an
isomorphism (normalize the scalar). Any automorphism fixing `\mathcal S` and
`p_1,\ldots,p_7` preserves `C` and `H`, hence fixes the residual `p_8`.

**Smoothness.** `G(3,\mathcal E)` is smooth over `V'` over `BG`, and `W` is
open in it, so `W` is smooth. The isomorphism `M_\omega\cong W` therefore
makes `M_\omega` smooth. Smoothness is a consequence of the inverse, not an
input to it.

**Dimensions close twice:** `\dim BG=-20`, plus `21` for `(\mathbf P F)^7`,
plus `15` for `G(3,\mathcal E)` with `\mathrm{rk}\,\mathcal E=8`, total `16`;
and independently `12+4=16` from §2.1. The hyperplane `H` is unique because
`h^0(\omega(-\Sigma))=1`.

**Irreducibility.** `G=\mathbf G_a^4\rtimes\mathrm{GL}_4` is connected, so
`BG` is irreducible. `(\mathbf P F)^7` is an iterated projective bundle over
`BG`, hence irreducible. `V'` is a nonempty open in it (Liu evaluation (12)),
hence irreducible. `G(3,\mathcal E)` is a Grassmann bundle over `V'`, hence
irreducible. `W` is a nonempty open, hence irreducible. Therefore `M_\omega`
is irreducible.

Corollary 3.4 follows: `A^*(M_\omega)` is generated by `c_i(\mathcal S)`,
`c_1(b_\omega^*\eta_i^*\mathcal O_{\mathbf P F}(1))` for `i=1,\ldots,7`, and
`c_j(G)` for `j=1,\ldots,4`. Grassmann-bundle permanence (Canning--Larson
Lemma 3.7) plus open restriction (Lemma 3.3) plus CKgP of `BG` give CKgP of
`M_\omega`.

### 2.6 The class `[M_\omega]` is tautological

By §2.5, `M_\omega` is irreducible of the expected Porteous codimension 4 on
`M_{5,8}\setminus M^3_{5,8}`. Fulton, *Intersection Theory*, Theorem 14.4(c)
therefore returns a positive multiple `m[M_\omega]` of the fundamental class,
with `m\in\mathbf Z_{>0}`. Rational coefficients let us divide by `m`. The
Porteous class itself is a Chern class of a virtual bundle built from the
Hodge bundle and the cotangent lines, hence tautological. Thus `[M_\omega]`
is tautological. (The slogan that "rational coefficients absorb multiplicity"
is valid only after this irreducibility, which is why it was not used in
§2.1.)

### 2.7 Remaining generators

Proposition 3.5: `c_1(L)=2\psi_i` on `M_\omega`, so all `\psi_i` agree there
and `c_1(L)` is tautological. Corollary 3.6 as repaired in §2.3. Lemma 3.7:
`c_i(\mathcal S)` tautological by Whitney on
`0\to\mathcal S\to\mathrm{Sym}^2(f_*\omega_f\otimes L^\vee)\to f_*(\omega_f\otimes f^*L^\vee)^{\otimes 2}\to 0`
and GRR for `f_*\omega_f^{\otimes 2}`.

Lemma 3.8 sign (harmless, must not be propagated): with
`\mathbf P K=\mathrm{Proj}(\mathrm{Sym}^\bullet K^\vee)`, twisting `K` by `L`
twists `\mathcal O(1)` by `L^\vee`. Since `G^\vee=L\otimes G'^\vee`, one has
`\mathcal O_{\mathbf P G^\vee}(1)=g^*\mathcal O_{\mathbf P G'^\vee}(1)\otimes a^*L^\vee`,
hence `c_1(b_\omega^*\eta_i^*\mathcal O(1))=\psi_i-2\psi_i=-\psi_i`, not
`3\psi_i`. The class is still tautological; Liu's own §2 analogue uses the
correct convention. Any later citation must use `-\psi_i`.

By §2.5, `M_\omega` is smooth, so `i^*` is a ring map and ring generators
suffice. With `[M_\omega]` tautological by §2.6, push--pull shows every class
supported on `M_\omega` is tautological.

---

## 3. Lower-gonality locus

Canning--Larson Lemma 9.9 (p. 33): if `g\ge 4` and `n\le g+7`, then `M^3_{g,n}`
has CKgP and every class supported on it is tautological. At `(g,n)=(5,8)` one
has `8\le 12`. (The hyperelliptic input is their Theorem 6.1, `n\le 2g+6=16`.)
Liu cites Lemma 9.9 in the proof of Corollary 2.11 (for `M_{5,7}`) and mentions
it in the "Idea of the proof", but does not list it in the citation list of
Corollary 3.9. The excision sequences for `M_{5,8}\supset M^3_{5,8}` with open
complement `U_8\sqcup M_\omega` therefore require this citation explicitly.

---

## 4. Gluing: `A^*(M_{5,8})=R^*(M_{5,8})`

Two excision sequences:
\[
A^*(M^3_{5,8})\to A^*(M_{5,8})\to A^*(M_{5,8}\setminus M^3_{5,8})\to 0,
\]
\[
A^*(M_\omega)\to A^*(M_{5,8}\setminus M^3_{5,8})\to A^*(U_8)\to 0.
\]
The outer terms have tautological Chow rings (or tautological image under
pushforward): `U_8` by Corollary 2.9 plus gerbe, `M_\omega` by §§2.5--2.7,
`M^3_{5,8}` by Lemma 9.9. Hence `A^*(M_{5,8})=R^*(M_{5,8})`.

---

## 5. Gluing: CKgP for `M_{5,8}`

Canning--Larson Lemma 3.4 (stratification): a finite stratification by CKgP
strata implies CKgP. The three strata `U_8`, `M_\omega`, `M^3_{5,8}` each have
CKgP (§§1.4, 2.4--2.5, 3). Therefore `M_{5,8}` has CKgP.

This is the content of Liu's Corollary 3.9 after the repairs: normalized Chern
formula for `G`; Lemma 3.6 for the gerbe; the affine-bundle justification of
Lemma 3.5 for `BG`; Lemma 9.9 plus stratification for gluing; the inverse for
Proposition 2.5; and the family inverse and round trip for Proposition 3.3,
including the missing disjointness condition on `p_8`.

---

## 6. Lowest-weight vanishing

Canning--Larson--Payne Lemma 4.3 (pp. 12--13): if `X` is an open substack of a
smooth proper Deligne--Mumford stack over `\mathbf C` and `X` has CKgP, then
\[
\mathrm{cl}:\bigoplus_i A^i(X)\twoheadrightarrow\bigoplus_k W_k H^k(X).
\]
`M_{5,8}\subset\overline{\mathcal M}_{5,8}` qualifies. Thus
`W_{24}H^{24}(M_{5,8};\mathbf Q)` is the cycle-class image of
`A^{12}(M_{5,8})`. Combined with §4 this equals the cycle-class image of
`R^{12}(M_{5,8})`, i.e. `RH^{24}(M_{5,8};\mathbf Q)`.

Ionel Theorem 0.1 is a *cohomological* vanishing: for `g\ge 2` and `n>0`, any
product of descendant or tautological classes of degree `\ge g` vanishes in
`H^*(M_{g,n})`. It does not by itself give Chow vanishing. Here the relevant
degree is 12, corresponding to `RH^{24}`, and `12\ge g=5` with slack 7. On
the open moduli stack the tautological ring is generated by `\psi` and `\kappa`
(`\lambda` classes are `\kappa`-polynomials, Liu Definition 1.1), so Ionel
kills the cycle-class image of `R^{12}`. Chow vanishing of `R^{12}` is not
used and is not claimed. Hence `W_{24}H^{24}(M_{5,8};\mathbf Q)=0`.

Both halves are needed: Lemma 4.3 alone yields only `cl(A^{12})`; Ionel alone
kills only the tautological summand in cohomology.

---

## 7. Borel--Moore form

`\dim_{\mathbf C}M_{5,8}=3\cdot5-3+8=20`. Smooth Poincaré duality
(manuscript (eq:pd-smooth), line 199)
\[
H_i^{\mathrm{BM}}(X;\mathbf Q)\cong H^{2d-i}(X;\mathbf Q)(d)
\]
gives `H^{\mathrm{BM}}_{16}\cong H^{24}(20)`. Weights shift by `-2d=-40`, so
weight 24 in `H^{24}` corresponds to weight `-16` in `H^{\mathrm{BM}}_{16}`,
which is the lowest weight occurring in `H^{\mathrm{BM}}_{16}` of a smooth
20-fold (Deligne: weights on `H^k` of smooth `X` lie in `[k,2k]`). Therefore
\[
W_{-16}H^{\mathrm{BM}}_{16}(M_{5,8};\mathbf Q)
\cong W_{24}H^{24}(M_{5,8};\mathbf Q)(20)=0.
\]

## What a disproof must exhibit

A surviving non-tautological class in `A^*(M_{5,8})`; a failure of CKgP on one
of the three strata or in the gluing; a gap in the family inverse or round trip
of Proposition 3.3; reducibility of `M_\omega` spoiling the Porteous
multiplicity; a gap in CLP Lemma 4.3 or in Ionel's cohomological vanishing
at degree 12; or a dimension/weight/twist error in the Borel--Moore
identification. A correct but unrepaired reading of Liu's Corollary 3.9 is
not a disproof of this argument, and is not an available axiom.
