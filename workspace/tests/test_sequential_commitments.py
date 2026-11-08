"""Tests for the narrow prerequisite/commitment trace audit."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "bottom_up_reports"))
from analyze_sequential_commitments import audit_run, mentioned_assignee  # noqa: E402


class SequentialCommitmentTests(unittest.TestCase):
    def test_broadcast_only_binds_named_recipient(self):
        text = "AGENT_2, after refilling at (8,24), head to (70,70). AGENT_3 continue patrol."
        self.assertTrue(mentioned_assignee(text, "2"))
        self.assertFalse(mentioned_assignee(text, "3"))

    def test_vague_after_refill_without_downstream_coordinate_is_excluded(self):
        text = "AGENT_2 and AGENT_3 refill and return staggered. I will cover after refill."
        self.assertFalse(mentioned_assignee(text, "3"))

    def test_real_trace_identifies_infeasible_positive_tank_top_up(self):
        path = "/data1/gzy/crew_ht_r2_pro_campaign_20261030/runs/pro_second_fire/run/events.jsonl"
        if not Path(path).exists():
            self.skipTest("campaign trace is not mounted")
        cases = audit_run(path, horizon=3)
        case = next(c for c in cases if c["event_id"] == 5226)
        self.assertEqual(case["initial_water"], 2)
        self.assertEqual(case["prerequisite_state_at_assignment"],
                         "INFEASIBLE_POSITIVE_TANK_TOP_UP")
        self.assertIn(68, case["downstream_action_before_refill_evidence_steps"])
        self.assertIsNone(case["refill_evidenced_step"])


if __name__ == "__main__":
    unittest.main()
