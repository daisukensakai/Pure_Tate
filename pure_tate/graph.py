from collections import defaultdict
from typing import Dict, Iterable, List, Set

from .models import Claim, Edge


class GraphError(ValueError):
    pass


class ClaimGraph:
    def __init__(self, claims: Dict[str, Claim], edges: Iterable[Edge]) -> None:
        self.claims = claims
        self.edges = list(edges)
        self.dependencies: Dict[str, List[str]] = {
            claim_id: list(claim.depends_on) for claim_id, claim in claims.items()
        }
        self.dependents: Dict[str, List[str]] = defaultdict(list)
        for claim_id, dependencies in self.dependencies.items():
            for dependency in dependencies:
                self.dependents[dependency].append(claim_id)

    def dependency_closure(self, claim_id: str) -> List[str]:
        if claim_id not in self.claims:
            raise GraphError("unknown claim %s" % claim_id)
        seen: Set[str] = set()
        ordered: List[str] = []

        def visit(current: str) -> None:
            if current in seen:
                return
            seen.add(current)
            for dependency in self.dependencies.get(current, []):
                visit(dependency)
            ordered.append(current)

        visit(claim_id)
        return ordered

    def cycles(self) -> List[List[str]]:
        state: Dict[str, int] = {}
        stack: List[str] = []
        found: List[List[str]] = []

        def visit(current: str) -> None:
            state[current] = 1
            stack.append(current)
            for dependency in self.dependencies.get(current, []):
                if dependency not in self.claims:
                    continue
                if state.get(dependency, 0) == 0:
                    visit(dependency)
                elif state.get(dependency) == 1:
                    start = stack.index(dependency)
                    found.append(stack[start:] + [dependency])
            stack.pop()
            state[current] = 2

        for claim_id in sorted(self.claims):
            if state.get(claim_id, 0) == 0:
                visit(claim_id)
        return found

    def edge_pairs(self) -> Set[tuple]:
        return {(edge.source, edge.target) for edge in self.edges}

