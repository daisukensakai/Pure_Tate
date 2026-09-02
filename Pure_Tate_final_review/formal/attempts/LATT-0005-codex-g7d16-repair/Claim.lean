set_option autoImplicit false
-- LEAN-CAMPAIGN LG7D16-002
-- LEAN-ATTEMPT LATT-0005
-- LEAN-SOURCE-ATTEMPT ATT-0148
-- LEAN-CLAIM-CONTRACT G7D16-COMPACT-H16-TARGET-V2
-- LEAN-TARGET-SIGNATURE ALL(stable(g,n),g<=7)=>COMPACT-DM-STACK(ordered,Q,H^16,weight=16,tate=-8,whole-group,rank>=0);OPEN-TERM=LOWEST-WEIGHT-BM
-- LEAN-THEOREM genus_at_most_seven_compact_h16_is_tate
-- LEAN-WEIGHT Strong induction on 3g+n uses an explicitly lowest-weight open BM carrier. The repaired genus-five input has four distinct premises; five endpoint records carry strict vcd arithmetic; the stronger zero range is distinct; right exactness, kernel orientation, purity, semisimplicity, and proper duality remain separately typed.

-- LEAN-TRUSTED-PRELUDE-BEGIN
inductive GeometryKind where
  | stableCompactifiedDMStack
  | smoothOpenDMStack
  | coarseModuliSpace
  deriving DecidableEq

inductive CoefficientKind where
  | rational
  | integral
  deriving DecidableEq

inductive MarkingKind where
  | ordered
  | unordered
  deriving DecidableEq

inductive CohomologyObjectKind where
  | wholeGroup
  | lowestWeightPiece
  | image
  | quotient
  | associatedGraded
  | semisimplification
  deriving DecidableEq

structure StablePairIndex where
  genus : Nat
  markings : Nat
  deriving DecidableEq

def IsStablePair (p : StablePairIndex) : Prop := 3 <= 2 * p.genus + p.markings

def PairComplexity (p : StablePairIndex) : Nat := 3 * p.genus + p.markings

structure CompactH16TargetIndex where
  pair : StablePairIndex
  geometry : GeometryKind
  coefficients : CoefficientKind
  markingsKind : MarkingKind
  objectKind : CohomologyObjectKind
  cohomologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

def compactH16Target (p : StablePairIndex) : CompactH16TargetIndex := {
  pair := p
  geometry := GeometryKind.stableCompactifiedDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  objectKind := CohomologyObjectKind.wholeGroup
  cohomologicalDegree := 16
  weight := 16
  tateIndex := -8
}

def AllStableGenusAtMostSevenCompactH16IsTate
    (P : CompactH16TargetIndex -> Prop) : Prop :=
  forall p : StablePairIndex, IsStablePair p -> p.genus <= 7 -> P (compactH16Target p)
-- LEAN-TRUSTED-PRELUDE-END

-- LEAN-SHARED-SIGNATURE-BEGIN
structure OpenBMIndex where
  pair : StablePairIndex
  geometry : GeometryKind
  coefficients : CoefficientKind
  markingsKind : MarkingKind
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

structure BoundaryImageIndex where
  pair : StablePairIndex
  geometry : GeometryKind
  coefficients : CoefficientKind
  markingsKind : MarkingKind
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

inductive PurityKind where
  | purePolarizable
  | impure
  deriving DecidableEq

structure CompactHomologyIndex where
  pair : StablePairIndex
  geometry : GeometryKind
  coefficients : CoefficientKind
  markingsKind : MarkingKind
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  purityKind : PurityKind
  deriving DecidableEq

inductive ExactSequenceOrientation where
  | boundaryToCompactToOpen
  | openToCompactToBoundary
  deriving DecidableEq

inductive KernelOrientation where
  | boundaryImageIsKernel
  | compactHomologyIsKernel
  deriving DecidableEq

structure BoundarySequenceIndex where
  pair : StablePairIndex
  boundary : BoundaryImageIndex
  compact : CompactHomologyIndex
  openPart : OpenBMIndex
  orientation : ExactSequenceOrientation
  kernelOrientation : KernelOrientation
  degreeShift : Int
  tateTwist : Int
  deriving DecidableEq

def openBMIndex (p : StablePairIndex) : OpenBMIndex := {
  pair := p
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  objectKind := CohomologyObjectKind.lowestWeightPiece
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

def boundaryImageIndex (p : StablePairIndex) : BoundaryImageIndex := {
  pair := p
  geometry := GeometryKind.stableCompactifiedDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  objectKind := CohomologyObjectKind.image
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

def compactHomologyIndex (p : StablePairIndex) : CompactHomologyIndex := {
  pair := p
  geometry := GeometryKind.stableCompactifiedDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  objectKind := CohomologyObjectKind.wholeGroup
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
  purityKind := PurityKind.purePolarizable
}

def boundarySequenceIndex (p : StablePairIndex) : BoundarySequenceIndex := {
  pair := p
  boundary := boundaryImageIndex p
  compact := compactHomologyIndex p
  openPart := openBMIndex p
  orientation := ExactSequenceOrientation.boundaryToCompactToOpen
  kernelOrientation := KernelOrientation.boundaryImageIsKernel
  degreeShift := 0
  tateTwist := 0
}

inductive DualityKind where
  | properSameDegree
  | openPoincareDimensionTwist
  deriving DecidableEq

structure ProperDualityIndex where
  pair : StablePairIndex
  homology : CompactHomologyIndex
  cohomology : CompactH16TargetIndex
  kind : DualityKind
  homologicalDegree : Int
  cohomologicalDegree : Int
  weightSign : Int
  tateSign : Int
  ambientDimensionTwist : Int
  deriving DecidableEq

def properDualityIndex (p : StablePairIndex) : ProperDualityIndex := {
  pair := p
  homology := compactHomologyIndex p
  cohomology := compactH16Target p
  kind := DualityKind.properSameDegree
  homologicalDegree := 16
  cohomologicalDegree := 16
  weightSign := -1
  tateSign := -1
  ambientDimensionTwist := 0
}

structure CriticalEndpointIndex where
  pair : StablePairIndex
  ordinaryDegree : Nat
  ckgpMarkingEndpoint : Nat
  primitiveDegree : Nat
  unpointedVcd : Nat
  smallerPointedVcd : Nat
  ionelCodimension : Nat
  deriving DecidableEq

def endpointG3 : CriticalEndpointIndex := {
  pair := { genus := 3, markings := 12 }
  ordinaryDegree := 20
  ckgpMarkingEndpoint := 11
  primitiveDegree := 8
  unpointedVcd := 7
  smallerPointedVcd := 19
  ionelCodimension := 9
}

def endpointG4 : CriticalEndpointIndex := {
  pair := { genus := 4, markings := 10 }
  ordinaryDegree := 22
  ckgpMarkingEndpoint := 9
  primitiveDegree := 12
  unpointedVcd := 11
  smallerPointedVcd := 21
  ionelCodimension := 10
}

def endpointG5 : CriticalEndpointIndex := {
  pair := { genus := 5, markings := 8 }
  ordinaryDegree := 24
  ckgpMarkingEndpoint := 7
  primitiveDegree := 16
  unpointedVcd := 15
  smallerPointedVcd := 23
  ionelCodimension := 11
}

def endpointG6 : CriticalEndpointIndex := {
  pair := { genus := 6, markings := 6 }
  ordinaryDegree := 26
  ckgpMarkingEndpoint := 5
  primitiveDegree := 20
  unpointedVcd := 19
  smallerPointedVcd := 25
  ionelCodimension := 12
}

def endpointG7 : CriticalEndpointIndex := {
  pair := { genus := 7, markings := 4 }
  ordinaryDegree := 28
  ckgpMarkingEndpoint := 3
  primitiveDegree := 24
  unpointedVcd := 23
  smallerPointedVcd := 27
  ionelCodimension := 13
}

def IsCriticalEndpoint (e : CriticalEndpointIndex) : Prop :=
  e = endpointG3 ∨ e = endpointG4 ∨ e = endpointG5 ∨ e = endpointG6 ∨ e = endpointG7

structure G7D16VocabularyV2 where
  GenusFiveCKgP : Prop
  GenusFiveTautologicalChow : Prop
  GenusFiveIonelCohomologicalVanishing : Prop
  GenusFiveOpenBMConversion : Prop
  GenusFiveEndpointVanishing : Prop
  PublishedOpenRangeControl : Prop
  StrictPrimitiveAboveUnpointedVCD : CriticalEndpointIndex -> Prop
  StrictPhiAboveSmallerPointedVCD : CriticalEndpointIndex -> Prop
  InclusiveCKgPMarkingEndpoint : CriticalEndpointIndex -> Prop
  IonelKillsPsiSource : CriticalEndpointIndex -> Prop
  CriticalEndpointVanishes : CriticalEndpointIndex -> Prop
  OpenBMVanishes : OpenBMIndex -> Prop
  OpenBMIsFiniteTateSum : OpenBMIndex -> Prop
  OddCompactVanishingThroughNine : Prop
  EvenCompactTateThroughFourteen : Prop
  OneEdgeBoundaryFactor : StablePairIndex -> StablePairIndex -> Prop
  BoundaryImageIsFiniteTateSum : BoundaryImageIndex -> Prop
  BoundarySequenceIsRightExact : BoundarySequenceIndex -> Prop
  BoundaryImageIsKernel : BoundarySequenceIndex -> Prop
  CompactHomologyIsPurePolarizable : CompactHomologyIndex -> Prop
  CompactHomologyIsFiniteTateSum : CompactHomologyIndex -> Prop
  ProperSameDegreeDuality : ProperDualityIndex -> Prop
-- LEAN-SHARED-SIGNATURE-END

axiom CompactH16IsFiniteTateSum : CompactH16TargetIndex -> Prop
-- LEAN-AXIOM CompactH16IsFiniteTateSum => VOCAB -- exact whole-group compact cohomology target predicate

axiom vocab : G7D16VocabularyV2
-- LEAN-AXIOM vocab => VOCAB -- shared repaired vocabulary with distinct endpoint, vanishing, exactness, kernel, and purity carriers

axiom genus_five_ckgp : vocab.GenusFiveCKgP
-- LEAN-AXIOM genus_five_ckgp => G7D16-OBL-01 -- CKgP for the repaired M_5,8 input

axiom genus_five_tautological_chow : vocab.GenusFiveTautologicalChow
-- LEAN-AXIOM genus_five_tautological_chow => G7D16-OBL-01 -- repaired Chow equality A-star equals R-star, separate from cohomological vanishing

axiom genus_five_ionel_cohomological_vanishing :
    vocab.GenusFiveIonelCohomologicalVanishing
-- LEAN-AXIOM genus_five_ionel_cohomological_vanishing => G7D16-OBL-01 -- cohomological Ionel input, not a Chow-level vanishing claim

axiom genus_five_open_bm_conversion : vocab.GenusFiveOpenBMConversion
-- LEAN-AXIOM genus_five_open_bm_conversion => G7D16-OBL-01 -- CLP pure-weight conversion followed by the exact Poincare twist to W_-16 H_16^BM

axiom genus_five_endpoint_from_repaired_inputs :
    vocab.GenusFiveCKgP ->
    vocab.GenusFiveTautologicalChow ->
    vocab.GenusFiveIonelCohomologicalVanishing ->
    vocab.GenusFiveOpenBMConversion ->
    vocab.GenusFiveEndpointVanishing
-- LEAN-AXIOM genus_five_endpoint_from_repaired_inputs => G7D16-OBL-01 -- firewall-preserving assembly of the four distinct repaired premises

axiom published_open_range_control : vocab.PublishedOpenRangeControl
-- LEAN-AXIOM published_open_range_control => G7D16-OBL-03 -- audited remaining published-range open Tate cases

axiom strict_primitive_vcd_at_critical_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.unpointedVcd < e.primitiveDegree ->
    vocab.StrictPrimitiveAboveUnpointedVCD e
-- LEAN-AXIOM strict_primitive_vcd_at_critical_endpoint => G7D16-OBL-02 -- k-n is strictly above 4g-5, never equal to it

axiom strict_phi_vcd_at_critical_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.smallerPointedVcd < e.ordinaryDegree ->
    vocab.StrictPhiAboveSmallerPointedVCD e
-- LEAN-AXIOM strict_phi_vcd_at_critical_endpoint => G7D16-OBL-02 -- k is strictly above the vcd with one fewer marking

axiom inclusive_ckgp_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.pair.markings = e.ckgpMarkingEndpoint + 1 ->
    vocab.InclusiveCKgPMarkingEndpoint e
-- LEAN-AXIOM inclusive_ckgp_endpoint => G7D16-OBL-02 -- n-1 equals the inclusive CKgP endpoint

axiom ionel_kills_critical_psi_source : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.pair.genus <= e.ionelCodimension ->
    vocab.GenusFiveIonelCohomologicalVanishing ->
    vocab.IonelKillsPsiSource e
-- LEAN-AXIOM ionel_kills_critical_psi_source => G7D16-OBL-02 -- cohomological Ionel bound at the exact source codimension

axiom critical_endpoint_vanishes_from_typed_inputs : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    vocab.StrictPrimitiveAboveUnpointedVCD e ->
    vocab.StrictPhiAboveSmallerPointedVCD e ->
    vocab.InclusiveCKgPMarkingEndpoint e ->
    vocab.IonelKillsPsiSource e ->
    (e.pair.genus = 5 -> vocab.GenusFiveEndpointVanishing) ->
    vocab.CriticalEndpointVanishes e
-- LEAN-AXIOM critical_endpoint_vanishes_from_typed_inputs => G7D16-OBL-02 -- endpoint vanishing with every strict and inclusive premise exposed

axiom open_bm_vanishes_strong_range : forall p : StablePairIndex,
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    11 <= 2 * p.genus + p.markings ->
    vocab.CriticalEndpointVanishes endpointG3 ->
    vocab.CriticalEndpointVanishes endpointG4 ->
    vocab.CriticalEndpointVanishes endpointG5 ->
    vocab.CriticalEndpointVanishes endpointG6 ->
    vocab.CriticalEndpointVanishes endpointG7 ->
    vocab.OpenBMVanishes (openBMIndex p)
-- LEAN-AXIOM open_bm_vanishes_strong_range => G7D16-OBL-03 -- explicit stronger zero range 2g+n at least eleven

axiom published_open_bm_tate_below_zero_range : forall p : StablePairIndex,
    vocab.PublishedOpenRangeControl ->
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    2 * p.genus + p.markings < 11 ->
    vocab.OpenBMIsFiniteTateSum (openBMIndex p)
-- LEAN-AXIOM published_open_bm_tate_below_zero_range => G7D16-OBL-03 -- remaining nonzero-range open Tate cases

axiom zero_open_bm_is_tate : forall i : OpenBMIndex,
    vocab.OpenBMVanishes i -> vocab.OpenBMIsFiniteTateSum i
-- LEAN-AXIOM zero_open_bm_is_tate => G7D16-OBL-03 -- zero is a finite Q(8)-sum, with rank zero explicit

axiom compact_base_genus_zero_one_two : forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 2 ->
    CompactH16IsFiniteTateSum (compactH16Target p)
-- LEAN-AXIOM compact_base_genus_zero_one_two => G7D16-OBL-04 -- compact degree-sixteen base cases

axiom odd_compact_vanishing_through_nine : vocab.OddCompactVanishingThroughNine
-- LEAN-AXIOM odd_compact_vanishing_through_nine => G7D16-OBL-04 -- low odd compact factors vanish

axiom even_compact_tate_through_fourteen : vocab.EvenCompactTateThroughFourteen
-- LEAN-AXIOM even_compact_tate_through_fourteen => G7D16-OBL-04 -- positive low even compact factors are Tate

axiom boundary_factor_is_stable : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> IsStablePair q
-- LEAN-AXIOM boundary_factor_is_stable => G7D16-OBL-05 -- every one-edge factor is stable

axiom boundary_factor_genus_le_parent : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> q.genus <= p.genus
-- LEAN-AXIOM boundary_factor_genus_le_parent => G7D16-OBL-05 -- a factor never increases genus

axiom boundary_factor_complexity_decreases : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> PairComplexity q < PairComplexity p
-- LEAN-AXIOM boundary_factor_complexity_decreases => G7D16-OBL-09 -- strict well-founded decrease

axiom boundary_image_tate_from_one_edge_graphs : forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 7 ->
    vocab.OddCompactVanishingThroughNine ->
    vocab.EvenCompactTateThroughFourteen ->
    (forall q : StablePairIndex, vocab.OneEdgeBoundaryFactor p q ->
      CompactH16IsFiniteTateSum (compactH16Target q)) ->
    vocab.BoundaryImageIsFiniteTateSum (boundaryImageIndex p)
-- LEAN-AXIOM boundary_image_tate_from_one_edge_graphs => G7D16-OBL-06 -- normalized-boundary Kunneth and passage to the homological image

axiom boundary_sequence_right_exact : forall s : BoundarySequenceIndex,
    IsStablePair s.pair ->
    s.boundary = boundaryImageIndex s.pair ->
    s.compact = compactHomologyIndex s.pair ->
    s.openPart = openBMIndex s.pair ->
    s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ->
    s.degreeShift = 0 -> s.tateTwist = 0 ->
    vocab.BoundarySequenceIsRightExact s
-- LEAN-AXIOM boundary_sequence_right_exact => G7D16-OBL-07 -- right exactness excludes kernel orientation so the two predicates remain independent

axiom boundary_image_is_kernel : forall p : StablePairIndex,
    vocab.BoundarySequenceIsRightExact (boundarySequenceIndex p) ->
    (boundarySequenceIndex p).kernelOrientation = KernelOrientation.boundaryImageIsKernel ->
    vocab.BoundaryImageIsKernel (boundarySequenceIndex p)
-- LEAN-AXIOM boundary_image_is_kernel => G7D16-OBL-07 -- separate correct kernel/quotient orientation premise

axiom compact_homology_pure_polarizable : forall p : StablePairIndex,
    IsStablePair p ->
    (compactHomologyIndex p).purityKind = PurityKind.purePolarizable ->
    vocab.CompactHomologyIsPurePolarizable (compactHomologyIndex p)
-- LEAN-AXIOM compact_homology_pure_polarizable => G7D16-OBL-08 -- smooth-proper purity is an explicit independent tag

axiom semisimple_boundary_extension : forall
    (s : BoundarySequenceIndex) (b : BoundaryImageIndex)
    (o : OpenBMIndex) (h : CompactHomologyIndex),
    s.boundary = b -> s.compact = h -> s.openPart = o ->
    vocab.BoundarySequenceIsRightExact s ->
    vocab.BoundaryImageIsKernel s ->
    vocab.BoundaryImageIsFiniteTateSum b ->
    vocab.OpenBMIsFiniteTateSum o ->
    vocab.CompactHomologyIsPurePolarizable h ->
    vocab.CompactHomologyIsFiniteTateSum h
-- LEAN-AXIOM semisimple_boundary_extension => G7D16-OBL-08 -- exactness, kernel, subobject, quotient, and purity are all explicit

axiom proper_same_degree_duality : forall p : StablePairIndex,
    IsStablePair p ->
    vocab.ProperSameDegreeDuality (properDualityIndex p)
-- LEAN-AXIOM proper_same_degree_duality => G7D16-OBL-08 -- proper H_16/H^16 duality with zero ambient twist

axiom proper_duality_transfers_tate : forall p : StablePairIndex,
    vocab.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) ->
    vocab.ProperSameDegreeDuality (properDualityIndex p) ->
    CompactH16IsFiniteTateSum (compactH16Target p)
-- LEAN-AXIOM proper_duality_transfers_tate => G7D16-OBL-08 -- Q(8) dualizes to Q(-8) in the same degree

theorem genusFiveEndpointInput : vocab.GenusFiveEndpointVanishing :=
  genus_five_endpoint_from_repaired_inputs genus_five_ckgp
    genus_five_tautological_chow genus_five_ionel_cohomological_vanishing
    genus_five_open_bm_conversion

theorem endpointG3Vanishes : vocab.CriticalEndpointVanishes endpointG3 :=
  critical_endpoint_vanishes_from_typed_inputs endpointG3 (by left; rfl)
    (strict_primitive_vcd_at_critical_endpoint endpointG3 (by left; rfl) (by decide))
    (strict_phi_vcd_at_critical_endpoint endpointG3 (by left; rfl) (by decide))
    (inclusive_ckgp_endpoint endpointG3 (by left; rfl) (by decide))
    (ionel_kills_critical_psi_source endpointG3 (by left; rfl) (by decide)
      genus_five_ionel_cohomological_vanishing)
    (by simp [endpointG3])

theorem endpointG4Vanishes : vocab.CriticalEndpointVanishes endpointG4 :=
  critical_endpoint_vanishes_from_typed_inputs endpointG4 (by right; left; rfl)
    (strict_primitive_vcd_at_critical_endpoint endpointG4 (by right; left; rfl) (by decide))
    (strict_phi_vcd_at_critical_endpoint endpointG4 (by right; left; rfl) (by decide))
    (inclusive_ckgp_endpoint endpointG4 (by right; left; rfl) (by decide))
    (ionel_kills_critical_psi_source endpointG4 (by right; left; rfl) (by decide)
      genus_five_ionel_cohomological_vanishing)
    (by simp [endpointG4])

theorem endpointG5Vanishes : vocab.CriticalEndpointVanishes endpointG5 :=
  critical_endpoint_vanishes_from_typed_inputs endpointG5 (by right; right; left; rfl)
    (strict_primitive_vcd_at_critical_endpoint endpointG5 (by right; right; left; rfl) (by decide))
    (strict_phi_vcd_at_critical_endpoint endpointG5 (by right; right; left; rfl) (by decide))
    (inclusive_ckgp_endpoint endpointG5 (by right; right; left; rfl) (by decide))
    (ionel_kills_critical_psi_source endpointG5 (by right; right; left; rfl) (by decide)
      genus_five_ionel_cohomological_vanishing)
    (by intro _; exact genusFiveEndpointInput)

theorem endpointG6Vanishes : vocab.CriticalEndpointVanishes endpointG6 :=
  critical_endpoint_vanishes_from_typed_inputs endpointG6 (by right; right; right; left; rfl)
    (strict_primitive_vcd_at_critical_endpoint endpointG6 (by right; right; right; left; rfl) (by decide))
    (strict_phi_vcd_at_critical_endpoint endpointG6 (by right; right; right; left; rfl) (by decide))
    (inclusive_ckgp_endpoint endpointG6 (by right; right; right; left; rfl) (by decide))
    (ionel_kills_critical_psi_source endpointG6 (by right; right; right; left; rfl) (by decide)
      genus_five_ionel_cohomological_vanishing)
    (by simp [endpointG6])

theorem endpointG7Vanishes : vocab.CriticalEndpointVanishes endpointG7 :=
  critical_endpoint_vanishes_from_typed_inputs endpointG7 (by right; right; right; right; rfl)
    (strict_primitive_vcd_at_critical_endpoint endpointG7 (by right; right; right; right; rfl) (by decide))
    (strict_phi_vcd_at_critical_endpoint endpointG7 (by right; right; right; right; rfl) (by decide))
    (inclusive_ckgp_endpoint endpointG7 (by right; right; right; right; rfl) (by decide))
    (ionel_kills_critical_psi_source endpointG7 (by right; right; right; right; rfl) (by decide)
      genus_five_ionel_cohomological_vanishing)
    (by simp [endpointG7])

theorem openBMTateForRange (p : StablePairIndex)
    (hstable : IsStablePair p) (hg3 : 3 <= p.genus) (hg7 : p.genus <= 7) :
    vocab.OpenBMIsFiniteTateSum (openBMIndex p) := by
  by_cases hzero : 11 <= 2 * p.genus + p.markings
  · exact zero_open_bm_is_tate (openBMIndex p)
      (open_bm_vanishes_strong_range p hstable hg3 hg7 hzero
        endpointG3Vanishes endpointG4Vanishes endpointG5Vanishes
        endpointG6Vanishes endpointG7Vanishes)
  · exact published_open_bm_tate_below_zero_range p published_open_range_control
      hstable hg3 hg7 (by omega)

theorem compact_h16_by_complexity (c : Nat) : forall p : StablePairIndex,
    PairComplexity p = c -> IsStablePair p -> p.genus <= 7 ->
    CompactH16IsFiniteTateSum (compactH16Target p) := by
  induction c using Nat.strongRecOn with
  | ind c ih =>
      intro p hcomplexity hstable hgenus
      by_cases hbase : p.genus <= 2
      · exact compact_base_genus_zero_one_two p hstable hbase
      · have hg3 : 3 <= p.genus := by omega
        have hopen : vocab.OpenBMIsFiniteTateSum (openBMIndex p) :=
          openBMTateForRange p hstable hg3 hgenus
        have hfactor : forall q : StablePairIndex,
            vocab.OneEdgeBoundaryFactor p q ->
            CompactH16IsFiniteTateSum (compactH16Target q) := by
          intro q hq
          have hdecrease : PairComplexity q < c := by
            rw [← hcomplexity]
            exact boundary_factor_complexity_decreases p q hq
          exact ih (PairComplexity q) hdecrease q rfl
            (boundary_factor_is_stable p q hq)
            (Nat.le_trans (boundary_factor_genus_le_parent p q hq) hgenus)
        have hboundary : vocab.BoundaryImageIsFiniteTateSum (boundaryImageIndex p) :=
          boundary_image_tate_from_one_edge_graphs p hstable hgenus
            odd_compact_vanishing_through_nine even_compact_tate_through_fourteen hfactor
        have hexact : vocab.BoundarySequenceIsRightExact (boundarySequenceIndex p) :=
          boundary_sequence_right_exact (boundarySequenceIndex p) hstable
            rfl rfl rfl rfl rfl rfl
        have hkernel : vocab.BoundaryImageIsKernel (boundarySequenceIndex p) :=
          boundary_image_is_kernel p hexact rfl
        have hpure : vocab.CompactHomologyIsPurePolarizable (compactHomologyIndex p) :=
          compact_homology_pure_polarizable p hstable rfl
        have hhom : vocab.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) :=
          semisimple_boundary_extension (boundarySequenceIndex p) (boundaryImageIndex p)
            (openBMIndex p) (compactHomologyIndex p) rfl rfl rfl
            hexact hkernel hboundary hopen hpure
        exact proper_duality_transfers_tate p hhom (proper_same_degree_duality p hstable)

theorem genus_at_most_seven_compact_h16_is_tate :
    AllStableGenusAtMostSevenCompactH16IsTate CompactH16IsFiniteTateSum := by
  intro p hstable hgenus
  exact compact_h16_by_complexity (PairComplexity p) p rfl hstable hgenus

#print axioms genus_at_most_seven_compact_h16_is_tate
