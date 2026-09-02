# Degree-sixteen cohomology in genus at most seven

This directory contains the second revised source package for the manuscript
“Degree-sixteen cohomology of moduli spaces of stable curves in genus at
most seven is Tate,” dated 2 September 2026.  The preceding version is
preserved in the sibling directory `degree16_genus_le7`.

## Contents

- `degree16_genus_le7.tex`: self-contained LaTeX source, including the
  bibliography.
- `degree16_genus_le7.pdf`: compiled manuscript.

The PDF was built with pdfTeX through `latexmk` and checked for undefined
citations, unresolved cross-references, and overfull boxes.  SHA-256 digests:

- `degree16_genus_le7.tex`:
  `5f80e754ae3cfacdd3d44c48750f42aefc57b93e46b3136fe513ef051f2b59b3`
- `degree16_genus_le7.pdf`:
  `92563ae86c0a8abdbe29605de177b39a6691f8d0d8ba2248b5ba7b7f50d81518`

Older manuscripts, proof attempts, campaign files, and audit reports in the
working repository are archival and are not part of this deposit.

## Mathematical scope

The unconditional theorem proved in the manuscript states that, for every
stable pair `(g,n)` with `g <= 7`,

`H^16(overline M_{g,n}; Q)`

is a direct sum of copies of `Q(-8)` as a polarizable rational Hodge
structure.  The critical open case `M_{5,8}` is handled directly by the
same one-marking argument as the other exceptional endpoints: the
Canning--Larson--Payne primitive quotient, virtual cohomological dimension,
their published `n=7=c(5)` Chow--Kunneth range, and Ionel's tautological
vanishing.  Consequently this version has no dependence on Liu's preprint
and does not require a separate genus-five appendix.

The global all-genera statement is not claimed unconditionally. The paper
proves that it follows from the two open genus-eight inputs for `(8,0)` and
`(8,1)`. The apparent case `(8,2)` vanishes by Wong's Theorem 4.1.

The manuscript determines Hodge type only. It does not compute an exact
Betti number and does not claim algebraic or tautological generation of the
compact degree-sixteen cohomology.
