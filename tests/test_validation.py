import copy
import datetime
import unittest

from pure_tate.citation import audit_citations
from pure_tate.models import Edge
from pure_tate.store import load_repository
from pure_tate.validate import validate_repository


class ValidationTests(unittest.TestCase):
    def setUp(self):
        (
            self.config,
            self.target,
            self.sources,
            self.claims,
            self.edges,
        ) = load_repository()

    def test_seed_repository_is_structurally_green(self):
        result = validate_repository(
            self.config, self.target, self.sources, self.claims, self.edges
        )
        self.assertEqual(result.errors, [])

    def test_missing_typed_edge_is_error(self):
        edges = [
            edge
            for edge in self.edges
            if not (edge.source == "THM-0004" and edge.target == "THM-0003")
        ]
        result = validate_repository(
            self.config, self.target, self.sources, self.claims, edges
        )
        self.assertTrue(any("lacks a typed edge" in item for item in result.errors))

    def test_unknown_edge_endpoint_is_error(self):
        edges = self.edges + [Edge("RED-0001", "THM-9999", "requires", "bad")]
        result = validate_repository(
            self.config, self.target, self.sources, self.claims, edges
        )
        self.assertTrue(any("unknown claim" in item for item in result.errors))

    def test_seed_citations_are_green(self):
        result = audit_citations(
            self.sources,
            self.claims,
            int(self.config["citation_freshness_days"]),
            datetime.date(2026, 7, 29),
        )
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])

    def test_load_bearing_v3_page_locator_is_pinned(self):
        self.assertEqual(
            self.claims["THM-0003"].locators[0].locator,
            "Equation (6.1), page 24",
        )
        self.assertEqual(
            self.claims["THM-0004"].locators[0].locator,
            "Proof of Theorem 1.5(3), page 24",
        )

    def test_stale_citation_is_warning(self):
        result = audit_citations(
            self.sources,
            self.claims,
            1,
            datetime.date(2026, 8, 2),
        )
        self.assertTrue(any("stale" in item for item in result.warnings))


if __name__ == "__main__":
    unittest.main()
