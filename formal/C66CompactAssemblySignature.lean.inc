structure C66CompactVocabulary where
  BoundaryImageIsFiniteTateSum : BoundaryImageIndex -> Prop
  OpenBMIsFiniteTateSum : OpenBMIndex -> Prop
  BoundarySequenceIsRightExact : BoundarySequenceIndex -> Prop
  BoundaryImageIsKernel : BoundarySequenceIndex -> Prop
  ShortExactOnBoundaryImage : BoundarySequenceIndex -> Prop
  CompactHomologyIsPurePolarizable : CompactHomologyIndex -> Prop
  CompactHomologyIsFiniteTateSum : CompactHomologyIndex -> Prop
  ProperHomologyCohomologyDuality : ProperDualityIndex -> Prop
  DualTateIndicesMatch : ProperDualityIndex -> Prop
