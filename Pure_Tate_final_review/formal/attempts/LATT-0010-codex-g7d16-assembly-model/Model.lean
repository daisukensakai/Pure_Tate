set_option autoImplicit false
-- LEAN-MODEL-WITNESS Assembly-sensitive concrete model for every LATT-0010 campaign axiom
-- LEAN-NONCOLLAPSE Rejects target perturbations, whole-open-group confusion, at-vcd endpoints, incoherent endpoint arithmetic, a shrunken or table-inconsistent CLP marking bound, compact-geometry and integral-coefficient Ionel and endpoint indices, the one-marking route at (4,10), the direct range outside (4,10), Chow-level Ionel, Ionel below the genus threshold, critical-line pairs with no endpoint record in genus two and genus eight, an untyped published-range control, a purity input whose weight is perturbed off the canonical index, reversed or shifted or twisted sequences, wrong kernel orientation, impure middle terms, same-complexity recursion, open dimension-twisted duality, and deletion of each of the four disjoint open-range routes at a target pair that only that route covers
-- LEAN-MODELS CompactH16IsFiniteTateSum vocab ionel_looijenga_cohomological_vanishing clp_pure_tautological_at_endpoint clp_pure_tautological_at_smaller_pointed strict_primitive_vcd_at_critical_endpoint strict_phi_vcd_at_critical_endpoint inclusive_ckgp_endpoint ionel_kills_critical_psi_source ionel_kills_endpoint_group critical_endpoint_vanishes_one_marking critical_endpoint_vanishes_direct_range bfp_whole_open_bm_vanishes_above_critical_line lowest_weight_piece_vanishes_from_whole_group clp_pure_tautological_in_open_range open_bm_vanishes_on_critical_line open_bm_vanishes_below_critical_line published_open_range_control published_open_bm_tate_below_zero_range zero_open_bm_is_tate compact_base_genus_zero_one_two odd_compact_vanishing_through_nine even_compact_tate_through_fourteen boundary_factor_is_stable boundary_factor_genus_le_parent boundary_factor_complexity_decreases kunneth_types_product_factors finite_graph_automorphism_invariants boundary_image_tate_from_one_edge_graphs boundary_sequence_right_exact boundary_image_is_kernel smooth_proper_purity_input compact_homology_pure_polarizable semisimple_boundary_extension proper_same_degree_duality proper_duality_transfers_tate
-- LEAN-MODEL-THEOREM g7d16_assembly_sensitive_model_is_consistent_and_materially_noncollapsing

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

def wholeOpenBMIndex (p : StablePairIndex) : OpenBMIndex :=
  { openBMIndex p with objectKind := CohomologyObjectKind.wholeGroup }

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

def normalizedCompactIndex (h : CompactHomologyIndex) : CompactHomologyIndex :=
  { h with purityKind := PurityKind.purePolarizable }

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
  geometry : GeometryKind
  coefficients : CoefficientKind
  level : VanishingLevel
  deriving DecidableEq

def clpMarkingBound (g : Nat) : Nat :=
  if g = 1 then 10
  else if g = 2 then 10
  else if g = 3 then 11
  else if g = 4 then 11
  else if g = 5 then 7
  else if g = 6 then 5
  else if g = 7 then 3
  else 0

inductive EndpointRoute where
  | oneMarkingPrimitiveQuotient
  | directPublishedRange
  deriving DecidableEq

structure CriticalEndpointIndex where
  pair : StablePairIndex
  geometry : GeometryKind
  coefficients : CoefficientKind
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
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
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
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
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
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
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
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
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
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
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
  e.smallerPointedVcd + 1 = e.ordinaryDegree ∧
  e.ckgpMarkingBound = clpMarkingBound e.pair.genus ∧
  e.geometry = GeometryKind.smoothOpenDMStack ∧
  e.coefficients = CoefficientKind.rational

def psiSourceIonelIndex (e : CriticalEndpointIndex) : IonelVanishingIndex := {
  genus := e.pair.genus
  markings := e.smallerPointedMarkings
  codimension := e.ionelCodimension
  geometry := e.geometry
  coefficients := e.coefficients
  level := VanishingLevel.cohomological
}

def endpointGroupIonelIndex (e : CriticalEndpointIndex) : IonelVanishingIndex := {
  genus := e.pair.genus
  markings := e.pair.markings
  codimension := e.ionelCodimension
  geometry := e.geometry
  coefficients := e.coefficients
  level := VanishingLevel.cohomological
}

def openRangeIonelIndex (p : StablePairIndex) (c : Nat) : IonelVanishingIndex := {
  genus := p.genus
  markings := p.markings
  codimension := c
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
  level := VanishingLevel.cohomological
}

structure G7D16VocabularyV5 where
  IonelLooijengaVanishes : IonelVanishingIndex -> Prop
  PureIsTautologicalAtEndpoint : CriticalEndpointIndex -> Prop
  PureIsTautologicalAtSmallerPointed : CriticalEndpointIndex -> Prop
  PureIsTautologicalInOpenRange : StablePairIndex -> Prop
  StrictPrimitiveAboveUnpointedVCD : CriticalEndpointIndex -> Prop
  StrictPhiAboveSmallerPointedVCD : CriticalEndpointIndex -> Prop
  InclusiveCKgPMarkingEndpoint : CriticalEndpointIndex -> Prop
  IonelKillsPsiSource : CriticalEndpointIndex -> Prop
  IonelKillsEndpointGroup : CriticalEndpointIndex -> Prop
  CriticalEndpointVanishes : CriticalEndpointIndex -> Prop
  PublishedOpenRangeControl : StablePairIndex -> Prop
  WholeOpenBMVanishes : OpenBMIndex -> Prop
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

def ionelModel (i : IonelVanishingIndex) : Prop :=
  i.level = VanishingLevel.cohomological ∧
  i.geometry = GeometryKind.smoothOpenDMStack ∧
  i.coefficients = CoefficientKind.rational ∧
  2 <= i.genus ∧
  (0 < i.markings -> i.genus <= i.codimension) ∧
  (i.markings = 0 -> i.genus <= i.codimension + 1)

def pureTautEndpointModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ e.pair.markings <= e.ckgpMarkingBound

def pureTautSmallerPointedModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ e.smallerPointedMarkings <= e.ckgpMarkingBound

def pureTautOpenRangeModel (p : StablePairIndex) : Prop :=
  IsStablePair p ∧ 3 <= p.genus ∧ p.genus <= 7 ∧ p.markings <= clpMarkingBound p.genus

def strictPrimitiveModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ e.unpointedVcd < e.primitiveDegree

def strictPhiModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ e.smallerPointedVcd < e.ordinaryDegree

def inclusiveEndpointModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ e.ckgpMarkingBound < e.pair.markings ∧
  e.smallerPointedMarkings = e.ckgpMarkingBound ∧ pureTautSmallerPointedModel e

def ionelPsiModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ 2 * e.ionelCodimension + 2 = e.ordinaryDegree ∧
  pureTautSmallerPointedModel e ∧ ionelModel (psiSourceIonelIndex e)

def ionelEndpointGroupModel (e : CriticalEndpointIndex) : Prop :=
  EndpointArithmeticIsCoherent e ∧ 2 * e.ionelCodimension = e.ordinaryDegree ∧
  pureTautEndpointModel e ∧ ionelModel (endpointGroupIonelIndex e)

def criticalVanishModel (e : CriticalEndpointIndex) : Prop :=
  IsCriticalEndpoint e ∧
  ((e.route = EndpointRoute.oneMarkingPrimitiveQuotient ∧
      strictPrimitiveModel e ∧ strictPhiModel e ∧
      inclusiveEndpointModel e ∧ ionelPsiModel e) ∨
   (e.route = EndpointRoute.directPublishedRange ∧
      e.pair.markings <= e.ckgpMarkingBound ∧ ionelEndpointGroupModel e))

def wholeOpenVanishModel (i : OpenBMIndex) : Prop :=
  i = wholeOpenBMIndex i.pair ∧ IsStablePair i.pair ∧
  2 <= i.pair.markings ∧ 18 < 2 * i.pair.genus + i.pair.markings

def publishedControlModel (p : StablePairIndex) : Prop :=
  IsStablePair p ∧ 3 <= p.genus ∧ p.genus <= 7 ∧
  2 * p.genus + p.markings < 11 ∧ p.markings <= clpMarkingBound p.genus

def openVanishModel (i : OpenBMIndex) : Prop :=
  i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
  (wholeOpenVanishModel (wholeOpenBMIndex i.pair) ∨
   (2 * i.pair.genus + i.pair.markings = 18 ∧
     exists e : CriticalEndpointIndex,
       e.pair.genus = i.pair.genus ∧ e.pair.markings = i.pair.markings ∧
       criticalVanishModel e) ∨
   (3 <= i.pair.genus ∧ i.pair.genus <= 7 ∧
     11 <= 2 * i.pair.genus + i.pair.markings ∧
     2 * i.pair.genus + i.pair.markings < 18 ∧
     pureTautOpenRangeModel i.pair ∧
     exists c : Nat, c + 11 = 3 * i.pair.genus + i.pair.markings ∧
       ionelModel (openRangeIonelIndex i.pair c)))

def openTateModel (i : OpenBMIndex) : Prop :=
  openVanishModel i ∨
  (i = openBMIndex i.pair ∧ publishedControlModel i.pair ∧ pureTautOpenRangeModel i.pair)

def openTateWithoutCriticalModel (i : OpenBMIndex) : Prop :=
  (i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
    (wholeOpenVanishModel (wholeOpenBMIndex i.pair) ∨
     (3 <= i.pair.genus ∧ i.pair.genus <= 7 ∧
       11 <= 2 * i.pair.genus + i.pair.markings ∧
       2 * i.pair.genus + i.pair.markings < 18 ∧
       pureTautOpenRangeModel i.pair ∧
       exists c : Nat, c + 11 = 3 * i.pair.genus + i.pair.markings ∧
         ionelModel (openRangeIonelIndex i.pair c)))) ∨
  (i = openBMIndex i.pair ∧ publishedControlModel i.pair ∧
    pureTautOpenRangeModel i.pair)

def openTateWithoutBFPModel (i : OpenBMIndex) : Prop :=
  (i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
    ((2 * i.pair.genus + i.pair.markings = 18 ∧
      exists e : CriticalEndpointIndex,
        e.pair.genus = i.pair.genus ∧ e.pair.markings = i.pair.markings ∧
        criticalVanishModel e) ∨
     (3 <= i.pair.genus ∧ i.pair.genus <= 7 ∧
       11 <= 2 * i.pair.genus + i.pair.markings ∧
       2 * i.pair.genus + i.pair.markings < 18 ∧
       pureTautOpenRangeModel i.pair ∧
       exists c : Nat, c + 11 = 3 * i.pair.genus + i.pair.markings ∧
         ionelModel (openRangeIonelIndex i.pair c)))) ∨
  (i = openBMIndex i.pair ∧ publishedControlModel i.pair ∧
    pureTautOpenRangeModel i.pair)

def openTateWithoutBelowLineModel (i : OpenBMIndex) : Prop :=
  (i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
    (wholeOpenVanishModel (wholeOpenBMIndex i.pair) ∨
     (2 * i.pair.genus + i.pair.markings = 18 ∧
      exists e : CriticalEndpointIndex,
        e.pair.genus = i.pair.genus ∧ e.pair.markings = i.pair.markings ∧
        criticalVanishModel e))) ∨
  (i = openBMIndex i.pair ∧ publishedControlModel i.pair ∧
    pureTautOpenRangeModel i.pair)

def openTateWithoutPublishedModel (i : OpenBMIndex) : Prop := openVanishModel i

def oddModel : Prop := 9 < 10
def evenModel : Prop := 14 <= 14
def kunnethModel : Prop := oddModel ∧ evenModel
def graphInvariantsModel : Prop := 1 <= 1

def boundaryTateModel (i : BoundaryImageIndex) : Prop :=
  i = boundaryImageIndex i.pair ∧ IsStablePair i.pair ∧ i.pair.genus <= 7 ∧
  kunnethModel ∧ graphInvariantsModel

def rightExactModel (s : BoundarySequenceIndex) : Prop :=
  IsStablePair s.pair ∧
  s.boundary = boundaryImageIndex s.pair ∧
  normalizedCompactIndex s.compact = compactHomologyIndex s.pair ∧
  s.openPart = openBMIndex s.pair ∧
  s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ∧
  s.degreeShift = 0 ∧ s.tateTwist = 0

def kernelModel (s : BoundarySequenceIndex) : Prop :=
  rightExactModel s ∧ s.kernelOrientation = KernelOrientation.boundaryImageIsKernel

def smoothProperInputModel (h : CompactHomologyIndex) : Prop :=
  IsStablePair h.pair ∧ normalizedCompactIndex h = compactHomologyIndex h.pair

def pureModel (h : CompactHomologyIndex) : Prop :=
  smoothProperInputModel h ∧ h.purityKind = PurityKind.purePolarizable

def homTateWithOpenModel (OpenTate : OpenBMIndex -> Prop)
    (h : CompactHomologyIndex) : Prop :=
  (exists (s : BoundarySequenceIndex) (b : BoundaryImageIndex) (o : OpenBMIndex),
    s.boundary = b ∧ s.compact = h ∧ s.openPart = o ∧
    rightExactModel s ∧ kernelModel s ∧ boundaryTateModel b ∧
    OpenTate o ∧ pureModel h) ∧
  normalizedCompactIndex h = compactHomologyIndex h.pair ∧
  IsStablePair h.pair ∧ h.pair.genus <= 7

def homTateModel (h : CompactHomologyIndex) : Prop :=
  homTateWithOpenModel openTateModel h

def dualityModel (d : ProperDualityIndex) : Prop :=
  d = properDualityIndex d.pair ∧ IsStablePair d.pair ∧
  (homTateModel d.homology -> d.pair.genus <= 7)

def modelVocabulary : G7D16VocabularyV5 where
  IonelLooijengaVanishes := ionelModel
  PureIsTautologicalAtEndpoint := pureTautEndpointModel
  PureIsTautologicalAtSmallerPointed := pureTautSmallerPointedModel
  PureIsTautologicalInOpenRange := pureTautOpenRangeModel
  StrictPrimitiveAboveUnpointedVCD := strictPrimitiveModel
  StrictPhiAboveSmallerPointedVCD := strictPhiModel
  InclusiveCKgPMarkingEndpoint := inclusiveEndpointModel
  IonelKillsPsiSource := ionelPsiModel
  IonelKillsEndpointGroup := ionelEndpointGroupModel
  CriticalEndpointVanishes := criticalVanishModel
  PublishedOpenRangeControl := publishedControlModel
  WholeOpenBMVanishes := wholeOpenVanishModel
  OpenBMVanishes := openVanishModel
  OpenBMIsFiniteTateSum := openTateModel
  OddCompactVanishingThroughNine := oddModel
  EvenCompactTateThroughFourteen := evenModel
  KunnethTypesProductFactors := kunnethModel
  FiniteGraphAutomorphismInvariants := graphInvariantsModel
  OneEdgeBoundaryFactor := fun p q =>
    IsStablePair q ∧ q.genus <= p.genus ∧ PairComplexity q < PairComplexity p
  BoundaryImageIsFiniteTateSum := boundaryTateModel
  BoundarySequenceIsRightExact := rightExactModel
  BoundaryImageIsKernel := kernelModel
  SmoothProperPurityInput := smoothProperInputModel
  CompactHomologyIsPurePolarizable := pureModel
  CompactHomologyIsFiniteTateSum := homTateModel
  ProperSameDegreeDuality := dualityModel

abbrev V := modelVocabulary

def compactTargetWithOpenModel (OpenTate : OpenBMIndex -> Prop)
    (t : CompactH16TargetIndex) : Prop :=
  t = compactH16Target t.pair ∧ IsStablePair t.pair ∧ t.pair.genus <= 7 ∧
  (t.pair.genus <= 2 ∨ homTateWithOpenModel OpenTate (compactHomologyIndex t.pair))

def CompactH16IsFiniteTateSum (t : CompactH16TargetIndex) : Prop :=
  compactTargetWithOpenModel openTateModel t

def AX01 : Prop := forall i : IonelVanishingIndex,
    i.level = VanishingLevel.cohomological ->
    i.geometry = GeometryKind.smoothOpenDMStack ->
    i.coefficients = CoefficientKind.rational ->
    2 <= i.genus ->
    (0 < i.markings -> i.genus <= i.codimension) ->
    (i.markings = 0 -> i.genus <= i.codimension + 1) ->
    V.IonelLooijengaVanishes i

def AX02 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    e.pair.markings <= e.ckgpMarkingBound ->
    V.PureIsTautologicalAtEndpoint e

def AX03 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    e.smallerPointedMarkings <= e.ckgpMarkingBound ->
    V.PureIsTautologicalAtSmallerPointed e

def AX04 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    e.unpointedVcd < e.primitiveDegree ->
    V.StrictPrimitiveAboveUnpointedVCD e

def AX05 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    e.smallerPointedVcd < e.ordinaryDegree ->
    V.StrictPhiAboveSmallerPointedVCD e

def AX06 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    e.ckgpMarkingBound < e.pair.markings ->
    e.smallerPointedMarkings = e.ckgpMarkingBound ->
    V.PureIsTautologicalAtSmallerPointed e ->
    V.InclusiveCKgPMarkingEndpoint e

def AX07 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    2 * e.ionelCodimension + 2 = e.ordinaryDegree ->
    V.PureIsTautologicalAtSmallerPointed e ->
    V.IonelLooijengaVanishes (psiSourceIonelIndex e) ->
    V.IonelKillsPsiSource e

def AX08 : Prop := forall e : CriticalEndpointIndex,
    EndpointArithmeticIsCoherent e ->
    2 * e.ionelCodimension = e.ordinaryDegree ->
    V.PureIsTautologicalAtEndpoint e ->
    V.IonelLooijengaVanishes (endpointGroupIonelIndex e) ->
    V.IonelKillsEndpointGroup e

def AX09 : Prop := forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.route = EndpointRoute.oneMarkingPrimitiveQuotient ->
    V.StrictPrimitiveAboveUnpointedVCD e ->
    V.StrictPhiAboveSmallerPointedVCD e ->
    V.InclusiveCKgPMarkingEndpoint e ->
    V.IonelKillsPsiSource e ->
    V.CriticalEndpointVanishes e

def AX10 : Prop := forall e : CriticalEndpointIndex,
    IsCriticalEndpoint e ->
    e.route = EndpointRoute.directPublishedRange ->
    e.pair.markings <= e.ckgpMarkingBound ->
    V.IonelKillsEndpointGroup e ->
    V.CriticalEndpointVanishes e

def AX11 : Prop := forall p : StablePairIndex,
    IsStablePair p ->
    2 <= p.markings ->
    18 < 2 * p.genus + p.markings ->
    V.WholeOpenBMVanishes (wholeOpenBMIndex p)

def AX12 : Prop := forall p : StablePairIndex,
    V.WholeOpenBMVanishes (wholeOpenBMIndex p) ->
    V.OpenBMVanishes (openBMIndex p)

def AX13 : Prop := forall p : StablePairIndex,
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    p.markings <= clpMarkingBound p.genus ->
    V.PureIsTautologicalInOpenRange p

def AX14 : Prop := forall (p : StablePairIndex) (e : CriticalEndpointIndex),
    IsStablePair p ->
    2 * p.genus + p.markings = 18 ->
    e.pair.genus = p.genus ->
    e.pair.markings = p.markings ->
    V.CriticalEndpointVanishes e ->
    V.OpenBMVanishes (openBMIndex p)

def AX15 : Prop := forall (p : StablePairIndex) (c : Nat),
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    11 <= 2 * p.genus + p.markings ->
    2 * p.genus + p.markings < 18 ->
    c + 11 = 3 * p.genus + p.markings ->
    V.PureIsTautologicalInOpenRange p ->
    V.IonelLooijengaVanishes (openRangeIonelIndex p c) ->
    V.OpenBMVanishes (openBMIndex p)

def AX16 : Prop := forall p : StablePairIndex,
    IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
    2 * p.genus + p.markings < 11 ->
    p.markings <= clpMarkingBound p.genus ->
    V.PublishedOpenRangeControl p

def AX17 : Prop := forall p : StablePairIndex,
    V.PublishedOpenRangeControl p ->
    V.PureIsTautologicalInOpenRange p ->
    V.OpenBMIsFiniteTateSum (openBMIndex p)

def AX18 : Prop := forall i : OpenBMIndex,
    V.OpenBMVanishes i -> V.OpenBMIsFiniteTateSum i

def AX19 : Prop := forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 2 ->
    CompactH16IsFiniteTateSum (compactH16Target p)

def AX20 : Prop := V.OddCompactVanishingThroughNine

def AX21 : Prop := V.EvenCompactTateThroughFourteen

def AX22 : Prop := forall p q : StablePairIndex,
    V.OneEdgeBoundaryFactor p q -> IsStablePair q

def AX23 : Prop := forall p q : StablePairIndex,
    V.OneEdgeBoundaryFactor p q -> q.genus <= p.genus

def AX24 : Prop := forall p q : StablePairIndex,
    V.OneEdgeBoundaryFactor p q -> PairComplexity q < PairComplexity p

def AX25 : Prop := V.OddCompactVanishingThroughNine ->
    V.EvenCompactTateThroughFourteen ->
    V.KunnethTypesProductFactors

def AX26 : Prop := V.FiniteGraphAutomorphismInvariants

def AX27 : Prop := forall p : StablePairIndex,
    IsStablePair p -> p.genus <= 7 ->
    V.KunnethTypesProductFactors ->
    V.FiniteGraphAutomorphismInvariants ->
    (forall q : StablePairIndex, V.OneEdgeBoundaryFactor p q ->
      CompactH16IsFiniteTateSum (compactH16Target q)) ->
    V.BoundaryImageIsFiniteTateSum (boundaryImageIndex p)

def AX28 : Prop := forall s : BoundarySequenceIndex,
    IsStablePair s.pair ->
    s.boundary = boundaryImageIndex s.pair ->
    normalizedCompactIndex s.compact = compactHomologyIndex s.pair ->
    s.openPart = openBMIndex s.pair ->
    s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ->
    s.degreeShift = 0 -> s.tateTwist = 0 ->
    V.BoundarySequenceIsRightExact s

def AX29 : Prop := forall p : StablePairIndex,
    V.BoundarySequenceIsRightExact (boundarySequenceIndex p) ->
    (boundarySequenceIndex p).kernelOrientation = KernelOrientation.boundaryImageIsKernel ->
    V.BoundaryImageIsKernel (boundarySequenceIndex p)

def AX30 : Prop := forall h : CompactHomologyIndex,
    IsStablePair h.pair ->
    normalizedCompactIndex h = compactHomologyIndex h.pair ->
    V.SmoothProperPurityInput h

def AX31 : Prop := forall h : CompactHomologyIndex,
    V.SmoothProperPurityInput h ->
    h.purityKind = PurityKind.purePolarizable ->
    V.CompactHomologyIsPurePolarizable h

def AX32 : Prop := forall
    (s : BoundarySequenceIndex) (b : BoundaryImageIndex)
    (o : OpenBMIndex) (h : CompactHomologyIndex),
    s.boundary = b -> s.compact = h -> s.openPart = o ->
    V.BoundarySequenceIsRightExact s ->
    V.BoundaryImageIsKernel s ->
    V.BoundaryImageIsFiniteTateSum b ->
    V.OpenBMIsFiniteTateSum o ->
    V.CompactHomologyIsPurePolarizable h ->
    V.CompactHomologyIsFiniteTateSum h

def AX33 : Prop := forall p : StablePairIndex,
    IsStablePair p ->
    V.ProperSameDegreeDuality (properDualityIndex p)

def AX34 : Prop := forall p : StablePairIndex,
    V.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) ->
    V.ProperSameDegreeDuality (properDualityIndex p) ->
    CompactH16IsFiniteTateSum (compactH16Target p)

theorem ax01 : AX01 := fun _ h1 h2 h3 h4 h5 h6 => ⟨h1, h2, h3, h4, h5, h6⟩
theorem ax02 : AX02 := fun _ h1 h2 => ⟨h1, h2⟩
theorem ax03 : AX03 := fun _ h1 h2 => ⟨h1, h2⟩
theorem ax04 : AX04 := fun _ h1 h2 => ⟨h1, h2⟩
theorem ax05 : AX05 := fun _ h1 h2 => ⟨h1, h2⟩
theorem ax06 : AX06 := fun _ h1 h2 h3 h4 => ⟨h1, h2, h3, h4⟩
theorem ax07 : AX07 := fun _ h1 h2 h3 h4 => ⟨h1, h2, h3, h4⟩
theorem ax08 : AX08 := fun _ h1 h2 h3 h4 => ⟨h1, h2, h3, h4⟩
theorem ax09 : AX09 := fun _ h1 h2 h3 h4 h5 h6 => ⟨h1, Or.inl ⟨h2, h3, h4, h5, h6⟩⟩
theorem ax10 : AX10 := fun _ h1 h2 h3 h4 => ⟨h1, Or.inr ⟨h2, h3, h4⟩⟩
theorem ax11 : AX11 := fun _ h1 h2 h3 => ⟨rfl, h1, h2, h3⟩
theorem ax12 : AX12 := fun _ h => ⟨rfl, h.2.1, Or.inl h⟩
theorem ax13 : AX13 := fun _ h1 h2 h3 h4 => ⟨h1, h2, h3, h4⟩
theorem ax14 : AX14 := fun _ e h1 h2 h3 h4 h5 => ⟨rfl, h1, Or.inr (Or.inl ⟨h2, e, h3, h4, h5⟩)⟩
theorem ax15 : AX15 := fun _ c h1 h2 h3 h4 h5 h6 h7 h8 =>
  ⟨rfl, h1, Or.inr (Or.inr ⟨h2, h3, h4, h5, h7, c, h6, h8⟩)⟩
theorem ax16 : AX16 := fun _ h1 h2 h3 h4 h5 => ⟨h1, h2, h3, h4, h5⟩
theorem ax17 : AX17 := fun _ h1 h2 => Or.inr ⟨rfl, h1, h2⟩
theorem ax18 : AX18 := fun _ h => Or.inl h
theorem ax19 : AX19 := by
  intro p hs hg
  exact ⟨rfl, hs, Nat.le_trans hg (by decide : (2 : Nat) <= 7), Or.inl hg⟩
theorem ax20 : AX20 := (by decide : (9 : Nat) < 10)
theorem ax21 : AX21 := (by decide : (14 : Nat) <= 14)
theorem ax22 : AX22 := fun _ _ h => h.1
theorem ax23 : AX23 := fun _ _ h => h.2.1
theorem ax24 : AX24 := fun _ _ h => h.2.2
theorem ax25 : AX25 := fun h1 h2 => ⟨h1, h2⟩
theorem ax26 : AX26 := (by decide : (1 : Nat) <= 1)
theorem ax27 : AX27 := fun _ hs hg hk hgi _ => ⟨rfl, hs, hg, hk, hgi⟩
theorem ax28 : AX28 := fun _ h1 h2 h3 h4 h5 h6 h7 => ⟨h1, h2, h3, h4, h5, h6, h7⟩
theorem ax29 : AX29 := fun _ hr hk => ⟨hr, hk⟩
theorem ax30 : AX30 := fun _ h1 h2 => ⟨h1, h2⟩
theorem ax31 : AX31 := fun _ h1 h2 => ⟨h1, h2⟩
theorem ax32 : AX32 := by
  intro s b o h hsb hsh hso hr hk hb ho hp
  have hnorm : normalizedCompactIndex h = compactHomologyIndex s.pair := by
    rw [← hsh]
    exact hr.2.2.1
  have hhp : h.pair = s.pair := by
    have hpair := congrArg CompactHomologyIndex.pair hnorm
    simpa [normalizedCompactIndex, compactHomologyIndex] using hpair
  have hbp : b.pair = s.pair := by
    rw [← hsb, hr.2.1]
    rfl
  refine ⟨⟨s, b, o, hsb, hsh, hso, hr, hk, hb, ho, hp⟩, ?_, hp.1.1, ?_⟩
  · rw [hnorm, hhp]
  · have hbg : b.pair.genus <= 7 := hb.2.2.1
    rw [hbp] at hbg
    rw [hhp]
    exact hbg
theorem ax33 : AX33 := fun _ hs => ⟨rfl, hs, fun hh => hh.2.2.2⟩
theorem ax34 : AX34 := fun _ hh hd =>
  ⟨rfl, hd.2.1, hd.2.2 hh, Or.inr hh⟩

def stable66 : StablePairIndex := { genus := 6, markings := 6 }
def stable78 : StablePairIndex := { genus := 7, markings := 8 }
def stable60 : StablePairIndex := { genus := 6, markings := 0 }
def stable30 : StablePairIndex := { genus := 3, markings := 0 }
def stable20 : StablePairIndex := { genus := 2, markings := 0 }
def genusEight : StablePairIndex := { genus := 8, markings := 0 }
def unstable10 : StablePairIndex := { genus := 1, markings := 0 }
def offRangeLine : StablePairIndex := { genus := 2, markings := 14 }
def genusEightLine : StablePairIndex := { genus := 8, markings := 2 }

def wrongOpenTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with geometry := GeometryKind.smoothOpenDMStack }
def wrongCoarseTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with geometry := GeometryKind.coarseModuliSpace }
def wrongIntegralTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with coefficients := CoefficientKind.integral }
def wrongUnorderedTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with markingsKind := MarkingKind.unordered }
def wrongDegreeTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with cohomologicalDegree := 15 }
def wrongWeightTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with weight := 15 }
def wrongTateTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with tateIndex := 8 }
def quotientTarget : CompactH16TargetIndex :=
  { compactH16Target stable66 with objectKind := CohomologyObjectKind.quotient }

def atPrimitiveVcd : CriticalEndpointIndex := { endpointG6 with unpointedVcd := 20 }
def atSmallerPointedVcd : CriticalEndpointIndex :=
  { endpointG6 with smallerPointedVcd := 26 }
def incoherentEndpoint : CriticalEndpointIndex := { endpointG6 with ordinaryDegree := 27 }
def shrunkCkgpBound : CriticalEndpointIndex := { endpointG6 with ckgpMarkingBound := 4 }
def compactGeometryEndpoint : CriticalEndpointIndex :=
  { endpointG6 with geometry := GeometryKind.stableCompactifiedDMStack }
def integralEndpoint : CriticalEndpointIndex :=
  { endpointG6 with coefficients := CoefficientKind.integral }

def chowLevelIonel : IonelVanishingIndex :=
  { endpointGroupIonelIndex endpointG5 with level := VanishingLevel.chow }
def belowCodimensionIonel : IonelVanishingIndex :=
  { openRangeIonelIndex { genus := 7, markings := 4 } 6 with }
def compactGeometryIonel : IonelVanishingIndex :=
  { endpointGroupIonelIndex endpointG5 with
    geometry := GeometryKind.stableCompactifiedDMStack }
def integralIonel : IonelVanishingIndex :=
  { endpointGroupIonelIndex endpointG5 with coefficients := CoefficientKind.integral }

def reversedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with
    orientation := ExactSequenceOrientation.openToCompactToBoundary }
def shiftedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with degreeShift := 1 }
def twistedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with tateTwist := 1 }
def wrongKernelSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with
    kernelOrientation := KernelOrientation.compactHomologyIsKernel }

def impureHomology : CompactHomologyIndex :=
  { compactHomologyIndex stable66 with purityKind := PurityKind.impure }
def impureSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with compact := impureHomology }
def badWeightHomology : CompactHomologyIndex :=
  { compactHomologyIndex stable66 with weight := 0 }
def openGeometryHomology : CompactHomologyIndex :=
  { compactHomologyIndex stable66 with geometry := GeometryKind.smoothOpenDMStack }
def imageObjectHomology : CompactHomologyIndex :=
  { compactHomologyIndex stable66 with objectKind := CohomologyObjectKind.image }

def ambientTwistedDuality : ProperDualityIndex :=
  { properDualityIndex stable66 with ambientDimensionTwist := 21 }
def openPoincareDuality : ProperDualityIndex :=
  { properDualityIndex stable66 with kind := DualityKind.openPoincareDimensionTwist }

theorem coh3 : EndpointArithmeticIsCoherent endpointG3 := by decide
theorem coh4 : EndpointArithmeticIsCoherent endpointG4 := by decide
theorem coh5 : EndpointArithmeticIsCoherent endpointG5 := by decide
theorem coh6 : EndpointArithmeticIsCoherent endpointG6 := by decide
theorem coh7 : EndpointArithmeticIsCoherent endpointG7 := by decide

theorem pts3 : pureTautSmallerPointedModel endpointG3 := ⟨coh3, by decide⟩
theorem pts5 : pureTautSmallerPointedModel endpointG5 := ⟨coh5, by decide⟩
theorem pts6 : pureTautSmallerPointedModel endpointG6 := ⟨coh6, by decide⟩
theorem pts7 : pureTautSmallerPointedModel endpointG7 := ⟨coh7, by decide⟩
theorem pte4 : pureTautEndpointModel endpointG4 := ⟨coh4, by decide⟩

theorem ionelPsi3 : ionelModel (psiSourceIonelIndex endpointG3) :=
  ⟨rfl, rfl, rfl, by decide, fun _ => by decide, fun _ => by decide⟩
theorem ionelPsi5 : ionelModel (psiSourceIonelIndex endpointG5) :=
  ⟨rfl, rfl, rfl, by decide, fun _ => by decide, fun _ => by decide⟩
theorem ionelPsi6 : ionelModel (psiSourceIonelIndex endpointG6) :=
  ⟨rfl, rfl, rfl, by decide, fun _ => by decide, fun _ => by decide⟩
theorem ionelPsi7 : ionelModel (psiSourceIonelIndex endpointG7) :=
  ⟨rfl, rfl, rfl, by decide, fun _ => by decide, fun _ => by decide⟩
theorem ionelEG4 : ionelModel (endpointGroupIonelIndex endpointG4) :=
  ⟨rfl, rfl, rfl, by decide, fun _ => by decide, fun _ => by decide⟩

theorem cv3 : criticalVanishModel endpointG3 :=
  ⟨Or.inl rfl, Or.inl ⟨rfl, ⟨coh3, by decide⟩, ⟨coh3, by decide⟩,
    ⟨coh3, by decide, rfl, pts3⟩, ⟨coh3, by decide, pts3, ionelPsi3⟩⟩⟩
theorem cv5 : criticalVanishModel endpointG5 :=
  ⟨Or.inr (Or.inr (Or.inl rfl)), Or.inl ⟨rfl, ⟨coh5, by decide⟩, ⟨coh5, by decide⟩,
    ⟨coh5, by decide, rfl, pts5⟩, ⟨coh5, by decide, pts5, ionelPsi5⟩⟩⟩
theorem cv6 : criticalVanishModel endpointG6 :=
  ⟨Or.inr (Or.inr (Or.inr (Or.inl rfl))), Or.inl ⟨rfl, ⟨coh6, by decide⟩, ⟨coh6, by decide⟩,
    ⟨coh6, by decide, rfl, pts6⟩, ⟨coh6, by decide, pts6, ionelPsi6⟩⟩⟩
theorem cv7 : criticalVanishModel endpointG7 :=
  ⟨Or.inr (Or.inr (Or.inr (Or.inr rfl))), Or.inl ⟨rfl, ⟨coh7, by decide⟩, ⟨coh7, by decide⟩,
    ⟨coh7, by decide, rfl, pts7⟩, ⟨coh7, by decide, pts7, ionelPsi7⟩⟩⟩
theorem cv4 : criticalVanishModel endpointG4 :=
  ⟨Or.inr (Or.inl rfl), Or.inr ⟨rfl, by decide, ⟨coh4, by decide, pte4, ionelEG4⟩⟩⟩

theorem stable66Stable : IsStablePair stable66 := (by decide : (3 : Nat) <= 2 * 6 + 6)
theorem stable78Stable : IsStablePair stable78 := (by decide : (3 : Nat) <= 2 * 7 + 8)
theorem stable60Stable : IsStablePair stable60 := (by decide : (3 : Nat) <= 2 * 6 + 0)
theorem stable30Stable : IsStablePair stable30 := (by decide : (3 : Nat) <= 2 * 3 + 0)
theorem stable20Stable : IsStablePair stable20 := (by decide : (3 : Nat) <= 2 * 2 + 0)
theorem offRangeLineStable : IsStablePair offRangeLine := (by decide : (3 : Nat) <= 2 * 2 + 14)

theorem openTate66 : openTateModel (openBMIndex stable66) :=
  Or.inl ⟨rfl, stable66Stable,
    Or.inr (Or.inl ⟨by decide, endpointG6, rfl, rfl, cv6⟩)⟩

theorem openTate78 : openTateModel (openBMIndex stable78) :=
  Or.inl ⟨rfl, stable78Stable,
    Or.inl ⟨rfl, stable78Stable, by decide, by decide⟩⟩

theorem openTate60 : openTateModel (openBMIndex stable60) :=
  Or.inl ⟨rfl, stable60Stable, Or.inr (Or.inr
    ⟨by decide, by decide, by decide, by decide,
      ⟨stable60Stable, by decide, by decide, by decide⟩,
      7, by decide,
      ⟨rfl, rfl, rfl, by decide,
        (by simp [openRangeIonelIndex, openBMIndex, stable60]),
        (fun _ => by decide)⟩⟩)⟩

theorem openTate30 : openTateModel (openBMIndex stable30) :=
  Or.inr ⟨rfl,
    ⟨stable30Stable, by decide, by decide, by decide, by decide⟩,
    ⟨stable30Stable, by decide, by decide, by decide⟩⟩

theorem homTateFromOpen (p : StablePairIndex)
    (hs : IsStablePair p) (hg : p.genus <= 7)
    (ho : openTateModel (openBMIndex p)) :
    homTateModel (compactHomologyIndex p) := by
  have hr : rightExactModel (boundarySequenceIndex p) :=
    ⟨hs, rfl, rfl, rfl, rfl, rfl, rfl⟩
  refine ⟨⟨boundarySequenceIndex p, boundaryImageIndex p, openBMIndex p,
    rfl, rfl, rfl, hr, ⟨hr, rfl⟩, ?_, ho, ?_⟩, rfl, hs, hg⟩
  · exact ⟨rfl, hs, hg,
      ⟨(by decide : (9 : Nat) < 10), (by decide : (14 : Nat) <= 14)⟩,
      (by decide : (1 : Nat) <= 1)⟩
  · exact ⟨⟨hs, rfl⟩, rfl⟩

theorem noCriticalOpen66 :
    ¬ openTateWithoutCriticalModel (openBMIndex stable66) := by
  rintro (⟨_, _, hwhole | hbelow⟩ | ⟨_, hpublished, _⟩)
  · exact absurd hwhole.2.2.2 (by decide)
  · exact absurd hbelow.2.2.2.1 (by decide)
  · exact absurd hpublished.2.2.2.1 (by decide)

theorem noBFPOpen78 : ¬ openTateWithoutBFPModel (openBMIndex stable78) := by
  rintro (⟨_, _, hcritical | hbelow⟩ | ⟨_, hpublished, _⟩)
  · exact absurd hcritical.1 (by decide)
  · exact absurd hbelow.2.2.2.1 (by decide)
  · exact absurd hpublished.2.2.2.1 (by decide)

theorem noBelowLineOpen60 :
    ¬ openTateWithoutBelowLineModel (openBMIndex stable60) := by
  rintro (⟨_, _, hwhole | hcritical⟩ | ⟨_, hpublished, _⟩)
  · exact absurd hwhole.2.2.2 (by decide)
  · exact absurd hcritical.1 (by decide)
  · exact absurd hpublished.2.2.2.1 (by decide)

theorem noPublishedOpen30 :
    ¬ openTateWithoutPublishedModel (openBMIndex stable30) := by
  rintro ⟨_, _, hwhole | hcritical | hbelow⟩
  · exact absurd hwhole.2.2.1 (by decide)
  · exact absurd hcritical.1 (by decide)
  · exact absurd hbelow.2.2.1 (by decide)

theorem compactTargetFailsWithoutOpen
    (OpenTate : OpenBMIndex -> Prop) (p : StablePairIndex)
    (hnotbase : ¬ p.genus <= 2) (hopen : ¬ OpenTate (openBMIndex p)) :
    ¬ compactTargetWithOpenModel OpenTate (compactH16Target p) := by
  intro ht
  rcases ht.2.2.2 with hbase | hh
  · exact hnotbase hbase
  · obtain ⟨s, b, o, _, hsh, hso, hr, _, _, ho, _⟩ := hh.1
    have hsp : s.pair = p := by
      have hn := congrArg CompactHomologyIndex.pair hr.2.2.1
      have hn2 : s.compact.pair = s.pair := by
        simpa [normalizedCompactIndex, compactHomologyIndex] using hn
      rw [hsh] at hn2
      exact hn2.symm
    have hop : o = openBMIndex p := by
      have heq : o = openBMIndex s.pair := hso.symm.trans hr.2.2.2.1
      rw [hsp] at heq
      exact heq
    rw [hop] at ho
    exact hopen ho

def NC01 : Prop := CompactH16IsFiniteTateSum (compactH16Target stable66)
def NC02 : Prop := CompactH16IsFiniteTateSum (compactH16Target stable78)
def NC03 : Prop := ¬ CompactH16IsFiniteTateSum wrongOpenTarget
def NC04 : Prop := ¬ CompactH16IsFiniteTateSum wrongCoarseTarget
def NC05 : Prop := ¬ CompactH16IsFiniteTateSum wrongIntegralTarget
def NC06 : Prop := ¬ CompactH16IsFiniteTateSum wrongUnorderedTarget
def NC07 : Prop := ¬ CompactH16IsFiniteTateSum (compactH16Target genusEight)
def NC08 : Prop := ¬ CompactH16IsFiniteTateSum (compactH16Target unstable10)
def NC09 : Prop := ¬ CompactH16IsFiniteTateSum wrongDegreeTarget
def NC10 : Prop := ¬ CompactH16IsFiniteTateSum wrongWeightTarget
def NC11 : Prop := ¬ CompactH16IsFiniteTateSum wrongTateTarget
def NC12 : Prop := ¬ CompactH16IsFiniteTateSum quotientTarget
def NC13 : Prop := ¬ V.OpenBMIsFiniteTateSum (wholeOpenBMIndex stable66)
def NC14 : Prop := V.OpenBMVanishes (openBMIndex stable66)
def NC15 : Prop := V.OpenBMIsFiniteTateSum (openBMIndex stable30) ∧
  ¬ V.OpenBMVanishes (openBMIndex stable30)
def NC16 : Prop := ¬ V.InclusiveCKgPMarkingEndpoint endpointG4 ∧
  ¬ (endpointG4.smallerPointedMarkings = endpointG4.ckgpMarkingBound) ∧
  ¬ (endpointG4.ckgpMarkingBound < endpointG4.pair.markings)
def NC17 : Prop := V.PureIsTautologicalAtEndpoint endpointG4 ∧
  ¬ V.PureIsTautologicalAtEndpoint endpointG3 ∧
  ¬ V.PureIsTautologicalAtEndpoint endpointG5 ∧
  ¬ V.PureIsTautologicalAtEndpoint endpointG6 ∧
  ¬ V.PureIsTautologicalAtEndpoint endpointG7
def NC18 : Prop := ¬ V.PureIsTautologicalAtSmallerPointed shrunkCkgpBound ∧
  ¬ EndpointArithmeticIsCoherent shrunkCkgpBound
def NC19 : Prop := ¬ V.IonelLooijengaVanishes chowLevelIonel
def NC20 : Prop := ¬ V.IonelLooijengaVanishes belowCodimensionIonel
def NC21 : Prop := ¬ V.IonelKillsPsiSource endpointG4 ∧
  ¬ V.IonelKillsEndpointGroup endpointG3
def NC22 : Prop := ¬ V.StrictPrimitiveAboveUnpointedVCD atPrimitiveVcd ∧
  ¬ (atPrimitiveVcd.unpointedVcd < atPrimitiveVcd.primitiveDegree)
def NC23 : Prop := ¬ V.StrictPhiAboveSmallerPointedVCD atSmallerPointedVcd ∧
  ¬ (atSmallerPointedVcd.smallerPointedVcd < atSmallerPointedVcd.ordinaryDegree)
def NC24 : Prop := ¬ V.StrictPrimitiveAboveUnpointedVCD incoherentEndpoint ∧
  ¬ EndpointArithmeticIsCoherent incoherentEndpoint
def NC25 : Prop := ¬ V.BoundarySequenceIsRightExact reversedSequence
def NC26 : Prop := ¬ V.BoundarySequenceIsRightExact shiftedSequence
def NC27 : Prop := ¬ V.BoundarySequenceIsRightExact twistedSequence
def NC28 : Prop := V.BoundarySequenceIsRightExact wrongKernelSequence ∧
  ¬ V.BoundaryImageIsKernel wrongKernelSequence
def NC29 : Prop := V.BoundarySequenceIsRightExact impureSequence ∧
  V.BoundaryImageIsKernel impureSequence ∧
  V.BoundaryImageIsFiniteTateSum impureSequence.boundary ∧
  V.OpenBMIsFiniteTateSum impureSequence.openPart ∧
  ¬ V.CompactHomologyIsPurePolarizable impureHomology ∧
  ¬ V.CompactHomologyIsFiniteTateSum impureHomology
def NC30 : Prop := ¬ V.SmoothProperPurityInput openGeometryHomology ∧
  ¬ V.SmoothProperPurityInput imageObjectHomology
def NC31 : Prop := ¬ V.OneEdgeBoundaryFactor stable66 stable66
def NC32 : Prop := V.BoundaryImageIsFiniteTateSum (boundaryImageIndex stable20) ∧
  ¬ V.CompactHomologyIsFiniteTateSum (compactHomologyIndex stable20)
def NC33 : Prop := ¬ V.ProperSameDegreeDuality ambientTwistedDuality
def NC34 : Prop := ¬ V.ProperSameDegreeDuality openPoincareDuality
def NC35 : Prop :=
  endpointG3.route = EndpointRoute.oneMarkingPrimitiveQuotient ∧
  endpointG5.route = EndpointRoute.oneMarkingPrimitiveQuotient ∧
  endpointG6.route = EndpointRoute.oneMarkingPrimitiveQuotient ∧
  endpointG7.route = EndpointRoute.oneMarkingPrimitiveQuotient ∧
  endpointG4.route = EndpointRoute.directPublishedRange ∧
  ¬ (endpointG4.route = EndpointRoute.oneMarkingPrimitiveQuotient)
def NC36 : Prop := ¬ V.SmoothProperPurityInput badWeightHomology
def NC37 : Prop := ¬ V.IonelLooijengaVanishes compactGeometryIonel ∧
  ¬ V.IonelLooijengaVanishes integralIonel
def NC38 : Prop := ¬ EndpointArithmeticIsCoherent compactGeometryEndpoint ∧
  ¬ EndpointArithmeticIsCoherent integralEndpoint
def NC39 : Prop := ¬ V.OpenBMVanishes (openBMIndex offRangeLine) ∧
  ¬ V.OpenBMVanishes (openBMIndex genusEightLine)
def NC40 : Prop := ¬ V.PublishedOpenRangeControl stable66 ∧
  ¬ V.PublishedOpenRangeControl genusEight
def NC41 : Prop := ¬ V.WholeOpenBMVanishes (wholeOpenBMIndex stable66) ∧
  V.WholeOpenBMVanishes (wholeOpenBMIndex stable78)
def NC42 : Prop :=
  ¬ compactTargetWithOpenModel openTateWithoutCriticalModel
    (compactH16Target stable66)
def NC43 : Prop :=
  ¬ compactTargetWithOpenModel openTateWithoutBFPModel
    (compactH16Target stable78)
def NC44 : Prop :=
  ¬ compactTargetWithOpenModel openTateWithoutBelowLineModel
    (compactH16Target stable60)
def NC45 : Prop :=
  ¬ compactTargetWithOpenModel openTateWithoutPublishedModel
    (compactH16Target stable30)

theorem nc01 : NC01 :=
  ⟨rfl, stable66Stable, by decide,
    Or.inr (homTateFromOpen stable66 stable66Stable (by decide) openTate66)⟩
theorem nc02 : NC02 :=
  ⟨rfl, stable78Stable, by decide,
    Or.inr (homTateFromOpen stable78 stable78Stable (by decide) openTate78)⟩
theorem nc03 : NC03 := fun h => absurd h.1 (by decide)
theorem nc04 : NC04 := fun h => absurd h.1 (by decide)
theorem nc05 : NC05 := fun h => absurd h.1 (by decide)
theorem nc06 : NC06 := fun h => absurd h.1 (by decide)
theorem nc07 : NC07 := fun h => absurd h.2.2.1 (by decide)
theorem nc08 : NC08 := fun h => absurd h.2.1 (by decide : ¬ ((3 : Nat) <= 2 * 1 + 0))
theorem nc09 : NC09 := fun h => absurd h.1 (by decide)
theorem nc10 : NC10 := fun h => absurd h.1 (by decide)
theorem nc11 : NC11 := fun h => absurd h.1 (by decide)
theorem nc12 : NC12 := fun h => absurd h.1 (by decide)
theorem nc13 : NC13 := by
  rintro (⟨hz, _⟩ | ⟨hp, _⟩)
  · exact absurd hz (by decide)
  · exact absurd hp (by decide)
theorem nc14 : NC14 :=
  ⟨rfl, stable66Stable, Or.inr (Or.inl ⟨by decide, endpointG6, rfl, rfl, cv6⟩)⟩
theorem nc15 : NC15 := by
  refine ⟨Or.inr ⟨rfl, ⟨stable30Stable, by decide, by decide, by decide, by decide⟩,
    ⟨stable30Stable, by decide, by decide, by decide⟩⟩, ?_⟩
  rintro ⟨_, _, (h | ⟨h, _⟩ | h)⟩
  · exact absurd h.2.2.2 (by decide)
  · exact absurd h (by decide)
  · exact absurd h.2.2.1 (by decide)
theorem nc16 : NC16 :=
  ⟨fun h => absurd h.2.1 (by decide), by decide, by decide⟩
theorem nc17 : NC17 :=
  ⟨pte4, fun h => absurd h.2 (by decide), fun h => absurd h.2 (by decide),
    fun h => absurd h.2 (by decide), fun h => absurd h.2 (by decide)⟩
theorem nc18 : NC18 := ⟨fun h => absurd h.1 (by decide), by decide⟩
theorem nc19 : NC19 := fun h => absurd h.1 (by decide)
theorem nc20 : NC20 := fun h => absurd (h.2.2.2.2.1 (by decide)) (by decide)
theorem nc21 : NC21 := ⟨fun h => absurd h.2.1 (by decide), fun h => absurd h.2.1 (by decide)⟩
theorem nc22 : NC22 := ⟨fun h => absurd h.2 (by decide), by decide⟩
theorem nc23 : NC23 := ⟨fun h => absurd h.2 (by decide), by decide⟩
theorem nc24 : NC24 := ⟨fun h => absurd h.1 (by decide), by decide⟩
theorem nc25 : NC25 := fun h => absurd h.2.2.2.2.1 (by decide)
theorem nc26 : NC26 := fun h => absurd h.2.2.2.2.2.1 (by decide)
theorem nc27 : NC27 := fun h => absurd h.2.2.2.2.2.2 (by decide)
theorem nc28 : NC28 :=
  ⟨⟨stable66Stable, rfl, rfl, rfl, rfl, rfl, rfl⟩, fun h => absurd h.2 (by decide)⟩
theorem nc29 : NC29 := by
  have hr : V.BoundarySequenceIsRightExact impureSequence :=
    ⟨stable66Stable, rfl, rfl, rfl, rfl, rfl, rfl⟩
  refine ⟨hr, ⟨hr, rfl⟩, ?_, Or.inl nc14, ?_, ?_⟩
  · exact ⟨rfl, stable66Stable, by decide,
      ⟨(by decide : (9 : Nat) < 10), (by decide : (14 : Nat) <= 14)⟩,
      (by decide : (1 : Nat) <= 1)⟩
  · intro h
    exact absurd h.2 (by decide : ¬ (PurityKind.impure = PurityKind.purePolarizable))
  · intro h
    obtain ⟨s, b, o, _, _, _, _, _, _, _, hp⟩ := h.1
    exact absurd hp.2 (by decide : ¬ (PurityKind.impure = PurityKind.purePolarizable))
theorem nc30 : NC30 := ⟨fun h => absurd h.2 (by decide), fun h => absurd h.2 (by decide)⟩
theorem nc31 : NC31 := fun h => absurd h.2.2 (by decide)
theorem nc32 : NC32 := by
  refine ⟨⟨rfl, stable20Stable, by decide, ⟨(by decide : (9 : Nat) < 10),
    (by decide : (14 : Nat) <= 14)⟩, (by decide : (1 : Nat) <= 1)⟩, ?_⟩
  intro h
  obtain ⟨s, b, o, _, hsh, hso, hr, _, _, ho, _⟩ := h.1
  have hopair : o.pair = stable20 := by
    have heq : o = openBMIndex s.pair := hso.symm.trans hr.2.2.2.1
    have hsp : s.pair = stable20 := by
      have hn := congrArg CompactHomologyIndex.pair hr.2.2.1
      have hn2 : s.compact.pair = s.pair := by
        simpa [normalizedCompactIndex, compactHomologyIndex] using hn
      rw [hsh] at hn2
      exact hn2.symm
    exact (congrArg OpenBMIndex.pair heq).trans hsp
  rcases ho with hz | hlow
  · rcases hz.2.2 with h | ⟨h, _⟩ | h
    · rw [hopair] at h
      exact absurd h.2.2.2 (by decide)
    · rw [hopair] at h
      exact absurd h (by decide)
    · rw [hopair] at h
      exact absurd h.1 (by decide)
  · have hg3 := hlow.2.1.2.1
    rw [hopair] at hg3
    exact absurd hg3 (by decide)
theorem nc33 : NC33 := fun h => absurd h.1 (by decide)
theorem nc34 : NC34 := fun h => absurd h.1 (by decide)
theorem nc35 : NC35 :=
  ⟨by decide, by decide, by decide, by decide, by decide, by decide⟩
theorem nc36 : NC36 := fun h => absurd h.2 (by decide)
theorem nc37 : NC37 := ⟨fun h => absurd h.2.1 (by decide), fun h => absurd h.2.2.1 (by decide)⟩
theorem nc38 : NC38 := ⟨by decide, by decide⟩
theorem nc39 : NC39 := by
  constructor
  · rintro ⟨_, _, (h | ⟨_, e, hg, _, hcv⟩ | h)⟩
    · exact absurd h.2.2.2 (by decide)
    · rcases hcv.1 with rfl | rfl | rfl | rfl | rfl <;> exact absurd hg (by decide)
    · exact absurd h.1 (by decide)
  · rintro ⟨_, _, (h | ⟨_, e, hg, _, hcv⟩ | h)⟩
    · exact absurd h.2.2.2 (by decide)
    · rcases hcv.1 with rfl | rfl | rfl | rfl | rfl <;> exact absurd hg (by decide)
    · exact absurd h.2.1 (by decide)
theorem nc40 : NC40 := ⟨fun h => absurd h.2.2.2.1 (by decide), fun h => absurd h.2.2.1 (by decide)⟩
theorem nc41 : NC41 :=
  ⟨fun h => absurd h.2.2.2 (by decide),
    ⟨rfl, stable78Stable, by decide, by decide⟩⟩
theorem nc42 : NC42 :=
  compactTargetFailsWithoutOpen openTateWithoutCriticalModel stable66
    (by decide) noCriticalOpen66
theorem nc43 : NC43 :=
  compactTargetFailsWithoutOpen openTateWithoutBFPModel stable78
    (by decide) noBFPOpen78
theorem nc44 : NC44 :=
  compactTargetFailsWithoutOpen openTateWithoutBelowLineModel stable60
    (by decide) noBelowLineOpen60
theorem nc45 : NC45 :=
  compactTargetFailsWithoutOpen openTateWithoutPublishedModel stable30
    (by decide) noPublishedOpen30

theorem g7d16_assembly_sensitive_model_is_consistent_and_materially_noncollapsing :
    AX01 ∧ AX02 ∧ AX03 ∧ AX04 ∧ AX05 ∧ AX06 ∧ AX07 ∧ AX08 ∧ AX09 ∧ AX10 ∧
    AX11 ∧ AX12 ∧ AX13 ∧ AX14 ∧ AX15 ∧ AX16 ∧ AX17 ∧ AX18 ∧ AX19 ∧ AX20 ∧
    AX21 ∧ AX22 ∧ AX23 ∧ AX24 ∧ AX25 ∧ AX26 ∧ AX27 ∧ AX28 ∧ AX29 ∧ AX30 ∧
    AX31 ∧ AX32 ∧ AX33 ∧ AX34 ∧
    NC01 ∧ NC02 ∧ NC03 ∧ NC04 ∧ NC05 ∧ NC06 ∧ NC07 ∧ NC08 ∧ NC09 ∧ NC10 ∧
    NC11 ∧ NC12 ∧ NC13 ∧ NC14 ∧ NC15 ∧ NC16 ∧ NC17 ∧ NC18 ∧ NC19 ∧ NC20 ∧
    NC21 ∧ NC22 ∧ NC23 ∧ NC24 ∧ NC25 ∧ NC26 ∧ NC27 ∧ NC28 ∧ NC29 ∧ NC30 ∧
    NC31 ∧ NC32 ∧ NC33 ∧ NC34 ∧ NC35 ∧ NC36 ∧ NC37 ∧ NC38 ∧ NC39 ∧ NC40 ∧
    NC41 ∧ NC42 ∧ NC43 ∧ NC44 ∧ NC45 :=
  ⟨ax01,ax02,ax03,ax04,ax05,ax06,ax07,ax08,ax09,ax10,
   ax11,ax12,ax13,ax14,ax15,ax16,ax17,ax18,ax19,ax20,
   ax21,ax22,ax23,ax24,ax25,ax26,ax27,ax28,ax29,ax30,
   ax31,ax32,ax33,ax34,
   nc01,nc02,nc03,nc04,nc05,nc06,nc07,nc08,nc09,nc10,
   nc11,nc12,nc13,nc14,nc15,nc16,nc17,nc18,nc19,nc20,
   nc21,nc22,nc23,nc24,nc25,nc26,nc27,nc28,nc29,nc30,
   nc31,nc32,nc33,nc34,nc35,nc36,nc37,nc38,nc39,nc40,nc41,
   nc42,nc43,nc44,nc45⟩

#print axioms g7d16_assembly_sensitive_model_is_consistent_and_materially_noncollapsing
