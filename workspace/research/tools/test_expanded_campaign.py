import unittest
from expanded_campaign import detail


class DetailTests(unittest.TestCase):
    def test_reward_delta_and_resource_event_provenance(self):
        events = [
            {"event_type": "TASK_VALIDATED", "payload": {"rewards": [0, 0, 0, 0, 12], "fire_active": True}},
            {"event_type": "ACTION_COMPLETED", "event_id": 7, "agent_id": "1", "action_id": "t0-agent1",
             "payload": {"action": [3, 1, 2], "verified_local_delta": {"resources": {
                 "before": {"water": 0}, "after": {"water": 5}}}}},
            {"event_type": "TASK_VALIDATED", "payload": {"rewards": [0, 0, 0, 0, 16], "fire_active": False}}
        ]
        result = detail(events)
        self.assertEqual(result["reward_delta"][4], 4)
        self.assertEqual(result["resource_transitions"][0]["event_id"], 7)
        self.assertFalse(result["final_fire_active"])

    def test_empty_evidence_not_fabricated(self):
        result = detail([])
        self.assertIsNone(result["reward_delta"])
        self.assertIsNone(result["final_fire_active"])
        self.assertEqual(result["resource_transitions"], [])

    def test_fire_clear_requires_prior_observed_ignition(self):
        def validation(event_id, active):
            return {"event_id": event_id, "event_type": "TASK_VALIDATED", "payload": {
                "observation_phase": "after_action", "fire_active": active, "rewards": [0]*13}}
        self.assertFalse(detail([validation(1, False)])["final_observed_clear_after_ignition"])
        result = detail([validation(1, False), validation(2, True), validation(3, False)])
        self.assertTrue(result["final_observed_clear_after_ignition"])
        self.assertEqual(result["first_observed_clear_after_ignition_event"], 3)


if __name__ == "__main__":
    unittest.main()
