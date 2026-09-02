set_option autoImplicit false

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


-- ATTACK 2: delete Bergstrom-Faber-Payne whole-group vanishing (G7D16-OBL-09).
def wholeOpenVanishModel (_i : OpenBMIndex) : Prop := False

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

def homTateModel (h : CompactHomologyIndex) : Prop :=
  (exists (s : BoundarySequenceIndex) (b : BoundaryImageIndex) (o : OpenBMIndex),
    s.boundary = b ∧ s.compact = h ∧ s.openPart = o ∧
    rightExactModel s ∧ kernelModel s ∧ boundaryTateModel b ∧
    openTateModel o ∧ pureModel h) ∧
  normalizedCompactIndex h = compactHomologyIndex h.pair ∧
  IsStablePair h.pair ∧ h.pair.genus <= 7

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

def CompactH16IsFiniteTateSum (t : CompactH16TargetIndex) : Prop :=
  t = compactH16Target t.pair ∧ IsStablePair t.pair ∧
  (t.pair.genus <= 2 ∨ homTateModel (compactHomologyIndex t.pair))

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
theorem ax13 : AX13 := fun _ h1 h2 h3 h4 => ⟨h1, h2, h3, h4⟩
theorem ax14 : AX14 := fun _ e h1 h2 h3 h4 h5 => ⟨rfl, h1, Or.inr (Or.inl ⟨h2, e, h3, h4, h5⟩)⟩
theorem ax15 : AX15 := fun _ c h1 h2 h3 h4 h5 h6 h7 h8 =>
  ⟨rfl, h1, Or.inr (Or.inr ⟨h2, h3, h4, h5, h7, c, h6, h8⟩)⟩
theorem ax16 : AX16 := fun _ h1 h2 h3 h4 h5 => ⟨h1, h2, h3, h4, h5⟩
theorem ax17 : AX17 := fun _ h1 h2 => Or.inr ⟨rfl, h1, h2⟩
theorem ax18 : AX18 := fun _ h => Or.inl h
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
theorem ax12 : AX12 := fun _ h => h.elim
theorem ax19 : AX19 := fun _ hs hg => ⟨rfl, hs, Or.inl hg⟩
theorem ax34 : AX34 := fun _ hh hd => ⟨rfl, hd.2.1, Or.inr hh⟩

def stable78 : StablePairIndex := { genus := 7, markings := 8 }
theorem stable78Stable : IsStablePair stable78 := (by decide : (3 : Nat) <= 2 * 7 + 8)

theorem attack2_models_all_but_ax11 :
    AX01 ∧ AX02 ∧ AX03 ∧ AX04 ∧ AX05 ∧ AX06 ∧ AX07 ∧ AX08 ∧ AX09 ∧ AX10 ∧
    AX12 ∧ AX13 ∧ AX14 ∧ AX15 ∧ AX16 ∧ AX17 ∧ AX18 ∧ AX19 ∧ AX20 ∧
    AX21 ∧ AX22 ∧ AX23 ∧ AX24 ∧ AX25 ∧ AX26 ∧ AX27 ∧ AX28 ∧ AX29 ∧ AX30 ∧
    AX31 ∧ AX32 ∧ AX33 ∧ AX34 :=
  ⟨ax01,ax02,ax03,ax04,ax05,ax06,ax07,ax08,ax09,ax10,
   ax12,ax13,ax14,ax15,ax16,ax17,ax18,ax19,ax20,
   ax21,ax22,ax23,ax24,ax25,ax26,ax27,ax28,ax29,ax30,
   ax31,ax32,ax33,ax34⟩

theorem attack2_refutes_ax11 : ¬ AX11 := by
  intro h
  exact (h stable78 stable78Stable (by decide) (by decide)).elim

theorem attack2_target_fails_at_78 :
    ¬ CompactH16IsFiniteTateSum (compactH16Target stable78) := by
  rintro ⟨_, _, (hg | hh)⟩
  · exact absurd hg (by decide)
  · obtain ⟨s, b, o, _, hsh, hso, hr, _, _, ho, _⟩ := hh.1
    have hsp : s.pair = stable78 := by
      have hn := congrArg CompactHomologyIndex.pair hr.2.2.1
      have hn2 : s.compact.pair = s.pair := by
        simpa [normalizedCompactIndex, compactHomologyIndex] using hn
      rw [hsh] at hn2
      exact hn2.symm
    have hopair : o.pair = stable78 := by
      have heq : o = openBMIndex s.pair := hso.symm.trans hr.2.2.2.1
      exact (congrArg OpenBMIndex.pair heq).trans hsp
    rcases ho with hz | hlow
    · rcases hz.2.2 with hw | ⟨hline, _, _, _, _⟩ | hb
      · exact hw.elim
      · rw [hopair] at hline; exact absurd hline (by decide)
      · rw [hopair] at hb; exact absurd hb.2.2.2.1 (by decide)
    · rw [hopair] at hlow; exact absurd hlow.2.1.2.2.2.1 (by decide)

#print axioms attack2_models_all_but_ax11
#print axioms attack2_refutes_ax11
#print axioms attack2_target_fails_at_78
