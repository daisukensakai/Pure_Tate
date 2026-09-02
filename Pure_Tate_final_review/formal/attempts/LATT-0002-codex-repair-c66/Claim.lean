set_option autoImplicit false
-- LEAN-CAMPAIGN LC66-002
-- LEAN-ATTEMPT LATT-0002
-- LEAN-SOURCE-ATTEMPT ATT-0136
-- LEAN-CLAIM-CONTRACT C66-EXACT-TARGET-V1
-- LEAN-TARGET-SIGNATURE BM(g=6,n=6,degree=16,weight=-16,tate=8);ORD(g=6,n=6,degree=26,weight=26,tate=-13,dimension=21,twist=21);rank>=0
-- LEAN-THEOREM c66_exact_bm_is_finite_tate_sum
-- LEAN-OPTIONAL-THEOREM optional_primitive_route_equals_psi
-- LEAN-WEIGHT ClosedPureIndex and OpenPureIndex are disjoint Lean types. The exported theorem uses only OBL-01 through OBL-05 and OBL-07 through OBL-09; OBL-06 is printed in a separate optional theorem closure. Arithmetic, six-slot combinatorics, and well-founded recursion are proved by Lean.

-- LEAN-TRUSTED-PRELUDE-BEGIN
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

axiom BMIsFiniteTateSum : BMTargetIndex -> Prop
-- LEAN-AXIOM BMIsFiniteTateSum => VOCAB -- exact BM target predicate; semantic interpretation is review-audited
-- LEAN-TRUSTED-PRELUDE-END

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

axiom vocab : C66Vocabulary
-- LEAN-AXIOM vocab => VOCAB -- the complete carrier vocabulary whose exact type is hash-shared with Model.lean

def moduliM6 : ModuliIndex := { genus := 6, markings := 0 }
def moduliM65 : ModuliIndex := { genus := 6, markings := 5 }
def moduliM66 : ModuliIndex := { genus := 6, markings := 6 }
def sourceC6deg26 : ClosedPureIndex := { genus := 6, factors := 6, degree := 26, weight := 26 }
def pureM66deg26 : OpenPureIndex := { space := moduliM66, degree := 26, weight := 26 }
def pureM66deg24 : OpenPureIndex := { space := moduliM66, degree := 24, weight := 24 }
def pureM65deg26 : OpenPureIndex := { space := moduliM65, degree := 26, weight := 26 }
def pureM65deg24 : OpenPureIndex := { space := moduliM65, degree := 24, weight := 24 }
def primitiveM6deg20 : LocalSystemIndex := { genus := 6, degree := 20, weight := 26, partitionSize := 6 }

axiom deligne_lowest_weight_restriction_surjection : forall (src : ClosedPureIndex) (tgt : OpenPureIndex),
    src.genus = tgt.space.genus -> src.factors = tgt.space.markings ->
    src.degree = tgt.degree -> src.weight = tgt.weight -> src.degree = src.weight ->
    vocab.RestrictionSurjectsOnLowestWeight src tgt
-- LEAN-AXIOM deligne_lowest_weight_restriction_surjection => LC66-OBL-01 -- lowest-weight restriction from the closed fibre power to the open diagonal complement; separate source and target types make an identity interpretation impossible

axiom containment_transfers_along_surjection : forall (src : ClosedPureIndex) (tgt : OpenPureIndex),
    vocab.RestrictionSurjectsOnLowestWeight src tgt ->
    (forall idx : KunnethIndex, idx.source = src -> lenOf idx.slots = Int.toNat src.factors ->
      vocab.KunnethSummandRestrictsIntoPsi idx tgt) ->
    vocab.KunnethSplittingByChowKunnethProjectors src -> vocab.ContainedInPsi tgt
-- LEAN-AXIOM containment_transfers_along_surjection => LC66-OBL-01 -- surjectivity plus the actual closed-source direct sum and containment of every source summand transfers containment to the whole open target

axiom deligne_smooth_proper_leray_degeneration : forall base : ModuliIndex,
    2 <= base.genus -> base.markings = 0 -> vocab.LerayDegeneratesAtE2 base
-- LEAN-AXIOM deligne_smooth_proper_leray_degeneration => LC66-OBL-02 -- smooth-proper Leray E2 degeneration, which alone gives only the associated graded

axiom pty_projectors_are_algebraic_correspondences : forall base : ModuliIndex,
    2 <= base.genus -> base.markings = 0 -> vocab.ChowKunnethProjectorIsAlgebraicCorrespondence base
-- LEAN-AXIOM pty_projectors_are_algebraic_correspondences => LC66-OBL-02 -- PTY algebraic correspondences supply an actual MHS splitting

axiom pty_r_two_projector_form : forall base : ModuliIndex,
    2 <= base.genus -> base.markings = 0 -> vocab.RTwoProjectorInPsiAndPullbackSpan base
-- LEAN-AXIOM pty_r_two_projector_form => LC66-OBL-02 -- pi_2=psi_2/(2g-2)-kappa_1/(2(2g-2)^2) lies in the psi-plus-pullback span

axiom kunneth_splitting_of_pure_weight_source : forall (src : ClosedPureIndex) (base : ModuliIndex),
    vocab.LerayDegeneratesAtE2 base -> vocab.ChowKunnethProjectorIsAlgebraicCorrespondence base ->
    vocab.RTwoProjectorInPsiAndPullbackSpan base -> base.genus = src.genus ->
    base.markings = 0 -> 1 <= src.factors -> src.degree = src.weight ->
    vocab.KunnethSplittingByChowKunnethProjectors src
-- LEAN-AXIOM kunneth_splitting_of_pure_weight_source => LC66-OBL-02 -- actual PTY-split Kunneth decomposition of W_k H^k(C^n), now typed only on ClosedPureIndex

axiom omega_class_slot_decomposition : forall base : ModuliIndex,
    2 <= base.genus -> base.markings = 0 -> vocab.DualizingClassSlotDecomposition base
-- LEAN-AXIOM omega_class_slot_decomposition => LC66-OBL-03 -- omega_s=a_s+b_s+c_s in slots zero, one, two, with only c_s the R2 isomorphism

axiom morita_slot_one_vanishing : forall base : ModuliIndex,
    2 <= base.genus -> base.markings = 0 -> vocab.SlotOneCrossTermVanishes base
-- LEAN-AXIOM morita_slot_one_vanishing => LC66-OBL-03 -- rational Morita vanishing kills b_s

axiom omega_multiplication_hits_slot_two_modulo_errors : forall base : ModuliIndex,
    vocab.DualizingClassSlotDecomposition base -> vocab.SlotOneCrossTermVanishes base ->
    vocab.RTwoProjectorInPsiAndPullbackSpan base -> vocab.OmegaMultiplicationHitsSlotTwo base
-- LEAN-AXIOM omega_multiplication_hits_slot_two_modulo_errors => LC66-OBL-03 -- omega multiplication reaches slot two modulo the explicitly tracked slot-zero and slot-one errors

axiom harer_vcd_pointed : forall (base : ModuliIndex) (v : Int),
    2 <= base.genus -> 1 <= base.markings -> v = 4 * base.genus - 4 + base.markings ->
    vocab.VirtualCohomologicalDimension base v
-- LEAN-AXIOM harer_vcd_pointed => LC66-OBL-04 -- vcd(PMod_g,n)=4g-4+n

axiom constant_coefficient_vanishing_above_vcd : forall (base : ModuliIndex) (v d : Int),
    vocab.VirtualCohomologicalDimension base v -> v < d -> vocab.OrdinaryCohomologyVanishes base d
-- LEAN-AXIOM constant_coefficient_vanishing_above_vcd => LC66-OBL-04 -- constant rational cohomology vanishes strictly above vcd

axiom phi_vanishes_from_pullback_source : forall (p q : OpenPureIndex),
    vocab.PhiSpannedByForgetfulPullbacks p q -> vocab.OrdinaryCohomologyVanishes q.space q.degree ->
    vocab.PhiVanishes p
-- LEAN-AXIOM phi_vanishes_from_pullback_source => LC66-OBL-04 -- Phi vanishes when its five-marking source cohomology vanishes

axiom phi_is_pullback_span : forall (p q : OpenPureIndex),
    q.space.genus = p.space.genus -> q.space.markings = p.space.markings - 1 ->
    q.degree = p.degree -> q.weight = p.weight -> vocab.PhiSpannedByForgetfulPullbacks p q
-- LEAN-AXIOM phi_is_pullback_span => LC66-OBL-04 -- definition of Phi by forgetful pullbacks

axiom psi_is_psi_multiple_span : forall (p r : OpenPureIndex),
    r.space = p.space -> r.degree = p.degree - 2 -> r.weight = p.weight - 2 ->
    vocab.PsiSpannedByPsiMultiples p r
-- LEAN-AXIOM psi_is_psi_multiple_span => LC66-OBL-04 -- definition of Psi as psi times Phi in degree and weight two lower

axiom harer_vcd_unpointed : forall (base : ModuliIndex) (v : Int),
    2 <= base.genus -> base.markings = 0 -> v = 4 * base.genus - 5 ->
    vocab.VirtualCohomologicalDimension base v
-- LEAN-AXIOM harer_vcd_unpointed => LC66-OBL-05 -- vcd(Mod_g)=4g-5

axiom local_coefficient_vanishing_above_vcd : forall (base : ModuliIndex) (v d : Int),
    vocab.VirtualCohomologicalDimension base v -> base.markings = 0 -> v < d ->
    vocab.LocalSystemCohomologyVanishesAllCoefficients base d
-- LEAN-AXIOM local_coefficient_vanishing_above_vcd => LC66-OBL-05 -- vanishing strictly above vcd for every finite-dimensional rational local system

axiom kunneth_summand_vanishes_below_base_degree : forall (idx : KunnethIndex) (base : ModuliIndex) (v : Int),
    base.genus = idx.source.genus -> base.markings = 0 ->
    vocab.LocalSystemCohomologyVanishesAllCoefficients base (idx.source.degree - (total idx.slots : Int)) ->
    vocab.VirtualCohomologicalDimension base v -> v < idx.source.degree - (total idx.slots : Int) ->
    vocab.KunnethSummandVanishes idx
-- LEAN-AXIOM kunneth_summand_vanishes_below_base_degree => LC66-OBL-05 -- A_i vanishes when its base degree k-|i| is above vcd

axiom vanishing_summand_restricts_into_psi : forall (idx : KunnethIndex) (tgt : OpenPureIndex),
    idx.source.genus = tgt.space.genus -> idx.source.factors = tgt.space.markings ->
    idx.source.degree = tgt.degree -> idx.source.weight = tgt.weight ->
    vocab.KunnethSummandVanishes idx -> vocab.KunnethSummandRestrictsIntoPsi idx tgt
-- LEAN-AXIOM vanishing_summand_restricts_into_psi => LC66-OBL-05 -- zero restriction lies in Psi

axiom slot_two_summand_restricts_into_psi_modulo_errors : forall
    (idx errZero errOne : KunnethIndex) (pre post : List Slot)
    (tgt r q : OpenPureIndex) (base5 : ModuliIndex),
    idx.slots = pre ++ Slot.two :: post -> errZero.source = idx.source ->
    errZero.slots = pre ++ Slot.zero :: post -> errOne.source = idx.source ->
    errOne.slots = pre ++ Slot.one :: post -> vocab.OmegaMultiplicationHitsSlotTwo moduliM6 ->
    idx.source.genus = tgt.space.genus -> idx.source.factors = tgt.space.markings ->
    idx.source.degree = tgt.degree -> idx.source.weight = tgt.weight ->
    vocab.PsiSpannedByPsiMultiples tgt r -> vocab.PhiSpannedByForgetfulPullbacks r q ->
    base5.genus = tgt.space.genus -> base5.markings = tgt.space.markings - 1 -> q.space = base5 ->
    vocab.OrdinaryCohomologyVanishes base5 tgt.degree ->
    vocab.KunnethSummandRestrictsIntoPsi errOne tgt -> vocab.KunnethSummandRestrictsIntoPsi idx tgt
-- LEAN-AXIOM slot_two_summand_restricts_into_psi_modulo_errors => LC66-OBL-05 -- one downward-induction step: omega term enters Psi, slot-zero dies through H^k(M_g,n-1), and slot-one has smaller total

axiom clp_primitive_quotient_formula : forall (p : OpenPureIndex) (prim : LocalSystemIndex),
    2 <= p.space.genus -> 1 <= p.space.markings -> p.degree = p.weight ->
    prim.genus = p.space.genus -> prim.degree = p.degree - p.space.markings ->
    prim.weight = p.weight -> prim.partitionSize = p.space.markings ->
    vocab.PrimitiveQuotientIsLocalSystemSum p prim
-- LEAN-AXIOM clp_primitive_quotient_formula => LC66-OBL-06 -- optional CLP primitive-quotient formula

axiom primitive_quotient_vanishes_from_local_coefficients : forall (p : OpenPureIndex) (prim : LocalSystemIndex),
    vocab.PrimitiveQuotientIsLocalSystemSum p prim ->
    vocab.LocalSystemCohomologyVanishesAllCoefficients { genus := prim.genus, markings := 0 } prim.degree ->
    vocab.PrimitiveQuotientVanishes p
-- LEAN-AXIOM primitive_quotient_vanishes_from_local_coefficients => LC66-OBL-06 -- optional quotient vanishing from H20(M6;V)=0

axiom equality_from_vanishing_primitive_quotient_and_phi : forall p : OpenPureIndex,
    vocab.PrimitiveQuotientVanishes p -> vocab.PhiVanishes p -> vocab.EqualsPsi p
-- LEAN-AXIOM equality_from_vanishing_primitive_quotient_and_phi => LC66-OBL-06 -- optional equality W=Psi from zero primitive quotient and Phi

axiom ckgp_marking_bound_genus_six : vocab.CkgpMarkingBound 6 5
-- LEAN-AXIOM ckgp_marking_bound_genus_six => LC66-OBL-07 -- c(6)=5 inclusively

axiom ckgp_holds_in_range : forall (base : ModuliIndex) (b : Int),
    vocab.CkgpMarkingBound base.genus b -> base.markings <= b ->
    vocab.ChowKunnethGenerationProperty base
-- LEAN-AXIOM ckgp_holds_in_range => LC66-OBL-07 -- CKgP on the open stack for n<=c(g)

axiom cycle_class_surjectivity_from_ckgp : forall (base : ModuliIndex) (p : OpenPureIndex),
    vocab.ChowKunnethGenerationProperty base -> p.space = base -> p.degree = p.weight ->
    vocab.CycleClassMapSurjectsOntoPureWeight p
-- LEAN-AXIOM cycle_class_surjectivity_from_ckgp => LC66-OBL-07 -- CKgP makes cycles surject onto lowest weight

axiom algebraic_pure_weight_is_tate : forall (p : OpenPureIndex) (c : Int),
    vocab.CycleClassMapSurjectsOntoPureWeight p -> vocab.PurePolarizableOfWeight p ->
    p.degree = 2 * c -> p.weight = p.degree -> vocab.PureIsFiniteTateSum p (-c)
-- LEAN-AXIOM algebraic_pure_weight_is_tate => LC66-OBL-07 -- algebraic pure weight 2c is a finite Q(-c)-sum

axiom lowest_weight_is_pure_polarizable : forall p : OpenPureIndex,
    p.degree = p.weight -> vocab.PurePolarizableOfWeight p
-- LEAN-AXIOM lowest_weight_is_pure_polarizable => LC66-OBL-07 -- lowest-weight cohomology of the smooth open stack is pure polarizable

axiom phi_tate_from_pullback_source : forall (p q : OpenPureIndex) (t : Int),
    vocab.PhiSpannedByForgetfulPullbacks p q -> vocab.PureIsFiniteTateSum q t ->
    vocab.PhiIsFiniteTateSum p t
-- LEAN-AXIOM phi_tate_from_pullback_source => LC66-OBL-08 -- pullback images preserve Tate type

axiom psi_class_is_tate_divisor : forall base : ModuliIndex,
    1 <= base.markings -> vocab.PsiClassIsAlgebraicOfTateType base (-1)
-- LEAN-AXIOM psi_class_is_tate_divisor => LC66-OBL-08 -- psi is algebraic of type Q(-1)

axiom psi_products_are_tate_quotient : forall (p r : OpenPureIndex) (a b t : Int),
    vocab.PsiSpannedByPsiMultiples p r -> vocab.PsiClassIsAlgebraicOfTateType p.space a ->
    vocab.PhiIsFiniteTateSum r b -> p.degree = r.degree + 2 -> p.weight = r.weight + 2 ->
    t = a + b -> vocab.PsiIsQuotientOfFiniteTateSum p t
-- LEAN-AXIOM psi_products_are_tate_quotient => LC66-OBL-08 -- psi products make Psi a quotient of a finite Q(a+b)-sum

axiom polarizable_semisimplicity_upgrade : forall (p : OpenPureIndex) (t : Int),
    vocab.ContainedInPsi p -> vocab.PurePolarizableOfWeight p ->
    vocab.PsiIsQuotientOfFiniteTateSum p t -> vocab.PureIsFiniteTateSum p t
-- LEAN-AXIOM polarizable_semisimplicity_upgrade => LC66-OBL-08 -- semisimplicity upgrades the whole contained pure group to an honest Tate sum

axiom poincare_duality_bm_twist : forall (bm : BMTargetIndex) (p : OpenPureIndex) (d : Int),
    bm.genus = p.space.genus -> bm.markings = p.space.markings ->
    d = 3 * bm.genus - 3 + bm.markings -> p.degree = 2 * d - bm.homologicalDegree ->
    p.weight = p.degree -> bm.weight = p.weight - 2 * d ->
    vocab.BorelMooreIsTwistOfPure bm p d
-- LEAN-AXIOM poincare_duality_bm_twist => LC66-OBL-09 -- stack-level rational Poincare duality with dimension twist

axiom tate_twist_shift_add : forall (a b u : Int), u = a + b -> vocab.TateTwistShift a b u
-- LEAN-AXIOM tate_twist_shift_add => LC66-OBL-09 -- Q(a)(b)=Q(a+b)

axiom bm_tate_sum_from_twisted_pure : forall (bm : BMTargetIndex) (p : OpenPureIndex) (d t u : Int),
    vocab.BorelMooreIsTwistOfPure bm p d -> vocab.PureIsFiniteTateSum p t ->
    vocab.TateTwistShift t d u -> bm.tateIndex = u -> BMIsFiniteTateSum bm
-- LEAN-AXIOM bm_tate_sum_from_twisted_pure => LC66-OBL-09 -- duality transports the whole pure Tate sum to the exact BM target, including rank zero

theorem closedSourceHasSixFactors : sourceC6deg26.factors = 6 := by decide

theorem vcdMod6 : vocab.VirtualCohomologicalDimension moduliM6 19 :=
  harer_vcd_unpointed moduliM6 19 (by decide) (by decide) (by decide)

theorem vcdPMod65 : vocab.VirtualCohomologicalDimension moduliM65 25 :=
  harer_vcd_pointed moduliM65 25 (by decide) (by decide) (by decide)

theorem ordVanishM65deg26 : vocab.OrdinaryCohomologyVanishes moduliM65 26 :=
  constant_coefficient_vanishing_above_vcd moduliM65 25 26 vcdPMod65 (by decide)

theorem phiSpan26 : vocab.PhiSpannedByForgetfulPullbacks pureM66deg26 pureM65deg26 :=
  phi_is_pullback_span pureM66deg26 pureM65deg26 (by decide) (by decide) (by decide) (by decide)

theorem phiSpan24 : vocab.PhiSpannedByForgetfulPullbacks pureM66deg24 pureM65deg24 :=
  phi_is_pullback_span pureM66deg24 pureM65deg24 (by decide) (by decide) (by decide) (by decide)

theorem psiSpan26 : vocab.PsiSpannedByPsiMultiples pureM66deg26 pureM66deg24 :=
  psi_is_psi_multiple_span pureM66deg26 pureM66deg24 rfl (by decide) (by decide)

theorem omegaHitsSlotTwo : vocab.OmegaMultiplicationHitsSlotTwo moduliM6 :=
  omega_multiplication_hits_slot_two_modulo_errors moduliM6
    (omega_class_slot_decomposition moduliM6 (by decide) (by decide))
    (morita_slot_one_vanishing moduliM6 (by decide) (by decide))
    (pty_r_two_projector_form moduliM6 (by decide) (by decide))

theorem restrictionSurjection : vocab.RestrictionSurjectsOnLowestWeight sourceC6deg26 pureM66deg26 :=
  deligne_lowest_weight_restriction_surjection sourceC6deg26 pureM66deg26
    (by decide) (by decide) (by decide) (by decide) (by decide)

theorem kunnethSplitting : vocab.KunnethSplittingByChowKunnethProjectors sourceC6deg26 :=
  kunneth_splitting_of_pure_weight_source sourceC6deg26 moduliM6
    (deligne_smooth_proper_leray_degeneration moduliM6 (by decide) (by decide))
    (pty_projectors_are_algebraic_correspondences moduliM6 (by decide) (by decide))
    (pty_r_two_projector_form moduliM6 (by decide) (by decide))
    (by decide) (by decide) (by decide) (by decide)

theorem localCoeffVanish20 : vocab.LocalSystemCohomologyVanishesAllCoefficients moduliM6 20 :=
  local_coefficient_vanishing_above_vcd moduliM6 19 20 vcdMod6 (by decide) (by decide)

theorem total_split (pre : List Slot) (a : Slot) (post : List Slot) :
    total (pre ++ a :: post) = total pre + (slotVal a + total post) := by
  induction pre with
  | nil => simp [total]
  | cons b rest ih => simp [total, ih, Nat.add_assoc]

theorem len_split (pre : List Slot) (a : Slot) (post : List Slot) :
    lenOf (pre ++ a :: post) = lenOf pre + (1 + lenOf post) := by
  induction pre with
  | nil => simp [lenOf]
  | cons b rest ih => simp [lenOf, ih, Nat.add_assoc]

theorem exists_two_of_len_lt_total : forall l : List Slot, lenOf l < total l ->
    Exists fun pre => Exists fun post => l = pre ++ Slot.two :: post := by
  intro l
  induction l with
  | nil => intro h; exact absurd h (by decide)
  | cons a rest ih =>
      intro h
      cases a with
      | two => exact Exists.intro [] (Exists.intro rest rfl)
      | zero =>
          have hh : 1 + lenOf rest < 0 + total rest := h
          obtain ⟨pre, post, hp⟩ := ih (by omega)
          exact ⟨Slot.zero :: pre, post, by rw [hp]; rfl⟩
      | one =>
          have hh : 1 + lenOf rest < 1 + total rest := h
          obtain ⟨pre, post, hp⟩ := ih (by omega)
          exact ⟨Slot.one :: pre, post, by rw [hp]; rfl⟩

theorem baseCaseVanishes (idx : KunnethIndex) (hs : idx.source = sourceC6deg26)
    (hm : total idx.slots <= 6) : vocab.KunnethSummandVanishes idx := by
  have hgt : (19 : Int) < idx.source.degree - (total idx.slots : Int) := by
    rw [hs]
    show (19 : Int) < 26 - (total idx.slots : Int)
    omega
  have hcoeff : vocab.LocalSystemCohomologyVanishesAllCoefficients moduliM6
      (idx.source.degree - (total idx.slots : Int)) :=
    local_coefficient_vanishing_above_vcd moduliM6 19
      (idx.source.degree - (total idx.slots : Int)) vcdMod6 (by decide) hgt
  exact kunneth_summand_vanishes_below_base_degree idx moduliM6 19
    (by rw [hs]; decide) (by decide) hcoeff vcdMod6 hgt

theorem summandAux : forall (fuel : Nat) (idx : KunnethIndex),
    total idx.slots <= fuel -> idx.source = sourceC6deg26 -> lenOf idx.slots = 6 ->
    vocab.KunnethSummandRestrictsIntoPsi idx pureM66deg26 := by
  intro fuel
  induction fuel with
  | zero =>
      intro idx hf hs hl
      exact vanishing_summand_restricts_into_psi idx pureM66deg26
        (by rw [hs]; decide) (by rw [hs]; decide) (by rw [hs]; decide) (by rw [hs]; decide)
        (baseCaseVanishes idx hs (by omega))
  | succ f ih =>
      intro idx hf hs hl
      by_cases hm : total idx.slots <= 6
      · exact vanishing_summand_restricts_into_psi idx pureM66deg26
          (by rw [hs]; decide) (by rw [hs]; decide) (by rw [hs]; decide) (by rw [hs]; decide)
          (baseCaseVanishes idx hs hm)
      · have hlt : lenOf idx.slots < total idx.slots := by omega
        obtain ⟨pre, post, hsplit⟩ := exists_two_of_len_lt_total idx.slots hlt
        let errZero : KunnethIndex := { source := idx.source, slots := pre ++ Slot.zero :: post }
        let errOne : KunnethIndex := { source := idx.source, slots := pre ++ Slot.one :: post }
        have hone : vocab.KunnethSummandRestrictsIntoPsi errOne pureM66deg26 := by
          apply ih errOne
          · dsimp [errOne]
            rw [total_split]
            have htwo : total idx.slots = total pre + (2 + total post) := by
              rw [hsplit, total_split]
              rfl
            show total pre + (1 + total post) <= f
            omega
          · dsimp [errOne]; exact hs
          · dsimp [errOne]
            rw [len_split]
            have hlen : lenOf idx.slots = lenOf pre + (1 + lenOf post) := by
              rw [hsplit, len_split]
            omega
        exact slot_two_summand_restricts_into_psi_modulo_errors idx errZero errOne pre post
          pureM66deg26 pureM66deg24 pureM65deg24 moduliM65 hsplit rfl rfl rfl rfl
          omegaHitsSlotTwo (by rw [hs]; decide) (by rw [hs]; decide) (by rw [hs]; decide)
          (by rw [hs]; decide) psiSpan26 phiSpan24 (by decide) (by decide) rfl
          ordVanishM65deg26 hone

theorem summandRestrictsIntoPsi (idx : KunnethIndex) (hs : idx.source = sourceC6deg26)
    (hl : lenOf idx.slots = Int.toNat sourceC6deg26.factors) :
    vocab.KunnethSummandRestrictsIntoPsi idx pureM66deg26 := by
  apply summandAux (total idx.slots) idx (Nat.le_refl _) hs
  simpa [sourceC6deg26] using hl

theorem containedInPsi : vocab.ContainedInPsi pureM66deg26 :=
  containment_transfers_along_surjection sourceC6deg26 pureM66deg26
    restrictionSurjection summandRestrictsIntoPsi kunnethSplitting

theorem tateM65deg24 : vocab.PureIsFiniteTateSum pureM65deg24 (-12) :=
  algebraic_pure_weight_is_tate pureM65deg24 12
    (cycle_class_surjectivity_from_ckgp moduliM65 pureM65deg24
      (ckgp_holds_in_range moduliM65 5 ckgp_marking_bound_genus_six (by decide)) rfl (by decide))
    (lowest_weight_is_pure_polarizable pureM65deg24 (by decide)) (by decide) (by decide)

theorem phiVanish26 : vocab.PhiVanishes pureM66deg26 :=
  phi_vanishes_from_pullback_source pureM66deg26 pureM65deg26 phiSpan26 ordVanishM65deg26

theorem optional_primitive_route_equals_psi : vocab.EqualsPsi pureM66deg26 :=
  equality_from_vanishing_primitive_quotient_and_phi pureM66deg26
    (primitive_quotient_vanishes_from_local_coefficients pureM66deg26 primitiveM6deg20
      (clp_primitive_quotient_formula pureM66deg26 primitiveM6deg20
        (by decide) (by decide) (by decide) (by decide) (by decide) (by decide) (by decide))
      localCoeffVanish20)
    phiVanish26

theorem ordinaryTate : vocab.PureIsFiniteTateSum pureM66deg26 (-13) :=
  polarizable_semisimplicity_upgrade pureM66deg26 (-13) containedInPsi
    (lowest_weight_is_pure_polarizable pureM66deg26 (by decide))
    (psi_products_are_tate_quotient pureM66deg26 pureM66deg24 (-1) (-12) (-13)
      psiSpan26 (psi_class_is_tate_divisor moduliM66 (by decide))
      (phi_tate_from_pullback_source pureM66deg24 pureM65deg24 (-12) phiSpan24 tateM65deg24)
      (by decide) (by decide) (by decide))

theorem c66_exact_bm_is_finite_tate_sum : BMIsFiniteTateSum exactC66BMTarget :=
  bm_tate_sum_from_twisted_pure exactC66BMTarget pureM66deg26 21 (-13) 8
    (poincare_duality_bm_twist exactC66BMTarget pureM66deg26 21
      (by decide) (by decide) (by decide) (by decide) (by decide) (by decide))
    ordinaryTate (tate_twist_shift_add (-13) 21 8 (by decide)) (by decide)

#print axioms optional_primitive_route_equals_psi
#print axioms c66_exact_bm_is_finite_tate_sum
