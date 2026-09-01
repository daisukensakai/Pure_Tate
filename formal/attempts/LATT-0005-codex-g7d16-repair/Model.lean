set_option autoImplicit false
-- LEAN-MODEL-WITNESS Concrete repaired model for every LATT-0005 campaign axiom
-- LEAN-NONCOLLAPSE Rejects target perturbations, whole-open-group confusion, at-vcd endpoints, missing zero range, reversed or shifted sequences, wrong kernel orientation, impure middle terms, same-complexity recursion, quotient-middle collapse, and open dimension-twisted duality
-- LEAN-MODELS CompactH16IsFiniteTateSum vocab genus_five_ckgp genus_five_tautological_chow genus_five_ionel_cohomological_vanishing genus_five_open_bm_conversion genus_five_endpoint_from_repaired_inputs published_open_range_control strict_primitive_vcd_at_critical_endpoint strict_phi_vcd_at_critical_endpoint inclusive_ckgp_endpoint ionel_kills_critical_psi_source critical_endpoint_vanishes_from_typed_inputs open_bm_vanishes_strong_range published_open_bm_tate_below_zero_range zero_open_bm_is_tate compact_base_genus_zero_one_two odd_compact_vanishing_through_nine even_compact_tate_through_fourteen boundary_factor_is_stable boundary_factor_genus_le_parent boundary_factor_complexity_decreases boundary_image_tate_from_one_edge_graphs boundary_sequence_right_exact boundary_image_is_kernel compact_homology_pure_polarizable semisimple_boundary_extension proper_same_degree_duality proper_duality_transfers_tate
-- LEAN-MODEL-THEOREM g7d16_repaired_model_is_consistent_and_materially_noncollapsing

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

def genusFiveCKgPModel : Prop := 5 = 5
def genusFiveChowModel : Prop := 8 = 8
def genusFiveIonelModel : Prop := 24 = 24
def genusFiveConversionModel : Prop := 16 + 8 = 24
def genusFiveEndpointModel : Prop :=
  genusFiveCKgPModel ∧ genusFiveChowModel ∧
  genusFiveIonelModel ∧ genusFiveConversionModel
def publishedRangeModel : Prop := 10 < 11

def strictPrimitiveModel (e : CriticalEndpointIndex) : Prop :=
  IsCriticalEndpoint e ∧ e.unpointedVcd < e.primitiveDegree

def strictPhiModel (e : CriticalEndpointIndex) : Prop :=
  IsCriticalEndpoint e ∧ e.smallerPointedVcd < e.ordinaryDegree

def inclusiveEndpointModel (e : CriticalEndpointIndex) : Prop :=
  IsCriticalEndpoint e ∧ e.pair.markings = e.ckgpMarkingEndpoint + 1

def ionelSourceModel (e : CriticalEndpointIndex) : Prop :=
  IsCriticalEndpoint e ∧ e.pair.genus <= e.ionelCodimension ∧ genusFiveIonelModel

def criticalVanishModel (e : CriticalEndpointIndex) : Prop :=
  IsCriticalEndpoint e ∧ strictPrimitiveModel e ∧ strictPhiModel e ∧
  inclusiveEndpointModel e ∧ ionelSourceModel e ∧
  (e.pair.genus = 5 -> genusFiveEndpointModel)

def allFiveEndpointsModel : Prop :=
  criticalVanishModel endpointG3 ∧ criticalVanishModel endpointG4 ∧
  criticalVanishModel endpointG5 ∧ criticalVanishModel endpointG6 ∧
  criticalVanishModel endpointG7

def openVanishModel (i : OpenBMIndex) : Prop :=
  i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
  3 <= i.pair.genus ∧ i.pair.genus <= 7 ∧
  11 <= 2 * i.pair.genus + i.pair.markings ∧ allFiveEndpointsModel

def openTateModel (i : OpenBMIndex) : Prop :=
  openVanishModel i ∨
  (i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
   3 <= i.pair.genus ∧ i.pair.genus <= 7 ∧
   2 * i.pair.genus + i.pair.markings < 11 ∧ publishedRangeModel)

def boundaryTateModel (i : BoundaryImageIndex) : Prop :=
  i = boundaryImageIndex i.pair ∧ IsStablePair i.pair ∧ i.pair.genus <= 7

def normalizedCompact (h : CompactHomologyIndex) : CompactHomologyIndex :=
  { h with purityKind := PurityKind.purePolarizable }

def rightExactModel (s : BoundarySequenceIndex) : Prop :=
  IsStablePair s.pair ∧
  s.boundary = boundaryImageIndex s.pair ∧
  normalizedCompact s.compact = compactHomologyIndex s.pair ∧
  s.openPart = openBMIndex s.pair ∧
  s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ∧
  s.degreeShift = 0 ∧ s.tateTwist = 0

def kernelModel (s : BoundarySequenceIndex) : Prop :=
  rightExactModel s ∧ s.kernelOrientation = KernelOrientation.boundaryImageIsKernel

def pureModel (h : CompactHomologyIndex) : Prop :=
  h = compactHomologyIndex h.pair ∧ IsStablePair h.pair ∧
  h.purityKind = PurityKind.purePolarizable

def homTateModel (h : CompactHomologyIndex) : Prop :=
  (exists (s : BoundarySequenceIndex) (b : BoundaryImageIndex) (o : OpenBMIndex),
    s.boundary = b ∧ s.compact = h ∧ s.openPart = o ∧
    rightExactModel s ∧ kernelModel s ∧ boundaryTateModel b ∧
    openTateModel o ∧ pureModel h) ∧
  h = compactHomologyIndex h.pair ∧ IsStablePair h.pair ∧ h.pair.genus <= 7

def dualityModel (d : ProperDualityIndex) : Prop :=
  d = properDualityIndex d.pair ∧ IsStablePair d.pair ∧
  (homTateModel d.homology -> d.pair.genus <= 7)

def modelVocabulary : G7D16VocabularyV2 where
  GenusFiveCKgP := genusFiveCKgPModel
  GenusFiveTautologicalChow := genusFiveChowModel
  GenusFiveIonelCohomologicalVanishing := genusFiveIonelModel
  GenusFiveOpenBMConversion := genusFiveConversionModel
  GenusFiveEndpointVanishing := genusFiveEndpointModel
  PublishedOpenRangeControl := publishedRangeModel
  StrictPrimitiveAboveUnpointedVCD := strictPrimitiveModel
  StrictPhiAboveSmallerPointedVCD := strictPhiModel
  InclusiveCKgPMarkingEndpoint := inclusiveEndpointModel
  IonelKillsPsiSource := ionelSourceModel
  CriticalEndpointVanishes := criticalVanishModel
  OpenBMVanishes := openVanishModel
  OpenBMIsFiniteTateSum := openTateModel
  OddCompactVanishingThroughNine := 9 < 10
  EvenCompactTateThroughFourteen := 14 <= 14
  OneEdgeBoundaryFactor := fun p q =>
    IsStablePair q ∧ q.genus <= p.genus ∧ PairComplexity q < PairComplexity p
  BoundaryImageIsFiniteTateSum := boundaryTateModel
  BoundarySequenceIsRightExact := rightExactModel
  BoundaryImageIsKernel := kernelModel
  CompactHomologyIsPurePolarizable := pureModel
  CompactHomologyIsFiniteTateSum := homTateModel
  ProperSameDegreeDuality := dualityModel

abbrev V := modelVocabulary

def CompactH16IsFiniteTateSum (t : CompactH16TargetIndex) : Prop :=
  t = compactH16Target t.pair ∧ IsStablePair t.pair ∧ t.pair.genus <= 7

def AX01 : Prop := V.GenusFiveCKgP
def AX02 : Prop := V.GenusFiveTautologicalChow
def AX03 : Prop := V.GenusFiveIonelCohomologicalVanishing
def AX04 : Prop := V.GenusFiveOpenBMConversion
def AX05 : Prop := V.GenusFiveCKgP -> V.GenusFiveTautologicalChow ->
  V.GenusFiveIonelCohomologicalVanishing -> V.GenusFiveOpenBMConversion ->
  V.GenusFiveEndpointVanishing
def AX06 : Prop := V.PublishedOpenRangeControl
def AX07 : Prop := forall e : CriticalEndpointIndex, IsCriticalEndpoint e ->
  e.unpointedVcd < e.primitiveDegree -> V.StrictPrimitiveAboveUnpointedVCD e
def AX08 : Prop := forall e : CriticalEndpointIndex, IsCriticalEndpoint e ->
  e.smallerPointedVcd < e.ordinaryDegree -> V.StrictPhiAboveSmallerPointedVCD e
def AX09 : Prop := forall e : CriticalEndpointIndex, IsCriticalEndpoint e ->
  e.pair.markings = e.ckgpMarkingEndpoint + 1 -> V.InclusiveCKgPMarkingEndpoint e
def AX10 : Prop := forall e : CriticalEndpointIndex, IsCriticalEndpoint e ->
  e.pair.genus <= e.ionelCodimension ->
  V.GenusFiveIonelCohomologicalVanishing -> V.IonelKillsPsiSource e
def AX11 : Prop := forall e : CriticalEndpointIndex, IsCriticalEndpoint e ->
  V.StrictPrimitiveAboveUnpointedVCD e ->
  V.StrictPhiAboveSmallerPointedVCD e ->
  V.InclusiveCKgPMarkingEndpoint e -> V.IonelKillsPsiSource e ->
  (e.pair.genus = 5 -> V.GenusFiveEndpointVanishing) ->
  V.CriticalEndpointVanishes e
def AX12 : Prop := forall p : StablePairIndex,
  IsStablePair p -> 3 <= p.genus -> p.genus <= 7 ->
  11 <= 2 * p.genus + p.markings ->
  V.CriticalEndpointVanishes endpointG3 ->
  V.CriticalEndpointVanishes endpointG4 ->
  V.CriticalEndpointVanishes endpointG5 ->
  V.CriticalEndpointVanishes endpointG6 ->
  V.CriticalEndpointVanishes endpointG7 ->
  V.OpenBMVanishes (openBMIndex p)
def AX13 : Prop := forall p : StablePairIndex,
  V.PublishedOpenRangeControl -> IsStablePair p ->
  3 <= p.genus -> p.genus <= 7 ->
  2 * p.genus + p.markings < 11 ->
  V.OpenBMIsFiniteTateSum (openBMIndex p)
def AX14 : Prop := forall i : OpenBMIndex,
  V.OpenBMVanishes i -> V.OpenBMIsFiniteTateSum i
def AX15 : Prop := forall p : StablePairIndex,
  IsStablePair p -> p.genus <= 2 -> CompactH16IsFiniteTateSum (compactH16Target p)
def AX16 : Prop := V.OddCompactVanishingThroughNine
def AX17 : Prop := V.EvenCompactTateThroughFourteen
def AX18 : Prop := forall p q : StablePairIndex, V.OneEdgeBoundaryFactor p q -> IsStablePair q
def AX19 : Prop := forall p q : StablePairIndex, V.OneEdgeBoundaryFactor p q -> q.genus <= p.genus
def AX20 : Prop := forall p q : StablePairIndex, V.OneEdgeBoundaryFactor p q ->
  PairComplexity q < PairComplexity p
def AX21 : Prop := forall p : StablePairIndex, IsStablePair p -> p.genus <= 7 ->
  V.OddCompactVanishingThroughNine -> V.EvenCompactTateThroughFourteen ->
  (forall q : StablePairIndex, V.OneEdgeBoundaryFactor p q ->
    CompactH16IsFiniteTateSum (compactH16Target q)) ->
  V.BoundaryImageIsFiniteTateSum (boundaryImageIndex p)
def AX22 : Prop := forall s : BoundarySequenceIndex,
  IsStablePair s.pair -> s.boundary = boundaryImageIndex s.pair ->
  s.compact = compactHomologyIndex s.pair -> s.openPart = openBMIndex s.pair ->
  s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ->
  s.degreeShift = 0 -> s.tateTwist = 0 -> V.BoundarySequenceIsRightExact s
def AX23 : Prop := forall p : StablePairIndex,
  V.BoundarySequenceIsRightExact (boundarySequenceIndex p) ->
  (boundarySequenceIndex p).kernelOrientation = KernelOrientation.boundaryImageIsKernel ->
  V.BoundaryImageIsKernel (boundarySequenceIndex p)
def AX24 : Prop := forall p : StablePairIndex, IsStablePair p ->
  (compactHomologyIndex p).purityKind = PurityKind.purePolarizable ->
  V.CompactHomologyIsPurePolarizable (compactHomologyIndex p)
def AX25 : Prop := forall (s : BoundarySequenceIndex) (b : BoundaryImageIndex)
  (o : OpenBMIndex) (h : CompactHomologyIndex),
  s.boundary = b -> s.compact = h -> s.openPart = o ->
  V.BoundarySequenceIsRightExact s -> V.BoundaryImageIsKernel s ->
  V.BoundaryImageIsFiniteTateSum b -> V.OpenBMIsFiniteTateSum o ->
  V.CompactHomologyIsPurePolarizable h -> V.CompactHomologyIsFiniteTateSum h
def AX26 : Prop := forall p : StablePairIndex, IsStablePair p ->
  V.ProperSameDegreeDuality (properDualityIndex p)
def AX27 : Prop := forall p : StablePairIndex,
  V.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) ->
  V.ProperSameDegreeDuality (properDualityIndex p) ->
  CompactH16IsFiniteTateSum (compactH16Target p)

theorem ax01 : AX01 := by dsimp [AX01, V, modelVocabulary, genusFiveCKgPModel]
theorem ax02 : AX02 := by dsimp [AX02, V, modelVocabulary, genusFiveChowModel]
theorem ax03 : AX03 := by dsimp [AX03, V, modelVocabulary, genusFiveIonelModel]
theorem ax04 : AX04 := by dsimp [AX04, V, modelVocabulary, genusFiveConversionModel]
theorem ax05 : AX05 := by intro h1 h2 h3 h4; exact ⟨h1,h2,h3,h4⟩
theorem ax06 : AX06 := by dsimp [AX06, V, modelVocabulary, publishedRangeModel]; decide
theorem ax07 : AX07 := by intro e he h; exact ⟨he,h⟩
theorem ax08 : AX08 := by intro e he h; exact ⟨he,h⟩
theorem ax09 : AX09 := by intro e he h; exact ⟨he,h⟩
theorem ax10 : AX10 := by intro e he h hi; exact ⟨he,h,hi⟩
theorem ax11 : AX11 := by
  intro e he hp hf hc hi hg5
  exact ⟨he,hp,hf,hc,hi,hg5⟩
theorem ax12 : AX12 := by
  intro p hs hg3 hg7 hz h3 h4 h5 h6 h7
  exact ⟨rfl,hs,hg3,hg7,hz,h3,h4,h5,h6,h7⟩
theorem ax13 : AX13 := by
  intro p hp hs hg3 hg7 hlt
  right
  exact ⟨rfl,hs,hg3,hg7,hlt,hp⟩
theorem ax14 : AX14 := by intro i h; exact Or.inl h
theorem ax15 : AX15 := by
  intro p hs hg
  dsimp [CompactH16IsFiniteTateSum, compactH16Target]
  exact ⟨rfl,hs,by omega⟩
theorem ax16 : AX16 := by dsimp [AX16, V, modelVocabulary]; decide
theorem ax17 : AX17 := by dsimp [AX17, V, modelVocabulary]; decide
theorem ax18 : AX18 := by intro _ _ h; exact h.1
theorem ax19 : AX19 := by intro _ _ h; exact h.2.1
theorem ax20 : AX20 := by intro _ _ h; exact h.2.2
theorem ax21 : AX21 := by intro p hs hg _ _ _; exact ⟨rfl,hs,hg⟩
theorem ax22 : AX22 := by
  intro s hs hb hh ho hor hd ht
  exact ⟨hs,hb,(by rw [hh]; rfl),ho,hor,hd,ht⟩
theorem ax23 : AX23 := by
  intro p hr hk
  exact ⟨hr,hk⟩
theorem ax24 : AX24 := by
  intro p hs hp
  exact ⟨rfl,hs,hp⟩
theorem ax25 : AX25 := by
  intro s b o h hsb hsh hso hr hk hb ho hp
  have hhexact : h = compactHomologyIndex h.pair := hp.1
  have hhstable : IsStablePair h.pair := hp.2.1
  have hgenus : h.pair.genus <= 7 := by
    have hbgenus : b.pair.genus <= 7 := hb.2.2
    have hbp : b.pair = s.pair := by
      rw [← hsb, hr.2.1]
      rfl
    have hhp : h.pair = s.pair := by
      have hn := congrArg CompactHomologyIndex.pair hr.2.2.1
      have hn' : s.compact.pair = s.pair := by
        simpa [normalizedCompact, compactHomologyIndex] using hn
      rw [hsh] at hn'
      exact hn'
    rw [hbp] at hbgenus
    rw [hhp]
    exact hbgenus
  exact ⟨⟨s,b,o,hsb,hsh,hso,hr,hk,hb,ho,hp⟩,hhexact,hhstable,hgenus⟩
theorem ax26 : AX26 := by
  intro p hs
  exact ⟨rfl,hs,fun hh => hh.2.2.2⟩
theorem ax27 : AX27 := by
  intro p hh hd
  exact ⟨rfl,hd.2.1,hd.2.2 hh⟩

def stable66 : StablePairIndex := { genus := 6, markings := 6 }
def stable78 : StablePairIndex := { genus := 7, markings := 8 }
def stable30 : StablePairIndex := { genus := 3, markings := 0 }
def stable20 : StablePairIndex := { genus := 2, markings := 0 }
def genusEight : StablePairIndex := { genus := 8, markings := 0 }
def unstable10 : StablePairIndex := { genus := 1, markings := 0 }

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

def wholeOpenBM : OpenBMIndex :=
  { openBMIndex stable66 with objectKind := CohomologyObjectKind.wholeGroup }
def atPrimitiveVcd : CriticalEndpointIndex :=
  { endpointG6 with unpointedVcd := 20 }
def atSmallerPointedVcd : CriticalEndpointIndex :=
  { endpointG6 with smallerPointedVcd := 26 }
def nonInclusiveEndpoint : CriticalEndpointIndex :=
  { endpointG6 with ckgpMarkingEndpoint := 4 }

def reversedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with orientation := ExactSequenceOrientation.openToCompactToBoundary }
def shiftedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with degreeShift := 1 }
def twistedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with tateTwist := 1 }
def wrongKernelSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with kernelOrientation := KernelOrientation.compactHomologyIsKernel }

def impureHomology : CompactHomologyIndex :=
  { compactHomologyIndex stable66 with purityKind := PurityKind.impure }
def impureSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with compact := impureHomology }

def ambientTwistedDuality : ProperDualityIndex :=
  { properDualityIndex stable66 with ambientDimensionTwist := 21 }
def openPoincareDuality : ProperDualityIndex :=
  { properDualityIndex stable66 with kind := DualityKind.openPoincareDimensionTwist }

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
def NC13 : Prop := ¬ V.OpenBMIsFiniteTateSum wholeOpenBM
def NC14 : Prop := ¬ V.StrictPrimitiveAboveUnpointedVCD atPrimitiveVcd
def NC15 : Prop := ¬ V.StrictPhiAboveSmallerPointedVCD atSmallerPointedVcd
def NC16 : Prop := ¬ V.InclusiveCKgPMarkingEndpoint nonInclusiveEndpoint
def NC17 : Prop := V.OpenBMVanishes (openBMIndex stable66)
def NC18 : Prop := V.OpenBMIsFiniteTateSum (openBMIndex stable30) ∧
  ¬ V.OpenBMVanishes (openBMIndex stable30)
def NC19 : Prop := ¬ V.BoundarySequenceIsRightExact reversedSequence
def NC20 : Prop := ¬ V.BoundarySequenceIsRightExact shiftedSequence
def NC21 : Prop := ¬ V.BoundarySequenceIsRightExact twistedSequence
def NC22 : Prop := V.BoundarySequenceIsRightExact wrongKernelSequence ∧
  ¬ V.BoundaryImageIsKernel wrongKernelSequence
def NC23 : Prop := V.BoundarySequenceIsRightExact impureSequence ∧
  V.BoundaryImageIsKernel impureSequence ∧
  V.BoundaryImageIsFiniteTateSum impureSequence.boundary ∧
  V.OpenBMIsFiniteTateSum impureSequence.openPart ∧
  ¬ V.CompactHomologyIsPurePolarizable impureHomology
def NC24 : Prop := ¬ V.OneEdgeBoundaryFactor stable66 stable66
def NC25 : Prop := V.BoundaryImageIsFiniteTateSum (boundaryImageIndex stable20) ∧
  ¬ V.CompactHomologyIsFiniteTateSum (compactHomologyIndex stable20)
def NC26 : Prop := ¬ V.ProperSameDegreeDuality ambientTwistedDuality
def NC27 : Prop := ¬ V.ProperSameDegreeDuality openPoincareDuality

theorem nc01 : NC01 := by dsimp [NC01, CompactH16IsFiniteTateSum, compactH16Target, stable66, IsStablePair]; decide
theorem nc02 : NC02 := by dsimp [NC02, CompactH16IsFiniteTateSum, compactH16Target, stable78, IsStablePair]; decide
theorem nc03 : NC03 := by simp [NC03, CompactH16IsFiniteTateSum, wrongOpenTarget, compactH16Target, stable66]
theorem nc04 : NC04 := by simp [NC04, CompactH16IsFiniteTateSum, wrongCoarseTarget, compactH16Target, stable66]
theorem nc05 : NC05 := by simp [NC05, CompactH16IsFiniteTateSum, wrongIntegralTarget, compactH16Target, stable66]
theorem nc06 : NC06 := by simp [NC06, CompactH16IsFiniteTateSum, wrongUnorderedTarget, compactH16Target, stable66]
theorem nc07 : NC07 := by dsimp [NC07, CompactH16IsFiniteTateSum, compactH16Target, genusEight, IsStablePair]; decide
theorem nc08 : NC08 := by dsimp [NC08, CompactH16IsFiniteTateSum, compactH16Target, unstable10, IsStablePair]; decide
theorem nc09 : NC09 := by simp [NC09, CompactH16IsFiniteTateSum, wrongDegreeTarget, compactH16Target, stable66]
theorem nc10 : NC10 := by simp [NC10, CompactH16IsFiniteTateSum, wrongWeightTarget, compactH16Target, stable66]
theorem nc11 : NC11 := by simp [NC11, CompactH16IsFiniteTateSum, wrongTateTarget, compactH16Target, stable66]
theorem nc12 : NC12 := by simp [NC12, CompactH16IsFiniteTateSum, quotientTarget, compactH16Target, stable66]
theorem nc13 : NC13 := by simp [NC13, V, modelVocabulary, openTateModel, openVanishModel, wholeOpenBM, openBMIndex]
theorem nc14 : NC14 := by simp [NC14, V, modelVocabulary, strictPrimitiveModel, atPrimitiveVcd, endpointG6, IsCriticalEndpoint]
theorem nc15 : NC15 := by simp [NC15, V, modelVocabulary, strictPhiModel, atSmallerPointedVcd, endpointG6, IsCriticalEndpoint]
theorem nc16 : NC16 := by simp [NC16, V, modelVocabulary, inclusiveEndpointModel, nonInclusiveEndpoint, endpointG6, IsCriticalEndpoint]
theorem nc17 : NC17 := by
  simp [NC17, V, modelVocabulary, openVanishModel, stable66, openBMIndex,
    IsStablePair, allFiveEndpointsModel, criticalVanishModel, strictPrimitiveModel,
    strictPhiModel, inclusiveEndpointModel, ionelSourceModel, genusFiveEndpointModel,
    genusFiveCKgPModel, genusFiveChowModel, genusFiveIonelModel,
    genusFiveConversionModel, IsCriticalEndpoint, endpointG3, endpointG4,
    endpointG5, endpointG6, endpointG7]
theorem nc18 : NC18 := by
  constructor
  · right
    dsimp [V, modelVocabulary, openTateModel, stable30, openBMIndex,
      IsStablePair, publishedRangeModel]
    decide
  · intro h
    have hz := h.2.2.2.2.1
    dsimp [stable30, openBMIndex] at hz
    omega
theorem nc19 : NC19 := by simp [NC19, V, modelVocabulary, rightExactModel, normalizedCompact, reversedSequence, boundarySequenceIndex]
theorem nc20 : NC20 := by simp [NC20, V, modelVocabulary, rightExactModel, normalizedCompact, shiftedSequence, boundarySequenceIndex]
theorem nc21 : NC21 := by simp [NC21, V, modelVocabulary, rightExactModel, normalizedCompact, twistedSequence, boundarySequenceIndex]
theorem nc22 : NC22 := by
  constructor
  · dsimp [V, modelVocabulary, rightExactModel, normalizedCompact,
      wrongKernelSequence, boundarySequenceIndex, stable66, IsStablePair]
    decide
  · simp [V, modelVocabulary, kernelModel, wrongKernelSequence, boundarySequenceIndex]
theorem nc23 : NC23 := by
  have hr : V.BoundarySequenceIsRightExact impureSequence := by
    dsimp [V, modelVocabulary, rightExactModel, normalizedCompact,
      impureSequence, impureHomology, boundarySequenceIndex, compactHomologyIndex,
      stable66, IsStablePair]
    decide
  have hk : V.BoundaryImageIsKernel impureSequence := ⟨hr,rfl⟩
  exact ⟨hr,hk,⟨rfl,(by dsimp [impureSequence, boundarySequenceIndex,
      boundaryImageIndex, IsStablePair, stable66]; omega),(by decide)⟩,
    Or.inl nc17,
    (by simp [V, modelVocabulary, pureModel, impureHomology, compactHomologyIndex])⟩
theorem nc24 : NC24 := by dsimp [NC24, V, modelVocabulary, PairComplexity]; omega
theorem nc25 : NC25 := by
  constructor
  · exact ⟨rfl,(by dsimp [IsStablePair, stable20, boundaryImageIndex]; omega),(by decide)⟩
  · intro h
    rcases h.1 with ⟨s,b,o,hsb,hsh,hso,hr,hk,hb,ho,hp⟩
    have hsp : s.pair = stable20 := by
      have heq : normalizedCompact (compactHomologyIndex stable20) =
          compactHomologyIndex s.pair := by
        rw [← hsh]
        exact hr.2.2.1
      simpa [normalizedCompact, compactHomologyIndex] using
        (congrArg CompactHomologyIndex.pair heq).symm
    have hopair : o.pair = stable20 := by
      have heq : o = openBMIndex s.pair := hso.symm.trans hr.2.2.2.1
      exact (congrArg OpenBMIndex.pair heq).trans hsp
    rcases ho with hz | hlow
    · have hg3 := hz.2.2.1
      rw [hopair] at hg3
      dsimp [stable20] at hg3
      omega
    · have hg3 := hlow.2.2.1
      rw [hopair] at hg3
      dsimp [stable20] at hg3
      omega
theorem nc26 : NC26 := by simp [NC26, V, modelVocabulary, dualityModel, ambientTwistedDuality, properDualityIndex, stable66]
theorem nc27 : NC27 := by simp [NC27, V, modelVocabulary, dualityModel, openPoincareDuality, properDualityIndex, stable66]

theorem g7d16_repaired_model_is_consistent_and_materially_noncollapsing :
    AX01 ∧ AX02 ∧ AX03 ∧ AX04 ∧ AX05 ∧ AX06 ∧ AX07 ∧ AX08 ∧ AX09 ∧
    AX10 ∧ AX11 ∧ AX12 ∧ AX13 ∧ AX14 ∧ AX15 ∧ AX16 ∧ AX17 ∧ AX18 ∧
    AX19 ∧ AX20 ∧ AX21 ∧ AX22 ∧ AX23 ∧ AX24 ∧ AX25 ∧ AX26 ∧ AX27 ∧
    NC01 ∧ NC02 ∧ NC03 ∧ NC04 ∧ NC05 ∧ NC06 ∧ NC07 ∧ NC08 ∧ NC09 ∧
    NC10 ∧ NC11 ∧ NC12 ∧ NC13 ∧ NC14 ∧ NC15 ∧ NC16 ∧ NC17 ∧ NC18 ∧
    NC19 ∧ NC20 ∧ NC21 ∧ NC22 ∧ NC23 ∧ NC24 ∧ NC25 ∧ NC26 ∧ NC27 :=
  ⟨ax01,ax02,ax03,ax04,ax05,ax06,ax07,ax08,ax09,ax10,ax11,ax12,ax13,ax14,
   ax15,ax16,ax17,ax18,ax19,ax20,ax21,ax22,ax23,ax24,ax25,ax26,ax27,
   nc01,nc02,nc03,nc04,nc05,nc06,nc07,nc08,nc09,nc10,nc11,nc12,nc13,nc14,
   nc15,nc16,nc17,nc18,nc19,nc20,nc21,nc22,nc23,nc24,nc25,nc26,nc27⟩

#print axioms g7d16_repaired_model_is_consistent_and_materially_noncollapsing
