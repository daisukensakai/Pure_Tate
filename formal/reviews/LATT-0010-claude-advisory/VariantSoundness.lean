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

-- Each route-deletion variant must be exactly openTateModel MINUS one disjunct.
-- Direction 1: every variant is WEAKER than the full predicate (no smuggled extra route).
theorem noCritical_weaker (i : OpenBMIndex) :
    openTateWithoutCriticalModel i -> openTateModel i := by
  rintro (⟨he, hs, hw | hb⟩ | hp)
  · exact Or.inl ⟨he, hs, Or.inl hw⟩
  · exact Or.inl ⟨he, hs, Or.inr (Or.inr hb)⟩
  · exact Or.inr hp

theorem noBFP_weaker (i : OpenBMIndex) :
    openTateWithoutBFPModel i -> openTateModel i := by
  rintro (⟨he, hs, hc | hb⟩ | hp)
  · exact Or.inl ⟨he, hs, Or.inr (Or.inl hc)⟩
  · exact Or.inl ⟨he, hs, Or.inr (Or.inr hb)⟩
  · exact Or.inr hp

theorem noBelowLine_weaker (i : OpenBMIndex) :
    openTateWithoutBelowLineModel i -> openTateModel i := by
  rintro (⟨he, hs, hw | hc⟩ | hp)
  · exact Or.inl ⟨he, hs, Or.inl hw⟩
  · exact Or.inl ⟨he, hs, Or.inr (Or.inl hc)⟩
  · exact Or.inr hp

theorem noPublished_weaker (i : OpenBMIndex) :
    openTateWithoutPublishedModel i -> openTateModel i := Or.inl

-- Direction 2: adding the deleted disjunct back recovers the full predicate exactly.
theorem critical_restores (i : OpenBMIndex) :
    openTateModel i ->
    openTateWithoutCriticalModel i ∨
      (i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
        2 * i.pair.genus + i.pair.markings = 18 ∧
        exists e : CriticalEndpointIndex,
          e.pair.genus = i.pair.genus ∧ e.pair.markings = i.pair.markings ∧
          criticalVanishModel e) := by
  rintro (⟨he, hs, hw | ⟨hl, e, hg, hm, hcv⟩ | hb⟩ | hp)
  · exact Or.inl (Or.inl ⟨he, hs, Or.inl hw⟩)
  · exact Or.inr ⟨he, hs, hl, e, hg, hm, hcv⟩
  · exact Or.inl (Or.inl ⟨he, hs, Or.inr hb⟩)
  · exact Or.inl (Or.inr hp)

theorem bfp_restores (i : OpenBMIndex) :
    openTateModel i ->
    openTateWithoutBFPModel i ∨
      (i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
        wholeOpenVanishModel (wholeOpenBMIndex i.pair)) := by
  rintro (⟨he, hs, hw | hc | hb⟩ | hp)
  · exact Or.inr ⟨he, hs, hw⟩
  · exact Or.inl (Or.inl ⟨he, hs, Or.inl hc⟩)
  · exact Or.inl (Or.inl ⟨he, hs, Or.inr hb⟩)
  · exact Or.inl (Or.inr hp)

#print axioms noCritical_weaker
#print axioms noBFP_weaker
#print axioms noBelowLine_weaker
#print axioms noPublished_weaker
#print axioms critical_restores
#print axioms bfp_restores

