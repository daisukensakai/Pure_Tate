# Target contract

For every pair of nonnegative integers $(g,n)$ satisfying
$2g-2+n>0$, determine whether

$$
H^{16}(\overline{\mathcal M}_{g,n};\mathbb Q)
\cong \mathbb Q(-8)^{\oplus b_{16}(g,n)}
$$

as rational Hodge structures.

## Fixed conventions

- $\overline{\mathcal M}_{g,n}$ is the smooth proper Deligne–Mumford **stack**, not its
  coarse moduli space.
- Cohomology is rational singular cohomology over $\mathbb C$.
- “Pure Tate” means a direct sum of copies of $\mathbb Q(-8)$ in degree $16$.
- Purity of weight $16$ is automatic from smooth properness and is not the target.
- Generation by algebraic cycles is stronger than the target.
- Generation by tautological cycles is stronger still.
- Arithmetic predictions and semisimplified $\ell$-adic statements are not accepted as
  proofs of the Hodge-structure statement.

## Stage-2 open-input convention

For a residual open stratum $\mathcal M_{g,n}$ of dimension
$d=3g-3+n$, the degree-16 boundary induction requires

$$
W_{-16}H^{BM}_{16}(\mathcal M_{g,n}),
$$

with expected Tate type $\mathbb Q(8)$. Poincaré duality realizes this group as

$$
W_{2d-16}H^{2d-16}(\mathcal M_{g,n})(d).
$$

Thus the untwisted ordinary-cohomology target has Tate type
$\mathbb Q(-(d-8))$ and Chow codimension $d-8$. This
dimension-dependent dictionary is canonical context revision 2.

## Completion conditions

A proof must cover every stable $(g,n)$. A disproof must exhibit a stable pair and a
nonzero off-diagonal Hodge summand in degree $16$. Conditional results must name every
unproved assumption.
