from dataclasses import dataclass, field
from typing import Any, Dict, List


RESEARCH_STATUSES = (
    "discovered",
    "extracted",
    "source_verified",
    "cross_checked",
)
TRUTH_STATUSES = ("conjectural", "established", "inferred", "refuted", "retired")
CLAIM_KINDS = (
    "definition",
    "theorem",
    "lemma",
    "conjecture",
    "observation",
    "reduction",
    "computation",
    "counterexample",
)
EDGE_TYPES = (
    "requires",
    "reduces",
    "strengthens",
    "conditional_on",
    "contradicts",
    "supersedes",
    "covers",
)


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    authors: List[str]
    year: int
    kind: str
    arxiv_id: str
    arxiv_version: str
    doi: str
    url: str
    publication_status: str
    submitted_on: str
    revised_on: str
    published_on: str
    checked_on: str
    supersedes: List[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Source":
        return cls(**value)


@dataclass(frozen=True)
class Locator:
    source_id: str
    locator: str
    evidence_note: str

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Locator":
        return cls(**value)


@dataclass(frozen=True)
class Claim:
    id: str
    kind: str
    title: str
    statement: str
    scope: Dict[str, Any]
    source_ids: List[str]
    locators: List[Locator]
    depends_on: List[str]
    verification_status: str
    truth_status: str
    conditional: bool
    confidence: str
    updated_on: str
    notes: str = ""

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Claim":
        prepared = dict(value)
        prepared["locators"] = [
            Locator.from_dict(item) for item in prepared.get("locators", [])
        ]
        return cls(**prepared)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    note: str

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Edge":
        prepared = dict(value)
        prepared["source"] = prepared.pop("from")
        prepared["target"] = prepared.pop("to")
        return cls(**prepared)


@dataclass(frozen=True)
class CaseResult:
    degree: int
    genus: int
    markings: int
    stable: bool
    required_by_vanishing_bound: bool
    covered: bool
    coverage_reason: str

    @property
    def label(self) -> str:
        return "M_{%d,%d}" % (self.genus, self.markings)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "degree": self.degree,
            "g": self.genus,
            "n": self.markings,
            "stable": self.stable,
            "required_by_vanishing_bound": self.required_by_vanishing_bound,
            "covered": self.covered,
            "coverage_reason": self.coverage_reason,
        }


@dataclass
class CheckResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "CheckResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

