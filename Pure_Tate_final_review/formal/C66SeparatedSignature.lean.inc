structure ModuliIndex where
  genus : Int
  markings : Int
  deriving DecidableEq

structure ClosedPureIndex where
  genus : Int
  factors : Int
  degree : Int
  weight : Int
  deriving DecidableEq

structure OpenPureIndex where
  space : ModuliIndex
  degree : Int
  weight : Int
  deriving DecidableEq

inductive Slot where
  | zero : Slot
  | one : Slot
  | two : Slot
  deriving DecidableEq

def slotVal : Slot -> Nat
  | Slot.zero => 0
  | Slot.one => 1
  | Slot.two => 2

def total : List Slot -> Nat
  | [] => 0
  | a :: rest => slotVal a + total rest

def lenOf : List Slot -> Nat
  | [] => 0
  | _ :: rest => 1 + lenOf rest

structure KunnethIndex where
  source : ClosedPureIndex
  slots : List Slot

structure LocalSystemIndex where
  genus : Int
  degree : Int
  weight : Int
  partitionSize : Int

structure C66Vocabulary where
  RestrictionSurjectsOnLowestWeight : ClosedPureIndex -> OpenPureIndex -> Prop
  KunnethSplittingByChowKunnethProjectors : ClosedPureIndex -> Prop
  ChowKunnethProjectorIsAlgebraicCorrespondence : ModuliIndex -> Prop
  LerayDegeneratesAtE2 : ModuliIndex -> Prop
  RTwoProjectorInPsiAndPullbackSpan : ModuliIndex -> Prop
  KunnethSummandVanishes : KunnethIndex -> Prop
  KunnethSummandRestrictsIntoPsi : KunnethIndex -> OpenPureIndex -> Prop
  DualizingClassSlotDecomposition : ModuliIndex -> Prop
  SlotOneCrossTermVanishes : ModuliIndex -> Prop
  OmegaMultiplicationHitsSlotTwo : ModuliIndex -> Prop
  PhiSpannedByForgetfulPullbacks : OpenPureIndex -> OpenPureIndex -> Prop
  PsiSpannedByPsiMultiples : OpenPureIndex -> OpenPureIndex -> Prop
  OrdinaryCohomologyVanishes : ModuliIndex -> Int -> Prop
  LocalSystemCohomologyVanishesAllCoefficients : ModuliIndex -> Int -> Prop
  PhiVanishes : OpenPureIndex -> Prop
  ContainedInPsi : OpenPureIndex -> Prop
  EqualsPsi : OpenPureIndex -> Prop
  PrimitiveQuotientIsLocalSystemSum : OpenPureIndex -> LocalSystemIndex -> Prop
  PrimitiveQuotientVanishes : OpenPureIndex -> Prop
  PureIsFiniteTateSum : OpenPureIndex -> Int -> Prop
  PhiIsFiniteTateSum : OpenPureIndex -> Int -> Prop
  PsiIsQuotientOfFiniteTateSum : OpenPureIndex -> Int -> Prop
  PurePolarizableOfWeight : OpenPureIndex -> Prop
  PsiClassIsAlgebraicOfTateType : ModuliIndex -> Int -> Prop
  ChowKunnethGenerationProperty : ModuliIndex -> Prop
  CkgpMarkingBound : Int -> Int -> Prop
  CycleClassMapSurjectsOntoPureWeight : OpenPureIndex -> Prop
  VirtualCohomologicalDimension : ModuliIndex -> Int -> Prop
  BorelMooreIsTwistOfPure : BMTargetIndex -> OpenPureIndex -> Int -> Prop
  TateTwistShift : Int -> Int -> Int -> Prop
