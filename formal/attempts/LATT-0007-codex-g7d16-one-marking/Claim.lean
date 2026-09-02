set_option autoImplicit false
-- LEAN-CAMPAIGN LG7D16-004
-- LEAN-ATTEMPT LATT-0007
-- LEAN-SOURCE-ATTEMPT ATT-0149
-- LEAN-CLAIM-CONTRACT G7D16-COMPACT-H16-TARGET-V2
-- LEAN-TARGET-SIGNATURE ALL(stable(g,n),g<=7)=>COMPACT-DM-STACK(ordered,Q,H^16,weight=16,tate=-8,whole-group,rank>=0);OPEN-TERM=LOWEST-WEIGHT-BM
-- LEAN-THEOREM genus_at_most_seven_compact_h16_is_tate
-- LEAN-WEIGHT Strong induction on 3g+n over a lowest-weight open BM carrier. The one-marking primitive-quotient route handles (3,12), (5,8), (6,6), and (7,4); only (4,10) uses the direct published CLP range. At (5,8), the mechanically checked gates are 16>15, 24>23, 7=c(5), and Ionel codimension 11>=5. No repaired genus-five, Chow, or M_5,8 CKgP premise remains. Smooth-proper purity, kernel orientation, right exactness and proper same-degree duality remain separately typed.

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

inductive VanishingLevel where
  | cohomological
  | chow
  deriving DecidableEq

structure IonelVanishingIndex where
  genus : Nat
  markings : Nat
  codimension : Nat
  level : VanishingLevel
  deriving DecidableEq

inductive EndpointRoute where
  | oneMarkingPrimitiveQuotient
  | directPublishedRange
  deriving DecidableEq

structure CriticalEndpointIndex where
  pair : StablePairIndex
  route : EndpointRoute
  ordinaryDegree : Nat
  ckgpMarkingBound : Nat
  primitiveDegree : Nat
  unpointedVcd : Nat
  smallerPointedMarkings : Nat
  smallerPointedVcd : Nat
  ionelCodimension : Nat
  deriving DecidableEq

def endpointG3 : CriticalEndpointIndex := {
  pair := { genus := 3, markings := 12 }
  route := EndpointRoute.oneMarkingPrimitiveQuotient
  ordinaryDegree := 20
  ckgpMarkingBound := 11
  primitiveDegree := 8
  unpointedVcd := 7
  smallerPointedMarkings := 11
  smallerPointedVcd := 19
  ionelCodimension := 9
}

def endpointG4 : CriticalEndpointIndex := {
  pair := { genus := 4, markings := 10 }
  route := EndpointRoute.directPublishedRange
  ordinaryDegree := 22
  ckgpMarkingBound := 11
  primitiveDegree := 12
  unpointedVcd := 11
  smallerPointedMarkings := 9
  smallerPointedVcd := 21
  ionelCodimension := 11
}

def endpointG5 : CriticalEndpointIndex := {
  pair := { genus := 5, markings := 8 }
  route := EndpointRoute.oneMarkingPrimitiveQuotient
  ordinaryDegree := 24
  ckgpMarkingBound := 7
  primitiveDegree := 16
  unpointedVcd := 15
  smallerPointedMarkings := 7
  smallerPointedVcd := 23
  ionelCodimension := 11
}

def endpointG6 : CriticalEndpointIndex := {
  pair := { genus := 6, markings := 6 }
  route := EndpointRoute.oneMarkingPrimitiveQuotient
  ordinaryDegree := 26
  ckgpMarkingBound := 5
  primitiveDegree := 20
  unpointedVcd := 19
  smallerPointedMarkings := 5
  smallerPointedVcd := 25
  ionelCodimension := 12
}

def endpointG7 : CriticalEndpointIndex := {
  pair := { genus := 7, markings := 4 }
  route := EndpointRoute.oneMarkingPrimitiveQuotient
  ordinaryDegree := 28
  ckgpMarkingBound := 3
  primitiveDegree := 24
  unpointedVcd := 23
  smallerPointedMarkings := 3
  smallerPointedVcd := 27
  ionelCodimension := 13
}

abbrev IsCriticalEndpoint (e : CriticalEndpointIndex) : Prop :=
  e = endpointG3 ∨ e = endpointG4 ∨ e = endpointG5 ∨ e = endpointG6 ∨ e = endpointG7

abbrev EndpointArithmeticIsCoherent (e : CriticalEndpointIndex) : Prop :=
  2 * e.pair.genus + e.pair.markings = 18 ∧
  e.ordinaryDegree + 22 = 6 * e.pair.genus + 2 * e.pair.markings ∧
  e.primitiveDegree + e.pair.markings = e.ordinaryDegree ∧
  e.unpointedVcd + 5 = 4 * e.pair.genus ∧
  e.smallerPointedMarkings + 1 = e.pair.markings ∧
  e.smallerPointedVcd + 1 = e.ordinaryDegree

def psiSourceIonelIndex (e : CriticalEndpointIndex) : IonelVanishingIndex := {
  genus := e.pair.genus
  markings := e.smallerPointedMarkings
  codimension := e.ionelCodimension
  level := VanishingLevel.cohomological
}

def endpointGroupIonelIndex (e : CriticalEndpointIndex) : IonelVanishingIndex := {
  genus := e.pair.genus
  markings := e.pair.markings
  codimension := e.ionelCodimension
  level := VanishingLevel.cohomological
}

structure G7D16VocabularyV4 where
  IonelLooijengaVanishes : IonelVanishingIndex -> Prop
  PureIsTautologicalAtEndpoint : CriticalEndpointIndex -> Prop
  PureIsTautologicalAtSmallerPointed : CriticalEndpointIndex -> Prop
  StrictPrimitiveAboveUnpointedVCD : CriticalEndpointIndex -> Prop
  StrictPhiAboveSmallerPointedVCD : CriticalEndpointIndex -> Prop
  InclusiveCKgPMarkingEndpoint : CriticalEndpointIndex -> Prop
  IonelKillsPsiSource : CriticalEndpointIndex -> Prop
  IonelKillsEndpointGroup : CriticalEndpointIndex -> Prop
  CriticalEndpointVanishes : CriticalEndpointIndex -> Prop
  PublishedOpenRangeControl : Prop
  OpenBMVanishes : OpenBMIndex -> Prop
  OpenBMIsFiniteTateSum : OpenBMIndex -> Prop
  OddCompactVanishingThroughNine : Prop
  EvenCompactTateThroughFourteen : Prop
  KunnethTypesProductFactors : Prop
  FiniteGraphAutomorphismInvariants : Prop
  OneEdgeBoundaryFactor : StablePairIndex -> StablePairIndex -> Prop
  BoundaryImageIsFiniteTateSum : BoundaryImageIndex -> Prop
  BoundarySequenceIsRightExact : BoundarySequenceIndex -> Prop
  BoundaryImageIsKernel : BoundarySequenceIndex -> Prop
  SmoothProperPurityInput : CompactHomologyIndex -> Prop
  CompactHomologyIsPurePolarizable : CompactHomologyIndex -> Prop
  CompactHomologyIsFiniteTateSum : CompactHomologyIndex -> Prop
  ProperSameDegreeDuality : ProperDualityIndex -> Prop
-- LEAN-SHARED-SIGNATURE-END

axiom CompactH16IsFiniteTateSum : CompactH16TargetIndex -> Prop
-- LEAN-AXIOM CompactH16IsFiniteTateSum => VOCAB -- exact whole-group compact cohomology target predicate, left uninterpreted

axiom vocab : G7D16VocabularyV4
-- LEAN-AXIOM vocab => VOCAB -- shared route-separated vocabulary with independent Ionel, CLP-range, purity and kernel carriers

axiom ionel_looijenga_cohomological_vanishing : forall i : IonelVanishingIndex,
    i.level = VanishingLevel.cohomological ->
    2 <= i.genus ->
    (0 < i.markings -> i.genus <= i.codimension) ->
    (i.markings = 0 -> i.genus <= i.codimension + 1) ->
    vocab.IonelLooijengaVanishes i
-- LEAN-AXIOM ionel_looijenga_cohomological_vanishing => G7D16-OBL-01 -- the single general Ionel-Looijenga premise, typed by genus, markings, codimension and cohomological level

axiom clp_pure_tautological_at_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    EndpointArithmeticIsCoherent e ->
    e.pair.markings <= e.ckgpMarkingBound ->
    vocab.PureIsTautologicalAtEndpoint e
-- LEAN-AXIOM clp_pure_tautological_at_endpoint => G7D16-OBL-01 -- CLP Table 1 and Proposition 4.5 at the endpoint pair itself, gated on n at most c(g)

axiom clp_pure_tautological_at_smaller_pointed : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    EndpointArithmeticIsCoherent e ->
    e.smallerPointedMarkings <= e.ckgpMarkingBound ->
    vocab.PureIsTautologicalAtSmallerPointed e
-- LEAN-AXIOM clp_pure_tautological_at_smaller_pointed => G7D16-OBL-01 -- CLP Table 1 and Proposition 4.5 at the one-marking source, gated on n-1 at most c(g)

axiom strict_primitive_vcd_at_critical_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    EndpointArithmeticIsCoherent e ->
    e.unpointedVcd < e.primitiveDegree ->
    vocab.StrictPrimitiveAboveUnpointedVCD e
-- LEAN-AXIOM strict_primitive_vcd_at_critical_endpoint => G7D16-OBL-01 -- k-n is strictly above 4g-5, never equal to it

axiom strict_phi_vcd_at_critical_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    EndpointArithmeticIsCoherent e ->
    e.smallerPointedVcd < e.ordinaryDegree ->
    vocab.StrictPhiAboveSmallerPointedVCD e
-- LEAN-AXIOM strict_phi_vcd_at_critical_endpoint => G7D16-OBL-01 -- k is strictly above the vcd with one fewer marking

axiom inclusive_ckgp_endpoint : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.ckgpMarkingBound < e.pair.markings ->
    e.smallerPointedMarkings = e.ckgpMarkingBound ->
    vocab.PureIsTautologicalAtSmallerPointed e ->
    vocab.InclusiveCKgPMarkingEndpoint e
-- LEAN-AXIOM inclusive_ckgp_endpoint => G7D16-OBL-01 -- the pair is out of the published range while its one-marking source sits exactly at the CLP Table 1 endpoint

axiom ionel_kills_critical_psi_source : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    2 * e.ionelCodimension + 2 = e.ordinaryDegree ->
    vocab.PureIsTautologicalAtSmallerPointed e ->
    vocab.IonelLooijengaVanishes (psiSourceIonelIndex e) ->
    vocab.IonelKillsPsiSource e
-- LEAN-AXIOM ionel_kills_critical_psi_source => G7D16-OBL-01 -- general Ionel at the psi-source codimension (k-2)/2 on the one-marking route

axiom ionel_kills_endpoint_group : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    2 * e.ionelCodimension = e.ordinaryDegree ->
    vocab.PureIsTautologicalAtEndpoint e ->
    vocab.IonelLooijengaVanishes (endpointGroupIonelIndex e) ->
    vocab.IonelKillsEndpointGroup e
-- LEAN-AXIOM ionel_kills_endpoint_group => G7D16-OBL-01 -- general Ionel at the endpoint codimension k/2 on the direct published range

axiom critical_endpoint_vanishes_one_marking : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.route = EndpointRoute.oneMarkingPrimitiveQuotient ->
    vocab.StrictPrimitiveAboveUnpointedVCD e ->
    vocab.StrictPhiAboveSmallerPointedVCD e ->
    vocab.InclusiveCKgPMarkingEndpoint e ->
    vocab.IonelKillsPsiSource e ->
    vocab.CriticalEndpointVanishes e
-- LEAN-AXIOM critical_endpoint_vanishes_one_marking => G7D16-OBL-01 -- one-marking primitive-quotient route, available only at (3,12), (5,8), (6,6), and (7,4)

axiom critical_endpoint_vanishes_direct_range : forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.route = EndpointRoute.directPublishedRange ->
    e.pair.markings <= e.ckgpMarkingBound ->
    vocab.IonelKillsEndpointGroup e ->
    vocab.CriticalEndpointVanishes e
-- LEAN-AXIOM critical_endpoint_vanishes_direct_range => G7D16-OBL-01 -- direct published Canning-Larson-Payne route, available only at (4,10)

axiom published_open_range_control : vocab.PublishedOpenRangeControl
-- LEAN-AXIOM published_open_range_control => G7D16-OBL-02 -- audited remaining published-range open Tate cases

axiom open_bm_vanishes_strong_range : forall (p : StablePairIndex) (c : Nat),
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    11 <= 2 * p.genus + p.markings ->
    c + 11 = 3 * p.genus + p.markings ->
    vocab.IonelLooijengaVanishes
      { genus := p.genus, markings := p.markings, codimension := c,
        level := VanishingLevel.cohomological } ->
    vocab.CriticalEndpointVanishes endpointG3 ->
    vocab.CriticalEndpointVanishes endpointG4 ->
    vocab.CriticalEndpointVanishes endpointG5 ->
    vocab.CriticalEndpointVanishes endpointG6 ->
    vocab.CriticalEndpointVanishes endpointG7 ->
    vocab.OpenBMVanishes (openBMIndex p)
-- LEAN-AXIOM open_bm_vanishes_strong_range => G7D16-OBL-02 -- explicit stronger zero range 2g+n at least eleven with its Ionel threshold codimension exposed

axiom published_open_bm_tate_below_zero_range : forall p : StablePairIndex,
    vocab.PublishedOpenRangeControl ->
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    2 * p.genus + p.markings < 11 ->
    vocab.OpenBMIsFiniteTateSum (openBMIndex p)
-- LEAN-AXIOM published_open_bm_tate_below_zero_range => G7D16-OBL-02 -- remaining nonzero-range open Tate cases

axiom zero_open_bm_is_tate : forall i : OpenBMIndex,
    vocab.OpenBMVanishes i -> vocab.OpenBMIsFiniteTateSum i
-- LEAN-AXIOM zero_open_bm_is_tate => G7D16-OBL-02 -- zero is a finite Q(8)-sum, with rank zero explicit

axiom compact_base_genus_zero_one_two : forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 2 ->
    CompactH16IsFiniteTateSum (compactH16Target p)
-- LEAN-AXIOM compact_base_genus_zero_one_two => G7D16-OBL-03 -- compact degree-sixteen base cases for every marking count

axiom odd_compact_vanishing_through_nine : vocab.OddCompactVanishingThroughNine
-- LEAN-AXIOM odd_compact_vanishing_through_nine => G7D16-OBL-03 -- low odd compact factors vanish

axiom even_compact_tate_through_fourteen : vocab.EvenCompactTateThroughFourteen
-- LEAN-AXIOM even_compact_tate_through_fourteen => G7D16-OBL-03 -- positive low even compact factors are Tate

axiom boundary_factor_is_stable : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> IsStablePair q
-- LEAN-AXIOM boundary_factor_is_stable => G7D16-OBL-04 -- every one-edge factor is stable

axiom boundary_factor_genus_le_parent : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> q.genus <= p.genus
-- LEAN-AXIOM boundary_factor_genus_le_parent => G7D16-OBL-04 -- a factor never increases genus

axiom boundary_factor_complexity_decreases : forall p q : StablePairIndex,
    vocab.OneEdgeBoundaryFactor p q -> PairComplexity q < PairComplexity p
-- LEAN-AXIOM boundary_factor_complexity_decreases => G7D16-OBL-08 -- strict well-founded decrease of 3g+n at every factor

axiom kunneth_types_product_factors :
    vocab.OddCompactVanishingThroughNine ->
    vocab.EvenCompactTateThroughFourteen ->
    vocab.KunnethTypesProductFactors
-- LEAN-AXIOM kunneth_types_product_factors => G7D16-OBL-05 -- Kunneth assembly consuming the odd and even low-degree compact inputs

axiom finite_graph_automorphism_invariants : vocab.FiniteGraphAutomorphismInvariants
-- LEAN-AXIOM finite_graph_automorphism_invariants => G7D16-OBL-05 -- rational finite graph-automorphism invariance, typed separately from Kunneth

axiom boundary_image_tate_from_one_edge_graphs : forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 7 ->
    vocab.KunnethTypesProductFactors ->
    vocab.FiniteGraphAutomorphismInvariants ->
    (forall q : StablePairIndex, vocab.OneEdgeBoundaryFactor p q ->
      CompactH16IsFiniteTateSum (compactH16Target q)) ->
    vocab.BoundaryImageIsFiniteTateSum (boundaryImageIndex p)
-- LEAN-AXIOM boundary_image_tate_from_one_edge_graphs => G7D16-OBL-05 -- passage from the normalized boundary source to its distinct homological image carrier

axiom boundary_sequence_right_exact : forall s : BoundarySequenceIndex,
    IsStablePair s.pair ->
    s.boundary = boundaryImageIndex s.pair ->
    s.compact = compactHomologyIndex s.pair ->
    s.openPart = openBMIndex s.pair ->
    s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ->
    s.degreeShift = 0 -> s.tateTwist = 0 ->
    vocab.BoundarySequenceIsRightExact s
-- LEAN-AXIOM boundary_sequence_right_exact => G7D16-OBL-06 -- right exactness excludes kernel orientation so the two predicates remain independent

axiom boundary_image_is_kernel : forall p : StablePairIndex,
    vocab.BoundarySequenceIsRightExact (boundarySequenceIndex p) ->
    (boundarySequenceIndex p).kernelOrientation = KernelOrientation.boundaryImageIsKernel ->
    vocab.BoundaryImageIsKernel (boundarySequenceIndex p)
-- LEAN-AXIOM boundary_image_is_kernel => G7D16-OBL-06 -- separate correct kernel/quotient orientation premise

axiom smooth_proper_purity_input : forall h : CompactHomologyIndex,
    IsStablePair h.pair ->
    h.geometry = GeometryKind.stableCompactifiedDMStack ->
    h.objectKind = CohomologyObjectKind.wholeGroup ->
    vocab.SmoothProperPurityInput h
-- LEAN-AXIOM smooth_proper_purity_input => G7D16-OBL-07 -- smooth-proper geometry input, typed separately from the purity it licenses

axiom compact_homology_pure_polarizable : forall h : CompactHomologyIndex,
    vocab.SmoothProperPurityInput h ->
    h.purityKind = PurityKind.purePolarizable ->
    vocab.CompactHomologyIsPurePolarizable h
-- LEAN-AXIOM compact_homology_pure_polarizable => G7D16-OBL-07 -- purity follows from the smooth-proper input plus the purity tag

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
-- LEAN-AXIOM semisimple_boundary_extension => G7D16-OBL-07 -- exactness, kernel, subobject, quotient, and purity are all explicit

axiom proper_same_degree_duality : forall p : StablePairIndex,
    IsStablePair p ->
    vocab.ProperSameDegreeDuality (properDualityIndex p)
-- LEAN-AXIOM proper_same_degree_duality => G7D16-OBL-07 -- proper H_16/H^16 duality with zero ambient twist

axiom proper_duality_transfers_tate : forall p : StablePairIndex,
    vocab.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) ->
    vocab.ProperSameDegreeDuality (properDualityIndex p) ->
    CompactH16IsFiniteTateSum (compactH16Target p)
-- LEAN-AXIOM proper_duality_transfers_tate => G7D16-OBL-07 -- Q(8) dualizes to Q(-8) in the same degree

theorem psiSourceIonel (e : CriticalEndpointIndex)
    (hg : 2 <= e.pair.genus)
    (hpos : 0 < e.smallerPointedMarkings)
    (hcodim : e.pair.genus <= e.ionelCodimension) :
    vocab.IonelLooijengaVanishes (psiSourceIonelIndex e) := by
  refine ionel_looijenga_cohomological_vanishing (psiSourceIonelIndex e) rfl ?_ ?_ ?_
  · show 2 <= e.pair.genus
    exact hg
  · show 0 < e.smallerPointedMarkings -> e.pair.genus <= e.ionelCodimension
    exact fun _ => hcodim
  · show e.smallerPointedMarkings = 0 -> e.pair.genus <= e.ionelCodimension + 1
    intro h
    omega

theorem endpointGroupIonel (e : CriticalEndpointIndex)
    (hg : 2 <= e.pair.genus)
    (hpos : 0 < e.pair.markings)
    (hcodim : e.pair.genus <= e.ionelCodimension) :
    vocab.IonelLooijengaVanishes (endpointGroupIonelIndex e) := by
  refine ionel_looijenga_cohomological_vanishing (endpointGroupIonelIndex e) rfl ?_ ?_ ?_
  · show 2 <= e.pair.genus
    exact hg
  · show 0 < e.pair.markings -> e.pair.genus <= e.ionelCodimension
    exact fun _ => hcodim
  · show e.pair.markings = 0 -> e.pair.genus <= e.ionelCodimension + 1
    intro h
    omega

theorem oneMarkingEndpointVanishes (e : CriticalEndpointIndex)
    (hmem : IsCriticalEndpoint e)
    (hcoh : EndpointArithmeticIsCoherent e)
    (hroute : e.route = EndpointRoute.oneMarkingPrimitiveQuotient)
    (hprim : e.unpointedVcd < e.primitiveDegree)
    (hphi : e.smallerPointedVcd < e.ordinaryDegree)
    (hout : e.ckgpMarkingBound < e.pair.markings)
    (hinc : e.smallerPointedMarkings = e.ckgpMarkingBound)
    (hcodim : 2 * e.ionelCodimension + 2 = e.ordinaryDegree)
    (hg2 : 2 <= e.pair.genus)
    (hpos : 0 < e.smallerPointedMarkings)
    (hionel : e.pair.genus <= e.ionelCodimension) :
    vocab.CriticalEndpointVanishes e :=
  have htaut : vocab.PureIsTautologicalAtSmallerPointed e :=
    clp_pure_tautological_at_smaller_pointed e hmem hcoh (by omega)
  critical_endpoint_vanishes_one_marking e hmem hroute
    (strict_primitive_vcd_at_critical_endpoint e hmem hcoh hprim)
    (strict_phi_vcd_at_critical_endpoint e hmem hcoh hphi)
    (inclusive_ckgp_endpoint e hmem hout hinc htaut)
    (ionel_kills_critical_psi_source e hmem hcodim htaut
      (psiSourceIonel e hg2 hpos hionel))

theorem endpointG3Vanishes : vocab.CriticalEndpointVanishes endpointG3 :=
  oneMarkingEndpointVanishes endpointG3 (by left; rfl)
    ⟨rfl, rfl, rfl, rfl, rfl, rfl⟩ rfl
    (by decide) (by decide) (by decide) (by decide) (by decide)
    (by decide) (by decide) (by decide)

theorem endpointG5Vanishes : vocab.CriticalEndpointVanishes endpointG5 :=
  oneMarkingEndpointVanishes endpointG5 (by right; right; left; rfl)
    ⟨rfl, rfl, rfl, rfl, rfl, rfl⟩ rfl
    (by decide) (by decide) (by decide) (by decide) (by decide)
    (by decide) (by decide) (by decide)

theorem endpointG6Vanishes : vocab.CriticalEndpointVanishes endpointG6 :=
  oneMarkingEndpointVanishes endpointG6 (by right; right; right; left; rfl)
    ⟨rfl, rfl, rfl, rfl, rfl, rfl⟩ rfl
    (by decide) (by decide) (by decide) (by decide) (by decide)
    (by decide) (by decide) (by decide)

theorem endpointG7Vanishes : vocab.CriticalEndpointVanishes endpointG7 :=
  oneMarkingEndpointVanishes endpointG7 (by right; right; right; right; rfl)
    ⟨rfl, rfl, rfl, rfl, rfl, rfl⟩ rfl
    (by decide) (by decide) (by decide) (by decide) (by decide)
    (by decide) (by decide) (by decide)

theorem endpointG4Vanishes : vocab.CriticalEndpointVanishes endpointG4 :=
  critical_endpoint_vanishes_direct_range endpointG4 (by right; left; rfl) rfl (by decide)
    (ionel_kills_endpoint_group endpointG4 (by right; left; rfl) (by decide)
      (clp_pure_tautological_at_endpoint endpointG4 (by right; left; rfl)
        ⟨rfl, rfl, rfl, rfl, rfl, rfl⟩ (by decide))
      (endpointGroupIonel endpointG4 (by decide) (by decide) (by decide)))

theorem openBMTateForRange (p : StablePairIndex)
    (hstable : IsStablePair p) (hg3 : 3 <= p.genus) (hg7 : p.genus <= 7) :
    vocab.OpenBMIsFiniteTateSum (openBMIndex p) := by
  by_cases hzero : 11 <= 2 * p.genus + p.markings
  · obtain ⟨c, hc⟩ : exists c : Nat, c + 11 = 3 * p.genus + p.markings :=
      ⟨3 * p.genus + p.markings - 11, by omega⟩
    have hionel : vocab.IonelLooijengaVanishes
        { genus := p.genus, markings := p.markings, codimension := c,
          level := VanishingLevel.cohomological } := by
      refine ionel_looijenga_cohomological_vanishing _ rfl ?_ ?_ ?_
      · show 2 <= p.genus
        omega
      · show 0 < p.markings -> p.genus <= c
        intro _
        omega
      · show p.markings = 0 -> p.genus <= c + 1
        intro _
        omega
    exact zero_open_bm_is_tate (openBMIndex p)
      (open_bm_vanishes_strong_range p c hstable hg3 hg7 hzero hc hionel
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
            (kunneth_types_product_factors odd_compact_vanishing_through_nine
              even_compact_tate_through_fourteen)
            finite_graph_automorphism_invariants hfactor
        have hexact : vocab.BoundarySequenceIsRightExact (boundarySequenceIndex p) :=
          boundary_sequence_right_exact (boundarySequenceIndex p) hstable
            rfl rfl rfl rfl rfl rfl
        have hkernel : vocab.BoundaryImageIsKernel (boundarySequenceIndex p) :=
          boundary_image_is_kernel p hexact rfl
        have hpure : vocab.CompactHomologyIsPurePolarizable (compactHomologyIndex p) :=
          compact_homology_pure_polarizable (compactHomologyIndex p)
            (smooth_proper_purity_input (compactHomologyIndex p) hstable rfl rfl) rfl
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
