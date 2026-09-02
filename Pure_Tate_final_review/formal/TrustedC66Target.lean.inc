structure BMTargetIndex where
  genus : Int
  markings : Int
  homologicalDegree : Int
  weight : Int
  tateIndex : Int

def exactC66BMTarget : BMTargetIndex := {
  genus := 6
  markings := 6
  homologicalDegree := 16
  weight := -16
  tateIndex := 8
}

axiom BMIsFiniteTateSum : BMTargetIndex -> Prop
-- LEAN-AXIOM BMIsFiniteTateSum => VOCAB -- exact BM target predicate; semantic interpretation is review-audited
