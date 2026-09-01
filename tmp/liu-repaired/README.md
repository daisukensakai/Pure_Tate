# Liu input, repaired (working directory)

Reserved git worktree / branch: `liu-claude-repairs`
Path: `/Users/ken/Desktop/Work/exploratory/Pure_Tate-liu-claude-repairs`

This directory holds a self-contained rewritten argument for the manuscript's
Liu dependency. Liu's Corollary 3.9 is not treated as an axiom. The manuscript
must cite this repaired argument, not Corollary 3.9 alone.

## Revisions

- Revision 1: Claude P1 repairs (normalized Chern formula; gerbe Lemma 3.6;
  affine bundle Lemma 3.5; pointwise inverse for Prop. 3.3; Lemma 9.9).
- Revision 2: Qwen P1 repairs. Family inverse for Prop. 3.3; Porteous on
  `M_{5,8} \ M^3_{5,8}`; Ionel only on the cycle-class image of `R^{12}`;
  Lemma 3.8 sign annotated as `-psi_i`.
- Revision 3 (current): Claude Rev2 fills. Round trip for Prop. 3.3;
  Liu's `W` too big; irreducibility before Porteous multiplicity; inverse
  for Prop. 2.5; citation vs justification for Lemmas 3.5 and 9.9.

## Attack surface for Codex

- `PROOF.md` — Revision 3 of the proposed argument (this is what to attack).
- `claims.json` — atomic claims L1--L10.
- `CODEX-P2-PROMPT.md` — independent rubric.
- Primary sources under `tmp/liu-audit/` (pinned hashes in `SOURCE-HASHES.json`).
- Manuscript use: `paper/degree16_genus_le7.tex`.

Do not treat Claude or Qwen reports as evidence. They are archival only.

## Exact theorem

Over `C` with rational coefficients:

1. `A^*(M_{5,8}) = R^*(M_{5,8})`
2. `M_{5,8}` has the Chow--Kunneth generation property
3. `W_{24} H^{24}(M_{5,8}; Q) = 0`
4. `W_{-16} H^{BM}_{16}(M_{5,8}; Q) = 0`

Section 4 of Liu (`M_{5,9}`) is not used. Chow vanishing of `R^{12}` is not
claimed.
