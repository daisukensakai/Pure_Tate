from typing import Any, Dict, List, Optional, Tuple

from .models import CaseResult


def is_stable(genus: int, markings: int) -> bool:
    return genus >= 0 and markings >= 0 and 2 * genus - 2 + markings > 0


def required_by_low_homology_bound(degree: int, genus: int, markings: int) -> bool:
    if markings in (0, 1):
        return degree >= 2 * genus
    return degree >= 2 * genus - 2 + markings


def coverage_reason(
    degree: int, genus: int, markings: int, config: Dict[str, Any]
) -> Tuple[bool, str]:
    if genus == 0:
        return True, "genus-zero cohomology is tautological"
    if genus == 1 and degree % 2 == 0:
        return True, "all genus-one even cohomology is tautological"
    genus_two_max = int(
        config["known_special_coverage"]["genus_two_even_max_degree"]
    )
    if genus == 2 and degree % 2 == 0 and degree <= genus_two_max:
        return True, "genus-two even cohomology is tautological through degree %d" % (
            genus_two_max
        )
    raw_bound: Optional[int] = config["ckgp_marking_bounds"].get(str(genus))
    if str(genus) in config["ckgp_marking_bounds"]:
        if raw_bound is None:
            return True, "published CKgP range is unrestricted"
        if markings <= int(raw_bound):
            return True, "published CKgP range n<=%d" % int(raw_bound)
    return False, "outside the recorded CKgP and special-genus ranges"


def enumerate_reduction_cases(
    degree: int, config: Dict[str, Any]
) -> List[CaseResult]:
    if degree < 0:
        raise ValueError("degree must be nonnegative")
    results: List[CaseResult] = []
    # The inequalities imply g<=degree/2 for n=0,1 and n<=degree+2 at g=0.
    max_genus = degree // 2
    max_markings = degree + 2
    for genus in range(max_genus + 1):
        for markings in range(max_markings + 1):
            stable = is_stable(genus, markings)
            required = stable and required_by_low_homology_bound(
                degree, genus, markings
            )
            if not required:
                continue
            covered, reason = coverage_reason(degree, genus, markings, config)
            results.append(
                CaseResult(
                    degree=degree,
                    genus=genus,
                    markings=markings,
                    stable=stable,
                    required_by_vanishing_bound=required,
                    covered=covered,
                    coverage_reason=reason,
                )
            )
    return results


def unresolved_cases(degree: int, config: Dict[str, Any]) -> List[CaseResult]:
    return [
        result
        for result in enumerate_reduction_cases(degree, config)
        if not result.covered
    ]


def compact_pairs(results: List[CaseResult]) -> List[Tuple[int, int]]:
    return [(result.genus, result.markings) for result in results]

