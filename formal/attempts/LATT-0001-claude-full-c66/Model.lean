set_option autoImplicit false
-- LEAN-MODEL-WITNESS Every Claim.lean carrier is reinterpreted here as a concrete arithmetic predicate on the same Int-indexed records, with no axioms at all. A BM index is a finite Tate sum exactly when weight + 2*tateIndex = 0 and homologicalDegree + weight = 0; a pure index is one exactly when weight + 2*t = 0 and degree = weight; vcd is the actual function vcdInt g n = 4g-5 for n = 0 and 4g-4+n for n >= 1; ordinary cohomology vanishes exactly above vcd; the primitive quotient vanishes exactly when the primitive slot degree k-n exceeds 4g-5; Phi vanishes exactly above the vcd of the (n-1)-marked stack; CKgP holds exactly for genus 6 with at most 5 markings; psi is Tate of index -1; the duality twist is forced to be 3g-3+n; and Q(a)(b) = Q(a+b) is literal Int addition. All twenty-five LC66-OBL axioms of Claim.lean become theorems of this interpretation, so the Claim axiom set is consistent and the exported deduction is not vacuous.
-- LEAN-NONCOLLAPSE Thirteen witnesses, all proved by decide: model_nc00 (the exact BM target is satisfied in this model, so the axioms are jointly satisfiable together with the conclusion) and twelve refutations showing the load-bearing predicates are not definitionally True -- NC01 bm_wrong_tate_index (tateIndex 7 fails), NC02 bm_wrong_homological_degree (degree 15 fails), NC03 pure_wrong_tate_index (Q(-12) fails at weight 26), NC04 ckgp_fails_at_six_markings (CKgP is unavailable at n = 6, the exact boundary of THM-0005), NC05 local_system_at_vcd (degree 19 is not above vcd(Mod_6) = 19), NC06 ordinary_at_vcd (degree 25 is not above vcd(PMod_{6,5}) = 25), NC07 primitive_quotient_degree_24 (the primitive slot 24-6 = 18 is below 19), NC08 phi_nonvanishing_degree_24 (Phi_{6,6}^{24} is not forced to vanish, which is why step 5 is needed), NC09 psi_does_not_span_degree_24, NC10 twist_is_exact (Q(-13)(21) is not Q(7)), NC11 duality_twist_is_dimension (the twist 20 is rejected) and NC12 slot_two_needs_genus_two (the omega_s repair fails at genus 1).
-- LEAN-MODELS BMIsFiniteTateSum PhiSpannedByForgetfulPullbacks PsiSpannedByPsiMultiples PrimitiveQuotientIsLocalSystemSum PrimitiveQuotientVanishes LocalSystemCohomologyVanishes OrdinaryCohomologyVanishes SpannedByPhiAndPsi PhiVanishes SpannedByPsi PureIsFiniteTateSum PhiIsFiniteTateSum PsiIsQuotientOfFiniteTateSum BorelMooreIsTwistOfPure TateTwistShift PsiClassIsAlgebraicOfTateType ChowKunnethGenerationProperty CkgpMarkingBound CycleClassMapSurjectsOntoPureWeight VirtualCohomologicalDimension DualizingClassSlotDecomposition SlotOneComponentVanishes PsiSpansSlotTwoModuloSlotZero phi_is_pullback_span psi_is_psi_multiple_span omega_class_slot_decomposition morita_slot_one_vanishing psi_multiplication_spans_slot_two clp_pure_weight_quotient_formula harer_vcd_unpointed local_system_vanishing_above_vcd primitive_quotient_vanishes_from_local_systems span_from_vanishing_primitive_quotient harer_vcd_pointed ordinary_vanishing_above_vcd phi_vanishes_from_pullback_source psi_spans_after_phi_vanishes ckgp_marking_bound_genus_six ckgp_holds_in_range cycle_class_surjectivity_from_ckgp algebraic_pure_weight_is_tate phi_tate_from_pullback_source psi_class_is_tate_divisor psi_products_are_tate_quotient polarizable_semisimplicity_upgrade poincare_duality_bm_twist tate_twist_shift_add bm_tate_sum_from_twisted_pure
-- LEAN-MODEL-THEOREM c66_model_is_consistent_and_noncollapsing

-- ---------------------------------------------------------------------------
-- The Claim.lean vocabulary, re-declared concretely.  Model.lean stands alone:
-- it repeats the record definitions rather than referring to Claim.lean.
-- ---------------------------------------------------------------------------

structure BMTargetIndex where
  genus : Int
  markings : Int
  homologicalDegree : Int
  weight : Int
  tateIndex : Int

def exactC66BMTarget : BMTargetIndex := {
  genus := 6
  markings := 6
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

structure ModuliIndex where
  genus : Int
  markings : Int

structure PureIndex where
  space : ModuliIndex
  degree : Int
  weight : Int

structure LocalSystemIndex where
  genus : Int
  degree : Int
  weight : Int
  partitionSize : Int

def moduliM6 : ModuliIndex := { genus := 6, markings := 0 }

def moduliM65 : ModuliIndex := { genus := 6, markings := 5 }

def moduliM66 : ModuliIndex := { genus := 6, markings := 6 }

def pureM66deg26 : PureIndex := { space := moduliM66, degree := 26, weight := 26 }

def pureM66deg24 : PureIndex := { space := moduliM66, degree := 24, weight := 24 }

def pureM65deg24 : PureIndex := { space := moduliM65, degree := 24, weight := 24 }

def primitiveM6deg20 : LocalSystemIndex :=
  { genus := 6, degree := 20, weight := 26, partitionSize := 6 }

-- The actual virtual cohomological dimension function of the interpretation.

def vcdInt (genus markings : Int) : Int :=
  if markings = 0 then 4 * genus - 5 else 4 * genus - 4 + markings

def vcdOf (X : ModuliIndex) : Int := vcdInt X.genus X.markings

theorem vcdInt_unpointed (genus markings : Int) (h : markings = 0) :
    vcdInt genus markings = 4 * genus - 5 := by
  show (if markings = 0 then 4 * genus - 5 else 4 * genus - 4 + markings)
      = 4 * genus - 5
  exact if_pos h

theorem vcdInt_pointed (genus markings : Int) (h : ¬ (markings = 0)) :
    vcdInt genus markings = 4 * genus - 4 + markings := by
  show (if markings = 0 then 4 * genus - 5 else 4 * genus - 4 + markings)
      = 4 * genus - 4 + markings
  exact if_neg h

-- The interpretation of every Claim.lean carrier.

def BMIsFiniteTateSum (bm : BMTargetIndex) : Prop :=
  bm.weight + 2 * bm.tateIndex = 0 ∧ bm.homologicalDegree + bm.weight = 0

def PhiSpannedByForgetfulPullbacks (p q : PureIndex) : Prop :=
  q.space.genus = p.space.genus ∧ q.space.markings = p.space.markings - 1 ∧
    q.degree = p.degree ∧ q.weight = p.weight

def PsiSpannedByPsiMultiples (p r : PureIndex) : Prop :=
  r.space = p.space ∧ r.degree = p.degree - 2 ∧ r.weight = p.weight - 2

def PrimitiveQuotientIsLocalSystemSum (p : PureIndex) (prim : LocalSystemIndex) : Prop :=
  prim.genus = p.space.genus ∧ prim.degree = p.degree - p.space.markings ∧
    prim.weight = p.weight ∧ prim.partitionSize = p.space.markings

def PrimitiveQuotientVanishes (p : PureIndex) : Prop :=
  4 * p.space.genus - 5 < p.degree - p.space.markings

def LocalSystemCohomologyVanishes (prim : LocalSystemIndex) : Prop :=
  4 * prim.genus - 5 < prim.degree

def OrdinaryCohomologyVanishes (X : ModuliIndex) (d : Int) : Prop := vcdOf X < d

def SpannedByPhiAndPsi (p : PureIndex) : Prop := PrimitiveQuotientVanishes p

def PhiVanishes (p : PureIndex) : Prop :=
  vcdInt p.space.genus (p.space.markings - 1) < p.degree

def SpannedByPsi (p : PureIndex) : Prop := SpannedByPhiAndPsi p ∧ PhiVanishes p

def PureIsFiniteTateSum (p : PureIndex) (t : Int) : Prop :=
  p.weight + 2 * t = 0 ∧ p.degree = p.weight

def PhiIsFiniteTateSum (p : PureIndex) (t : Int) : Prop :=
  p.weight + 2 * t = 0 ∧ p.degree = p.weight

def PsiIsQuotientOfFiniteTateSum (p : PureIndex) (t : Int) : Prop :=
  p.weight + 2 * t = 0 ∧ p.degree = p.weight

def BorelMooreIsTwistOfPure (bm : BMTargetIndex) (p : PureIndex) (d : Int) : Prop :=
  bm.genus = p.space.genus ∧ bm.markings = p.space.markings ∧
    d = 3 * bm.genus - 3 + bm.markings ∧
    p.degree = 2 * d - bm.homologicalDegree ∧ p.weight = p.degree ∧
    bm.weight = p.weight - 2 * d

def TateTwistShift (a b u : Int) : Prop := u = a + b

def PsiClassIsAlgebraicOfTateType (X : ModuliIndex) (t : Int) : Prop :=
  1 ≤ X.markings ∧ t = -1

def ChowKunnethGenerationProperty (X : ModuliIndex) : Prop :=
  X.genus = 6 ∧ X.markings ≤ 5

def CkgpMarkingBound (g b : Int) : Prop := g = 6 ∧ b = 5

def CycleClassMapSurjectsOntoPureWeight (p : PureIndex) : Prop :=
  p.degree = p.weight ∧ p.space.genus = 6 ∧ p.space.markings ≤ 5

def VirtualCohomologicalDimension (X : ModuliIndex) (v : Int) : Prop := v = vcdOf X

def DualizingClassSlotDecomposition (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

def SlotOneComponentVanishes (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

def PsiSpansSlotTwoModuloSlotZero (X : ModuliIndex) : Prop :=
  2 ≤ X.genus ∧ X.markings = 0

-- ---------------------------------------------------------------------------
-- The twenty-five LC66-OBL axiom statements of Claim.lean, as Props.
-- ---------------------------------------------------------------------------

def AX01_phi_is_pullback_span : Prop :=
  ∀ (p q : PureIndex), q.space.genus = p.space.genus →
    q.space.markings = p.space.markings - 1 → q.degree = p.degree →
    q.weight = p.weight → PhiSpannedByForgetfulPullbacks p q

def AX02_psi_is_psi_multiple_span : Prop :=
  ∀ (p r : PureIndex), r.space = p.space → r.degree = p.degree - 2 →
    r.weight = p.weight - 2 → PsiSpannedByPsiMultiples p r

def AX03_omega_class_slot_decomposition : Prop :=
  ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
    DualizingClassSlotDecomposition base

def AX04_morita_slot_one_vanishing : Prop :=
  ∀ (base : ModuliIndex), 2 ≤ base.genus → base.markings = 0 →
    SlotOneComponentVanishes base

def AX05_psi_multiplication_spans_slot_two : Prop :=
  ∀ (base : ModuliIndex), DualizingClassSlotDecomposition base →
    SlotOneComponentVanishes base → PsiSpansSlotTwoModuloSlotZero base

def AX06_clp_pure_weight_quotient_formula : Prop :=
  ∀ (p q r : PureIndex) (base : ModuliIndex) (prim : LocalSystemIndex),
    2 ≤ p.space.genus → 1 ≤ p.space.markings → p.degree = p.weight →
    base.genus = p.space.genus → base.markings = 0 →
    PhiSpannedByForgetfulPullbacks p q → PsiSpannedByPsiMultiples p r →
    PsiSpansSlotTwoModuloSlotZero base → prim.genus = p.space.genus →
    prim.degree = p.degree - p.space.markings → prim.weight = p.weight →
    prim.partitionSize = p.space.markings →
    PrimitiveQuotientIsLocalSystemSum p prim

def AX07_harer_vcd_unpointed : Prop :=
  ∀ (base : ModuliIndex) (v : Int), 2 ≤ base.genus → base.markings = 0 →
    v = 4 * base.genus - 5 → VirtualCohomologicalDimension base v

def AX08_local_system_vanishing_above_vcd : Prop :=
  ∀ (base : ModuliIndex) (v : Int) (prim : LocalSystemIndex),
    VirtualCohomologicalDimension base v → base.markings = 0 →
    prim.genus = base.genus → v < prim.degree →
    LocalSystemCohomologyVanishes prim

def AX09_primitive_quotient_vanishes_from_local_systems : Prop :=
  ∀ (p : PureIndex) (prim : LocalSystemIndex),
    PrimitiveQuotientIsLocalSystemSum p prim →
    LocalSystemCohomologyVanishes prim → PrimitiveQuotientVanishes p

def AX10_span_from_vanishing_primitive_quotient : Prop :=
  ∀ (p : PureIndex), PrimitiveQuotientVanishes p → SpannedByPhiAndPsi p

def AX11_harer_vcd_pointed : Prop :=
  ∀ (base : ModuliIndex) (v : Int), 2 ≤ base.genus → 1 ≤ base.markings →
    v = 4 * base.genus - 4 + base.markings → VirtualCohomologicalDimension base v

def AX12_ordinary_vanishing_above_vcd : Prop :=
  ∀ (base : ModuliIndex) (v d : Int), VirtualCohomologicalDimension base v →
    v < d → OrdinaryCohomologyVanishes base d

def AX13_phi_vanishes_from_pullback_source : Prop :=
  ∀ (p q : PureIndex), PhiSpannedByForgetfulPullbacks p q →
    OrdinaryCohomologyVanishes q.space q.degree → PhiVanishes p

def AX14_psi_spans_after_phi_vanishes : Prop :=
  ∀ (p : PureIndex), SpannedByPhiAndPsi p → PhiVanishes p → SpannedByPsi p

def AX15_ckgp_marking_bound_genus_six : Prop := CkgpMarkingBound 6 5

def AX16_ckgp_holds_in_range : Prop :=
  ∀ (base : ModuliIndex) (b : Int), CkgpMarkingBound base.genus b →
    base.markings ≤ b → ChowKunnethGenerationProperty base

def AX17_cycle_class_surjectivity_from_ckgp : Prop :=
  ∀ (base : ModuliIndex) (p : PureIndex), ChowKunnethGenerationProperty base →
    p.space = base → p.degree = p.weight → CycleClassMapSurjectsOntoPureWeight p

def AX18_algebraic_pure_weight_is_tate : Prop :=
  ∀ (p : PureIndex) (c : Int), CycleClassMapSurjectsOntoPureWeight p →
    p.degree = 2 * c → p.weight = p.degree → PureIsFiniteTateSum p (-c)

def AX19_phi_tate_from_pullback_source : Prop :=
  ∀ (p q : PureIndex) (t : Int), PhiSpannedByForgetfulPullbacks p q →
    PureIsFiniteTateSum q t → PhiIsFiniteTateSum p t

def AX20_psi_class_is_tate_divisor : Prop :=
  ∀ (base : ModuliIndex), 1 ≤ base.markings →
    PsiClassIsAlgebraicOfTateType base (-1)

def AX21_psi_products_are_tate_quotient : Prop :=
  ∀ (p r : PureIndex) (a b t : Int), PsiSpannedByPsiMultiples p r →
    PsiClassIsAlgebraicOfTateType p.space a → PhiIsFiniteTateSum r b →
    p.degree = r.degree + 2 → p.weight = r.weight + 2 → t = a + b →
    PsiIsQuotientOfFiniteTateSum p t

def AX22_polarizable_semisimplicity_upgrade : Prop :=
  ∀ (p : PureIndex) (t : Int), SpannedByPsi p →
    PsiIsQuotientOfFiniteTateSum p t → PureIsFiniteTateSum p t

def AX23_poincare_duality_bm_twist : Prop :=
  ∀ (bm : BMTargetIndex) (p : PureIndex) (d : Int), bm.genus = p.space.genus →
    bm.markings = p.space.markings → d = 3 * bm.genus - 3 + bm.markings →
    p.degree = 2 * d - bm.homologicalDegree → p.weight = p.degree →
    bm.weight = p.weight - 2 * d → BorelMooreIsTwistOfPure bm p d

def AX24_tate_twist_shift_add : Prop :=
  ∀ (a b u : Int), u = a + b → TateTwistShift a b u

def AX25_bm_tate_sum_from_twisted_pure : Prop :=
  ∀ (bm : BMTargetIndex) (p : PureIndex) (d t u : Int),
    BorelMooreIsTwistOfPure bm p d → PureIsFiniteTateSum p t →
    TateTwistShift t d u → bm.tateIndex = u → BMIsFiniteTateSum bm

-- ---------------------------------------------------------------------------
-- Each of the twenty-five is a theorem of the interpretation.
-- ---------------------------------------------------------------------------

theorem model_ax01 : AX01_phi_is_pullback_span := by
  intro p q h1 h2 h3 h4
  exact ⟨h1, h2, h3, h4⟩

theorem model_ax02 : AX02_psi_is_psi_multiple_span := by
  intro p r h1 h2 h3
  exact ⟨h1, h2, h3⟩

theorem model_ax03 : AX03_omega_class_slot_decomposition := by
  intro base h1 h2
  exact ⟨h1, h2⟩

theorem model_ax04 : AX04_morita_slot_one_vanishing := by
  intro base h1 h2
  exact ⟨h1, h2⟩

theorem model_ax05 : AX05_psi_multiplication_spans_slot_two := by
  intro base h1 h2
  exact ⟨h1.1, h2.2⟩

theorem model_ax06 : AX06_clp_pure_weight_quotient_formula := by
  intro p q r base prim _ _ _ _ _ _ _ _ h9 h10 h11 h12
  exact ⟨h9, h10, h11, h12⟩

theorem model_ax07 : AX07_harer_vcd_unpointed := by
  intro base v _ h2 h3
  show v = vcdInt base.genus base.markings
  rw [vcdInt_unpointed base.genus base.markings h2]
  exact h3

theorem model_ax08 : AX08_local_system_vanishing_above_vcd := by
  intro base v prim h1 h2 h3 h4
  have hstep : v = vcdInt base.genus base.markings := h1
  rw [vcdInt_unpointed base.genus base.markings h2] at hstep
  show 4 * prim.genus - 5 < prim.degree
  rw [h3]
  omega

theorem model_ax09 : AX09_primitive_quotient_vanishes_from_local_systems := by
  intro p prim h1 h2
  have hg : prim.genus = p.space.genus := h1.1
  have hd : prim.degree = p.degree - p.space.markings := h1.2.1
  have hlt : 4 * prim.genus - 5 < prim.degree := h2
  show 4 * p.space.genus - 5 < p.degree - p.space.markings
  omega

theorem model_ax10 : AX10_span_from_vanishing_primitive_quotient := by
  intro p h
  exact h

theorem model_ax11 : AX11_harer_vcd_pointed := by
  intro base v _ h2 h3
  have hne : ¬ (base.markings = 0) := by omega
  show v = vcdInt base.genus base.markings
  rw [vcdInt_pointed base.genus base.markings hne]
  exact h3

theorem model_ax12 : AX12_ordinary_vanishing_above_vcd := by
  intro base v d h1 h2
  have hv : v = vcdOf base := h1
  show vcdOf base < d
  omega

theorem model_ax13 : AX13_phi_vanishes_from_pullback_source := by
  intro p q h1 h2
  have hg : q.space.genus = p.space.genus := h1.1
  have hm : q.space.markings = p.space.markings - 1 := h1.2.1
  have hd : q.degree = p.degree := h1.2.2.1
  have hv : vcdInt q.space.genus q.space.markings < q.degree := h2
  show vcdInt p.space.genus (p.space.markings - 1) < p.degree
  rw [← hg, ← hm, ← hd]
  exact hv

theorem model_ax14 : AX14_psi_spans_after_phi_vanishes := by
  intro p h1 h2
  exact ⟨h1, h2⟩

theorem model_ax15 : AX15_ckgp_marking_bound_genus_six := by
  exact ⟨rfl, rfl⟩

theorem model_ax16 : AX16_ckgp_holds_in_range := by
  intro base b h1 h2
  have hg : base.genus = 6 := h1.1
  have hb : b = 5 := h1.2
  show base.genus = 6 ∧ base.markings ≤ 5
  exact ⟨hg, by omega⟩

theorem model_ax17 : AX17_cycle_class_surjectivity_from_ckgp := by
  intro base p h1 h2 h3
  show p.degree = p.weight ∧ p.space.genus = 6 ∧ p.space.markings ≤ 5
  rw [h2]
  exact ⟨h3, h1.1, h1.2⟩

theorem model_ax18 : AX18_algebraic_pure_weight_is_tate := by
  intro p c _ h2 h3
  show p.weight + 2 * (-c) = 0 ∧ p.degree = p.weight
  exact ⟨by omega, by omega⟩

theorem model_ax19 : AX19_phi_tate_from_pullback_source := by
  intro p q t h1 h2
  have hd : q.degree = p.degree := h1.2.2.1
  have hw : q.weight = p.weight := h1.2.2.2
  have h2a : q.weight + 2 * t = 0 := h2.1
  have h2b : q.degree = q.weight := h2.2
  show p.weight + 2 * t = 0 ∧ p.degree = p.weight
  exact ⟨by omega, by omega⟩

theorem model_ax20 : AX20_psi_class_is_tate_divisor := by
  intro base h
  exact ⟨h, rfl⟩

theorem model_ax21 : AX21_psi_products_are_tate_quotient := by
  intro p r a b t _ h2 h3 h4 h5 h6
  have ha : a = -1 := h2.2
  have h3a : r.weight + 2 * b = 0 := h3.1
  have h3b : r.degree = r.weight := h3.2
  show p.weight + 2 * t = 0 ∧ p.degree = p.weight
  exact ⟨by omega, by omega⟩

theorem model_ax22 : AX22_polarizable_semisimplicity_upgrade := by
  intro p t _ h2
  exact h2

theorem model_ax23 : AX23_poincare_duality_bm_twist := by
  intro bm p d h1 h2 h3 h4 h5 h6
  exact ⟨h1, h2, h3, h4, h5, h6⟩

theorem model_ax24 : AX24_tate_twist_shift_add := by
  intro a b u h
  exact h

theorem model_ax25 : AX25_bm_tate_sum_from_twisted_pure := by
  intro bm p d t u h1 h2 h3 h4
  have hd : p.degree = 2 * d - bm.homologicalDegree := h1.2.2.2.1
  have hw : p.weight = p.degree := h1.2.2.2.2.1
  have hbw : bm.weight = p.weight - 2 * d := h1.2.2.2.2.2
  have hp : p.weight + 2 * t = 0 := h2.1
  have hu : u = t + d := h3
  show bm.weight + 2 * bm.tateIndex = 0 ∧ bm.homologicalDegree + bm.weight = 0
  exact ⟨by omega, by omega⟩

-- ---------------------------------------------------------------------------
-- Non-collapse.  The interpretation satisfies the exact target, and refutes
-- twelve nearby statements, so none of the load-bearing predicates is True.
-- ---------------------------------------------------------------------------

def NC00_target_holds : Prop := BMIsFiniteTateSum exactC66BMTarget

def NC01_bm_wrong_tate_index : Prop :=
  ¬ BMIsFiniteTateSum { genus := 6, markings := 6, homologicalDegree := 16,
      weight := -16, tateIndex := 7 }

def NC02_bm_wrong_homological_degree : Prop :=
  ¬ BMIsFiniteTateSum { genus := 6, markings := 6, homologicalDegree := 15,
      weight := -16, tateIndex := 8 }

def NC03_pure_wrong_tate_index : Prop := ¬ PureIsFiniteTateSum pureM66deg26 (-12)

def NC04_ckgp_fails_at_six_markings : Prop := ¬ ChowKunnethGenerationProperty moduliM66

def NC05_local_system_at_vcd : Prop :=
  ¬ LocalSystemCohomologyVanishes { genus := 6, degree := 19, weight := 26,
      partitionSize := 6 }

def NC06_ordinary_at_vcd : Prop := ¬ OrdinaryCohomologyVanishes moduliM65 25

def NC07_primitive_quotient_degree_24 : Prop := ¬ PrimitiveQuotientVanishes pureM66deg24

def NC08_phi_nonvanishing_degree_24 : Prop := ¬ PhiVanishes pureM66deg24

def NC09_psi_does_not_span_degree_24 : Prop := ¬ SpannedByPsi pureM66deg24

def NC10_twist_is_exact : Prop := ¬ TateTwistShift (-13) 21 7

def NC11_duality_twist_is_dimension : Prop :=
  ¬ BorelMooreIsTwistOfPure exactC66BMTarget pureM66deg26 20

def NC12_slot_two_needs_genus_two : Prop :=
  ¬ PsiSpansSlotTwoModuloSlotZero { genus := 1, markings := 0 }

theorem model_nc00 : NC00_target_holds := by decide

theorem model_nc01 : NC01_bm_wrong_tate_index := by decide

theorem model_nc02 : NC02_bm_wrong_homological_degree := by decide

theorem model_nc03 : NC03_pure_wrong_tate_index := by decide

theorem model_nc04 : NC04_ckgp_fails_at_six_markings := by decide

theorem model_nc05 : NC05_local_system_at_vcd := by decide

theorem model_nc06 : NC06_ordinary_at_vcd := by decide

theorem model_nc07 : NC07_primitive_quotient_degree_24 := by decide

theorem model_nc08 : NC08_phi_nonvanishing_degree_24 := by decide

theorem model_nc09 : NC09_psi_does_not_span_degree_24 := by decide

theorem model_nc10 : NC10_twist_is_exact := by decide

theorem model_nc11 : NC11_duality_twist_is_dimension := by decide

theorem model_nc12 : NC12_slot_two_needs_genus_two := by decide

-- ---------------------------------------------------------------------------
-- The single model theorem: all twenty-five modeled axioms and all thirteen
-- consistency/non-collapse witnesses at once.
-- ---------------------------------------------------------------------------

theorem c66_model_is_consistent_and_noncollapsing :
    AX01_phi_is_pullback_span ∧ AX02_psi_is_psi_multiple_span ∧
    AX03_omega_class_slot_decomposition ∧ AX04_morita_slot_one_vanishing ∧
    AX05_psi_multiplication_spans_slot_two ∧
    AX06_clp_pure_weight_quotient_formula ∧ AX07_harer_vcd_unpointed ∧
    AX08_local_system_vanishing_above_vcd ∧
    AX09_primitive_quotient_vanishes_from_local_systems ∧
    AX10_span_from_vanishing_primitive_quotient ∧ AX11_harer_vcd_pointed ∧
    AX12_ordinary_vanishing_above_vcd ∧ AX13_phi_vanishes_from_pullback_source ∧
    AX14_psi_spans_after_phi_vanishes ∧ AX15_ckgp_marking_bound_genus_six ∧
    AX16_ckgp_holds_in_range ∧ AX17_cycle_class_surjectivity_from_ckgp ∧
    AX18_algebraic_pure_weight_is_tate ∧ AX19_phi_tate_from_pullback_source ∧
    AX20_psi_class_is_tate_divisor ∧ AX21_psi_products_are_tate_quotient ∧
    AX22_polarizable_semisimplicity_upgrade ∧ AX23_poincare_duality_bm_twist ∧
    AX24_tate_twist_shift_add ∧ AX25_bm_tate_sum_from_twisted_pure ∧
    NC00_target_holds ∧ NC01_bm_wrong_tate_index ∧
    NC02_bm_wrong_homological_degree ∧ NC03_pure_wrong_tate_index ∧
    NC04_ckgp_fails_at_six_markings ∧ NC05_local_system_at_vcd ∧
    NC06_ordinary_at_vcd ∧ NC07_primitive_quotient_degree_24 ∧
    NC08_phi_nonvanishing_degree_24 ∧ NC09_psi_does_not_span_degree_24 ∧
    NC10_twist_is_exact ∧ NC11_duality_twist_is_dimension ∧
    NC12_slot_two_needs_genus_two :=
  ⟨model_ax01, model_ax02, model_ax03, model_ax04, model_ax05, model_ax06,
    model_ax07, model_ax08, model_ax09, model_ax10, model_ax11, model_ax12,
    model_ax13, model_ax14, model_ax15, model_ax16, model_ax17, model_ax18,
    model_ax19, model_ax20, model_ax21, model_ax22, model_ax23, model_ax24,
    model_ax25, model_nc00, model_nc01, model_nc02, model_nc03, model_nc04,
    model_nc05, model_nc06, model_nc07, model_nc08, model_nc09, model_nc10,
    model_nc11, model_nc12⟩

#print axioms c66_model_is_consistent_and_noncollapsing
