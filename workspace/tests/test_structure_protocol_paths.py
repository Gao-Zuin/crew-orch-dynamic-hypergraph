"""Protocol-level checks for anticipatory versus reactive regrouping."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "structure_calibration"))
from protocol_paths import analyze  # noqa: E402


class StructureProtocolPathTests(unittest.TestCase):
    def test_real_graph_paths_separate_center_and_worker_delivery(self):
        result = analyze()
        fixed = result["fixed"]
        adaptive = result["adaptive_pre_shared"]
        self.assertEqual(fixed["worker_deliveries"], 3)
        self.assertEqual(fixed["leader_deliveries"], 2)
        self.assertEqual(fixed["center_deliveries"], 2)
        self.assertEqual(adaptive["worker_deliveries"], 1)
        self.assertEqual(adaptive["leader_deliveries"], 1)
        # The shared drone remains a non-leader, so topology does not shorten
        # its legal route to the organizer.
        self.assertEqual(adaptive["center_deliveries"], 2)
        self.assertTrue(fixed["worker_path_can_cascade_same_immediate_round"])
        self.assertTrue(fixed["center_path_can_cascade_same_immediate_round"])

    def test_reactive_regroup_cannot_beat_fixed_center_binding(self):
        timeline = analyze()["causal_timelines"]
        self.assertEqual(timeline["fixed_center_task_binding"], 2)
        self.assertEqual(timeline["adaptive_reactive_peer_delivery"], 3)
        self.assertLess(timeline["adaptive_pre_shared_peer_delivery"],
                        timeline["fixed_center_task_binding"])

    def test_hop_reduction_is_a_reliability_hypothesis_not_measured_effect(self):
        sensitivity = analyze()["independent_hop_success_sensitivity"]
        row = next(item for item in sensitivity if item["per_message_success"] == 0.7)
        self.assertEqual(row["fixed_peer_chain"], 0.343)
        self.assertEqual(row["fixed_center_chain_before_planner"], 0.49)
        self.assertEqual(row["adaptive_pre_shared_peer_chain"], 0.7)


if __name__ == "__main__":
    unittest.main()
