import importlib.util
from pathlib import Path
import sys
import unittest


REPORTS = Path(__file__).parents[1] / "research/bottom_up_reports"
PAPER = Path(__file__).parents[1] / "research/orch_paper"
sys.path[:0] = [str(REPORTS), str(PAPER)]
MODULE = REPORTS / "run_responsibility_ledger_ab.py"
SPEC = importlib.util.spec_from_file_location("run_responsibility_ledger_ab", MODULE)
AB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AB)


class ResponsibilityLedgerABTests(unittest.TestCase):
    def test_frozen_cases_match_logged_actions(self):
        cases = {case["id"]: case for case in AB.frozen_cases()}
        self.assertEqual(len(cases), 3)
        self.assertEqual(cases["r3_stale_message_overridden_by_graph"]["logged_class"], "CUT")
        self.assertEqual(cases["r3_explicit_provisional_takeover"]["logged_class"], "CUT")
        self.assertEqual(cases["r2_unassigned_actor_against_owner"]["logged_class"], "CUT")

    def test_expected_controls_have_two_negatives_and_one_positive(self):
        self.assertEqual([case["expected"] for case in AB.CASE_SPECS],
                         ["AVOID_CUT", "CUT", "AVOID_CUT"])

    def test_reminder_preserves_provisional_takeover(self):
        positive = AB.CASE_SPECS[1]
        text = AB.reminder(positive)
        self.assertIn("may continue cutting", text)
        self.assertIn("does not forbid helping another group", text)

    def test_classifier(self):
        self.assertEqual(AB.classify("<action>Cut down a single tree</action>"), "CUT")
        self.assertEqual(AB.classify("<action>Move towards (21,43)</action>"), "AVOID_CUT")
        self.assertEqual(AB.classify("no action tag"), "UNPARSEABLE")


if __name__ == "__main__":
    unittest.main()
