set_option autoImplicit false
-- LEAN-CAMPAIGN LG7D16-001
-- LEAN-ATTEMPT LATT-0004
-- LEAN-SOURCE-ATTEMPT ATT-0148
-- LEAN-CLAIM-CONTRACT G7D16-COMPACT-H16-TARGET-V1
-- LEAN-TARGET-SIGNATURE ALL(stable(g,n),g<=7)=>COMPACT-DM-STACK(ordered,Q,H^16,weight=16,tate=-8,whole-group,rank>=0)
-- LEAN-THEOREM genus_at_most_seven_compact_h16_is_tate
-- LEAN-WEIGHT The theorem is universal over stable pairs and is proved by genuine strong induction on 3g+n. Boundary image, compact homology, open Borel-Moore homology, and compact cohomology are distinct types; the sequence has a typed orientation, zero shift, and zero twist; proper duality is same-degree and changes Q(8) to Q(-8).

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

structure CompactHomologyIndex where
  pair : StablePairIndex
  geometry : GeometryKind
  coefficients : CoefficientKind
  markingsKind : MarkingKind
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

inductive ExactSequenceOrientation where
  | boundaryToCompactToOpen
  | openToCompactToBoundary
  deriving DecidableEq

structure BoundarySequenceIndex where
  pair : StablePairIndex
  boundary : BoundaryImageIndex
  compact : CompactHomologyIndex
  openPart : OpenBMIndex
  orientation : ExactSequenceOrientation
  degreeShift : Int
  tateTwist : Int
  deriving DecidableEq

def openBMIndex (p : StablePairIndex) : OpenBMIndex := {
  pair := p
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  objectKind := CohomologyObjectKind.wholeGroup
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
}

def boundarySequenceIndex (p : StablePairIndex) : BoundarySequenceIndex := {
  pair := p
  boundary := boundaryImageIndex p
  compact := compactHomologyIndex p
  openPart := openBMIndex p
  orientation := ExactSequenceOrientation.boundaryToCompactToOpen
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

structure G7D16Vocabulary where
  RepairedGenusFiveInput : Prop
  IonelLooijengaVanishing : Prop
  CriticalEndpointVanishings : Prop
  PublishedOpenRangeControl : Prop
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

axiom vocab : G7D16Vocabulary
-- LEAN-AXIOM vocab => VOCAB -- shared vocabulary with distinct carriers and a typed boundary sequence

axiom liu_repaired_genus_five_input : vocab.RepairedGenusFiveInput
-- LEAN-AXIOM liu_repaired_genus_five_input => G7D16-OBL-01 -- repaired M_5,8 package replacing the invalid shortcut in Liu Corollary 3.9

axiom ionel_looijenga_vanishing : vocab.IonelLooijengaVanishing
-- LEAN-AXIOM ionel_looijenga_vanishing => G7D16-OBL-02 -- cohomological vanishing source used only with strict vcd inequalities

axiom critical_endpoint_vanishings :
    vocab.RepairedGenusFiveInput -> vocab.IonelLooijengaVanishing ->
    vocab.CriticalEndpointVanishings
-- LEAN-AXIOM critical_endpoint_vanishings => G7D16-OBL-02 -- all five inclusive endpoint vanishings, including the repaired genus-five endpoint

axiom published_open_range_control : vocab.PublishedOpenRangeControl
-- LEAN-AXIOM published_open_range_control => G7D16-OBL-03 -- audited published-range open calculations outside the critical endpoints

axiom open_bm_tate_genus_le_seven : forall p : StablePairIndex,
    vocab.RepairedGenusFiveInput -> vocab.IonelLooijengaVanishing ->
    vocab.CriticalEndpointVanishings -> vocab.PublishedOpenRangeControl ->
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    vocab.OpenBMIsFiniteTateSum (openBMIndex p)
-- LEAN-AXIOM open_bm_tate_genus_le_seven => G7D16-OBL-03 -- complete open BM theorem in the genus-three-through-seven range

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
-- LEAN-AXIOM boundary_factor_is_stable => G7D16-OBL-05 -- every factor in the one-edge normalization is stable

axiom boundary_factor_genus_le_parent : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> q.genus <= p.genus
-- LEAN-AXIOM boundary_factor_genus_le_parent => G7D16-OBL-05 -- boundary factors do not increase genus

axiom boundary_factor_complexity_decreases : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> PairComplexity q < PairComplexity p
-- LEAN-AXIOM boundary_factor_complexity_decreases => G7D16-OBL-09 -- strict well-founded decrease for the actual strong induction

axiom boundary_image_tate_from_one_edge_graphs : forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 7 ->
    vocab.OddCompactVanishingThroughNine ->
    vocab.EvenCompactTateThroughFourteen ->
    (forall q : StablePairIndex, vocab.OneEdgeBoundaryFactor p q ->
      CompactH16IsFiniteTateSum (compactH16Target q)) ->
    vocab.BoundaryImageIsFiniteTateSum (boundaryImageIndex p)
-- LEAN-AXIOM boundary_image_tate_from_one_edge_graphs => G7D16-OBL-06 -- Kunneth, graph invariants, and image passage for the normalized boundary

axiom boundary_sequence_right_exact : forall s : BoundarySequenceIndex,
    IsStablePair s.pair ->
    s.boundary = boundaryImageIndex s.pair ->
    s.compact = compactHomologyIndex s.pair ->
    s.openPart = openBMIndex s.pair ->
    s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ->
    s.degreeShift = 0 -> s.tateTwist = 0 ->
    vocab.BoundarySequenceIsRightExact s
-- LEAN-AXIOM boundary_sequence_right_exact => G7D16-OBL-07 -- degree-preserving untwisted boundary-image to compact-homology to open-BM sequence

axiom boundary_image_is_kernel : forall p : StablePairIndex,
    vocab.BoundarySequenceIsRightExact (boundarySequenceIndex p) ->
    vocab.BoundaryImageIsKernel (boundarySequenceIndex p)
-- LEAN-AXIOM boundary_image_is_kernel => G7D16-OBL-07 -- correct kernel and quotient orientation

axiom compact_homology_pure_polarizable : forall p : StablePairIndex,
    IsStablePair p ->
    vocab.CompactHomologyIsPurePolarizable (compactHomologyIndex p)
-- LEAN-AXIOM compact_homology_pure_polarizable => G7D16-OBL-08 -- smooth-proper purity in homological weight minus sixteen

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
-- LEAN-AXIOM semisimple_boundary_extension => G7D16-OBL-08 -- every exactness, kernel, subobject, quotient, and purity premise is explicit

axiom proper_same_degree_duality : forall p : StablePairIndex,
    IsStablePair p ->
    vocab.ProperSameDegreeDuality (properDualityIndex p)
-- LEAN-AXIOM proper_same_degree_duality => G7D16-OBL-08 -- proper H_16/H^16 duality with Q(8) dual to Q(-8)

axiom proper_duality_transfers_tate : forall p : StablePairIndex,
    vocab.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) ->
    vocab.ProperSameDegreeDuality (properDualityIndex p) ->
    CompactH16IsFiniteTateSum (compactH16Target p)
-- LEAN-AXIOM proper_duality_transfers_tate => G7D16-OBL-08 -- transports the whole finite Tate sum without an open-space dimension twist

theorem compact_h16_by_complexity (c : Nat) : forall p : StablePairIndex,
    PairComplexity p = c -> IsStablePair p -> p.genus <= 7 ->
    CompactH16IsFiniteTateSum (compactH16Target p) := by
  induction c using Nat.strongRecOn with
  | ind c ih =>
      intro p hcomplexity hstable hgenus
      by_cases hbase : p.genus <= 2
      · exact compact_base_genus_zero_one_two p hstable hbase
      · have hgenus_three : 3 <= p.genus := by omega
        have hcritical : vocab.CriticalEndpointVanishings :=
          critical_endpoint_vanishings liu_repaired_genus_five_input ionel_looijenga_vanishing
        have hopen : vocab.OpenBMIsFiniteTateSum (openBMIndex p) :=
          open_bm_tate_genus_le_seven p liu_repaired_genus_five_input
            ionel_looijenga_vanishing hcritical published_open_range_control
            hstable hgenus_three hgenus
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
          boundary_image_tate_from_one_edge_graphs p hstable
            hgenus odd_compact_vanishing_through_nine even_compact_tate_through_fourteen hfactor
        have hexact : vocab.BoundarySequenceIsRightExact (boundarySequenceIndex p) :=
          boundary_sequence_right_exact (boundarySequenceIndex p) hstable rfl rfl rfl rfl rfl rfl
        have hkernel : vocab.BoundaryImageIsKernel (boundarySequenceIndex p) :=
          boundary_image_is_kernel p hexact
        have hpure : vocab.CompactHomologyIsPurePolarizable (compactHomologyIndex p) :=
          compact_homology_pure_polarizable p hstable
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
