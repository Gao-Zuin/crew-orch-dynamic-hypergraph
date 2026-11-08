import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).parents[1] / "research/orch_paper/run_cut_tree_affordance_ab.py"
SPEC = importlib.util.spec_from_file_location("cut_tree_affordance_ab", MODULE)
AB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AB)


class CutTreeAffordanceABTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(AB.classify("<action>Cut down a tree</action>", [(11, 26)]), "CUT")
        self.assertEqual(AB.classify("<action>Refill water</action>", [(11, 26)]), "REFILL")
        self.assertEqual(AB.classify("<action>Move towards (11, 26)</action>", [(11, 26)]),
                         "MOVE_WATER_SOURCE")
        self.assertEqual(AB.classify("<action>Move towards (9, 28)</action>", [(11, 26)]),
                         "MOVE_OTHER")

    def test_contract_includes_both_checks(self):
        self.assertIn("does not require or consume water", AB.CONTRACT_HINT)
        self.assertIn("assigned or claimed by another agent", AB.CONTRACT_HINT)


if __name__ == "__main__":
    unittest.main()
