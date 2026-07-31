import unittest

from pure_tate.graph import ClaimGraph
from pure_tate.models import Claim, Edge
from pure_tate.store import load_repository


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _config, _target, _sources, cls.claims, cls.edges = load_repository()

    def test_reduction_closure_is_dependency_first(self):
        graph = ClaimGraph(self.claims, self.edges)
        closure = graph.dependency_closure("RED-0001")
        self.assertEqual(closure[-1], "RED-0001")
        self.assertIn("THM-0003", closure)
        self.assertLess(closure.index("THM-0003"), closure.index("THM-0004"))

    def test_seed_graph_is_acyclic(self):
        graph = ClaimGraph(self.claims, self.edges)
        self.assertEqual(graph.cycles(), [])

    def test_cycle_is_detected(self):
        claim_a = Claim(
            id="LEM-9001",
            kind="lemma",
            title="a",
            statement="a",
            scope={},
            source_ids=[],
            locators=[],
            depends_on=["LEM-9002"],
            verification_status="extracted",
            truth_status="inferred",
            conditional=False,
            confidence="low",
            updated_on="2026-07-29",
        )
        claim_b = Claim(
            id="LEM-9002",
            kind="lemma",
            title="b",
            statement="b",
            scope={},
            source_ids=[],
            locators=[],
            depends_on=["LEM-9001"],
            verification_status="extracted",
            truth_status="inferred",
            conditional=False,
            confidence="low",
            updated_on="2026-07-29",
        )
        graph = ClaimGraph(
            {claim_a.id: claim_a, claim_b.id: claim_b},
            [
                Edge(claim_a.id, claim_b.id, "requires", "test"),
                Edge(claim_b.id, claim_a.id, "requires", "test"),
            ],
        )
        self.assertTrue(graph.cycles())


if __name__ == "__main__":
    unittest.main()

