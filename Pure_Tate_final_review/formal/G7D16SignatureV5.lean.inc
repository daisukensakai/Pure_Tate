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
