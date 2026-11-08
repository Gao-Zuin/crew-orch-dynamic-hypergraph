"""Tests for frozen action-prompt A/B replay helpers."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "orch_paper"))
from run_commitment_prompt_ab import classify_action, domain_aware_reminder  # noqa: E402


class CommitmentPromptABTests(unittest.TestCase):
    def test_action_classification(self):
        self.assertEqual(classify_action("<action>Move towards (8,24)</action>",
                                         (8, 24), (70, 70)), "MOVE_WATER_SOURCE")
        self.assertEqual(classify_action("<action>Move towards (70,70)</action>",
                                         (8, 24), (70, 70)), "MOVE_DOWNSTREAM_TARGET")
        self.assertEqual(classify_action("<action>Refill water</action>",
                                         (8, 24), (70, 70)), "REFILL")

    def test_domain_hint_rejects_positive_tank_top_up(self):
        text = domain_aware_reminder({"water": 2, "water_source": (8, 24),
                                      "target": (70, 70), "position": (27, 45)})
        self.assertIn("only when the tank is exactly 0", text)
        self.assertIn("Do not repeat refill", text)


if __name__ == "__main__":
    unittest.main()
