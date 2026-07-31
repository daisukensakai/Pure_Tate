import unittest

from pure_tate.reports import case_report, obstruction_report
from pure_tate.store import load_repository


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config, _target, _sources, cls.claims, _edges = load_repository()

    def test_obstruction_report_names_gate_and_cases(self):
        report = obstruction_report(self.config, self.claims)
        self.assertIn("Stage 2: **UNBLOCKED**", report)
        self.assertIn("\\mathcal M_{3,12}", report)
        self.assertIn("\\mathcal M_{8,2}", report)

    def test_degree_14_report_has_no_unresolved_pairs(self):
        report = case_report(14, self.config)
        self.assertIn("- Unresolved: 0", report)


if __name__ == "__main__":
    unittest.main()

