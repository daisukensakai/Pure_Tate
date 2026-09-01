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
