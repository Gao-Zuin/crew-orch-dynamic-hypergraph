import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).parents[1] / "research/bottom_up_reports/analyze_cut_tree_false_prerequisites.py"
SPEC = importlib.util.spec_from_file_location("cut_tree_false_prerequisites", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class CutTreeFalsePrerequisiteTests(unittest.TestCase):
    def test_sequence_and_false_necessity_are_distinct(self):
        self.assertTrue(AUDIT.REFILL_CUT_SEQUENCE.search(
            "Refill at (10,10), then cut (12,12)."))
        self.assertFalse(AUDIT.FALSE_NECESSITY.search(
            "Refill at (10,10), then cut (12,12)."))
        self.assertTrue(AUDIT.FALSE_NECESSITY.search(
            "Do not cut until you have water."))
        self.assertTrue(AUDIT.FALSE_NECESSITY.search(
            "I have no water and cannot cut this tree."))
        self.assertFalse(AUDIT.FALSE_NECESSITY.search(
            "Do not cut (26,44); report any fire or water."))

    def test_fixed_horizon_carries_terminal_progress(self):
        self.assertEqual(AUDIT.fixed_horizon_auc([0, 2], 4, 4), 0.375)

    def test_cell_delta_requires_verified_change(self):
        event = {"payload": {"verified_local_delta": {"facts": {
            "before": {"current_cell": "2"}, "after": {"current_cell": "1"}}}}}
        self.assertEqual(AUDIT.cell_delta(event), 1)
        self.assertIsNone(AUDIT.cell_delta({"payload": {}}))


if __name__ == "__main__":
    unittest.main()
