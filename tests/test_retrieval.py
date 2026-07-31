import unittest

from pure_tate.graph import ClaimGraph
from pure_tate.retrieval import compile_packet, search_claims
from pure_tate.store import load_repository


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _target, cls.sources, cls.claims, cls.edges = load_repository()
        cls.graph = ClaimGraph(cls.claims, cls.edges)

    def test_packet_is_dependency_closed_and_ready(self):
        packet = compile_packet(
            "RED-0001",
            self.claims,
            self.sources,
            self.graph,
            int(self.config["proof_packet_claim_limit"]),
            int(self.config["proof_packet_source_limit"]),
        )
        self.assertIn("Stage-2 readiness: **READY**", packet)
        self.assertIn("THM-0004", packet)
        self.assertIn("SRC-0002", packet)
        self.assertIn("Do not replace the stack", packet)

    def test_packet_limit_fails_closed(self):
        with self.assertRaises(ValueError):
            compile_packet(
                "RED-0001",
                self.claims,
                self.sources,
                self.graph,
                2,
                20,
            )

    def test_lexical_search(self):
        results = search_claims("degree 16 obstruction", self.claims)
        self.assertTrue(results)
        self.assertIn(results[0].id, {"RED-0001", "CONJ-0001", "OBS-0001"})


if __name__ == "__main__":
    unittest.main()

