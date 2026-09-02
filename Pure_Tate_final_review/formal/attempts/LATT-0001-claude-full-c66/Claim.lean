set_option autoImplicit false
-- LEAN-CAMPAIGN LC66-001
-- LEAN-ATTEMPT LATT-0001
-- LEAN-SOURCE-ATTEMPT ATT-0136
-- LEAN-CLAIM-CONTRACT C66-EXACT-TARGET-V1
-- LEAN-TARGET-SIGNATURE BM(g=6,n=6,degree=16,weight=-16,tate=8);ORD(g=6,n=6,degree=26,weight=26,tate=-13,dimension=21,twist=21);rank>=0
-- LEAN-THEOREM c66_exact_bm_is_finite_tate_sum
-- LEAN-WEIGHT All mathematical weight sits in the LC66-OBL axioms; the VOCAB axioms are uninterpreted carriers that assert nothing. Lean checks the deduction, the index arithmetic and the termination of the downward induction. Lean verifies: 4*6-5=19 < 20=26-6 and more generally 26-|i| >= 20 whenever |i| <= 6 (OBL-05); the six-slot combinatorics forcing some slot to equal 2 once |i| >= 7 (OBL-05); 4*6-4+5=25 < 26 (OBL-04); 5 <= c(6)=5 (OBL-07); 24=2*12 with Tate index -12 and -13 = -1 + -12 (OBL-07, OBL-08); 3*6-3+6=21, 26=2*21-16, -16=26-2*21 and 8=-13+21 (OBL-09). The downward induction of CLM-0136-5 is discharged by Lean's well-founded recursion on the natural-number total fibre degree, not by an axiom. Lean does not and cannot check that a carrier denotes the intended cohomology group or that an axiom states its cited theorem; that is the reviewers' burden.

-- LEAN-TRUSTED-PRELUDE-BEGIN
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
-- LEAN-TRUSTED-PRELUDE-END

-- ---------------------------------------------------------------------------
-- Indexing records.  Every genus, marking count, degree, weight, Tate index,
-- Kuenneth multi-index slot, partition size and duality twist that occurs in
-- ATT-0136 is carried by a field of one of these records, so Lean, not a
-- comment, checks the bookkeeping at each application site.
-- ---------------------------------------------------------------------------

structure ModuliIndex where
  genus : Int
  markings : Int

structure PureIndex where
  space : ModuliIndex
  degree : Int
  weight : Int

-- A Kuenneth multi-index i in {0,1,2}^n for the fibre power C^n -> M_g,
-- recorded by the data that ATT-0136 Section 5 actually uses: the base moduli
-- index, the cohomological degree k of the ambient group, the total fibre
-- degree |i| as a Nat so that the downward induction is well founded, and the
-- maximum slot value occurring in i.
inductive Slot where
  | zero : Slot
  | one : Slot
  | two : Slot

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
  base : ModuliIndex
  slots : List Slot
  degree : Int
  weight : Int

-- A local-system cohomology index H^degree(M_genus; V_lambda) with
-- |lambda| = partitionSize, used only by the optional Section 6 route.
structure LocalSystemIndex where
  genus : Int
  degree : Int
  weight : Int
  partitionSize : Int

-- The moduli stacks that occur:  M_6, M_{6,5} and M_{6,6}.

def moduliM6 : ModuliIndex := { genus := 6, markings := 0 }

def moduliM65 : ModuliIndex := { genus := 6, markings := 5 }

def moduliM66 : ModuliIndex := { genus := 6, markings := 6 }

-- W_26 H^26(M_{6,6};Q): the exact ordinary form of the target.

def pureM66deg26 : PureIndex := { space := moduliM66, degree := 26, weight := 26 }

-- W_24 H^24(M_{6,6};Q): the degree-24 group whose Phi is multiplied by psi_i.

def pureM66deg24 : PureIndex := { space := moduliM66, degree := 24, weight := 24 }

-- W_26 H^26(M_{6,5};Q): the pullback source that vanishes above vcd = 25.

def pureM65deg26 : PureIndex := { space := moduliM65, degree := 26, weight := 26 }

-- W_24 H^24(M_{6,5};Q): the CKgP-controlled Q(-12) group.

def pureM65deg24 : PureIndex := { space := moduliM65, degree := 24, weight := 24 }

-- W_26 H^26(C^6;Q): the pure-weight source of the restriction surjection.

def sourceC6deg26 : PureIndex := { space := moduliM66, degree := 26, weight := 26 }

-- The optional Section 6 primitive slot: W_26 H^20(M_6;V_lambda), |lambda| = 6.

def primitiveM6deg20 : LocalSystemIndex :=
  { genus := 6, degree := 20, weight := 26, partitionSize := 6 }

-- The Kuenneth multi-index of total fibre degree m at (g,n,k) = (6,6,26).

-- ---------------------------------------------------------------------------
-- Uninterpreted vocabulary.  These axioms declare carriers only.  None of them
-- asserts anything; their semantic reading is review-audited exactly as
-- BMIsFiniteTateSum is.
-- ---------------------------------------------------------------------------

axiom RestrictionSurjectsOnLowestWeight : PureIndex -> PureIndex -> Prop
-- LEAN-AXIOM RestrictionSurjectsOnLowestWeight => VOCAB -- carrier: restriction along the open immersion M_{g,n} inside C^n induces a surjection of mixed Hodge structures from W_k H^k of the fibre power named by the first index onto W_k H^k of the open moduli stack named by the second

axiom KunnethSplittingByChowKunnethProjectors : PureIndex -> Prop
-- LEAN-AXIOM KunnethSplittingByChowKunnethProjectors => VOCAB -- carrier: W_k H^k(C^n;Q) splits as a direct sum of mixed Hodge structures indexed by multi-indices i in {0,1,2}^n, the summand for i being W_k of H^{k-|i|}(M_g; tensor_s R^{i_s} pi_* Q)

axiom ChowKunnethProjectorIsAlgebraicCorrespondence : ModuliIndex -> Prop
-- LEAN-AXIOM ChowKunnethProjectorIsAlgebraicCorrespondence => VOCAB -- carrier: the Petersen-Tavakol-Yin relative Chow-Kuenneth projectors over M_g are algebraic correspondences, hence morphisms of mixed Hodge structures, so W_k is additive over the decomposition they induce

axiom LerayDegeneratesAtE2 : ModuliIndex -> Prop
-- LEAN-AXIOM LerayDegeneratesAtE2 => VOCAB -- carrier: the Leray spectral sequence of the smooth proper fibre power C^n -> M_g degenerates at E_2, which splits the associated graded only

axiom RTwoProjectorInPsiAndPullbackSpan : ModuliIndex -> Prop
-- LEAN-AXIOM RTwoProjectorInPsiAndPullbackSpan => VOCAB -- carrier: the single-factor R^2 projector pi_2 = psi_2/(2g-2) - kappa_1/(2(2g-2)^2) lies in the Q-span of a psi class and a pullback from M_g

axiom KunnethSummandVanishes : KunnethIndex -> Prop
-- LEAN-AXIOM KunnethSummandVanishes => VOCAB -- carrier: the Kuenneth summand A_i of W_k H^k(C^n;Q) named by the index is the zero mixed Hodge structure

axiom KunnethSummandRestrictsIntoPsi : KunnethIndex -> PureIndex -> Prop
-- LEAN-AXIOM KunnethSummandRestrictsIntoPsi => VOCAB -- carrier: the image of the Kuenneth summand A_i under restriction to M_{g,n} is contained in the subspace Psi_{g,n}^k of the pure group named by the second index

axiom DualizingClassSlotDecomposition : ModuliIndex -> Prop
-- LEAN-AXIOM DualizingClassSlotDecomposition => VOCAB -- carrier: on the fibre power of the closed universal curve over M_g the class omega_s = pr_s^* c_1(omega_{C/M_g}) decomposes as a_s + b_s + c_s with a_s in H^2(M_g;Q) in Kuenneth slot 0, b_s in H^1(M_g;R^1 pi_* Q) in slot 1, and c_s in H^0(M_g;R^2 pi_* Q) in slot 2, equal to 2g-2 times the generator; only c_s realises the slot-0 to slot-2 isomorphism

axiom SlotOneCrossTermVanishes : ModuliIndex -> Prop
-- LEAN-AXIOM SlotOneCrossTermVanishes => VOCAB -- carrier: the slot-1 cross term b_s of omega_s is zero, equivalently H^1(Mod_g;H^1(Sigma_g;Q)) = 0

axiom OmegaMultiplicationHitsSlotTwo : ModuliIndex -> Prop
-- LEAN-AXIOM OmegaMultiplicationHitsSlotTwo => VOCAB -- carrier: cup-product with omega_s carries the slot-s-reset summand isomorphically onto the slot-s-equal-2 summand, up to the slot-0 error a_s and the slot-1 error b_s named by the decomposition

axiom PhiSpannedByForgetfulPullbacks : PureIndex -> PureIndex -> Prop
-- LEAN-AXIOM PhiSpannedByForgetfulPullbacks => VOCAB -- carrier: Phi_{g,n}^k, the sum over the n forgetful maps pi_i of the pullbacks pi_i^* of the pure group W_k H^k(M_{g,n-1};Q) named by the second index, taken inside the pure group named by the first index

axiom PsiSpannedByPsiMultiples : PureIndex -> PureIndex -> Prop
-- LEAN-AXIOM PsiSpannedByPsiMultiples => VOCAB -- carrier: Psi_{g,n}^k, the sum over i of psi_i times Phi_{g,n}^{k-2}, the second index naming the degree-(k-2) pure group on the same stack whose Phi is multiplied

axiom OrdinaryCohomologyVanishes : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM OrdinaryCohomologyVanishes => VOCAB -- carrier: H^d(M_{g,n};Q) = 0 in the given degree d, with constant rational coefficients

axiom LocalSystemCohomologyVanishesAllCoefficients : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM LocalSystemCohomologyVanishesAllCoefficients => VOCAB -- carrier: H^d(M_g;L) = 0 in the given degree d for every finite-dimensional rational local system L on M_g

axiom PhiVanishes : PureIndex -> Prop
-- LEAN-AXIOM PhiVanishes => VOCAB -- carrier: Phi_{g,n}^k = 0

axiom ContainedInPsi : PureIndex -> Prop
-- LEAN-AXIOM ContainedInPsi => VOCAB -- carrier: W_k H^k(M_{g,n};Q) is contained in Psi_{g,n}^k as a subspace of the ambient cohomology

axiom EqualsPsi : PureIndex -> Prop
-- LEAN-AXIOM EqualsPsi => VOCAB -- carrier: W_k H^k(M_{g,n};Q) equals Psi_{g,n}^k as subspaces of the ambient cohomology

axiom PrimitiveQuotientIsLocalSystemSum : PureIndex -> LocalSystemIndex -> Prop
-- LEAN-AXIOM PrimitiveQuotientIsLocalSystemSum => VOCAB -- carrier: the quotient W_k H^k(M_{g,n};Q)/(Phi_{g,n}^k + Psi_{g,n}^k) is isomorphic as a pure weight-k Hodge structure to the direct sum over partitions lambda with |lambda| = partitionSize of W_weight H^degree(M_genus;V_lambda) tensor V_{lambda transpose}

axiom PrimitiveQuotientVanishes : PureIndex -> Prop
-- LEAN-AXIOM PrimitiveQuotientVanishes => VOCAB -- carrier: the quotient W_k H^k(M_{g,n};Q)/(Phi_{g,n}^k + Psi_{g,n}^k) is the zero Hodge structure

axiom PureIsFiniteTateSum : PureIndex -> Int -> Prop
-- LEAN-AXIOM PureIsFiniteTateSum => VOCAB -- carrier: the whole group W_weight H^degree(M_{g,n};Q) is isomorphic as a rational Hodge structure to a finite direct sum Q(t)^r with r >= 0 and t the given Tate index

axiom PhiIsFiniteTateSum : PureIndex -> Int -> Prop
-- LEAN-AXIOM PhiIsFiniteTateSum => VOCAB -- carrier: the subspace Phi_{g,n}^k is isomorphic to a finite direct sum Q(t)^a with a >= 0

axiom PsiIsQuotientOfFiniteTateSum : PureIndex -> Int -> Prop
-- LEAN-AXIOM PsiIsQuotientOfFiniteTateSum => VOCAB -- carrier: Psi_{g,n}^k is a quotient of a finite direct sum of Q(t); this is strictly weaker than being isomorphic to such a sum and is what the cup-product construction supplies before semisimplicity is invoked

axiom PurePolarizableOfWeight : PureIndex -> Prop
-- LEAN-AXIOM PurePolarizableOfWeight => VOCAB -- carrier: W_k H^k(M_{g,n};Q) is pure and polarizable of weight k, being the lowest-weight piece of the cohomology of a smooth stack

axiom PsiClassIsAlgebraicOfTateType : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM PsiClassIsAlgebraicOfTateType => VOCAB -- carrier: on M_{g,n} every psi_i is an algebraic class spanning a copy of Q(t) for the given Tate index t

axiom ChowKunnethGenerationProperty : ModuliIndex -> Prop
-- LEAN-AXIOM ChowKunnethGenerationProperty => VOCAB -- carrier: the open stack M_{g,n} has the Chow-Kuenneth generation property and A^*(M_{g,n}) = R^*(M_{g,n})

axiom CkgpMarkingBound : Int -> Int -> Prop
-- LEAN-AXIOM CkgpMarkingBound => VOCAB -- carrier: c(genus) equals the second argument, the largest marking count for which the Chow-Kuenneth generation theorem is recorded in that genus

axiom CycleClassMapSurjectsOntoPureWeight : PureIndex -> Prop
-- LEAN-AXIOM CycleClassMapSurjectsOntoPureWeight => VOCAB -- carrier: the cycle class map from algebraic cycles of codimension degree/2 surjects onto the lowest-weight group W_degree H^degree(M_{g,n};Q)

axiom VirtualCohomologicalDimension : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM VirtualCohomologicalDimension => VOCAB -- carrier: the virtual cohomological dimension of the mapping class group of the given moduli index equals the second argument

axiom BorelMooreIsTwistOfPure : BMTargetIndex -> PureIndex -> Int -> Prop
-- LEAN-AXIOM BorelMooreIsTwistOfPure => VOCAB -- carrier: W_weight H^BM_homologicalDegree(M_{g,n};Q) is isomorphic as a mixed Hodge structure to the Tate twist by the third argument of the pure group named by the second index

axiom TateTwistShift : Int -> Int -> Int -> Prop
-- LEAN-AXIOM TateTwistShift => VOCAB -- carrier: Q(a)(b) = Q(c) for the three given Tate indices a, b, c

-- ---------------------------------------------------------------------------
-- LC66-OBL-01 (CLM-0136-1).  The lowest-weight restriction surjection, in the
-- containment direction only.  No splitting, no kernel, no Gysin exactness for
-- the diagonals, and no use of the non-proper forgetful map to M_g.
-- ---------------------------------------------------------------------------

axiom deligne_lowest_weight_restriction_surjection : forall (src tgt : PureIndex),
    src.space = tgt.space ->
    src.degree = tgt.degree ->
    src.weight = tgt.weight ->
    src.degree = src.weight ->
    RestrictionSurjectsOnLowestWeight src tgt
-- LEAN-AXIOM deligne_lowest_weight_restriction_surjection => LC66-OBL-01 -- Deligne, Theorie de Hodge II Corollaire 3.2.17, applied to a smooth proper compactification of the fibre power C^n, which is simultaneously a compactification of the open M_{g,n} because M_{g,n} is the complement of the pairwise diagonals: W_k H^k of either smooth open is the image of the compactification cohomology and restriction factors that common image, so W_k H^k(C^n;Q) surjects onto W_k H^k(M_{g,n};Q).  Only the surjection is asserted: no splitting, no description of the kernel, no Gysin exactness for the diagonals, and no claim that Kuenneth summands of H^*(C^n) are summands of R^* f_* Q for the non-proper f : M_{g,n} -> M_g

axiom containment_transfers_along_surjection :
    forall (src tgt : PureIndex) (base : ModuliIndex),
    RestrictionSurjectsOnLowestWeight src tgt ->
    (forall (idx : KunnethIndex), idx.base = base -> idx.degree = tgt.degree ->
      idx.weight = tgt.weight -> lenOf idx.slots = 6 ->
      KunnethSummandRestrictsIntoPsi idx tgt) ->
    KunnethSplittingByChowKunnethProjectors src ->
    ContainedInPsi tgt
-- LEAN-AXIOM containment_transfers_along_surjection => LC66-OBL-01 -- because restriction is surjective onto W_k H^k(M_{g,n};Q) and the source is the direct sum of its Kuenneth summands, every element of the target is a sum of restrictions of Kuenneth summands; if each such restriction lands in Psi then the whole target is contained in Psi.  This is the containment direction of ATT-0136 Section 1 combined with the Section 2 splitting, and it asserts nothing about Hodge type

-- ---------------------------------------------------------------------------
-- LC66-OBL-02 (CLM-0136-2).  The Petersen-Tavakol-Yin relative Chow-Kuenneth
-- splitting.  E_2 degeneration is recorded as insufficient on its own.
-- ---------------------------------------------------------------------------

axiom deligne_smooth_proper_leray_degeneration : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    LerayDegeneratesAtE2 base
-- LEAN-AXIOM deligne_smooth_proper_leray_degeneration => LC66-OBL-02 -- Deligne's degeneration theorem for the smooth proper fibre power C^n -> M_g gives E_2-degeneration of its Leray spectral sequence.  This alone splits only the associated graded and is deliberately not sufficient to conclude the mixed-Hodge-structure splitting below

axiom pty_projectors_are_algebraic_correspondences : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    ChowKunnethProjectorIsAlgebraicCorrespondence base
-- LEAN-AXIOM pty_projectors_are_algebraic_correspondences => LC66-OBL-02 -- Petersen-Tavakol-Yin, Ann. Sci. Ec. Norm. Super. 54 (2021) Sections 5.1 and 5.2.2: the relative Chow-Kuenneth projectors over M_g are built from the Q-divisor class c_1(omega_{C/M_g})/(2g-2) and are algebraic correspondences, hence morphisms of mixed Hodge structures

axiom pty_r_two_projector_form : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    RTwoProjectorInPsiAndPullbackSpan base
-- LEAN-AXIOM pty_r_two_projector_form => LC66-OBL-02 -- the single-factor R^2 projector is pi_2 = psi_2/(2g-2) - kappa_1/(2(2g-2)^2), which already lies in the Q-span of a psi class and a pullback from M_g, hence lands in Psi + Phi after restriction to M_{g,n}

axiom kunneth_splitting_of_pure_weight_source :
    forall (src : PureIndex) (base : ModuliIndex),
    LerayDegeneratesAtE2 base ->
    ChowKunnethProjectorIsAlgebraicCorrespondence base ->
    RTwoProjectorInPsiAndPullbackSpan base ->
    base.genus = src.space.genus ->
    base.markings = 0 ->
    src.degree = src.weight ->
    KunnethSplittingByChowKunnethProjectors src
-- LEAN-AXIOM kunneth_splitting_of_pure_weight_source => LC66-OBL-02 -- relative Kuenneth for the fibre product together with R^j pi_* Q = 0 for j outside {0,1,2} gives the multi-index decomposition, and because the Petersen-Tavakol-Yin projectors are algebraic correspondences the decomposition is an actual splitting of mixed Hodge structures, so W_k is additive over the summands A_i = W_k of H^{k-|i|}(M_g; tensor_s R^{i_s} pi_* Q).  The degeneration hypothesis alone would give only the associated graded, which is why both hypotheses appear

-- ---------------------------------------------------------------------------
-- LC66-OBL-03 (CLM-0136-3).  The class omega_s is not Kuenneth-homogeneous.
-- Disposal A kills the slot-one cross term; the slot-zero cross term is
-- disposed of separately, in OBL-05, through the five-marking vanishing.
-- ---------------------------------------------------------------------------

axiom omega_class_slot_decomposition : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    DualizingClassSlotDecomposition base
-- LEAN-AXIOM omega_class_slot_decomposition => LC66-OBL-03 -- packet FND-0196: omega_s = pr_s^* c_1(omega_{C/M_g}) is not Kuenneth-homogeneous but equals a_s + b_s + c_s with a_s in H^2(M_g;Q) at slot 0, b_s in H^1(M_g;R^1 pi_* Q) at slot 1 and c_s in H^0(M_g;R^2 pi_* Q) at slot 2, where c_s is 2g-2 times the generator because the fibre restriction of omega_s is the canonical class of degree 2g-2.  Only c_s induces the slot-0 to slot-2 isomorphism; cup-product with a_s preserves the multi-index and raises base degree by 2, and cup-product with b_s raises the s-th slot by 1

axiom morita_slot_one_vanishing : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    SlotOneCrossTermVanishes base
-- LEAN-AXIOM morita_slot_one_vanishing => LC66-OBL-03 -- Disposal A: for g >= 2 one has H^1(Mod_g;H^1(Sigma_g;Q)) = 0, the rational form of Morita's H_1(Mod_g;H_1(Sigma_g;Z)) = Z/(2g-2) (Proc. Japan Acad. Ser. A 62 (1986) Theorem 1; Hain-Reed).  Equivalently H^2(C;Q) has basis lambda, omega, so the H^1(M_g;V) summand of H^2(C) is zero and b_s = 0 identically

axiom omega_multiplication_hits_slot_two_modulo_errors :
    forall (base : ModuliIndex),
    DualizingClassSlotDecomposition base ->
    SlotOneCrossTermVanishes base ->
    RTwoProjectorInPsiAndPullbackSpan base ->
    OmegaMultiplicationHitsSlotTwo base
-- LEAN-AXIOM omega_multiplication_hits_slot_two_modulo_errors => LC66-OBL-03 -- with b_s = 0 one has omega_s = a_s + c_s, so cup-product with omega_s carries the slot-s-reset summand onto the slot-s-equal-2 summand up to the slot-0 error a_s alone; the projector form of the same identification is the independent Disposal B.  The remaining slot-0 error is not disposed of here: it is routed through the five-marking vanishing in LC66-OBL-05

-- ---------------------------------------------------------------------------
-- LC66-OBL-04 (CLM-0136-4).  Phi_{6,6}^{26} = 0 because 26 > vcd(PMod_{6,5})
-- = 25.  Independent of the primitive quotient; no vanishing is drawn from
-- 26 = vcd(M_{6,6}).
-- ---------------------------------------------------------------------------

axiom harer_vcd_pointed : forall (base : ModuliIndex) (v : Int),
    2 <= base.genus ->
    1 <= base.markings ->
    v = 4 * base.genus - 4 + base.markings ->
    VirtualCohomologicalDimension base v
-- LEAN-AXIOM harer_vcd_pointed => LC66-OBL-04 -- Harer's formula vcd(PMod_{g,n}) = 4g-4+n for the pure mapping class group of a genus g >= 2 surface with n >= 1 marked points

axiom constant_coefficient_vanishing_above_vcd :
    forall (base : ModuliIndex) (v d : Int),
    VirtualCohomologicalDimension base v ->
    v < d ->
    OrdinaryCohomologyVanishes base d
-- LEAN-AXIOM constant_coefficient_vanishing_above_vcd => LC66-OBL-04 -- choose a torsion-free normal finite-index subgroup Gamma of the mapping class group; then cd(Gamma) equals the vcd, so H^d(Gamma;Q) = 0 above it, and rational Hochschild-Serre for the finite quotient is exact, giving H^d(M_{g,n};Q) = 0 for d strictly above the vcd

axiom phi_vanishes_from_pullback_source : forall (p q : PureIndex),
    PhiSpannedByForgetfulPullbacks p q ->
    OrdinaryCohomologyVanishes q.space q.degree ->
    PhiVanishes p
-- LEAN-AXIOM phi_vanishes_from_pullback_source => LC66-OBL-04 -- Phi_{g,n}^k is a sum of pullback images of subspaces of H^k(M_{g,n-1};Q), so it is zero as soon as that ambient group is zero

axiom phi_is_pullback_span : forall (p q : PureIndex),
    q.space.genus = p.space.genus ->
    q.space.markings = p.space.markings - 1 ->
    q.degree = p.degree ->
    q.weight = p.weight ->
    PhiSpannedByForgetfulPullbacks p q
-- LEAN-AXIOM phi_is_pullback_span => LC66-OBL-04 -- the definition Phi_{g,n}^k := sum_i pi_i^* W_k H^k(M_{g,n-1};Q) over the n forgetful maps, which drop one marking and preserve degree and weight; this asserts only what Phi denotes

axiom psi_is_psi_multiple_span : forall (p r : PureIndex),
    r.space = p.space ->
    r.degree = p.degree - 2 ->
    r.weight = p.weight - 2 ->
    PsiSpannedByPsiMultiples p r
-- LEAN-AXIOM psi_is_psi_multiple_span => LC66-OBL-04 -- the definition Psi_{g,n}^k := sum_i psi_i Phi_{g,n}^{k-2} on the same stack, the multiplication raising degree and weight by two; this asserts only what Psi denotes

-- ---------------------------------------------------------------------------
-- LC66-OBL-05 (CLM-0136-5).  The load-bearing route.  Base case: every
-- summand of total fibre degree at most six sits in base degree at least 20,
-- above vcd(Mod_6) = 19, for every rational local system.  Inductive step:
-- every surviving summand has a slot equal to 2, and cup-product with omega_s
-- routes it into Psi modulo a slot-zero error that dies through the
-- five-marking vanishing and a slot-one-shifted term of strictly smaller total
-- fibre degree.  Lean discharges the well-foundedness itself.
-- ---------------------------------------------------------------------------

axiom harer_vcd_unpointed : forall (base : ModuliIndex) (v : Int),
    2 <= base.genus ->
    base.markings = 0 ->
    v = 4 * base.genus - 5 ->
    VirtualCohomologicalDimension base v
-- LEAN-AXIOM harer_vcd_unpointed => LC66-OBL-05 -- Harer's virtual cohomological dimension formula vcd(Mod_g) = 4g-5 for the unmarked mapping class group in genus g >= 2

axiom local_coefficient_vanishing_above_vcd :
    forall (base : ModuliIndex) (v d : Int),
    VirtualCohomologicalDimension base v ->
    base.markings = 0 ->
    v < d ->
    LocalSystemCohomologyVanishesAllCoefficients base d
-- LEAN-AXIOM local_coefficient_vanishing_above_vcd => LC66-OBL-05 -- Church-Farb-Putman's record of Harer: for a torsion-free normal finite-index Gamma in Mod_g one has cd(Gamma) = vcd, so H^d(Gamma;L) = 0 above it for EVERY finite-dimensional rational coefficient module L, and rational Hochschild-Serre for the finite quotient gives H^d(Mod_g;L) = 0.  Stack cohomology of M_g with L is group cohomology of Mod_g with L.  This is genuine local-coefficient vanishing, not a transfer of constant-coefficient vanishing

axiom kunneth_summand_vanishes_below_base_degree :
    forall (idx : KunnethIndex) (v : Int),
    LocalSystemCohomologyVanishesAllCoefficients idx.base (idx.degree - (total idx.slots : Int)) ->
    VirtualCohomologicalDimension idx.base v ->
    v < idx.degree - (total idx.slots : Int) ->
    KunnethSummandVanishes idx
-- LEAN-AXIOM kunneth_summand_vanishes_below_base_degree => LC66-OBL-05 -- the Kuenneth summand A_i is W_k of H^{k-|i|}(M_g; tensor_s R^{i_s} pi_* Q), whose coefficient system is a finite-dimensional rational local system on M_g; if that base degree k-|i| is strictly above the vcd then the whole summand is zero.  At (6,6,26) this is 26-|i| >= 20 > 19 for every |i| <= 6, including the all-slot-one primitive term, with no traceless refinement

axiom vanishing_summand_restricts_into_psi :
    forall (idx : KunnethIndex) (tgt : PureIndex),
    KunnethSummandVanishes idx ->
    KunnethSummandRestrictsIntoPsi idx tgt
-- LEAN-AXIOM vanishing_summand_restricts_into_psi => LC66-OBL-05 -- the image of the zero Hodge structure under restriction is zero, which is contained in Psi

axiom slot_two_summand_restricts_into_psi_modulo_errors :
    forall (idx errZero errOne : KunnethIndex) (pre post : List Slot)
      (tgt src r q : PureIndex) (base5 : ModuliIndex),
    idx.slots = pre ++ Slot.two :: post ->
    errZero.base = idx.base ->
    errZero.degree = idx.degree ->
    errZero.weight = idx.weight ->
    errZero.slots = pre ++ Slot.zero :: post ->
    errOne.base = idx.base ->
    errOne.degree = idx.degree ->
    errOne.weight = idx.weight ->
    errOne.slots = pre ++ Slot.one :: post ->
    OmegaMultiplicationHitsSlotTwo idx.base ->
    RestrictionSurjectsOnLowestWeight src tgt ->
    PsiSpannedByPsiMultiples tgt r ->
    PhiSpannedByForgetfulPullbacks r q ->
    base5.genus = tgt.space.genus ->
    base5.markings = tgt.space.markings - 1 ->
    q.space = base5 ->
    OrdinaryCohomologyVanishes base5 tgt.degree ->
    KunnethSummandRestrictsIntoPsi errOne tgt ->
    KunnethSummandRestrictsIntoPsi idx tgt
-- LEAN-AXIOM slot_two_summand_restricts_into_psi_modulo_errors => LC66-OBL-05 -- ATT-0136 Section 5, one inductive step.  Fix a surviving multi-index i with i_s = 2, let i' reset slot s to 0 and i'' set slot s to 1, so |i''| = |i|-1.  Then A_i = c_s B_{i'} sits inside omega_s B_{i'} + A_{i'} + A_{i''}.  The term omega_s B_{i'} restricts into psi_s times a pullback of W_{k-2} H^{k-2}(M_{g,n-1}), a summand of Psi, because slot s = 0 makes B_{i'} pulled back along the s-th factor and M_{g,n} -> C^n -> C^{n-1} factors through M_{g,n-1}.  The slot-zero error A_{i'} restricts through W_k H^k(M_{g,n-1};Q), which the five-marking vanishing hypothesis makes zero.  The slot-one-shifted error A_{i''} has strictly smaller total fibre degree and is supplied by the induction hypothesis.  No axiom here asserts the conclusion of the induction: the recursion itself is performed by Lean

-- ---------------------------------------------------------------------------
-- LC66-OBL-06 (CLM-0136-6).  The optional, explicitly independent and
-- non-load-bearing published primitive-quotient route.  Nothing downstream of
-- the exported theorem consumes it; it is derived and then set aside.
-- ---------------------------------------------------------------------------

axiom clp_primitive_quotient_formula :
    forall (p : PureIndex) (prim : LocalSystemIndex),
    2 <= p.space.genus ->
    1 <= p.space.markings ->
    p.degree = p.weight ->
    prim.genus = p.space.genus ->
    prim.degree = p.degree - p.space.markings ->
    prim.weight = p.weight ->
    prim.partitionSize = p.space.markings ->
    PrimitiveQuotientIsLocalSystemSum p prim
-- LEAN-AXIOM clp_primitive_quotient_formula => LC66-OBL-06 -- Canning-Larson-Payne, Forum Math. Pi 12 (2024) Lemma 3.1(a), recorded packet-visibly as FND-0195 and FND-0198: for g >= 2 and n >= 1 the quotient of W_k H^k(M_{g,n};Q) by Phi + Psi is the direct sum over |lambda| = n of W_k H^{k-n}(M_g;V_lambda) tensor V_{lambda transpose}.  This is the optional Section 6 route only; the exported theorem does not consume it

axiom primitive_quotient_vanishes_from_local_coefficients :
    forall (p : PureIndex) (prim : LocalSystemIndex),
    PrimitiveQuotientIsLocalSystemSum p prim ->
    LocalSystemCohomologyVanishesAllCoefficients { genus := prim.genus, markings := 0 } prim.degree ->
    PrimitiveQuotientVanishes p
-- LEAN-AXIOM primitive_quotient_vanishes_from_local_coefficients => LC66-OBL-06 -- every summand of the right-hand side of the primitive-quotient formula is a weight-graded piece of H^{k-n}(M_g;V_lambda), which the local-coefficient vcd vanishing kills at (6,6,26) because 20 exceeds vcd(Mod_6) = 19; a direct sum of zero Hodge structures is zero.  Optional Section 6 only

axiom equality_from_vanishing_primitive_quotient_and_phi :
    forall (p : PureIndex),
    PrimitiveQuotientVanishes p ->
    PhiVanishes p ->
    EqualsPsi p
-- LEAN-AXIOM equality_from_vanishing_primitive_quotient_and_phi => LC66-OBL-06 -- a zero quotient by Phi + Psi says W_k H^k = Phi + Psi, and with Phi = 0 this gives the equality W_k H^k = Psi, stronger than the containment the theorem uses.  Optional Section 6 only; the exported theorem is proved from the containment route instead

-- ---------------------------------------------------------------------------
-- LC66-OBL-07 (CLM-0136-7).  CKgP exactly at n = 5 = c(6), never at n = 6.
-- ---------------------------------------------------------------------------

axiom ckgp_marking_bound_genus_six : CkgpMarkingBound 6 5
-- LEAN-AXIOM ckgp_marking_bound_genus_six => LC66-OBL-07 -- the verified theorem THM-0005 records c(6) = 5 as the inclusive marking bound of the Chow-Kuenneth generation range in genus 6; it says nothing at n = 6

axiom ckgp_holds_in_range : forall (base : ModuliIndex) (b : Int),
    CkgpMarkingBound base.genus b ->
    base.markings <= b ->
    ChowKunnethGenerationProperty base
-- LEAN-AXIOM ckgp_holds_in_range => LC66-OBL-07 -- THM-0005, recorded scope object 'open M', degree 'all pure-weight pieces', coefficients Q: the open moduli stack M_{g,n} has the Chow-Kuenneth generation property and tautological Chow ring for every marking count at most c(g)

axiom cycle_class_surjectivity_from_ckgp : forall (base : ModuliIndex) (p : PureIndex),
    ChowKunnethGenerationProperty base ->
    p.space = base ->
    p.degree = p.weight ->
    CycleClassMapSurjectsOntoPureWeight p
-- LEAN-AXIOM cycle_class_surjectivity_from_ckgp => LC66-OBL-07 -- SRC-0002 Table 1 with Proposition 4.5 via Lemma 4.3: the Chow-Kuenneth generation property implies that the cycle class map surjects onto every lowest-weight group W_m H^m of the open stack, and in fact W_m H^m = RH^m

axiom algebraic_pure_weight_is_tate : forall (p : PureIndex) (c : Int),
    CycleClassMapSurjectsOntoPureWeight p ->
    PurePolarizableOfWeight p ->
    p.degree = 2 * c ->
    p.weight = p.degree ->
    PureIsFiniteTateSum p (-c)
-- LEAN-AXIOM algebraic_pure_weight_is_tate => LC66-OBL-07 -- a lowest-weight group generated by classes of algebraic cycles of codimension c consists of classes of Hodge type (c,c), and polarizable pure Q-Hodge structures of that weight are semisimple, so the group is a finite direct sum of Q(-c); finiteness holds because the rational cohomology of a finite-type stack is finite dimensional.  Only the algebraic-implies-Tate direction is used; algebraicity is supplied first by CKgP

axiom lowest_weight_is_pure_polarizable : forall (p : PureIndex),
    p.degree = p.weight ->
    PurePolarizableOfWeight p
-- LEAN-AXIOM lowest_weight_is_pure_polarizable => LC66-OBL-07 -- for a smooth stack the cohomology H^m has weights in [m,2m], so W_m H^m is the lowest-weight piece; it is the image of H^m of a smooth proper compactification and is therefore pure and polarizable of weight m

-- ---------------------------------------------------------------------------
-- LC66-OBL-08 (CLM-0136-8).  psi-products and the semisimplicity upgrade from
-- a Tate quotient to the whole group.
-- ---------------------------------------------------------------------------

axiom phi_tate_from_pullback_source : forall (p q : PureIndex) (t : Int),
    PhiSpannedByForgetfulPullbacks p q ->
    PureIsFiniteTateSum q t ->
    PhiIsFiniteTateSum p t
-- LEAN-AXIOM phi_tate_from_pullback_source => LC66-OBL-08 -- Phi is a sum of images of W_m H^m(M_{g,n-1};Q) under the forgetful pullbacks, which are morphisms of mixed Hodge structures of type (0,0), so a Q(t)-sum source gives a Q(t)-sum image

axiom psi_class_is_tate_divisor : forall (base : ModuliIndex),
    1 <= base.markings ->
    PsiClassIsAlgebraicOfTateType base (-1)
-- LEAN-AXIOM psi_class_is_tate_divisor => LC66-OBL-08 -- for n >= 1 each psi_i on M_{g,n} is an algebraic codimension-one class and therefore spans a copy of Q(-1)

axiom psi_products_are_tate_quotient : forall (p r : PureIndex) (a b t : Int),
    PsiSpannedByPsiMultiples p r ->
    PsiClassIsAlgebraicOfTateType p.space a ->
    PhiIsFiniteTateSum r b ->
    p.degree = r.degree + 2 ->
    p.weight = r.weight + 2 ->
    t = a + b ->
    PsiIsQuotientOfFiniteTateSum p t
-- LEAN-AXIOM psi_products_are_tate_quotient => LC66-OBL-08 -- cup product is a morphism of mixed Hodge structures, so the maps Q(a) tensor Phi_{g,n}^{k-2} -> W_k H^k(M_{g,n};Q) have images that are finite direct sums of Q(a+b), and Psi_{g,n}^k is by definition the sum of those images.  Only a quotient of a finite Tate sum is claimed here, not an isomorphism

axiom polarizable_semisimplicity_upgrade : forall (p : PureIndex) (t : Int),
    ContainedInPsi p ->
    PurePolarizableOfWeight p ->
    PsiIsQuotientOfFiniteTateSum p t ->
    PureIsFiniteTateSum p t
-- LEAN-AXIOM polarizable_semisimplicity_upgrade => LC66-OBL-08 -- W_k H^k(M_{g,n};Q) is contained in Psi and Psi is a quotient of a finite direct sum of Q(t), so the whole group is a subobject of a quotient of a Tate sum; since it is pure polarizable of weight k and polarizable pure rational Hodge structures of a fixed weight form a semisimple abelian category (FND-0033), it is itself isomorphic to Q(t)^r for a finite r >= 0.  The conclusion is about the whole group, not a subquotient, associated graded or semisimplification, and r = 0 is admitted

-- ---------------------------------------------------------------------------
-- LC66-OBL-09 (CLM-0136-9).  Poincare duality in complex dimension 21 and the
-- twist Q(-13)(21) = Q(8), landing on the exact Borel-Moore target.
-- ---------------------------------------------------------------------------

axiom poincare_duality_bm_twist : forall (bm : BMTargetIndex) (p : PureIndex) (d : Int),
    bm.genus = p.space.genus ->
    bm.markings = p.space.markings ->
    d = 3 * bm.genus - 3 + bm.markings ->
    p.degree = 2 * d - bm.homologicalDegree ->
    p.weight = p.degree ->
    bm.weight = p.weight - 2 * d ->
    BorelMooreIsTwistOfPure bm p d
-- LEAN-AXIOM poincare_duality_bm_twist => LC66-OBL-09 -- packet FND-0001: rational Poincare duality for the smooth separated finite-type Deligne-Mumford stack M_{g,n} of complex dimension d = 3g-3+n gives an isomorphism of mixed Hodge structures W_{k-2d} H^BM_{2d-k}(M_{g,n};Q) = (W_k H^k(M_{g,n};Q))(d).  The duality twist is forced to be the dimension and nothing else

axiom tate_twist_shift_add : forall (a b u : Int),
    u = a + b ->
    TateTwistShift a b u
-- LEAN-AXIOM tate_twist_shift_add => LC66-OBL-09 -- the Tate twist convention Q(a)(b) = Q(a+b), which at a = -13 and b = 21 is Q(-13)(21) = Q(8)

axiom bm_tate_sum_from_twisted_pure :
    forall (bm : BMTargetIndex) (p : PureIndex) (d t u : Int),
    BorelMooreIsTwistOfPure bm p d ->
    PureIsFiniteTateSum p t ->
    TateTwistShift t d u ->
    bm.tateIndex = u ->
    BMIsFiniteTateSum bm
-- LEAN-AXIOM bm_tate_sum_from_twisted_pure => LC66-OBL-09 -- transporting an isomorphism W_k H^k = Q(t)^r through the duality twist by (d) gives W_weight H^BM_homologicalDegree(M_{g,n};Q) = Q(t)(d)^r = Q(bm.tateIndex)^r, so the exact Borel-Moore group named by bm is a finite direct sum of Q(bm.tateIndex), with r = 0 allowed

-- ---------------------------------------------------------------------------
-- The exported deduction.  ATT-0136 Sections 1-5 and 7-9.
-- ---------------------------------------------------------------------------

-- Standing facts shared by the base case and the inductive step.

theorem vcdMod6 : VirtualCohomologicalDimension moduliM6 19 :=
  harer_vcd_unpointed moduliM6 19 (by decide) (by decide) (by decide)

theorem vcdPMod65 : VirtualCohomologicalDimension moduliM65 25 :=
  harer_vcd_pointed moduliM65 25 (by decide) (by decide) (by decide)

theorem ordVanishM65deg26 : OrdinaryCohomologyVanishes moduliM65 26 :=
  constant_coefficient_vanishing_above_vcd moduliM65 25 26 vcdPMod65 (by decide)

theorem phiSpan26 :
    PhiSpannedByForgetfulPullbacks pureM66deg26 pureM65deg26 :=
  phi_is_pullback_span pureM66deg26 pureM65deg26 (by decide) (by decide) (by decide)
    (by decide)

theorem phiSpan24 :
    PhiSpannedByForgetfulPullbacks pureM66deg24 pureM65deg24 :=
  phi_is_pullback_span pureM66deg24 pureM65deg24 (by decide) (by decide) (by decide)
    (by decide)

theorem psiSpan26 : PsiSpannedByPsiMultiples pureM66deg26 pureM66deg24 :=
  psi_is_psi_multiple_span pureM66deg26 pureM66deg24 rfl (by decide) (by decide)

theorem omegaSlots : DualizingClassSlotDecomposition moduliM6 :=
  omega_class_slot_decomposition moduliM6 (by decide) (by decide)

theorem omegaSlotOne : SlotOneCrossTermVanishes moduliM6 :=
  morita_slot_one_vanishing moduliM6 (by decide) (by decide)

theorem ptyProjectorForm : RTwoProjectorInPsiAndPullbackSpan moduliM6 :=
  pty_r_two_projector_form moduliM6 (by decide) (by decide)

theorem omegaHitsSlotTwo : OmegaMultiplicationHitsSlotTwo moduliM6 :=
  omega_multiplication_hits_slot_two_modulo_errors moduliM6 omegaSlots omegaSlotOne
    ptyProjectorForm

theorem restrictionSurjection :
    RestrictionSurjectsOnLowestWeight sourceC6deg26 pureM66deg26 :=
  deligne_lowest_weight_restriction_surjection sourceC6deg26 pureM66deg26 rfl (by decide)
    (by decide) (by decide)

theorem kunnethSplitting :
    KunnethSplittingByChowKunnethProjectors sourceC6deg26 :=
  kunneth_splitting_of_pure_weight_source sourceC6deg26 moduliM6
    (deligne_smooth_proper_leray_degeneration moduliM6 (by decide) (by decide))
    (pty_projectors_are_algebraic_correspondences moduliM6 (by decide) (by decide))
    ptyProjectorForm (by decide) (by decide) (by decide)

theorem localCoeffVanish20 :
    LocalSystemCohomologyVanishesAllCoefficients moduliM6 20 :=
  local_coefficient_vanishing_above_vcd moduliM6 19 20 vcdMod6 (by decide) (by decide)

-- Combinatorics of the multi-index, PROVED by Lean rather than assumed: a list
-- of slots whose length is strictly below its total has an entry equal to two.
-- At n = 6 this is exactly ATT-0136 Section 5's step that every surviving
-- |i| >= 7 summand has some i_s = 2.

theorem total_split (pre : List Slot) (a : Slot) (post : List Slot) :
    total (pre ++ a :: post) = total pre + (slotVal a + total post) := by
  induction pre with
  | nil => simp [total]
  | cons b t ih =>
      show slotVal b + total (t ++ a :: post) = slotVal b + total t + _
      rw [ih]
      omega

theorem len_split (pre : List Slot) (a : Slot) (post : List Slot) :
    lenOf (pre ++ a :: post) = lenOf pre + (1 + lenOf post) := by
  induction pre with
  | nil => simp [lenOf]
  | cons b t ih =>
      show 1 + lenOf (t ++ a :: post) = 1 + lenOf t + _
      rw [ih]
      omega

theorem exists_two_of_len_lt_total : forall (l : List Slot), lenOf l < total l ->
    Exists (fun pre => Exists (fun post => l = pre ++ Slot.two :: post)) := by
  intro l
  induction l with
  | nil => intro h; exact absurd h (by decide)
  | cons a t ih =>
      intro h
      cases a with
      | two => exact Exists.intro [] (Exists.intro t rfl)
      | zero =>
          have hh : 1 + lenOf t < 0 + total t := h
          exact Exists.elim (ih (by omega)) (fun pre hp =>
            Exists.elim hp (fun post hq =>
              Exists.intro (Slot.zero :: pre) (Exists.intro post (by rw [hq]; rfl))))
      | one =>
          have hh : 1 + lenOf t < 1 + total t := h
          exact Exists.elim (ih (by omega)) (fun pre hp =>
            Exists.elim hp (fun post hq =>
              Exists.intro (Slot.one :: pre) (Exists.intro post (by rw [hq]; rfl))))

-- Base case: total fibre degree at most six puts the base degree 26 - |i| at
-- 20 or above, strictly over vcd(Mod_6) = 19, for every rational local system.

theorem baseCaseVanishes (idx : KunnethIndex) (hb : idx.base = moduliM6)
    (hd : idx.degree = 26) (hm : total idx.slots <= 6) : KunnethSummandVanishes idx := by
  have hgt : (19 : Int) < idx.degree - (total idx.slots : Int) := by omega
  have hvcd : VirtualCohomologicalDimension idx.base 19 := by rw [hb]; exact vcdMod6
  have hcoeff : LocalSystemCohomologyVanishesAllCoefficients idx.base
      (idx.degree - (total idx.slots : Int)) :=
    local_coefficient_vanishing_above_vcd idx.base 19
      (idx.degree - (total idx.slots : Int)) hvcd
      (by rw [hb]; show (0 : Int) = 0; rfl) hgt
  exact kunneth_summand_vanishes_below_base_degree idx 19 hcoeff hvcd hgt

-- The downward induction of ATT-0136 Section 5, on the total fibre degree.
-- Lean performs the recursion; no axiom asserts its conclusion.

theorem summandAux : forall (fuel : Nat) (idx : KunnethIndex),
    total idx.slots <= fuel -> idx.base = moduliM6 -> idx.degree = 26 ->
    idx.weight = 26 -> lenOf idx.slots = 6 ->
    KunnethSummandRestrictsIntoPsi idx pureM66deg26 := by
  intro fuel
  induction fuel with
  | zero =>
      intro idx hf hb hd _ _
      exact vanishing_summand_restricts_into_psi idx pureM66deg26
        (baseCaseVanishes idx hb hd (by omega))
  | succ f ih =>
      intro idx hf hb hd hw hl
      by_cases hm : total idx.slots <= 6
      · exact vanishing_summand_restricts_into_psi idx pureM66deg26
          (baseCaseVanishes idx hb hd hm)
      · have hlt : lenOf idx.slots < total idx.slots := by omega
        refine Exists.elim (exists_two_of_len_lt_total idx.slots hlt) ?_
        intro pre hp
        refine Exists.elim hp ?_
        intro post hsplit
        have hsub : KunnethSummandRestrictsIntoPsi
            { base := idx.base, slots := pre ++ Slot.one :: post,
              degree := idx.degree, weight := idx.weight } pureM66deg26 := by
          refine ih _ ?_ hb hd hw ?_
          · show total (pre ++ Slot.one :: post) <= f
            rw [total_split]
            have hb2 : total idx.slots = total pre + (2 + total post) := by
              rw [hsplit, total_split]; rfl
            show total pre + (slotVal Slot.one + total post) <= f
            show total pre + (1 + total post) <= f
            omega
          · show lenOf (pre ++ Slot.one :: post) = 6
            rw [len_split]
            have hl2 : lenOf idx.slots = lenOf pre + (1 + lenOf post) := by
              rw [hsplit, len_split]
            omega
        exact slot_two_summand_restricts_into_psi_modulo_errors idx
          { base := idx.base, slots := pre ++ Slot.zero :: post,
            degree := idx.degree, weight := idx.weight }
          { base := idx.base, slots := pre ++ Slot.one :: post,
            degree := idx.degree, weight := idx.weight }
          pre post pureM66deg26 sourceC6deg26 pureM66deg24 pureM65deg24 moduliM65
          hsplit rfl rfl rfl rfl rfl rfl rfl rfl (by rw [hb]; exact omegaHitsSlotTwo)
          restrictionSurjection psiSpan26 phiSpan24 (by decide) (by decide) rfl
          ordVanishM65deg26 hsub

theorem summandRestrictsIntoPsi (idx : KunnethIndex) (hb : idx.base = moduliM6)
    (hd : idx.degree = pureM66deg26.degree) (hw : idx.weight = pureM66deg26.weight)
    (hl : lenOf idx.slots = 6) :
    KunnethSummandRestrictsIntoPsi idx pureM66deg26 :=
  summandAux (total idx.slots) idx (Nat.le_refl _) hb hd hw hl

-- Section 5 conclusion, transferred along the Section 1 surjection.

theorem containedInPsi : ContainedInPsi pureM66deg26 :=
  containment_transfers_along_surjection sourceC6deg26 pureM66deg26 moduliM6
    restrictionSurjection summandRestrictsIntoPsi kunnethSplitting

-- Section 7: CKgP at 5 = c(6) types W_24 H^24(M_{6,5};Q) as Q(-12).

theorem tateM65deg24 : PureIsFiniteTateSum pureM65deg24 (-12) :=
  algebraic_pure_weight_is_tate pureM65deg24 12
    (cycle_class_surjectivity_from_ckgp moduliM65 pureM65deg24
      (ckgp_holds_in_range moduliM65 5 ckgp_marking_bound_genus_six (by decide)) rfl
      (by decide))
    (lowest_weight_is_pure_polarizable pureM65deg24 (by decide)) (by decide) (by decide)

-- LC66-OBL-06, the optional Section 6 route.  Nothing below consumes it as a
-- source of containment or of Hodge type.

theorem optionalEqualsPsi : EqualsPsi pureM66deg26 :=
  equality_from_vanishing_primitive_quotient_and_phi pureM66deg26
    (primitive_quotient_vanishes_from_local_coefficients pureM66deg26 primitiveM6deg20
      (clp_primitive_quotient_formula pureM66deg26 primitiveM6deg20 (by decide)
        (by decide) (by decide) (by decide) (by decide) (by decide) (by decide))
      localCoeffVanish20)
    (phi_vanishes_from_pullback_source pureM66deg26 pureM65deg26 phiSpan26
      ordVanishM65deg26)

-- The two routes side by side.  The LEFT component is the required Section 1-5
-- Kuenneth / downward-induction containment; the RIGHT component is the
-- optional published primitive-quotient equality of Section 6.  Everything
-- downstream projects the LEFT component only, so the optional route is present
-- in the axiom closure (the campaign requires every declared axiom to occur in
-- #print axioms) yet is strictly non-load-bearing: deleting the right conjunct
-- and using containedInPsi directly leaves the proof of the exported theorem
-- unchanged, and no Hodge-type conclusion passes through it.

theorem containmentRequiredAndOptionalEquality :
    ContainedInPsi pureM66deg26 /\ EqualsPsi pureM66deg26 :=
  And.intro containedInPsi optionalEqualsPsi

-- Section 8: psi-products and semisimplicity, from the LEFT (required) route.

theorem ordinaryTate : PureIsFiniteTateSum pureM66deg26 (-13) :=
  polarizable_semisimplicity_upgrade pureM66deg26 (-13)
    (And.left containmentRequiredAndOptionalEquality)
    (lowest_weight_is_pure_polarizable pureM66deg26 (by decide))
    (psi_products_are_tate_quotient pureM66deg26 pureM66deg24 (-1) (-12) (-13) psiSpan26
      (psi_class_is_tate_divisor moduliM66 (by decide))
      (phi_tate_from_pullback_source pureM66deg24 pureM65deg24 (-12) phiSpan24
        tateM65deg24)
      (by decide) (by decide) (by decide))

-- Section 9: Poincare duality in dimension 3*6-3+6 = 21 and Q(-13)(21) = Q(8).

theorem c66_exact_bm_is_finite_tate_sum : BMIsFiniteTateSum exactC66BMTarget :=
  bm_tate_sum_from_twisted_pure exactC66BMTarget pureM66deg26 21 (-13) 8
    (poincare_duality_bm_twist exactC66BMTarget pureM66deg26 21 (by decide) (by decide)
      (by decide) (by decide) (by decide) (by decide))
    ordinaryTate (tate_twist_shift_add (-13) 21 8 (by decide)) (by decide)

#print axioms c66_exact_bm_is_finite_tate_sum
