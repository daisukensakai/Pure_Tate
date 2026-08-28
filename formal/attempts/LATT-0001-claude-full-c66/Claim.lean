set_option autoImplicit false
-- LEAN-CAMPAIGN LC66-001
-- LEAN-ATTEMPT LATT-0001
-- LEAN-SOURCE-ATTEMPT ATT-0135
-- LEAN-CLAIM-CONTRACT C66-EXACT-TARGET-V1
-- LEAN-TARGET-SIGNATURE BM(g=6,n=6,degree=16,weight=-16,tate=8);ORD(g=6,n=6,degree=26,weight=26,tate=-13,dimension=21,twist=21);rank>=0
-- LEAN-THEOREM c66_exact_bm_is_finite_tate_sum
-- LEAN-WEIGHT All mathematical weight sits in the twenty-five LC66-OBL axioms; the twenty-three VOCAB axioms are uninterpreted carriers that assert nothing. Lean itself checks only the deduction and the index arithmetic, and the index arithmetic is where this attempt is not vacuous: every numeric side condition below is discharged by decide on Int, so Lean verifies 4*6-5=19 < 20 = 26-6 (OBL-02), 4*6-4+5=25 < 26 (OBL-03), 5 <= c(6)=5 (OBL-04), 24=2*12 with Tate index -12, -13 = -1 + -12 (OBL-05), 3*6-3+6=21, 26 = 2*21-16, -16 = 26-2*21 and 8 = -13+21 (OBL-06). Lean does not and cannot check that a carrier denotes the intended cohomology group or that an axiom states its cited theorem; that is the reviewers' burden.

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
-- partition size and duality twist that occurs in ATT-0135 is carried by an
-- Int field of one of these records, so Lean, not a comment, checks the
-- bookkeeping at each application site.
-- ---------------------------------------------------------------------------

structure ModuliIndex where
  genus : Int
  markings : Int

structure PureIndex where
  space : ModuliIndex
  degree : Int
  weight : Int

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

-- The primitive slot: W_26 H^20(M_6;V_lambda) with |lambda| = 6, degree 20 = 26 - 6.

def primitiveM6deg20 : LocalSystemIndex :=
  { genus := 6, degree := 20, weight := 26, partitionSize := 6 }

-- ---------------------------------------------------------------------------
-- Uninterpreted vocabulary.  These axioms declare carriers only.  None of them
-- asserts anything, and none of them is a proposition; their semantic reading
-- is review-audited exactly as BMIsFiniteTateSum is.
-- ---------------------------------------------------------------------------

axiom PhiSpannedByForgetfulPullbacks : PureIndex -> PureIndex -> Prop
-- LEAN-AXIOM PhiSpannedByForgetfulPullbacks => VOCAB -- carrier: Phi_{g,n}^k, the sum over the n forgetful maps pi_i of the pullbacks pi_i^* of the pure group W_k H^k(M_{g,n-1};Q) named by the second index, taken inside the pure group named by the first index

axiom PsiSpannedByPsiMultiples : PureIndex -> PureIndex -> Prop
-- LEAN-AXIOM PsiSpannedByPsiMultiples => VOCAB -- carrier: Psi_{g,n}^k, the sum over i of psi_i times Phi_{g,n}^{k-2}, the second index naming the degree-(k-2) pure group on the same stack whose Phi is multiplied

axiom PrimitiveQuotientIsLocalSystemSum : PureIndex -> LocalSystemIndex -> Prop
-- LEAN-AXIOM PrimitiveQuotientIsLocalSystemSum => VOCAB -- carrier: the quotient W_k H^k(M_{g,n};Q)/(Phi_{g,n}^k + Psi_{g,n}^k) is isomorphic as a pure weight-k Hodge structure to the direct sum over partitions lambda with |lambda| = partitionSize of W_weight H^degree(M_genus;V_lambda) tensor V_{lambda transpose}

axiom PrimitiveQuotientVanishes : PureIndex -> Prop
-- LEAN-AXIOM PrimitiveQuotientVanishes => VOCAB -- carrier: the quotient W_k H^k(M_{g,n};Q)/(Phi_{g,n}^k + Psi_{g,n}^k) is the zero Hodge structure

axiom LocalSystemCohomologyVanishes : LocalSystemIndex -> Prop
-- LEAN-AXIOM LocalSystemCohomologyVanishes => VOCAB -- carrier: H^degree(M_genus;V_lambda) = 0 for every irreducible rational symplectic local system V_lambda with |lambda| = partitionSize, hence every weight-graded piece of it is zero

axiom OrdinaryCohomologyVanishes : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM OrdinaryCohomologyVanishes => VOCAB -- carrier: H^d(M_{g,n};Q) = 0 in the given degree d, with constant rational coefficients

axiom SpannedByPhiAndPsi : PureIndex -> Prop
-- LEAN-AXIOM SpannedByPhiAndPsi => VOCAB -- carrier: W_k H^k(M_{g,n};Q) = Phi_{g,n}^k + Psi_{g,n}^k as subspaces of the ambient cohomology

axiom PhiVanishes : PureIndex -> Prop
-- LEAN-AXIOM PhiVanishes => VOCAB -- carrier: Phi_{g,n}^k = 0

axiom SpannedByPsi : PureIndex -> Prop
-- LEAN-AXIOM SpannedByPsi => VOCAB -- carrier: W_k H^k(M_{g,n};Q) = Psi_{g,n}^k as subspaces of the ambient cohomology

axiom PureIsFiniteTateSum : PureIndex -> Int -> Prop
-- LEAN-AXIOM PureIsFiniteTateSum => VOCAB -- carrier: the whole group W_weight H^degree(M_{g,n};Q) is isomorphic as a rational Hodge structure to a finite direct sum Q(t)^r with r >= 0 and t the given Tate index

axiom PhiIsFiniteTateSum : PureIndex -> Int -> Prop
-- LEAN-AXIOM PhiIsFiniteTateSum => VOCAB -- carrier: the subspace Phi_{g,n}^k is isomorphic to a finite direct sum Q(t)^a with a >= 0

axiom PsiIsQuotientOfFiniteTateSum : PureIndex -> Int -> Prop
-- LEAN-AXIOM PsiIsQuotientOfFiniteTateSum => VOCAB -- carrier: Psi_{g,n}^k is a quotient of a finite direct sum of Q(t); this is strictly weaker than being isomorphic to such a sum and is what the cup-product construction supplies before semisimplicity is invoked

axiom BorelMooreIsTwistOfPure : BMTargetIndex -> PureIndex -> Int -> Prop
-- LEAN-AXIOM BorelMooreIsTwistOfPure => VOCAB -- carrier: W_weight H^BM_homologicalDegree(M_{g,n};Q) is isomorphic as a mixed Hodge structure to the Tate twist by the third argument of the pure group named by the second index

axiom TateTwistShift : Int -> Int -> Int -> Prop
-- LEAN-AXIOM TateTwistShift => VOCAB -- carrier: Q(a)(b) = Q(c) for the three given Tate indices a, b, c

axiom PsiClassIsAlgebraicOfTateType : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM PsiClassIsAlgebraicOfTateType => VOCAB -- carrier: on M_{g,n} every psi_i is an algebraic class spanning a copy of Q(t) for the given Tate index t

axiom ChowKunnethGenerationProperty : ModuliIndex -> Prop
-- LEAN-AXIOM ChowKunnethGenerationProperty => VOCAB -- carrier: M_{g,n} has the Chow-Kuenneth generation property and A^*(M_{g,n}) = R^*(M_{g,n})

axiom CkgpMarkingBound : Int -> Int -> Prop
-- LEAN-AXIOM CkgpMarkingBound => VOCAB -- carrier: c(genus) equals the second argument, the largest marking count for which the Chow-Kuenneth generation theorem is recorded in that genus

axiom CycleClassMapSurjectsOntoPureWeight : PureIndex -> Prop
-- LEAN-AXIOM CycleClassMapSurjectsOntoPureWeight => VOCAB -- carrier: the cycle class map from algebraic cycles of codimension degree/2 surjects onto the lowest-weight group W_degree H^degree(M_{g,n};Q)

axiom VirtualCohomologicalDimension : ModuliIndex -> Int -> Prop
-- LEAN-AXIOM VirtualCohomologicalDimension => VOCAB -- carrier: the virtual cohomological dimension of the mapping class group of the given moduli index equals the second argument

axiom DualizingClassSlotDecomposition : ModuliIndex -> Prop
-- LEAN-AXIOM DualizingClassSlotDecomposition => VOCAB -- carrier: on the fibre power of the closed universal curve over M_g the class omega_s = pr_s^* c_1(omega_{C/M_g}) decomposes as a_s + b_s + c_s, with a_s in H^2(M_g;Q) in Kuenneth slot 0, b_s in H^1(M_g;V) in slot 1, and c_s the R^2 component in slot 2 with coefficient 2g-2

axiom SlotOneComponentVanishes : ModuliIndex -> Prop
-- LEAN-AXIOM SlotOneComponentVanishes => VOCAB -- carrier: the slot-1 cross term b_s of omega_s is zero, equivalently H^1(M_g;V) = 0 for the rational weight-one symplectic local system V

axiom PsiSpansSlotTwoModuloSlotZero : ModuliIndex -> Prop
-- LEAN-AXIOM PsiSpansSlotTwoModuloSlotZero => VOCAB -- carrier: multiplication by psi_s carries the Kuenneth summands with slot s equal to 0 onto those with slot s equal to 2, modulo summands having some slot equal to 0, with no residual slot-1 error term

-- ---------------------------------------------------------------------------
-- LC66-OBL-01.  The pure-weight finite-generation quotient formula, with Phi
-- and Psi given by their definitions and with the omega_s slot-1 cross term
-- disposed of rather than ignored (REV-0184 strongest attack).
-- ---------------------------------------------------------------------------

axiom phi_is_pullback_span : forall (p q : PureIndex),
    q.space.genus = p.space.genus ->
    q.space.markings = p.space.markings - 1 ->
    q.degree = p.degree ->
    q.weight = p.weight ->
    PhiSpannedByForgetfulPullbacks p q
-- LEAN-AXIOM phi_is_pullback_span => LC66-OBL-01 -- the definition Phi_{g,n}^k := sum_i pi_i^* W_k H^k(M_{g,n-1};Q), the n forgetful maps dropping one marking and preserving degree and weight; asserts only that this is what Phi denotes

axiom psi_is_psi_multiple_span : forall (p r : PureIndex),
    r.space = p.space ->
    r.degree = p.degree - 2 ->
    r.weight = p.weight - 2 ->
    PsiSpannedByPsiMultiples p r
-- LEAN-AXIOM psi_is_psi_multiple_span => LC66-OBL-01 -- the definition Psi_{g,n}^k := sum_i psi_i Phi_{g,n}^{k-2} on the same stack, the multiplication raising degree and weight by two; asserts only that this is what Psi denotes

axiom omega_class_slot_decomposition : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    DualizingClassSlotDecomposition base
-- LEAN-AXIOM omega_class_slot_decomposition => LC66-OBL-01 -- for g >= 2 the class omega_s on the fibre power of the closed universal curve over M_g is not Kuenneth-homogeneous: omega_s = a_s + b_s + c_s with slot-0, slot-1 and slot-2 parts, and only c_s, of coefficient 2g-2, induces the slot-0 to slot-2 isomorphism

axiom morita_slot_one_vanishing : forall (base : ModuliIndex),
    2 <= base.genus ->
    base.markings = 0 ->
    SlotOneComponentVanishes base
-- LEAN-AXIOM morita_slot_one_vanishing => LC66-OBL-01 -- Morita's computation H^1(Mod_g;H_1(Sigma_g;Z)) = Z/(2g-2) gives H^1(M_g;V) = 0 with rational coefficients for g >= 2, so the slot-1 cross term b_s of omega_s vanishes identically

axiom psi_multiplication_spans_slot_two : forall (base : ModuliIndex),
    DualizingClassSlotDecomposition base ->
    SlotOneComponentVanishes base ->
    PsiSpansSlotTwoModuloSlotZero base
-- LEAN-AXIOM psi_multiplication_spans_slot_two => LC66-OBL-01 -- given the three-slot decomposition and b_s = 0 one has omega_s = a_s + c_s exactly, so multiplying a slot-0 summand by psi_s yields the wanted slot-2 class plus a slot-0 error and nothing else; this is the repaired form of the abbreviated psi-restricts-to-the-canonical-class sentence of ATT-0135 Section 1

axiom clp_pure_weight_quotient_formula :
    forall (p q r : PureIndex) (base : ModuliIndex) (prim : LocalSystemIndex),
    2 <= p.space.genus ->
    1 <= p.space.markings ->
    p.degree = p.weight ->
    base.genus = p.space.genus ->
    base.markings = 0 ->
    PhiSpannedByForgetfulPullbacks p q ->
    PsiSpannedByPsiMultiples p r ->
    PsiSpansSlotTwoModuloSlotZero base ->
    prim.genus = p.space.genus ->
    prim.degree = p.degree - p.space.markings ->
    prim.weight = p.weight ->
    prim.partitionSize = p.space.markings ->
    PrimitiveQuotientIsLocalSystemSum p prim
-- LEAN-AXIOM clp_pure_weight_quotient_formula => LC66-OBL-01 -- the Canning-Larson-Payne pure-weight finite-generation formula, reproved in ATT-0135 Section 1 from the lowest-weight surjection out of a smooth compactification of the fibre power of the closed universal curve, Deligne degeneration with the Deninger-Murre relative Chow-Kuenneth splitting, and symplectic Schur-Weyl: for g >= 2 and n >= 1 the quotient of W_k H^k(M_{g,n};Q) by Phi + Psi is the direct sum over |lambda| = n of W_k H^{k-n}(M_g;V_lambda) tensor V_{lambda transpose}.  It concludes nothing about vanishing, Tate type or the Borel-Moore group

-- ---------------------------------------------------------------------------
-- LC66-OBL-02.  First vcd vanishing: local coefficients on M_6, degree 20
-- strictly above vcd(Mod_6) = 19.
-- ---------------------------------------------------------------------------

axiom harer_vcd_unpointed : forall (base : ModuliIndex) (v : Int),
    2 <= base.genus ->
    base.markings = 0 ->
    v = 4 * base.genus - 5 ->
    VirtualCohomologicalDimension base v
-- LEAN-AXIOM harer_vcd_unpointed => LC66-OBL-02 -- Harer's virtual cohomological dimension formula vcd(Mod_g) = 4g-5 for the unmarked mapping class group in genus g >= 2

axiom local_system_vanishing_above_vcd :
    forall (base : ModuliIndex) (v : Int) (prim : LocalSystemIndex),
    VirtualCohomologicalDimension base v ->
    base.markings = 0 ->
    prim.genus = base.genus ->
    v < prim.degree ->
    LocalSystemCohomologyVanishes prim
-- LEAN-AXIOM local_system_vanishing_above_vcd => LC66-OBL-02 -- a torsion-free normal finite-index subgroup Gamma of Mod_g has cd(Gamma) = vcd(Mod_g), hence H^p(Gamma;M) = 0 for every p above vcd and every rational coefficient module M; rational Hochschild-Serre for the finite quotient then gives H^p(Mod_g;V_lambda) = H^p(Gamma;V_lambda)^{Mod_g/Gamma} = 0.  This is genuine local-coefficient vanishing, not a transfer of constant-coefficient vanishing

axiom primitive_quotient_vanishes_from_local_systems :
    forall (p : PureIndex) (prim : LocalSystemIndex),
    PrimitiveQuotientIsLocalSystemSum p prim ->
    LocalSystemCohomologyVanishes prim ->
    PrimitiveQuotientVanishes p
-- LEAN-AXIOM primitive_quotient_vanishes_from_local_systems => LC66-OBL-02 -- every summand of the right-hand side of the quotient formula is a weight-graded piece of a local-system cohomology group that is zero, and a direct sum of zero Hodge structures is zero, so the primitive quotient vanishes

axiom span_from_vanishing_primitive_quotient : forall (p : PureIndex),
    PrimitiveQuotientVanishes p ->
    SpannedByPhiAndPsi p
-- LEAN-AXIOM span_from_vanishing_primitive_quotient => LC66-OBL-02 -- a zero quotient by Phi + Psi says exactly that W_k H^k(M_{g,n};Q) equals Phi_{g,n}^k + Psi_{g,n}^k

-- ---------------------------------------------------------------------------
-- LC66-OBL-03.  Second, logically distinct vcd vanishing: constant
-- coefficients on M_{6,5}, degree 26 strictly above vcd(PMod_{6,5}) = 25.
-- ---------------------------------------------------------------------------

axiom harer_vcd_pointed : forall (base : ModuliIndex) (v : Int),
    2 <= base.genus ->
    1 <= base.markings ->
    v = 4 * base.genus - 4 + base.markings ->
    VirtualCohomologicalDimension base v
-- LEAN-AXIOM harer_vcd_pointed => LC66-OBL-03 -- Harer's formula vcd(PMod_{g,n}) = 4g-4+n for the pure mapping class group of a genus g >= 2 surface with n >= 1 marked points

axiom ordinary_vanishing_above_vcd : forall (base : ModuliIndex) (v d : Int),
    VirtualCohomologicalDimension base v ->
    v < d ->
    OrdinaryCohomologyVanishes base d
-- LEAN-AXIOM ordinary_vanishing_above_vcd => LC66-OBL-03 -- rational cohomology of M_{g,n} with constant coefficients vanishes strictly above the virtual cohomological dimension, by the same torsion-free finite-index and rational Hochschild-Serre argument

axiom phi_vanishes_from_pullback_source : forall (p q : PureIndex),
    PhiSpannedByForgetfulPullbacks p q ->
    OrdinaryCohomologyVanishes q.space q.degree ->
    PhiVanishes p
-- LEAN-AXIOM phi_vanishes_from_pullback_source => LC66-OBL-03 -- Phi_{g,n}^k is a sum of pullback images of subspaces of H^k(M_{g,n-1};Q), so it is zero as soon as that ambient group is zero

axiom psi_spans_after_phi_vanishes : forall (p : PureIndex),
    SpannedByPhiAndPsi p ->
    PhiVanishes p ->
    SpannedByPsi p
-- LEAN-AXIOM psi_spans_after_phi_vanishes => LC66-OBL-03 -- combining W_k H^k = Phi + Psi with Phi = 0 gives W_k H^k = Psi, which is equation (5) of ATT-0135

-- ---------------------------------------------------------------------------
-- LC66-OBL-04.  CKgP at n = 5 = c(6), algebraicity, and Q(-12).
-- ---------------------------------------------------------------------------

axiom ckgp_marking_bound_genus_six : CkgpMarkingBound 6 5
-- LEAN-AXIOM ckgp_marking_bound_genus_six => LC66-OBL-04 -- the verified theorem THM-0005 records c(6) = 5 as the marking bound of the Chow-Kuenneth generation range in genus 6; it says nothing about n = 6

axiom ckgp_holds_in_range : forall (base : ModuliIndex) (b : Int),
    CkgpMarkingBound base.genus b ->
    base.markings <= b ->
    ChowKunnethGenerationProperty base
-- LEAN-AXIOM ckgp_holds_in_range => LC66-OBL-04 -- THM-0005: the open moduli stack M_{g,n} has the Chow-Kuenneth generation property and tautological Chow ring for every marking count at most c(g)

axiom cycle_class_surjectivity_from_ckgp : forall (base : ModuliIndex) (p : PureIndex),
    ChowKunnethGenerationProperty base ->
    p.space = base ->
    p.degree = p.weight ->
    CycleClassMapSurjectsOntoPureWeight p
-- LEAN-AXIOM cycle_class_surjectivity_from_ckgp => LC66-OBL-04 -- SRC-0002 Lemma 4.3 with Proposition 4.5: the Chow-Kuenneth generation property implies that the cycle class map surjects onto every lowest-weight group W_k H^k of the open moduli stack

axiom algebraic_pure_weight_is_tate : forall (p : PureIndex) (c : Int),
    CycleClassMapSurjectsOntoPureWeight p ->
    p.degree = 2 * c ->
    p.weight = p.degree ->
    PureIsFiniteTateSum p (-c)
-- LEAN-AXIOM algebraic_pure_weight_is_tate => LC66-OBL-04 -- a lowest-weight group spanned by classes of algebraic cycles of codimension c consists of classes of Hodge type (c,c), so it is a finite direct sum of Q(-c); finiteness holds because the rational cohomology of a finite-type stack is finite dimensional.  Only the algebraic-implies-Tate direction is used

-- ---------------------------------------------------------------------------
-- LC66-OBL-05.  The psi-product construction and the semisimplicity upgrade
-- from a Tate quotient to the whole group.
-- ---------------------------------------------------------------------------

axiom phi_tate_from_pullback_source : forall (p q : PureIndex) (t : Int),
    PhiSpannedByForgetfulPullbacks p q ->
    PureIsFiniteTateSum q t ->
    PhiIsFiniteTateSum p t
-- LEAN-AXIOM phi_tate_from_pullback_source => LC66-OBL-05 -- Phi is a sum of images of W_k H^k(M_{g,n-1};Q) under forgetful pullbacks, which are morphisms of mixed Hodge structures of type (0,0), so a Q(t)-sum source gives a Q(t)-sum image

axiom psi_class_is_tate_divisor : forall (base : ModuliIndex),
    1 <= base.markings ->
    PsiClassIsAlgebraicOfTateType base (-1)
-- LEAN-AXIOM psi_class_is_tate_divisor => LC66-OBL-05 -- for n >= 1 each psi_i on M_{g,n} is an algebraic codimension-one class and therefore spans a copy of Q(-1) in W_2 H^2

axiom psi_products_are_tate_quotient : forall (p r : PureIndex) (a b t : Int),
    PsiSpannedByPsiMultiples p r ->
    PsiClassIsAlgebraicOfTateType p.space a ->
    PhiIsFiniteTateSum r b ->
    p.degree = r.degree + 2 ->
    p.weight = r.weight + 2 ->
    t = a + b ->
    PsiIsQuotientOfFiniteTateSum p t
-- LEAN-AXIOM psi_products_are_tate_quotient => LC66-OBL-05 -- the cup-product maps Q(a) tensor Phi_{g,n}^{k-2} -> W_k H^k(M_{g,n};Q) have images that are finite direct sums of Q(a+b), and Psi_{g,n}^k is by definition the sum of those images, so Psi is a quotient of a finite direct sum of Q(a+b).  Only a quotient is claimed here

axiom polarizable_semisimplicity_upgrade : forall (p : PureIndex) (t : Int),
    SpannedByPsi p ->
    PsiIsQuotientOfFiniteTateSum p t ->
    PureIsFiniteTateSum p t
-- LEAN-AXIOM polarizable_semisimplicity_upgrade => LC66-OBL-05 -- because W_k H^k(M_{g,n};Q) equals Psi and is pure and polarizable of weight k, semisimplicity of polarizable pure rational Hodge structures of a fixed weight turns the quotient presentation into an isomorphism with Q(t)^r for a finite r >= 0; the conclusion is about the whole group, not a subquotient, associated graded or semisimplification

-- ---------------------------------------------------------------------------
-- LC66-OBL-06.  Poincare duality in complex dimension 21 and the Tate twist
-- Q(-13)(21) = Q(8), landing on the exact Borel-Moore target.
-- ---------------------------------------------------------------------------

axiom poincare_duality_bm_twist : forall (bm : BMTargetIndex) (p : PureIndex) (d : Int),
    bm.genus = p.space.genus ->
    bm.markings = p.space.markings ->
    d = 3 * bm.genus - 3 + bm.markings ->
    p.degree = 2 * d - bm.homologicalDegree ->
    p.weight = p.degree ->
    bm.weight = p.weight - 2 * d ->
    BorelMooreIsTwistOfPure bm p d
-- LEAN-AXIOM poincare_duality_bm_twist => LC66-OBL-06 -- rational Poincare duality for the smooth separated Deligne-Mumford stack M_{g,n} of complex dimension d = 3g-3+n gives an isomorphism of mixed Hodge structures W_{k-2d} H^BM_{2d-k}(M_{g,n};Q) = (W_k H^k(M_{g,n};Q))(d); it fixes the duality twist to be the dimension and nothing else

axiom tate_twist_shift_add : forall (a b u : Int),
    u = a + b ->
    TateTwistShift a b u
-- LEAN-AXIOM tate_twist_shift_add => LC66-OBL-06 -- the Tate twist convention Q(a)(b) = Q(a+b), which at a = -13 and b = 21 is Q(-13)(21) = Q(8)

axiom bm_tate_sum_from_twisted_pure :
    forall (bm : BMTargetIndex) (p : PureIndex) (d t u : Int),
    BorelMooreIsTwistOfPure bm p d ->
    PureIsFiniteTateSum p t ->
    TateTwistShift t d u ->
    bm.tateIndex = u ->
    BMIsFiniteTateSum bm
-- LEAN-AXIOM bm_tate_sum_from_twisted_pure => LC66-OBL-06 -- transporting an isomorphism W_k H^k = Q(t)^r through the duality twist by (d) gives W_weight H^BM_homologicalDegree(M_{g,n};Q) = Q(t)(d)^r = Q(tateIndex)^r, so the exact Borel-Moore group named by bm is a finite direct sum of Q(bm.tateIndex), with r = 0 allowed

-- ---------------------------------------------------------------------------
-- The exported deduction.  Steps 1-6 of ATT-0135, in order.
-- ---------------------------------------------------------------------------

theorem c66_exact_bm_is_finite_tate_sum : BMIsFiniteTateSum exactC66BMTarget := by
  -- Step 1a.  Phi and Psi at (6,6), by their definitions.
  have hPhi26 : PhiSpannedByForgetfulPullbacks pureM66deg26 pureM65deg26 :=
    phi_is_pullback_span pureM66deg26 pureM65deg26 (by decide) (by decide) (by decide)
      (by decide)
  have hPsi26 : PsiSpannedByPsiMultiples pureM66deg26 pureM66deg24 :=
    psi_is_psi_multiple_span pureM66deg26 pureM66deg24 rfl (by decide) (by decide)
  -- Step 1b.  The omega_s repair of REV-0184: expose the slot-1 cross term and
  -- kill it before the psi-multiple step is used.
  have hSlots : DualizingClassSlotDecomposition moduliM6 :=
    omega_class_slot_decomposition moduliM6 (by decide) (by decide)
  have hSlotOne : SlotOneComponentVanishes moduliM6 :=
    morita_slot_one_vanishing moduliM6 (by decide) (by decide)
  have hSlotTwo : PsiSpansSlotTwoModuloSlotZero moduliM6 :=
    psi_multiplication_spans_slot_two moduliM6 hSlots hSlotOne
  -- Step 1c.  The quotient formula at (g,n,k) = (6,6,26); primitive slot degree
  -- 26 - 6 = 20 on M_6, weight 26, |lambda| = 6.
  have hQuot : PrimitiveQuotientIsLocalSystemSum pureM66deg26 primitiveM6deg20 :=
    clp_pure_weight_quotient_formula pureM66deg26 pureM65deg26 pureM66deg24 moduliM6
      primitiveM6deg20 (by decide) (by decide) (by decide) (by decide) (by decide)
      hPhi26 hPsi26 hSlotTwo (by decide) (by decide) (by decide) (by decide)
  -- Step 2.  vcd(Mod_6) = 4*6-5 = 19 < 20, so the primitive quotient vanishes.
  have hVcd6 : VirtualCohomologicalDimension moduliM6 19 :=
    harer_vcd_unpointed moduliM6 19 (by decide) (by decide) (by decide)
  have hLocalZero : LocalSystemCohomologyVanishes primitiveM6deg20 :=
    local_system_vanishing_above_vcd moduliM6 19 primitiveM6deg20 hVcd6 (by decide)
      (by decide) (by decide)
  have hPrimZero : PrimitiveQuotientVanishes pureM66deg26 :=
    primitive_quotient_vanishes_from_local_systems pureM66deg26 primitiveM6deg20 hQuot
      hLocalZero
  have hPhiPsi : SpannedByPhiAndPsi pureM66deg26 :=
    span_from_vanishing_primitive_quotient pureM66deg26 hPrimZero
  -- Step 3.  vcd(PMod_{6,5}) = 4*6-4+5 = 25 < 26, so Phi_{6,6}^{26} = 0.
  have hVcd65 : VirtualCohomologicalDimension moduliM65 25 :=
    harer_vcd_pointed moduliM65 25 (by decide) (by decide) (by decide)
  have hOrdZero : OrdinaryCohomologyVanishes moduliM65 26 :=
    ordinary_vanishing_above_vcd moduliM65 25 26 hVcd65 (by decide)
  have hPhiZero : PhiVanishes pureM66deg26 :=
    phi_vanishes_from_pullback_source pureM66deg26 pureM65deg26 hPhi26 hOrdZero
  have hPsiAll : SpannedByPsi pureM66deg26 :=
    psi_spans_after_phi_vanishes pureM66deg26 hPhiPsi hPhiZero
  -- Step 4.  CKgP at 5 = c(6): W_24 H^24(M_{6,5};Q) is a finite sum of Q(-12).
  have hCkgp : ChowKunnethGenerationProperty moduliM65 :=
    ckgp_holds_in_range moduliM65 5 ckgp_marking_bound_genus_six (by decide)
  have hCycle : CycleClassMapSurjectsOntoPureWeight pureM65deg24 :=
    cycle_class_surjectivity_from_ckgp moduliM65 pureM65deg24 hCkgp rfl (by decide)
  have hTate65 : PureIsFiniteTateSum pureM65deg24 (-12) :=
    algebraic_pure_weight_is_tate pureM65deg24 12 hCycle (by decide) (by decide)
  -- Step 4b/5.  Phi_{6,6}^{24} is a Q(-12)-sum; psi_i is Q(-1); Psi is a
  -- quotient of a Q(-13)-sum; semisimplicity makes the whole group a Q(-13)-sum.
  have hPhi24 : PhiSpannedByForgetfulPullbacks pureM66deg24 pureM65deg24 :=
    phi_is_pullback_span pureM66deg24 pureM65deg24 (by decide) (by decide) (by decide)
      (by decide)
  have hPhiTate : PhiIsFiniteTateSum pureM66deg24 (-12) :=
    phi_tate_from_pullback_source pureM66deg24 pureM65deg24 (-12) hPhi24 hTate65
  have hPsiClass : PsiClassIsAlgebraicOfTateType moduliM66 (-1) :=
    psi_class_is_tate_divisor moduliM66 (by decide)
  have hPsiQuot : PsiIsQuotientOfFiniteTateSum pureM66deg26 (-13) :=
    psi_products_are_tate_quotient pureM66deg26 pureM66deg24 (-1) (-12) (-13) hPsi26
      hPsiClass hPhiTate (by decide) (by decide) (by decide)
  have hOrdTate : PureIsFiniteTateSum pureM66deg26 (-13) :=
    polarizable_semisimplicity_upgrade pureM66deg26 (-13) hPsiAll hPsiQuot
  -- Step 6.  Poincare duality in dimension 3*6-3+6 = 21 and Q(-13)(21) = Q(8).
  have hDual : BorelMooreIsTwistOfPure exactC66BMTarget pureM66deg26 21 :=
    poincare_duality_bm_twist exactC66BMTarget pureM66deg26 21 (by decide) (by decide)
      (by decide) (by decide) (by decide) (by decide)
  have hTwist : TateTwistShift (-13) 21 8 := tate_twist_shift_add (-13) 21 8 (by decide)
  exact bm_tate_sum_from_twisted_pure exactC66BMTarget pureM66deg26 21 (-13) 8 hDual
    hOrdTate hTwist (by decide)

#print axioms c66_exact_bm_is_finite_tate_sum
