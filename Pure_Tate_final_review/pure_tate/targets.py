from dataclasses import dataclass
from typing import Any, Dict


CONTEXT_REVISION = 2
COMPACT_COHOMOLOGY_DEGREE = 16


@dataclass(frozen=True)
class OpenInputTarget:
    genus: int
    markings: int
    dimension: int
    compact_cohomology_degree: int
    compact_tate_type: str
    open_bm_degree: int
    open_bm_weight: int
    open_bm_tate_type: str
    ordinary_cohomology_degree: int
    ordinary_weight: int
    ordinary_tate_type: str
    poincare_twist: int
    chow_codimension: int

    @property
    def case_id(self) -> str:
        return "CASE-%d-%d" % (self.genus, self.markings)

    @property
    def packet_id(self) -> str:
        return "%s-v%d" % (self.case_id, CONTEXT_REVISION)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "g": self.genus,
            "n": self.markings,
            "dimension": self.dimension,
            "compact_cohomology_degree": self.compact_cohomology_degree,
            "compact_tate_type": self.compact_tate_type,
            "open_bm_degree": self.open_bm_degree,
            "open_bm_weight": self.open_bm_weight,
            "open_bm_tate_type": self.open_bm_tate_type,
            "ordinary_cohomology_degree": self.ordinary_cohomology_degree,
            "ordinary_weight": self.ordinary_weight,
            "ordinary_tate_type": self.ordinary_tate_type,
            "poincare_twist": self.poincare_twist,
            "chow_codimension": self.chow_codimension,
        }


def open_input_target(
    genus: int,
    markings: int,
    compact_degree: int = COMPACT_COHOMOLOGY_DEGREE,
) -> OpenInputTarget:
    if genus < 0 or markings < 0 or 2 * genus - 2 + markings <= 0:
        raise ValueError("open-input target requires a stable pair")
    if compact_degree < 0 or compact_degree % 2:
        raise ValueError("compact degree must be a nonnegative even integer")
    dimension = 3 * genus - 3 + markings
    ordinary_degree = 2 * dimension - compact_degree
    if ordinary_degree < 0 or ordinary_degree % 2:
        raise ValueError("ordinary dual degree must be nonnegative and even")
    codimension = ordinary_degree // 2
    return OpenInputTarget(
        genus=genus,
        markings=markings,
        dimension=dimension,
        compact_cohomology_degree=compact_degree,
        compact_tate_type="Q(-%d)" % (compact_degree // 2),
        open_bm_degree=compact_degree,
        open_bm_weight=-compact_degree,
        open_bm_tate_type="Q(%d)" % (compact_degree // 2),
        ordinary_cohomology_degree=ordinary_degree,
        ordinary_weight=ordinary_degree,
        ordinary_tate_type="Q(-%d)" % codimension,
        poincare_twist=dimension,
        chow_codimension=codimension,
    )


def target_formula(target: OpenInputTarget) -> str:
    return (
        "W_{-%d}H^{BM}_{%d}(M_{%d,%d}) = "
        "W_{%d}H^{%d}(M_{%d,%d})(%d)"
        % (
            target.open_bm_degree,
            target.open_bm_degree,
            target.genus,
            target.markings,
            target.ordinary_weight,
            target.ordinary_cohomology_degree,
            target.genus,
            target.markings,
            target.poincare_twist,
        )
    )
