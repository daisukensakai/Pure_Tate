set_option autoImplicit false
-- LEAN-MODEL-WITNESS Every Claim.lean carrier is reinterpreted as a concrete arithmetic or list predicate on the same records, with no axioms at all. Kuenneth multi-indices are genuine lists of slots drawn from {0,1,2}, so total fibre degree and length are computed, not posited: a summand vanishes exactly when its base degree degree - total slots exceeds 4g-5, and restricts into Psi exactly when it either vanishes or actually contains a slot equal to two. A BM index is a finite Tate sum exactly when weight + 2*tateIndex = 0 and homologicalDegree + weight = 0; a pure index is one exactly when weight + 2*t = 0 and degree = weight; vcd is the real function vcdInt g n = 4g-5 for n = 0 and 4g-4+n for n >= 1; CKgP holds exactly for genus 6 with at most 5 markings; psi is Tate of index -1; the duality twist is forced to be 3g-3+n; and Q(a)(b) = Q(a+b) is literal Int addition. All thirty-four mathematical axioms of Claim.lean are theorems of this interpretation, so the Claim axiom set is consistent and the exported deduction is not vacuous.
-- LEAN-NONCOLLAPSE Thirteen witnesses, all proved by decide: model_nc00 (the exact BM target is satisfied here, so the axioms are jointly satisfiable together with the conclusion) and twelve refutations showing the load-bearing predicates are not definitionally True -- NC01 wrong BM Tate index 7; NC02 wrong BM homological degree 15; NC03 Q(-12) fails at weight 26; NC04 CKgP is unavailable at n = 6, the exact boundary of THM-0005; NC05 degree 19 is not above vcd(Mod_6) = 19 for local coefficients; NC06 degree 25 is not above vcd(PMod_{6,5}) = 25; NC07 a seven-slot all-ones multi-index does NOT vanish by base degree (26-7 = 19 is not above 19) and NC08 does not restrict into Psi either, since it contains no slot equal to two -- these two are exactly why the six-slot hypothesis is load-bearing and why the downward induction of CLM-0136-5 is needed; NC09 Phi_{6,6}^{24} does not vanish; NC10 Q(-13)(21) is not Q(7); NC11 the duality twist 20 is rejected; NC12 the omega_s repair fails at genus 1. model_nc13 records positively that a six-slot all-ones index does vanish, so the base case is non-empty rather than vacuously true.
-- LEAN-MODELS BMIsFiniteTateSum RestrictionSurjectsOnLowestWeight KunnethSplittingByChowKunnethProjectors ChowKunnethProjectorIsAlgebraicCorrespondence LerayDegeneratesAtE2 RTwoProjectorInPsiAndPullbackSpan KunnethSummandVanishes KunnethSummandRestrictsIntoPsi DualizingClassSlotDecomposition SlotOneCrossTermVanishes OmegaMultiplicationHitsSlotTwo PhiSpannedByForgetfulPullbacks PsiSpannedByPsiMultiples OrdinaryCohomologyVanishes LocalSystemCohomologyVanishesAllCoefficients PhiVanishes ContainedInPsi EqualsPsi PrimitiveQuotientIsLocalSystemSum PrimitiveQuotientVanishes PureIsFiniteTateSum PhiIsFiniteTateSum PsiIsQuotientOfFiniteTateSum PurePolarizableOfWeight PsiClassIsAlgebraicOfTateType ChowKunnethGenerationProperty CkgpMarkingBound CycleClassMapSurjectsOntoPureWeight VirtualCohomologicalDimension BorelMooreIsTwistOfPure TateTwistShift deligne_lowest_weight_restriction_surjection containment_transfers_along_surjection deligne_smooth_proper_leray_degeneration pty_projectors_are_algebraic_correspondences pty_r_two_projector_form kunneth_splitting_of_pure_weight_source omega_class_slot_decomposition morita_slot_one_vanishing omega_multiplication_hits_slot_two_modulo_errors harer_vcd_pointed constant_coefficient_vanishing_above_vcd phi_vanishes_from_pullback_source phi_is_pullback_span psi_is_psi_multiple_span harer_vcd_unpointed local_coefficient_vanishing_above_vcd kunneth_summand_vanishes_below_base_degree vanishing_summand_restricts_into_psi slot_two_summand_restricts_into_psi_modulo_errors clp_primitive_quotient_formula primitive_quotient_vanishes_from_local_coefficients equality_from_vanishing_primitive_quotient_and_phi ckgp_marking_bound_genus_six ckgp_holds_in_range cycle_class_surjectivity_from_ckgp algebraic_pure_weight_is_tate lowest_weight_is_pure_polarizable phi_tate_from_pullback_source psi_class_is_tate_divisor psi_products_are_tate_quotient polarizable_semisimplicity_upgrade poincare_duality_bm_twist tate_twist_shift_add bm_tate_sum_from_twisted_pure
-- LEAN-MODEL-THEOREM c66_model_is_consistent_and_noncollapsing

-- ---------------------------------------------------------------------------
-- The Claim.lean vocabulary, re-declared concretely.  Model.lean stands alone.
-- ---------------------------------------------------------------------------

structure BMTargetIndex where
  genus : Int
  markings : Int
  homologicalDegree : Int
  weight : Int
  tateIndex : Int

abbrev exactC66BMTarget : BMTargetIndex :=
  { genus := 6, markings := 6, homologicalDegree := 16, weight := -16, tateIndex := 8 }

structure ModuliIndex where
  genus : Int
  markings : Int

structure PureIndex where
  space : ModuliIndex
  degree : Int
  weight : Int

inductive Slot where
  | zero : Slot
  | one : Slot
  | two : Slot

def slotVal : Slot -> Nat
  | Slot.zero => 0
  | Slot.one => 1
  | Slot.two => 2

def total : List Slot -> Nat
  | [] => 0
  | a :: rest => slotVal a + total rest

def lenOf : List Slot -> Nat
  | [] => 0
  | _ :: rest => 1 + lenOf rest

def hasTwo : List Slot -> Bool
  | [] => false
  | Slot.two :: _ => true
  | _ :: rest => hasTwo rest

structure KunnethIndex where
  base : ModuliIndex
  slots : List Slot
  degree : Int
  weight : Int

structure LocalSystemIndex where
  genus : Int
  degree : Int
  weight : Int
  partitionSize : Int

abbrev moduliM6 : ModuliIndex := { genus := 6, markings := 0 }

abbrev moduliM65 : ModuliIndex := { genus := 6, markings := 5 }

abbrev moduliM66 : ModuliIndex := { genus := 6, markings := 6 }

abbrev pureM66deg26 : PureIndex := { space := moduliM66, degree := 26, weight := 26 }

abbrev pureM66deg24 : PureIndex := { space := moduliM66, degree := 24, weight := 24 }

abbrev vcdInt (genus markings : Int) : Int :=
  if markings = 0 then 4 * genus - 5 else 4 * genus - 4 + markings

abbrev vcdOf (X : ModuliIndex) : Int := vcdInt X.genus X.markings

theorem vcdInt_unpointed (genus markings : Int) (h : markings = 0) :
    vcdInt genus markings = 4 * genus - 5 := by
  show (if markings = 0 then 4 * genus - 5 else 4 * genus - 4 + markings) = 4 * genus - 5
  exact if_pos h

theorem vcdInt_pointed (genus markings : Int) (h : ¬ (markings = 0)) :
    vcdInt genus markings = 4 * genus - 4 + markings := by
  show (if markings = 0 then 4 * genus - 5 else 4 * genus - 4 + markings)
      = 4 * genus - 4 + markings
  exact if_neg h

-- The genuine combinatorial fact behind the slot-two step of the model.
theorem hasTwo_split (pre post : List Slot) :
    hasTwo (pre ++ Slot.two :: post) = true := by
  induction pre with
  | nil => rfl
  | cons b t ih =>
      cases b with
      | zero => exact ih
      | one => exact ih
      | two => rfl

-- The interpretation of every Claim.lean carrier.

abbrev BMIsFiniteTateSum (bm : BMTargetIndex) : Prop :=
  bm.weight + 2 * bm.tateIndex = 0 ∧ bm.homologicalDegree + bm.weight = 0

abbrev RestrictionSurjectsOnLowestWeight (src tgt : PureIndex) : Prop :=
  src.space = tgt.space ∧ src.degree = tgt.degree ∧ src.weight = tgt.weight ∧
    src.degree = src.weight

abbrev KunnethSplittingByChowKunnethProjectors (src : PureIndex) : Prop :=
  src.degree = src.weight

abbrev ChowKunnethProjectorIsAlgebraicCorrespondence (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

abbrev LerayDegeneratesAtE2 (X : ModuliIndex) : Prop := 2 ≤ X.genus ∧ X.markings = 0

abbrev RTwoProjectorInPsiAndPullbackSpan (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

abbrev KunnethSummandVanishes (idx : KunnethIndex) : Prop :=
  4 * idx.base.genus - 5 < idx.degree - (total idx.slots : Int)

abbrev KunnethSummandRestrictsIntoPsi (idx : KunnethIndex) (_tgt : PureIndex) : Prop :=
  KunnethSummandVanishes idx ∨ hasTwo idx.slots = true

abbrev DualizingClassSlotDecomposition (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

abbrev SlotOneCrossTermVanishes (X : ModuliIndex) : Prop := 2 ≤ X.genus ∧ X.markings = 0

abbrev OmegaMultiplicationHitsSlotTwo (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

abbrev PhiSpannedByForgetfulPullbacks (p q : PureIndex) : Prop :=
  q.space.genus = p.space.genus ∧ q.space.markings = p.space.markings - 1 ∧
    q.degree = p.degree ∧ q.weight = p.weight

abbrev PsiSpannedByPsiMultiples (p r : PureIndex) : Prop :=
  r.space = p.space ∧ r.degree = p.degree - 2 ∧ r.weight = p.weight - 2

abbrev OrdinaryCohomologyVanishes (X : ModuliIndex) (d : Int) : Prop := vcdOf X < d

abbrev LocalSystemCohomologyVanishesAllCoefficients (X : ModuliIndex) (d : Int) : Prop :=
  X.markings = 0 ∧ vcdOf X < d

abbrev PhiVanishes (p : PureIndex) : Prop :=
  vcdInt p.space.genus (p.space.markings - 1) < p.degree

abbrev ContainedInPsi (p : PureIndex) : Prop := p.degree = p.weight

abbrev PrimitiveQuotientVanishes (p : PureIndex) : Prop :=
  4 * p.space.genus - 5 < p.degree - p.space.markings

abbrev EqualsPsi (p : PureIndex) : Prop :=
  PrimitiveQuotientVanishes p ∧ PhiVanishes p

abbrev PrimitiveQuotientIsLocalSystemSum (p : PureIndex) (prim : LocalSystemIndex) : Prop :=
  prim.genus = p.space.genus ∧ prim.degree = p.degree - p.space.markings ∧
    prim.weight = p.weight ∧ prim.partitionSize = p.space.markings

abbrev PureIsFiniteTateSum (p : PureIndex) (t : Int) : Prop :=
  p.weight + 2 * t = 0 ∧ p.degree = p.weight

abbrev PhiIsFiniteTateSum (p : PureIndex) (t : Int) : Prop :=
  p.weight + 2 * t = 0 ∧ p.degree = p.weight

abbrev PsiIsQuotientOfFiniteTateSum (p : PureIndex) (t : Int) : Prop :=
  p.weight + 2 * t = 0 ∧ p.degree = p.weight

abbrev PurePolarizableOfWeight (p : PureIndex) : Prop := p.degree = p.weight

abbrev PsiClassIsAlgebraicOfTateType (X : ModuliIndex) (t : Int) : Prop :=
  1 ≤ X.markings ∧ t = -1

abbrev ChowKunnethGenerationProperty (X : ModuliIndex) : Prop :=
  X.genus = 6 ∧ X.markings ≤ 5

abbrev CkgpMarkingBound (g b : Int) : Prop := g = 6 ∧ b = 5

abbrev CycleClassMapSurjectsOntoPureWeight (p : PureIndex) : Prop :=
  p.degree = p.weight ∧ p.space.genus = 6 ∧ p.space.markings ≤ 5

abbrev VirtualCohomologicalDimension (X : ModuliIndex) (v : Int) : Prop := v = vcdOf X

abbrev BorelMooreIsTwistOfPure (bm : BMTargetIndex) (p : PureIndex) (d : Int) : Prop :=
  bm.genus = p.space.genus ∧ bm.markings = p.space.markings ∧
    d = 3 * bm.genus - 3 + bm.markings ∧
    p.degree = 2 * d - bm.homologicalDegree ∧ p.weight = p.degree ∧
    bm.weight = p.weight - 2 * d

abbrev TateTwistShift (a b u : Int) : Prop := u = a + b

-- ---------------------------------------------------------------------------
-- The thirty-four mathematical axiom statements of Claim.lean, as Props.
-- ---------------------------------------------------------------------------

abbrev AX01 : Prop := ∀ (src tgt : PureIndex), src.space = tgt.space →
  src.degree = tgt.degree → src.weight = tgt.weight → src.degree = src.weight →
  RestrictionSurjectsOnLowestWeight src tgt

abbrev AX02 : Prop := ∀ (src tgt : PureIndex) (base : ModuliIndex),
  RestrictionSurjectsOnLowestWeight src tgt →
  (∀ (idx : KunnethIndex), idx.base = base → idx.degree = tgt.degree →
    idx.weight = tgt.weight → lenOf idx.slots = 6 →
    KunnethSummandRestrictsIntoPsi idx tgt) →
  KunnethSplittingByChowKunnethProjectors src → ContainedInPsi tgt

abbrev AX03 : Prop := ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
  LerayDegeneratesAtE2 base

abbrev AX04 : Prop := ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
  ChowKunnethProjectorIsAlgebraicCorrespondence base

abbrev AX05 : Prop := ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
  RTwoProjectorInPsiAndPullbackSpan base

abbrev AX06 : Prop := ∀ (src : PureIndex) (base : ModuliIndex),
  LerayDegeneratesAtE2 base → ChowKunnethProjectorIsAlgebraicCorrespondence base →
  RTwoProjectorInPsiAndPullbackSpan base → base.genus = src.space.genus →
  base.markings = 0 → src.degree = src.weight →
  KunnethSplittingByChowKunnethProjectors src

abbrev AX07 : Prop := ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
  DualizingClassSlotDecomposition base

abbrev AX08 : Prop := ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
  SlotOneCrossTermVanishes base

abbrev AX09 : Prop := ∀ (base : ModuliIndex), DualizingClassSlotDecomposition base →
  SlotOneCrossTermVanishes base → RTwoProjectorInPsiAndPullbackSpan base →
  OmegaMultiplicationHitsSlotTwo base

abbrev AX10 : Prop := ∀ (base : ModuliIndex) (v : Int), 2 ≤ base.genus →
  1 ≤ base.markings → v = 4 * base.genus - 4 + base.markings →
  VirtualCohomologicalDimension base v

abbrev AX11 : Prop := ∀ (base : ModuliIndex) (v d : Int),
  VirtualCohomologicalDimension base v → v < d → OrdinaryCohomologyVanishes base d

abbrev AX12 : Prop := ∀ (p q : PureIndex), PhiSpannedByForgetfulPullbacks p q →
  OrdinaryCohomologyVanishes q.space q.degree → PhiVanishes p

abbrev AX13 : Prop := ∀ (p q : PureIndex), q.space.genus = p.space.genus →
  q.space.markings = p.space.markings - 1 → q.degree = p.degree → q.weight = p.weight →
  PhiSpannedByForgetfulPullbacks p q

abbrev AX14 : Prop := ∀ (p r : PureIndex), r.space = p.space →
  r.degree = p.degree - 2 → r.weight = p.weight - 2 → PsiSpannedByPsiMultiples p r

abbrev AX15 : Prop := ∀ (base : ModuliIndex) (v : Int), 2 ≤ base.genus →
  base.markings = 0 → v = 4 * base.genus - 5 → VirtualCohomologicalDimension base v

abbrev AX16 : Prop := ∀ (base : ModuliIndex) (v d : Int),
  VirtualCohomologicalDimension base v → base.markings = 0 → v < d →
  LocalSystemCohomologyVanishesAllCoefficients base d

abbrev AX17 : Prop := ∀ (idx : KunnethIndex) (v : Int),
  LocalSystemCohomologyVanishesAllCoefficients idx.base
    (idx.degree - (total idx.slots : Int)) →
  VirtualCohomologicalDimension idx.base v →
  v < idx.degree - (total idx.slots : Int) → KunnethSummandVanishes idx

abbrev AX18 : Prop := ∀ (idx : KunnethIndex) (tgt : PureIndex),
  KunnethSummandVanishes idx → KunnethSummandRestrictsIntoPsi idx tgt

abbrev AX19 : Prop :=
  ∀ (idx errZero errOne : KunnethIndex) (pre post : List Slot)
    (tgt src r q : PureIndex) (base5 : ModuliIndex),
  idx.slots = pre ++ Slot.two :: post → errZero.base = idx.base →
  errZero.degree = idx.degree → errZero.weight = idx.weight →
  errZero.slots = pre ++ Slot.zero :: post → errOne.base = idx.base →
  errOne.degree = idx.degree → errOne.weight = idx.weight →
  errOne.slots = pre ++ Slot.one :: post → OmegaMultiplicationHitsSlotTwo idx.base →
  RestrictionSurjectsOnLowestWeight src tgt → PsiSpannedByPsiMultiples tgt r →
  PhiSpannedByForgetfulPullbacks r q → base5.genus = tgt.space.genus →
  base5.markings = tgt.space.markings - 1 → q.space = base5 →
  OrdinaryCohomologyVanishes base5 tgt.degree →
  KunnethSummandRestrictsIntoPsi errOne tgt → KunnethSummandRestrictsIntoPsi idx tgt

abbrev AX20 : Prop := ∀ (p : PureIndex) (prim : LocalSystemIndex), 2 ≤ p.space.genus →
  1 ≤ p.space.markings → p.degree = p.weight → prim.genus = p.space.genus →
  prim.degree = p.degree - p.space.markings → prim.weight = p.weight →
  prim.partitionSize = p.space.markings → PrimitiveQuotientIsLocalSystemSum p prim

abbrev AX21 : Prop := ∀ (p : PureIndex) (prim : LocalSystemIndex),
  PrimitiveQuotientIsLocalSystemSum p prim →
  LocalSystemCohomologyVanishesAllCoefficients { genus := prim.genus, markings := 0 }
    prim.degree → PrimitiveQuotientVanishes p

abbrev AX22 : Prop := ∀ (p : PureIndex), PrimitiveQuotientVanishes p → PhiVanishes p →
  EqualsPsi p

abbrev AX23 : Prop := CkgpMarkingBound 6 5

abbrev AX24 : Prop := ∀ (base : ModuliIndex) (b : Int), CkgpMarkingBound base.genus b →
  base.markings ≤ b → ChowKunnethGenerationProperty base

abbrev AX25 : Prop := ∀ (base : ModuliIndex) (p : PureIndex),
  ChowKunnethGenerationProperty base → p.space = base → p.degree = p.weight →
  CycleClassMapSurjectsOntoPureWeight p

abbrev AX26 : Prop := ∀ (p : PureIndex) (c : Int),
  CycleClassMapSurjectsOntoPureWeight p → PurePolarizableOfWeight p →
  p.degree = 2 * c → p.weight = p.degree → PureIsFiniteTateSum p (-c)

abbrev AX27 : Prop := ∀ (p : PureIndex), p.degree = p.weight → PurePolarizableOfWeight p

abbrev AX28 : Prop := ∀ (p q : PureIndex) (t : Int),
  PhiSpannedByForgetfulPullbacks p q → PureIsFiniteTateSum q t → PhiIsFiniteTateSum p t

abbrev AX29 : Prop := ∀ (base : ModuliIndex), 1 ≤ base.markings →
  PsiClassIsAlgebraicOfTateType base (-1)

abbrev AX30 : Prop := ∀ (p r : PureIndex) (a b t : Int), PsiSpannedByPsiMultiples p r →
  PsiClassIsAlgebraicOfTateType p.space a → PhiIsFiniteTateSum r b →
  p.degree = r.degree + 2 → p.weight = r.weight + 2 → t = a + b →
  PsiIsQuotientOfFiniteTateSum p t

abbrev AX31 : Prop := ∀ (p : PureIndex) (t : Int), ContainedInPsi p →
  PurePolarizableOfWeight p → PsiIsQuotientOfFiniteTateSum p t → PureIsFiniteTateSum p t

abbrev AX32 : Prop := ∀ (bm : BMTargetIndex) (p : PureIndex) (d : Int),
  bm.genus = p.space.genus → bm.markings = p.space.markings →
  d = 3 * bm.genus - 3 + bm.markings → p.degree = 2 * d - bm.homologicalDegree →
  p.weight = p.degree → bm.weight = p.weight - 2 * d → BorelMooreIsTwistOfPure bm p d

abbrev AX33 : Prop := ∀ (a b u : Int), u = a + b → TateTwistShift a b u

abbrev AX34 : Prop := ∀ (bm : BMTargetIndex) (p : PureIndex) (d t u : Int),
  BorelMooreIsTwistOfPure bm p d → PureIsFiniteTateSum p t → TateTwistShift t d u →
  bm.tateIndex = u → BMIsFiniteTateSum bm

-- ---------------------------------------------------------------------------
-- Each is a theorem of the interpretation.
-- ---------------------------------------------------------------------------

theorem model_ax01 : AX01 := by intro _ _ h1 h2 h3 h4; exact ⟨h1, h2, h3, h4⟩

theorem model_ax02 : AX02 := by
  intro src tgt _ h1 _ _
  have hd : src.degree = tgt.degree := h1.2.1
  have hw : src.weight = tgt.weight := h1.2.2.1
  have he : src.degree = src.weight := h1.2.2.2
  show tgt.degree = tgt.weight
  omega

theorem model_ax03 : AX03 := by intro _ h1 h2; exact ⟨h1, h2⟩

theorem model_ax04 : AX04 := by intro _ h1 h2; exact ⟨h1, h2⟩

theorem model_ax05 : AX05 := by intro _ h1 h2; exact ⟨h1, h2⟩

theorem model_ax06 : AX06 := by intro _ _ _ _ _ _ _ h6; exact h6

theorem model_ax07 : AX07 := by intro _ h1 h2; exact ⟨h1, h2⟩

theorem model_ax08 : AX08 := by intro _ h1 h2; exact ⟨h1, h2⟩

theorem model_ax09 : AX09 := by intro _ h1 h2 _; exact ⟨h1.1, h2.2⟩

theorem model_ax10 : AX10 := by
  intro base v _ h2 h3
  have hne : ¬ (base.markings = 0) := by omega
  show v = vcdInt base.genus base.markings
  rw [vcdInt_pointed base.genus base.markings hne]
  exact h3

theorem model_ax11 : AX11 := by
  intro base v d h1 h2
  have hv : v = vcdOf base := h1
  show vcdOf base < d
  omega

theorem model_ax12 : AX12 := by
  intro p q h1 h2
  have hg : q.space.genus = p.space.genus := h1.1
  have hm : q.space.markings = p.space.markings - 1 := h1.2.1
  have hd : q.degree = p.degree := h1.2.2.1
  have hv : vcdInt q.space.genus q.space.markings < q.degree := h2
  show vcdInt p.space.genus (p.space.markings - 1) < p.degree
  rw [← hg, ← hm, ← hd]
  exact hv

theorem model_ax13 : AX13 := by intro _ _ h1 h2 h3 h4; exact ⟨h1, h2, h3, h4⟩

theorem model_ax14 : AX14 := by intro _ _ h1 h2 h3; exact ⟨h1, h2, h3⟩

theorem model_ax15 : AX15 := by
  intro base v _ h2 h3
  show v = vcdInt base.genus base.markings
  rw [vcdInt_unpointed base.genus base.markings h2]
  exact h3

theorem model_ax16 : AX16 := by
  intro base v d h1 h2 h3
  have hv : v = vcdOf base := h1
  exact ⟨h2, by omega⟩

theorem model_ax17 : AX17 := by
  intro idx v h1 h2 h3
  have hm : idx.base.markings = 0 := h1.1
  have hv : v = vcdOf idx.base := h2
  have hvc : vcdInt idx.base.genus idx.base.markings = 4 * idx.base.genus - 5 :=
    vcdInt_unpointed idx.base.genus idx.base.markings hm
  have hv2 : v = 4 * idx.base.genus - 5 := by rw [← hvc]; exact hv
  show 4 * idx.base.genus - 5 < idx.degree - (total idx.slots : Int)
  omega

theorem model_ax18 : AX18 := by intro _ _ h; exact Or.inl h

theorem model_ax19 : AX19 := by
  intro idx _ _ pre post _ _ _ _ _
  intro hsplit
  intro _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
  refine Or.inr ?_
  rw [hsplit]
  exact hasTwo_split pre post

theorem model_ax20 : AX20 := by intro _ _ _ _ _ h4 h5 h6 h7; exact ⟨h4, h5, h6, h7⟩

theorem model_ax21 : AX21 := by
  intro p prim h1 h2
  have hg : prim.genus = p.space.genus := h1.1
  have hd : prim.degree = p.degree - p.space.markings := h1.2.1
  have hlt : vcdOf { genus := prim.genus, markings := 0 } < prim.degree := h2.2
  have hvc : vcdInt prim.genus 0 = 4 * prim.genus - 5 := vcdInt_unpointed prim.genus 0 rfl
  have hlt2 : 4 * prim.genus - 5 < prim.degree := by rw [← hvc]; exact hlt
  show 4 * p.space.genus - 5 < p.degree - p.space.markings
  omega

theorem model_ax22 : AX22 := by intro _ h1 h2; exact ⟨h1, h2⟩

theorem model_ax23 : AX23 := ⟨rfl, rfl⟩

theorem model_ax24 : AX24 := by
  intro base b h1 h2
  have hg : base.genus = 6 := h1.1
  have hb : b = 5 := h1.2
  show base.genus = 6 ∧ base.markings ≤ 5
  exact ⟨hg, by omega⟩

theorem model_ax25 : AX25 := by
  intro base p h1 h2 h3
  show p.degree = p.weight ∧ p.space.genus = 6 ∧ p.space.markings ≤ 5
  rw [h2]
  exact ⟨h3, h1.1, h1.2⟩

theorem model_ax26 : AX26 := by
  intro p c _ _ h3 h4
  show p.weight + 2 * (-c) = 0 ∧ p.degree = p.weight
  exact ⟨by omega, by omega⟩

theorem model_ax27 : AX27 := by intro _ h; exact h

theorem model_ax28 : AX28 := by
  intro p q t h1 h2
  have hd : q.degree = p.degree := h1.2.2.1
  have hw : q.weight = p.weight := h1.2.2.2
  have ha : q.weight + 2 * t = 0 := h2.1
  have hb : q.degree = q.weight := h2.2
  show p.weight + 2 * t = 0 ∧ p.degree = p.weight
  exact ⟨by omega, by omega⟩

theorem model_ax29 : AX29 := by intro _ h; exact ⟨h, rfl⟩

theorem model_ax30 : AX30 := by
  intro p r a b t _ h2 h3 h4 h5 h6
  have ha : a = -1 := h2.2
  have h3a : r.weight + 2 * b = 0 := h3.1
  have h3b : r.degree = r.weight := h3.2
  show p.weight + 2 * t = 0 ∧ p.degree = p.weight
  exact ⟨by omega, by omega⟩

theorem model_ax31 : AX31 := by intro _ _ _ _ h3; exact h3

theorem model_ax32 : AX32 := by intro _ _ _ h1 h2 h3 h4 h5 h6; exact ⟨h1, h2, h3, h4, h5, h6⟩

theorem model_ax33 : AX33 := by intro _ _ _ h; exact h

theorem model_ax34 : AX34 := by
  intro bm p d t u h1 h2 h3 h4
  have hd : p.degree = 2 * d - bm.homologicalDegree := h1.2.2.2.1
  have hw : p.weight = p.degree := h1.2.2.2.2.1
  have hbw : bm.weight = p.weight - 2 * d := h1.2.2.2.2.2
  have hp : p.weight + 2 * t = 0 := h2.1
  have hu : u = t + d := h3
  show bm.weight + 2 * bm.tateIndex = 0 ∧ bm.homologicalDegree + bm.weight = 0
  exact ⟨by omega, by omega⟩

-- ---------------------------------------------------------------------------
-- Non-collapse.
-- ---------------------------------------------------------------------------

abbrev sixOnes : List Slot :=
  [Slot.one, Slot.one, Slot.one, Slot.one, Slot.one, Slot.one]

abbrev sevenOnes : List Slot :=
  [Slot.one, Slot.one, Slot.one, Slot.one, Slot.one, Slot.one, Slot.one]

abbrev idxSix : KunnethIndex :=
  { base := moduliM6, slots := sixOnes, degree := 26, weight := 26 }

abbrev idxSeven : KunnethIndex :=
  { base := moduliM6, slots := sevenOnes, degree := 26, weight := 26 }

abbrev NC00 : Prop := BMIsFiniteTateSum exactC66BMTarget
abbrev NC01 : Prop := ¬ BMIsFiniteTateSum
  { genus := 6, markings := 6, homologicalDegree := 16, weight := -16, tateIndex := 7 }
abbrev NC02 : Prop := ¬ BMIsFiniteTateSum
  { genus := 6, markings := 6, homologicalDegree := 15, weight := -16, tateIndex := 8 }
abbrev NC03 : Prop := ¬ PureIsFiniteTateSum pureM66deg26 (-12)
abbrev NC04 : Prop := ¬ ChowKunnethGenerationProperty moduliM66
abbrev NC05 : Prop := ¬ LocalSystemCohomologyVanishesAllCoefficients moduliM6 19
abbrev NC06 : Prop := ¬ OrdinaryCohomologyVanishes moduliM65 25
abbrev NC07 : Prop := ¬ KunnethSummandVanishes idxSeven
abbrev NC08 : Prop := ¬ KunnethSummandRestrictsIntoPsi idxSeven pureM66deg26
abbrev NC09 : Prop := ¬ PhiVanishes pureM66deg24
abbrev NC10 : Prop := ¬ TateTwistShift (-13) 21 7
abbrev NC11 : Prop := ¬ BorelMooreIsTwistOfPure exactC66BMTarget pureM66deg26 20
abbrev NC12 : Prop := ¬ OmegaMultiplicationHitsSlotTwo { genus := 1, markings := 0 }
abbrev NC13 : Prop := KunnethSummandVanishes idxSix

theorem model_nc00 : NC00 := by decide
theorem model_nc01 : NC01 := by decide
theorem model_nc02 : NC02 := by decide
theorem model_nc03 : NC03 := by decide
theorem model_nc04 : NC04 := by decide
theorem model_nc05 : NC05 := by decide
theorem model_nc06 : NC06 := by decide
theorem model_nc07 : NC07 := by decide
theorem model_nc08 : NC08 := by decide
theorem model_nc09 : NC09 := by decide
theorem model_nc10 : NC10 := by decide
theorem model_nc11 : NC11 := by decide
theorem model_nc12 : NC12 := by decide
theorem model_nc13 : NC13 := by decide

-- ---------------------------------------------------------------------------
-- The single model theorem.
-- ---------------------------------------------------------------------------

theorem c66_model_is_consistent_and_noncollapsing :
    AX01 ∧ AX02 ∧ AX03 ∧ AX04 ∧ AX05 ∧ AX06 ∧ AX07 ∧ AX08 ∧ AX09 ∧ AX10 ∧ AX11 ∧
    AX12 ∧ AX13 ∧ AX14 ∧ AX15 ∧ AX16 ∧ AX17 ∧ AX18 ∧ AX19 ∧ AX20 ∧ AX21 ∧ AX22 ∧
    AX23 ∧ AX24 ∧ AX25 ∧ AX26 ∧ AX27 ∧ AX28 ∧ AX29 ∧ AX30 ∧ AX31 ∧ AX32 ∧ AX33 ∧
    AX34 ∧ NC00 ∧ NC01 ∧ NC02 ∧ NC03 ∧ NC04 ∧ NC05 ∧ NC06 ∧ NC07 ∧ NC08 ∧ NC09 ∧
    NC10 ∧ NC11 ∧ NC12 ∧ NC13 :=
  ⟨model_ax01, model_ax02, model_ax03, model_ax04, model_ax05, model_ax06, model_ax07,
    model_ax08, model_ax09, model_ax10, model_ax11, model_ax12, model_ax13, model_ax14,
    model_ax15, model_ax16, model_ax17, model_ax18, model_ax19, model_ax20, model_ax21,
    model_ax22, model_ax23, model_ax24, model_ax25, model_ax26, model_ax27, model_ax28,
    model_ax29, model_ax30, model_ax31, model_ax32, model_ax33, model_ax34, model_nc00,
    model_nc01, model_nc02, model_nc03, model_nc04, model_nc05, model_nc06, model_nc07,
    model_nc08, model_nc09, model_nc10, model_nc11, model_nc12, model_nc13⟩

#print axioms c66_model_is_consistent_and_noncollapsing
