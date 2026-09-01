inductive GeometryKind where
  | smoothOpenDMStack
  | stableCompactifiedDMStack
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

inductive BoundarySourceKind where
  | normalizedReducedBoundary
  | unnormalizedBoundary
  | arbitraryClosedSubstack
  deriving DecidableEq

inductive ExactSequenceOrientation where
  | boundaryToCompactToOpen
  | openToCompactToBoundary
  deriving DecidableEq

structure ModuliSpaceIdentity where
  geometry : GeometryKind
  coefficients : CoefficientKind
  markingsKind : MarkingKind
  genus : Int
  markings : Int
  deriving DecidableEq

structure BoundaryImageIndex where
  ambient : ModuliSpaceIdentity
  source : BoundarySourceKind
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

structure CompactHomologyIndex where
  space : ModuliSpaceIdentity
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

structure OpenBMIndex where
  space : ModuliSpaceIdentity
  objectKind : CohomologyObjectKind
  homologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

structure CompactCohomologyTargetIndex where
  space : ModuliSpaceIdentity
  objectKind : CohomologyObjectKind
  cohomologicalDegree : Int
  weight : Int
  tateIndex : Int
  deriving DecidableEq

structure BoundarySequenceIndex where
  boundaryImage : BoundaryImageIndex
  compactHomology : CompactHomologyIndex
  openBM : OpenBMIndex
  orientation : ExactSequenceOrientation
  homologicalDegreeShift : Int
  tateTwist : Int
  deriving DecidableEq

structure ProperDualityIndex where
  homology : CompactHomologyIndex
  cohomology : CompactCohomologyTargetIndex
  degreeShift : Int
  tateIndexSum : Int
  deriving DecidableEq

def exactC66CompactSpace : ModuliSpaceIdentity := {
  geometry := GeometryKind.stableCompactifiedDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  genus := 6
  markings := 6
}

def exactC66OpenSpace : ModuliSpaceIdentity := {
  geometry := GeometryKind.smoothOpenDMStack
  coefficients := CoefficientKind.rational
  markingsKind := MarkingKind.ordered
  genus := 6
  markings := 6
}

def exactC66BoundaryImage : BoundaryImageIndex := {
  ambient := exactC66CompactSpace
  source := BoundarySourceKind.normalizedReducedBoundary
  objectKind := CohomologyObjectKind.image
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

def exactC66CompactHomology : CompactHomologyIndex := {
  space := exactC66CompactSpace
  objectKind := CohomologyObjectKind.wholeGroup
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

def exactC66OpenBM : OpenBMIndex := {
  space := exactC66OpenSpace
  objectKind := CohomologyObjectKind.wholeGroup
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

def exactC66CompactH16Target : CompactCohomologyTargetIndex := {
  space := exactC66CompactSpace
  objectKind := CohomologyObjectKind.wholeGroup
  cohomologicalDegree := 16
  weight := 16
  tateIndex := -8
}

def exactC66BoundarySequence : BoundarySequenceIndex := {
  boundaryImage := exactC66BoundaryImage
  compactHomology := exactC66CompactHomology
  openBM := exactC66OpenBM
  orientation := ExactSequenceOrientation.boundaryToCompactToOpen
  homologicalDegreeShift := 0
  tateTwist := 0
}

def exactC66ProperDuality : ProperDualityIndex := {
  homology := exactC66CompactHomology
  cohomology := exactC66CompactH16Target
  degreeShift := 0
  tateIndexSum := 0
}
