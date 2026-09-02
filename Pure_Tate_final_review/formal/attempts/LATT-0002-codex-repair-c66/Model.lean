set_option autoImplicit false
-- LEAN-MODEL-WITNESS The LC66-002 hash-pinned C66Vocabulary signature is embedded verbatim. modelVocabulary is a concrete instance with genuinely different ClosedPureIndex and OpenPureIndex types; restriction checks genus, factor/marking count, degree and weight, while Kunneth splitting accepts only the closed type. All 34 mathematical axiom schemas are proved for this single concrete vocabulary.
-- LEAN-NONCOLLAPSE The exact closed-to-open restriction holds, but a five-factor source does not restrict to the six-marking target; off-diagonal pure indices are not ContainedInPsi or Tate; the wrong CKgP boundary, vcd threshold, BM Tate index, and duality twist fail. The source cannot be supplied to any open-only predicate, or the target to the closed-only Kunneth predicate, by Lean's type checker.
-- LEAN-MODELS BMIsFiniteTateSum vocab deligne_lowest_weight_restriction_surjection containment_transfers_along_surjection deligne_smooth_proper_leray_degeneration pty_projectors_are_algebraic_correspondences pty_r_two_projector_form kunneth_splitting_of_pure_weight_source omega_class_slot_decomposition morita_slot_one_vanishing omega_multiplication_hits_slot_two_modulo_errors harer_vcd_pointed constant_coefficient_vanishing_above_vcd phi_vanishes_from_pullback_source phi_is_pullback_span psi_is_psi_multiple_span harer_vcd_unpointed local_coefficient_vanishing_above_vcd kunneth_summand_vanishes_below_base_degree vanishing_summand_restricts_into_psi slot_two_summand_restricts_into_psi_modulo_errors clp_primitive_quotient_formula primitive_quotient_vanishes_from_local_coefficients equality_from_vanishing_primitive_quotient_and_phi ckgp_marking_bound_genus_six ckgp_holds_in_range cycle_class_surjectivity_from_ckgp algebraic_pure_weight_is_tate lowest_weight_is_pure_polarizable phi_tate_from_pullback_source psi_class_is_tate_divisor psi_products_are_tate_quotient polarizable_semisimplicity_upgrade poincare_duality_bm_twist tate_twist_shift_add bm_tate_sum_from_twisted_pure
-- LEAN-MODEL-THEOREM c66_model_is_consistent_and_materially_noncollapsing

structure BMTargetIndex where
  genus : Int
  markings : Int
  homologicalDegree : Int
  weight : Int
  tateIndex : Int

-- LEAN-SHARED-SIGNATURE-BEGIN
structure ModuliIndex where
  genus : Int
  markings : Int
  deriving DecidableEq

structure ClosedPureIndex where
  genus : Int
  factors : Int
  degree : Int
  weight : Int
  deriving DecidableEq

structure OpenPureIndex where
  space : ModuliIndex
  degree : Int
  weight : Int
  deriving DecidableEq

inductive Slot where
  | zero : Slot
  | one : Slot
  | two : Slot
  deriving DecidableEq

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

structure KunnethIndex where
  source : ClosedPureIndex
  slots : List Slot

structure LocalSystemIndex where
  genus : Int
  degree : Int
  weight : Int
  partitionSize : Int

structure C66Vocabulary where
  RestrictionSurjectsOnLowestWeight : ClosedPureIndex -> OpenPureIndex -> Prop
  KunnethSplittingByChowKunnethProjectors : ClosedPureIndex -> Prop
  ChowKunnethProjectorIsAlgebraicCorrespondence : ModuliIndex -> Prop
  LerayDegeneratesAtE2 : ModuliIndex -> Prop
  RTwoProjectorInPsiAndPullbackSpan : ModuliIndex -> Prop
  KunnethSummandVanishes : KunnethIndex -> Prop
  KunnethSummandRestrictsIntoPsi : KunnethIndex -> OpenPureIndex -> Prop
  DualizingClassSlotDecomposition : ModuliIndex -> Prop
  SlotOneCrossTermVanishes : ModuliIndex -> Prop
  OmegaMultiplicationHitsSlotTwo : ModuliIndex -> Prop
  PhiSpannedByForgetfulPullbacks : OpenPureIndex -> OpenPureIndex -> Prop
  PsiSpannedByPsiMultiples : OpenPureIndex -> OpenPureIndex -> Prop
  OrdinaryCohomologyVanishes : ModuliIndex -> Int -> Prop
  LocalSystemCohomologyVanishesAllCoefficients : ModuliIndex -> Int -> Prop
  PhiVanishes : OpenPureIndex -> Prop
  ContainedInPsi : OpenPureIndex -> Prop
  EqualsPsi : OpenPureIndex -> Prop
  PrimitiveQuotientIsLocalSystemSum : OpenPureIndex -> LocalSystemIndex -> Prop
  PrimitiveQuotientVanishes : OpenPureIndex -> Prop
  PureIsFiniteTateSum : OpenPureIndex -> Int -> Prop
  PhiIsFiniteTateSum : OpenPureIndex -> Int -> Prop
  PsiIsQuotientOfFiniteTateSum : OpenPureIndex -> Int -> Prop
  PurePolarizableOfWeight : OpenPureIndex -> Prop
  PsiClassIsAlgebraicOfTateType : ModuliIndex -> Int -> Prop
  ChowKunnethGenerationProperty : ModuliIndex -> Prop
  CkgpMarkingBound : Int -> Int -> Prop
  CycleClassMapSurjectsOntoPureWeight : OpenPureIndex -> Prop
  VirtualCohomologicalDimension : ModuliIndex -> Int -> Prop
  BorelMooreIsTwistOfPure : BMTargetIndex -> OpenPureIndex -> Int -> Prop
  TateTwistShift : Int -> Int -> Int -> Prop
-- LEAN-SHARED-SIGNATURE-END

def vcdInt (g n : Int) : Int := if n = 0 then 4 * g - 5 else 4 * g - 4 + n

def hasTwo : List Slot -> Bool
  | [] => false
  | Slot.two :: _ => true
  | _ :: rest => hasTwo rest

def summandVanishes (idx : KunnethIndex) : Prop :=
  4 * idx.source.genus - 5 < idx.source.degree - (total idx.slots : Int)

def aligned (src : ClosedPureIndex) (tgt : OpenPureIndex) : Prop :=
  src.genus = tgt.space.genus ∧ src.factors = tgt.space.markings ∧
  src.degree = tgt.degree ∧ src.weight = tgt.weight

def modelVocabulary : C66Vocabulary where
  RestrictionSurjectsOnLowestWeight := fun src tgt => aligned src tgt ∧ src.degree = src.weight
  KunnethSplittingByChowKunnethProjectors := fun src => src.degree = src.weight
  ChowKunnethProjectorIsAlgebraicCorrespondence := fun X => 2 <= X.genus ∧ X.markings = 0
  LerayDegeneratesAtE2 := fun X => 2 <= X.genus ∧ X.markings = 0
  RTwoProjectorInPsiAndPullbackSpan := fun X => 2 <= X.genus ∧ X.markings = 0
  KunnethSummandVanishes := summandVanishes
  KunnethSummandRestrictsIntoPsi := fun idx tgt => aligned idx.source tgt ∧ (summandVanishes idx ∨ hasTwo idx.slots = true)
  DualizingClassSlotDecomposition := fun X => 2 <= X.genus ∧ X.markings = 0
  SlotOneCrossTermVanishes := fun X => 2 <= X.genus ∧ X.markings = 0
  OmegaMultiplicationHitsSlotTwo := fun X => 2 <= X.genus ∧ X.markings = 0
  PhiSpannedByForgetfulPullbacks := fun p q => q.space.genus = p.space.genus ∧ q.space.markings = p.space.markings - 1 ∧ q.degree = p.degree ∧ q.weight = p.weight
  PsiSpannedByPsiMultiples := fun p r => r.space = p.space ∧ r.degree = p.degree - 2 ∧ r.weight = p.weight - 2
  OrdinaryCohomologyVanishes := fun X d => vcdInt X.genus X.markings < d
  LocalSystemCohomologyVanishesAllCoefficients := fun X d => X.markings = 0 ∧ vcdInt X.genus X.markings < d
  PhiVanishes := fun p => vcdInt p.space.genus (p.space.markings - 1) < p.degree
  ContainedInPsi := fun p => p.degree = p.weight
  EqualsPsi := fun p => 4 * p.space.genus - 5 < p.degree - p.space.markings ∧ vcdInt p.space.genus (p.space.markings - 1) < p.degree
  PrimitiveQuotientIsLocalSystemSum := fun p prim => prim.genus = p.space.genus ∧ prim.degree = p.degree - p.space.markings ∧ prim.weight = p.weight ∧ prim.partitionSize = p.space.markings
  PrimitiveQuotientVanishes := fun p => 4 * p.space.genus - 5 < p.degree - p.space.markings
  PureIsFiniteTateSum := fun p t => p.weight + 2 * t = 0 ∧ p.degree = p.weight
  PhiIsFiniteTateSum := fun p t => p.weight + 2 * t = 0 ∧ p.degree = p.weight
  PsiIsQuotientOfFiniteTateSum := fun p t => p.weight + 2 * t = 0 ∧ p.degree = p.weight
  PurePolarizableOfWeight := fun p => p.degree = p.weight
  PsiClassIsAlgebraicOfTateType := fun X t => 1 <= X.markings ∧ t = -1
  ChowKunnethGenerationProperty := fun X => X.genus = 6 ∧ X.markings <= 5
  CkgpMarkingBound := fun g b => g = 6 ∧ b = 5
  CycleClassMapSurjectsOntoPureWeight := fun p => p.degree = p.weight ∧ p.space.genus = 6 ∧ p.space.markings <= 5
  VirtualCohomologicalDimension := fun X v => v = vcdInt X.genus X.markings
  BorelMooreIsTwistOfPure := fun bm p d => bm.genus = p.space.genus ∧ bm.markings = p.space.markings ∧ d = 3 * bm.genus - 3 + bm.markings ∧ p.degree = 2 * d - bm.homologicalDegree ∧ p.weight = p.degree ∧ bm.weight = p.weight - 2 * d
  TateTwistShift := fun a b u => u = a + b

abbrev V := modelVocabulary
def BMIsFiniteTateSum (bm : BMTargetIndex) : Prop :=
  bm.weight + 2 * bm.tateIndex = 0 ∧ bm.homologicalDegree + bm.weight = 0

def AX01 : Prop := forall (src : ClosedPureIndex) (tgt : OpenPureIndex),
  src.genus = tgt.space.genus -> src.factors = tgt.space.markings -> src.degree = tgt.degree ->
  src.weight = tgt.weight -> src.degree = src.weight -> V.RestrictionSurjectsOnLowestWeight src tgt
def AX02 : Prop := forall (src : ClosedPureIndex) (tgt : OpenPureIndex),
  V.RestrictionSurjectsOnLowestWeight src tgt ->
  (forall idx : KunnethIndex, idx.source = src -> lenOf idx.slots = Int.toNat src.factors -> V.KunnethSummandRestrictsIntoPsi idx tgt) ->
  V.KunnethSplittingByChowKunnethProjectors src -> V.ContainedInPsi tgt
def AX03 : Prop := forall base : ModuliIndex, 2 <= base.genus -> base.markings = 0 -> V.LerayDegeneratesAtE2 base
def AX04 : Prop := forall base : ModuliIndex, 2 <= base.genus -> base.markings = 0 -> V.ChowKunnethProjectorIsAlgebraicCorrespondence base
def AX05 : Prop := forall base : ModuliIndex, 2 <= base.genus -> base.markings = 0 -> V.RTwoProjectorInPsiAndPullbackSpan base
def AX06 : Prop := forall (src : ClosedPureIndex) (base : ModuliIndex), V.LerayDegeneratesAtE2 base -> V.ChowKunnethProjectorIsAlgebraicCorrespondence base -> V.RTwoProjectorInPsiAndPullbackSpan base -> base.genus = src.genus -> base.markings = 0 -> 1 <= src.factors -> src.degree = src.weight -> V.KunnethSplittingByChowKunnethProjectors src
def AX07 : Prop := forall base : ModuliIndex, 2 <= base.genus -> base.markings = 0 -> V.DualizingClassSlotDecomposition base
def AX08 : Prop := forall base : ModuliIndex, 2 <= base.genus -> base.markings = 0 -> V.SlotOneCrossTermVanishes base
def AX09 : Prop := forall base : ModuliIndex, V.DualizingClassSlotDecomposition base -> V.SlotOneCrossTermVanishes base -> V.RTwoProjectorInPsiAndPullbackSpan base -> V.OmegaMultiplicationHitsSlotTwo base
def AX10 : Prop := forall (base : ModuliIndex) (v : Int), 2 <= base.genus -> 1 <= base.markings -> v = 4 * base.genus - 4 + base.markings -> V.VirtualCohomologicalDimension base v
def AX11 : Prop := forall (base : ModuliIndex) (v d : Int), V.VirtualCohomologicalDimension base v -> v < d -> V.OrdinaryCohomologyVanishes base d
def AX12 : Prop := forall (p q : OpenPureIndex), V.PhiSpannedByForgetfulPullbacks p q -> V.OrdinaryCohomologyVanishes q.space q.degree -> V.PhiVanishes p
def AX13 : Prop := forall (p q : OpenPureIndex), q.space.genus = p.space.genus -> q.space.markings = p.space.markings - 1 -> q.degree = p.degree -> q.weight = p.weight -> V.PhiSpannedByForgetfulPullbacks p q
def AX14 : Prop := forall (p r : OpenPureIndex), r.space = p.space -> r.degree = p.degree - 2 -> r.weight = p.weight - 2 -> V.PsiSpannedByPsiMultiples p r
def AX15 : Prop := forall (base : ModuliIndex) (v : Int), 2 <= base.genus -> base.markings = 0 -> v = 4 * base.genus - 5 -> V.VirtualCohomologicalDimension base v
def AX16 : Prop := forall (base : ModuliIndex) (v d : Int), V.VirtualCohomologicalDimension base v -> base.markings = 0 -> v < d -> V.LocalSystemCohomologyVanishesAllCoefficients base d
def AX17 : Prop := forall (idx : KunnethIndex) (base : ModuliIndex) (v : Int), base.genus = idx.source.genus -> base.markings = 0 -> V.LocalSystemCohomologyVanishesAllCoefficients base (idx.source.degree - (total idx.slots : Int)) -> V.VirtualCohomologicalDimension base v -> v < idx.source.degree - (total idx.slots : Int) -> V.KunnethSummandVanishes idx
def AX18 : Prop := forall (idx : KunnethIndex) (tgt : OpenPureIndex), idx.source.genus = tgt.space.genus -> idx.source.factors = tgt.space.markings -> idx.source.degree = tgt.degree -> idx.source.weight = tgt.weight -> V.KunnethSummandVanishes idx -> V.KunnethSummandRestrictsIntoPsi idx tgt
def AX19 : Prop := forall (idx errZero errOne : KunnethIndex) (pre post : List Slot) (tgt r q : OpenPureIndex) (base5 : ModuliIndex), idx.slots = pre ++ Slot.two :: post -> errZero.source = idx.source -> errZero.slots = pre ++ Slot.zero :: post -> errOne.source = idx.source -> errOne.slots = pre ++ Slot.one :: post -> V.OmegaMultiplicationHitsSlotTwo { genus := 6, markings := 0 } -> idx.source.genus = tgt.space.genus -> idx.source.factors = tgt.space.markings -> idx.source.degree = tgt.degree -> idx.source.weight = tgt.weight -> V.PsiSpannedByPsiMultiples tgt r -> V.PhiSpannedByForgetfulPullbacks r q -> base5.genus = tgt.space.genus -> base5.markings = tgt.space.markings - 1 -> q.space = base5 -> V.OrdinaryCohomologyVanishes base5 tgt.degree -> V.KunnethSummandRestrictsIntoPsi errOne tgt -> V.KunnethSummandRestrictsIntoPsi idx tgt
def AX20 : Prop := forall (p : OpenPureIndex) (prim : LocalSystemIndex), 2 <= p.space.genus -> 1 <= p.space.markings -> p.degree = p.weight -> prim.genus = p.space.genus -> prim.degree = p.degree - p.space.markings -> prim.weight = p.weight -> prim.partitionSize = p.space.markings -> V.PrimitiveQuotientIsLocalSystemSum p prim
def AX21 : Prop := forall (p : OpenPureIndex) (prim : LocalSystemIndex), V.PrimitiveQuotientIsLocalSystemSum p prim -> V.LocalSystemCohomologyVanishesAllCoefficients { genus := prim.genus, markings := 0 } prim.degree -> V.PrimitiveQuotientVanishes p
def AX22 : Prop := forall p : OpenPureIndex, V.PrimitiveQuotientVanishes p -> V.PhiVanishes p -> V.EqualsPsi p
def AX23 : Prop := V.CkgpMarkingBound 6 5
def AX24 : Prop := forall (base : ModuliIndex) (b : Int), V.CkgpMarkingBound base.genus b -> base.markings <= b -> V.ChowKunnethGenerationProperty base
def AX25 : Prop := forall (base : ModuliIndex) (p : OpenPureIndex), V.ChowKunnethGenerationProperty base -> p.space = base -> p.degree = p.weight -> V.CycleClassMapSurjectsOntoPureWeight p
def AX26 : Prop := forall (p : OpenPureIndex) (c : Int), V.CycleClassMapSurjectsOntoPureWeight p -> V.PurePolarizableOfWeight p -> p.degree = 2 * c -> p.weight = p.degree -> V.PureIsFiniteTateSum p (-c)
def AX27 : Prop := forall p : OpenPureIndex, p.degree = p.weight -> V.PurePolarizableOfWeight p
def AX28 : Prop := forall (p q : OpenPureIndex) (t : Int), V.PhiSpannedByForgetfulPullbacks p q -> V.PureIsFiniteTateSum q t -> V.PhiIsFiniteTateSum p t
def AX29 : Prop := forall base : ModuliIndex, 1 <= base.markings -> V.PsiClassIsAlgebraicOfTateType base (-1)
def AX30 : Prop := forall (p r : OpenPureIndex) (a b t : Int), V.PsiSpannedByPsiMultiples p r -> V.PsiClassIsAlgebraicOfTateType p.space a -> V.PhiIsFiniteTateSum r b -> p.degree = r.degree + 2 -> p.weight = r.weight + 2 -> t = a + b -> V.PsiIsQuotientOfFiniteTateSum p t
def AX31 : Prop := forall (p : OpenPureIndex) (t : Int), V.ContainedInPsi p -> V.PurePolarizableOfWeight p -> V.PsiIsQuotientOfFiniteTateSum p t -> V.PureIsFiniteTateSum p t
def AX32 : Prop := forall (bm : BMTargetIndex) (p : OpenPureIndex) (d : Int), bm.genus = p.space.genus -> bm.markings = p.space.markings -> d = 3 * bm.genus - 3 + bm.markings -> p.degree = 2 * d - bm.homologicalDegree -> p.weight = p.degree -> bm.weight = p.weight - 2 * d -> V.BorelMooreIsTwistOfPure bm p d
def AX33 : Prop := forall (a b u : Int), u = a + b -> V.TateTwistShift a b u
def AX34 : Prop := forall (bm : BMTargetIndex) (p : OpenPureIndex) (d t u : Int), V.BorelMooreIsTwistOfPure bm p d -> V.PureIsFiniteTateSum p t -> V.TateTwistShift t d u -> bm.tateIndex = u -> BMIsFiniteTateSum bm

theorem hasTwo_split (pre post : List Slot) : hasTwo (pre ++ Slot.two :: post) = true := by
  induction pre with
  | nil => rfl
  | cons a rest ih => cases a <;> simp [hasTwo, ih]

theorem ax01 : AX01 := by intro src tgt h1 h2 h3 h4 h5; exact ⟨⟨h1,h2,h3,h4⟩,h5⟩
theorem ax02 : AX02 := by intro src tgt h _ _; dsimp [V, modelVocabulary, aligned] at h ⊢; omega
theorem ax03 : AX03 := by intro _ h1 h2; exact ⟨h1,h2⟩
theorem ax04 : AX04 := by intro _ h1 h2; exact ⟨h1,h2⟩
theorem ax05 : AX05 := by intro _ h1 h2; exact ⟨h1,h2⟩
theorem ax06 : AX06 := by intro _ _ _ _ _ _ _ _ h; exact h
theorem ax07 : AX07 := by intro _ h1 h2; exact ⟨h1,h2⟩
theorem ax08 : AX08 := by intro _ h1 h2; exact ⟨h1,h2⟩
theorem ax09 : AX09 := by intro _ h1 h2 _; exact ⟨h1.1,h2.2⟩
theorem ax10 : AX10 := by
  intro base v _ hm hv
  have hne : ¬ base.markings = 0 := by omega
  dsimp [V, modelVocabulary]
  simp [vcdInt, hne]
  exact hv
theorem ax11 : AX11 := by intro _ _ _ hv h; simpa [C66Vocabulary.VirtualCohomologicalDimension, C66Vocabulary.OrdinaryCohomologyVanishes, V, modelVocabulary] using hv ▸ h
theorem ax12 : AX12 := by
  intro p q h hv
  dsimp [V, modelVocabulary] at h hv ⊢
  rw [← h.1, ← h.2.1, ← h.2.2.1]
  exact hv
theorem ax13 : AX13 := by intro _ _ h1 h2 h3 h4; exact ⟨h1,h2,h3,h4⟩
theorem ax14 : AX14 := by intro _ _ h1 h2 h3; exact ⟨h1,h2,h3⟩
theorem ax15 : AX15 := by intro base v _ hm hv; simp [V, modelVocabulary, vcdInt, hm]; exact hv
theorem ax16 : AX16 := by intro base v d hv hm h; exact ⟨hm, by simpa [C66Vocabulary.VirtualCohomologicalDimension, V, modelVocabulary] using hv ▸ h⟩
theorem ax17 : AX17 := by
  intro idx base v hg hm hc hv h
  dsimp [V, modelVocabulary, summandVanishes] at hc hv ⊢
  simp [vcdInt, hm] at hv hc
  omega
theorem ax18 : AX18 := by intro idx tgt h1 h2 h3 h4 hv; exact ⟨⟨h1,h2,h3,h4⟩,Or.inl hv⟩
theorem ax19 : AX19 := by
  intro idx _ _ pre post tgt _ _ _ hs _ _ _ _ _ h1 h2 h3 h4 _ _ _ _ _ _ _
  exact ⟨⟨h1,h2,h3,h4⟩, Or.inr (by rw [hs]; exact hasTwo_split pre post)⟩
theorem ax20 : AX20 := by intro _ _ _ _ _ h1 h2 h3 h4; exact ⟨h1,h2,h3,h4⟩
theorem ax21 : AX21 := by
  intro p prim h hc
  dsimp [V, modelVocabulary] at h hc ⊢
  simp [vcdInt] at hc
  omega
theorem ax22 : AX22 := by intro _ h1 h2; exact ⟨h1,h2⟩
theorem ax23 : AX23 := ⟨rfl,rfl⟩
theorem ax24 : AX24 := by intro base b h hb; dsimp [V, modelVocabulary] at h ⊢; exact ⟨h.1, by omega⟩
theorem ax25 : AX25 := by intro base p h hs hd; dsimp [V, modelVocabulary] at h ⊢; rw [hs]; exact ⟨hd,h.1,h.2⟩
theorem ax26 : AX26 := by intro p c _ _ hd hw; exact ⟨by omega, by omega⟩
theorem ax27 : AX27 := by intro _ h; exact h
theorem ax28 : AX28 := by intro p q t h ht; dsimp [V, modelVocabulary] at h ht ⊢; omega
theorem ax29 : AX29 := by intro _ h; exact ⟨h,rfl⟩
theorem ax30 : AX30 := by intro p r a b t h1 h2 h3 h4 h5 h6; dsimp [V, modelVocabulary] at h1 h2 h3 ⊢; omega
theorem ax31 : AX31 := by intro _ _ _ _ h; exact h
theorem ax32 : AX32 := by intro _ _ _ h1 h2 h3 h4 h5 h6; exact ⟨h1,h2,h3,h4,h5,h6⟩
theorem ax33 : AX33 := by intro _ _ _ h; exact h
theorem ax34 : AX34 := by
  intro bm p d t u h1 h2 h3 h4
  dsimp [V, modelVocabulary, BMIsFiniteTateSum] at h1 h2 h3 ⊢
  omega

def source6 : ClosedPureIndex := { genus := 6, factors := 6, degree := 26, weight := 26 }
def source5 : ClosedPureIndex := { genus := 6, factors := 5, degree := 26, weight := 26 }
def target66 : OpenPureIndex := { space := { genus := 6, markings := 6 }, degree := 26, weight := 26 }
def offDiagonal : OpenPureIndex := { space := { genus := 6, markings := 6 }, degree := 26, weight := 25 }
def exactBM : BMTargetIndex := { genus := 6, markings := 6, homologicalDegree := 16, weight := -16, tateIndex := 8 }

def NC01 : Prop := V.RestrictionSurjectsOnLowestWeight source6 target66
def NC02 : Prop := ¬ V.RestrictionSurjectsOnLowestWeight source5 target66
def NC03 : Prop := ¬ V.ContainedInPsi offDiagonal
def NC04 : Prop := ¬ V.PureIsFiniteTateSum target66 (-12)
def NC05 : Prop := ¬ V.ChowKunnethGenerationProperty { genus := 6, markings := 6 }
def NC06 : Prop := ¬ V.LocalSystemCohomologyVanishesAllCoefficients { genus := 6, markings := 0 } 19
def NC07 : Prop := BMIsFiniteTateSum exactBM
def NC08 : Prop := ¬ BMIsFiniteTateSum { genus := 6, markings := 6, homologicalDegree := 16, weight := -16, tateIndex := 7 }
def NC09 : Prop := ¬ V.BorelMooreIsTwistOfPure exactBM target66 20

theorem nc01 : NC01 := by dsimp [NC01, V, modelVocabulary, aligned, source6, target66]; decide
theorem nc02 : NC02 := by dsimp [NC02, V, modelVocabulary, aligned, source5, target66]; decide
theorem nc03 : NC03 := by dsimp [NC03, V, modelVocabulary, offDiagonal]; decide
theorem nc04 : NC04 := by dsimp [NC04, V, modelVocabulary, target66]; decide
theorem nc05 : NC05 := by dsimp [NC05, V, modelVocabulary]; decide
theorem nc06 : NC06 := by dsimp [NC06, V, modelVocabulary, vcdInt]; decide
theorem nc07 : NC07 := by dsimp [NC07, BMIsFiniteTateSum, exactBM]; decide
theorem nc08 : NC08 := by dsimp [NC08, BMIsFiniteTateSum]; decide
theorem nc09 : NC09 := by dsimp [NC09, V, modelVocabulary, exactBM, target66]; decide

theorem c66_model_is_consistent_and_materially_noncollapsing :
    AX01 ∧ AX02 ∧ AX03 ∧ AX04 ∧ AX05 ∧ AX06 ∧ AX07 ∧ AX08 ∧ AX09 ∧ AX10 ∧ AX11 ∧
    AX12 ∧ AX13 ∧ AX14 ∧ AX15 ∧ AX16 ∧ AX17 ∧ AX18 ∧ AX19 ∧ AX20 ∧ AX21 ∧ AX22 ∧
    AX23 ∧ AX24 ∧ AX25 ∧ AX26 ∧ AX27 ∧ AX28 ∧ AX29 ∧ AX30 ∧ AX31 ∧ AX32 ∧ AX33 ∧
    AX34 ∧ NC01 ∧ NC02 ∧ NC03 ∧ NC04 ∧ NC05 ∧ NC06 ∧ NC07 ∧ NC08 ∧ NC09 :=
  ⟨ax01,ax02,ax03,ax04,ax05,ax06,ax07,ax08,ax09,ax10,ax11,ax12,ax13,ax14,ax15,ax16,
   ax17,ax18,ax19,ax20,ax21,ax22,ax23,ax24,ax25,ax26,ax27,ax28,ax29,ax30,ax31,ax32,
   ax33,ax34,nc01,nc02,nc03,nc04,nc05,nc06,nc07,nc08,nc09⟩

#print axioms c66_model_is_consistent_and_materially_noncollapsing
