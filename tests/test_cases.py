import unittest

from pure_tate.cases import (
    compact_pairs,
    enumerate_reduction_cases,
    is_stable,
    unresolved_cases,
)
from pure_tate.store import load_repository


class CaseReductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _target, _sources, _claims, _edges = load_repository()

    def test_stability(self):
        self.assertTrue(is_stable(0, 3))
        self.assertTrue(is_stable(1, 1))
        self.assertTrue(is_stable(2, 0))
        self.assertFalse(is_stable(0, 2))
        self.assertFalse(is_stable(1, 0))

    def test_degree_14_replay_closes(self):
        self.assertEqual(unresolved_cases(14, self.config), [])

    def test_degree_16_candidate_obstruction(self):
        self.assertEqual(
            compact_pairs(unresolved_cases(16, self.config)),
            [(3, 12), (5, 8), (6, 6), (7, 4), (8, 0), (8, 1), (8, 2)],
        )

    def test_only_stable_required_cases_are_enumerated(self):
        cases = enumerate_reduction_cases(16, self.config)
        self.assertTrue(cases)
        self.assertTrue(all(item.stable for item in cases))
        self.assertTrue(all(item.required_by_vanishing_bound for item in cases))

    def test_genus_one_and_two_are_discharged(self):
        unresolved = unresolved_cases(16, self.config)
        self.assertFalse(any(item.genus in (0, 1, 2) for item in unresolved))


if __name__ == "__main__":
    unittest.main()

