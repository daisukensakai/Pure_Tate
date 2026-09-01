set_option autoImplicit false
-- LEAN-MODEL-WITNESS Concrete arithmetic-and-index model for every campaign axiom
-- LEAN-NONCOLLAPSE Rejects wrong geometry, coefficients, markings, stability, genus bound, degree, weight, Tate sign, object proxy, sequence orientation, shift, twist, same-complexity factors, and quotient-equals-middle collapse
-- LEAN-MODELS CompactH16IsFiniteTateSum vocab liu_repaired_genus_five_input ionel_looijenga_vanishing critical_endpoint_vanishings published_open_range_control open_bm_tate_genus_le_seven compact_base_genus_zero_one_two odd_compact_vanishing_through_nine even_compact_tate_through_fourteen boundary_factor_is_stable boundary_factor_genus_le_parent boundary_factor_complexity_decreases boundary_image_tate_from_one_edge_graphs boundary_sequence_right_exact boundary_image_is_kernel compact_homology_pure_polarizable semisimple_boundary_extension proper_same_degree_duality proper_duality_transfers_tate
-- LEAN-MODEL-THEOREM g7d16_model_is_consistent_and_materially_noncollapsing

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

def repairedInputModel : Prop := 5 + 8 = 13
def ionelModel : Prop := 6 + 6 = 12
def criticalModel : Prop := repairedInputModel ∧ ionelModel
def publishedModel : Prop := 7 <= 7

def openTateModel (i : OpenBMIndex) : Prop :=
  i = openBMIndex i.pair ∧ IsStablePair i.pair ∧
  3 <= i.pair.genus ∧ i.pair.genus <= 7 ∧
  repairedInputModel ∧ ionelModel ∧ criticalModel ∧ publishedModel

def boundaryTateModel (i : BoundaryImageIndex) : Prop :=
  i = boundaryImageIndex i.pair ∧ IsStablePair i.pair ∧ i.pair.genus <= 7

def rightExactModel (s : BoundarySequenceIndex) : Prop :=
  IsStablePair s.pair ∧
  s.boundary = boundaryImageIndex s.pair ∧
  s.compact = compactHomologyIndex s.pair ∧
  s.openPart = openBMIndex s.pair ∧
  s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ∧
  s.degreeShift = 0 ∧ s.tateTwist = 0

def kernelModel (s : BoundarySequenceIndex) : Prop :=
  rightExactModel s ∧
  s.boundary.objectKind = CohomologyObjectKind.image ∧
  s.compact.objectKind = CohomologyObjectKind.wholeGroup ∧
  s.openPart.objectKind = CohomologyObjectKind.wholeGroup

def pureModel (h : CompactHomologyIndex) : Prop :=
  h = compactHomologyIndex h.pair ∧ IsStablePair h.pair

def homTateModel (h : CompactHomologyIndex) : Prop :=
  (exists (s : BoundarySequenceIndex) (b : BoundaryImageIndex) (o : OpenBMIndex),
    s.boundary = b ∧ s.compact = h ∧ s.openPart = o ∧
    rightExactModel s ∧ kernelModel s ∧ boundaryTateModel b ∧
    openTateModel o ∧ pureModel h) ∧
  h = compactHomologyIndex h.pair ∧ IsStablePair h.pair ∧ h.pair.genus <= 7

def dualityModel (d : ProperDualityIndex) : Prop :=
  d = properDualityIndex d.pair ∧ IsStablePair d.pair ∧
  (homTateModel d.homology -> d.pair.genus <= 7)

def modelVocabulary : G7D16Vocabulary where
  RepairedGenusFiveInput := repairedInputModel
  IonelLooijengaVanishing := ionelModel
  CriticalEndpointVanishings := criticalModel
  PublishedOpenRangeControl := publishedModel
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

def AX01 : Prop := V.RepairedGenusFiveInput
def AX02 : Prop := V.IonelLooijengaVanishing
def AX03 : Prop := V.RepairedGenusFiveInput -> V.IonelLooijengaVanishing -> V.CriticalEndpointVanishings
def AX04 : Prop := V.PublishedOpenRangeControl
def AX05 : Prop := forall p : StablePairIndex,
  V.RepairedGenusFiveInput -> V.IonelLooijengaVanishing ->
  V.CriticalEndpointVanishings -> V.PublishedOpenRangeControl ->
  IsStablePair p -> 3 <= p.genus -> p.genus <= 7 -> V.OpenBMIsFiniteTateSum (openBMIndex p)
def AX06 : Prop := forall p : StablePairIndex,
  IsStablePair p -> p.genus <= 2 -> CompactH16IsFiniteTateSum (compactH16Target p)
def AX07 : Prop := V.OddCompactVanishingThroughNine
def AX08 : Prop := V.EvenCompactTateThroughFourteen
def AX09 : Prop := forall p q : StablePairIndex, V.OneEdgeBoundaryFactor p q -> IsStablePair q
def AX10 : Prop := forall p q : StablePairIndex, V.OneEdgeBoundaryFactor p q -> q.genus <= p.genus
def AX11 : Prop := forall p q : StablePairIndex, V.OneEdgeBoundaryFactor p q -> PairComplexity q < PairComplexity p
def AX12 : Prop := forall p : StablePairIndex,
  IsStablePair p -> p.genus <= 7 -> V.OddCompactVanishingThroughNine ->
  V.EvenCompactTateThroughFourteen ->
  (forall q : StablePairIndex, V.OneEdgeBoundaryFactor p q ->
    CompactH16IsFiniteTateSum (compactH16Target q)) ->
  V.BoundaryImageIsFiniteTateSum (boundaryImageIndex p)
def AX13 : Prop := forall s : BoundarySequenceIndex,
  IsStablePair s.pair -> s.boundary = boundaryImageIndex s.pair ->
  s.compact = compactHomologyIndex s.pair -> s.openPart = openBMIndex s.pair ->
  s.orientation = ExactSequenceOrientation.boundaryToCompactToOpen ->
  s.degreeShift = 0 -> s.tateTwist = 0 -> V.BoundarySequenceIsRightExact s
def AX14 : Prop := forall p : StablePairIndex,
  V.BoundarySequenceIsRightExact (boundarySequenceIndex p) ->
  V.BoundaryImageIsKernel (boundarySequenceIndex p)
def AX15 : Prop := forall p : StablePairIndex,
  IsStablePair p -> V.CompactHomologyIsPurePolarizable (compactHomologyIndex p)
def AX16 : Prop := forall (s : BoundarySequenceIndex) (b : BoundaryImageIndex)
  (o : OpenBMIndex) (h : CompactHomologyIndex),
  s.boundary = b -> s.compact = h -> s.openPart = o ->
  V.BoundarySequenceIsRightExact s -> V.BoundaryImageIsKernel s ->
  V.BoundaryImageIsFiniteTateSum b -> V.OpenBMIsFiniteTateSum o ->
  V.CompactHomologyIsPurePolarizable h -> V.CompactHomologyIsFiniteTateSum h
def AX17 : Prop := forall p : StablePairIndex,
  IsStablePair p -> V.ProperSameDegreeDuality (properDualityIndex p)
def AX18 : Prop := forall p : StablePairIndex,
  V.CompactHomologyIsFiniteTateSum (compactHomologyIndex p) ->
  V.ProperSameDegreeDuality (properDualityIndex p) ->
  CompactH16IsFiniteTateSum (compactH16Target p)

theorem ax01 : AX01 := by dsimp [AX01, V, modelVocabulary, repairedInputModel]
theorem ax02 : AX02 := by dsimp [AX02, V, modelVocabulary, ionelModel]
theorem ax03 : AX03 := by intro h1 h2; exact ⟨h1,h2⟩
theorem ax04 : AX04 := by dsimp [AX04, V, modelVocabulary, publishedModel]; decide
theorem ax05 : AX05 := by
  intro p hr hi hc hp hs hg3 hg7
  exact ⟨rfl,hs,hg3,hg7,hr,hi,hc,hp⟩
theorem ax06 : AX06 := by
  intro p hs hg
  dsimp [CompactH16IsFiniteTateSum, compactH16Target]
  exact ⟨rfl,hs,by omega⟩
theorem ax07 : AX07 := by dsimp [AX07, V, modelVocabulary]; decide
theorem ax08 : AX08 := by dsimp [AX08, V, modelVocabulary]; decide
theorem ax09 : AX09 := by intro _ _ h; exact h.1
theorem ax10 : AX10 := by intro _ _ h; exact h.2.1
theorem ax11 : AX11 := by intro _ _ h; exact h.2.2
theorem ax12 : AX12 := by
  intro p hs hg _ _ _
  exact ⟨rfl,hs,hg⟩
theorem ax13 : AX13 := by
  intro s hs hb hh ho hor hd ht
  exact ⟨hs,hb,hh,ho,hor,hd,ht⟩
theorem ax14 : AX14 := by
  intro p hr
  exact ⟨hr,rfl,rfl,rfl⟩
theorem ax15 : AX15 := by intro p hs; exact ⟨rfl,hs⟩
theorem ax16 : AX16 := by
  intro s b o h hsb hsh hso hr hk hb ho hp
  have hhexact : h = compactHomologyIndex h.pair := hp.1
  have hhstable : IsStablePair h.pair := hp.2
  have hgenus : h.pair.genus <= 7 := by
    have hbgenus : b.pair.genus <= 7 := hb.2.2
    have hbp : b.pair = s.pair := by
      rw [← hsb, hr.2.1]
      rfl
    have hhp : h.pair = s.pair := by
      rw [← hsh, hr.2.2.1]
      rfl
    rw [hbp] at hbgenus
    rw [hhp]
    exact hbgenus
  exact ⟨⟨s,b,o,hsb,hsh,hso,hr,hk,hb,ho,hp⟩,hhexact,hhstable,hgenus⟩
theorem ax17 : AX17 := by
  intro p hs
  exact ⟨rfl,hs,fun hh => hh.2.2.2⟩
theorem ax18 : AX18 := by
  intro p hh hd
  exact ⟨rfl,hd.2.1,hd.2.2 hh⟩

def stable66 : StablePairIndex := { genus := 6, markings := 6 }
def stable78 : StablePairIndex := { genus := 7, markings := 8 }
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

def reversedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with orientation := ExactSequenceOrientation.openToCompactToBoundary }
def shiftedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with degreeShift := 1 }
def twistedSequence : BoundarySequenceIndex :=
  { boundarySequenceIndex stable66 with tateTwist := 1 }
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
def NC13 : Prop := ¬ V.BoundarySequenceIsRightExact reversedSequence
def NC14 : Prop := ¬ V.BoundarySequenceIsRightExact shiftedSequence
def NC15 : Prop := ¬ V.BoundarySequenceIsRightExact twistedSequence
def NC16 : Prop := ¬ V.OneEdgeBoundaryFactor stable66 stable66
def NC17 : Prop := V.BoundaryImageIsFiniteTateSum (boundaryImageIndex stable20) ∧
  ¬ V.CompactHomologyIsFiniteTateSum (compactHomologyIndex stable20)
def NC18 : Prop := ¬ V.ProperSameDegreeDuality ambientTwistedDuality
def NC19 : Prop := ¬ V.ProperSameDegreeDuality openPoincareDuality

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
theorem nc13 : NC13 := by simp [NC13, V, modelVocabulary, rightExactModel, reversedSequence, boundarySequenceIndex]
theorem nc14 : NC14 := by simp [NC14, V, modelVocabulary, rightExactModel, shiftedSequence, boundarySequenceIndex]
theorem nc15 : NC15 := by simp [NC15, V, modelVocabulary, rightExactModel, twistedSequence, boundarySequenceIndex]
theorem nc16 : NC16 := by dsimp [NC16, V, modelVocabulary, PairComplexity]; omega
theorem nc17 : NC17 := by
  constructor
  · exact ⟨rfl,(by dsimp [IsStablePair, stable20, boundaryImageIndex]; omega),(by decide)⟩
  · intro h
    rcases h.1 with ⟨s,b,o,hsb,hsh,hso,hr,hk,hb,ho,hp⟩
    have hsp : s.pair = stable20 := by
      have heq : compactHomologyIndex stable20 = compactHomologyIndex s.pair :=
        hsh.symm.trans hr.2.2.1
      exact (congrArg CompactHomologyIndex.pair heq).symm
    have hopair : o.pair = stable20 := by
      have heq : o = openBMIndex s.pair := hso.symm.trans hr.2.2.2.1
      have hp : o.pair = s.pair := congrArg OpenBMIndex.pair heq
      exact hp.trans hsp
    have hg3 : 3 <= o.pair.genus := ho.2.2.1
    rw [hopair] at hg3
    dsimp [stable20] at hg3
    omega
theorem nc18 : NC18 := by simp [NC18, V, modelVocabulary, dualityModel, ambientTwistedDuality, properDualityIndex, stable66]
theorem nc19 : NC19 := by simp [NC19, V, modelVocabulary, dualityModel, openPoincareDuality, properDualityIndex, stable66]

theorem g7d16_model_is_consistent_and_materially_noncollapsing :
    AX01 ∧ AX02 ∧ AX03 ∧ AX04 ∧ AX05 ∧ AX06 ∧ AX07 ∧ AX08 ∧ AX09 ∧
    AX10 ∧ AX11 ∧ AX12 ∧ AX13 ∧ AX14 ∧ AX15 ∧ AX16 ∧ AX17 ∧ AX18 ∧
    NC01 ∧ NC02 ∧ NC03 ∧ NC04 ∧ NC05 ∧ NC06 ∧ NC07 ∧ NC08 ∧ NC09 ∧
    NC10 ∧ NC11 ∧ NC12 ∧ NC13 ∧ NC14 ∧ NC15 ∧ NC16 ∧ NC17 ∧ NC18 ∧ NC19 :=
  ⟨ax01,ax02,ax03,ax04,ax05,ax06,ax07,ax08,ax09,ax10,ax11,ax12,ax13,ax14,
   ax15,ax16,ax17,ax18,nc01,nc02,nc03,nc04,nc05,nc06,nc07,nc08,nc09,nc10,
   nc11,nc12,nc13,nc14,nc15,nc16,nc17,nc18,nc19⟩

#print axioms g7d16_model_is_consistent_and_materially_noncollapsing
