"""Tests for the cross-group message/action spatial response proxy."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "bottom_up_reports"))
from analyze_message_action_alignment import (  # noqa: E402
    close, distance_to_coords, leader_deliveries, max_persistence, score,
)


class MessageActionAlignmentTests(unittest.TestCase):
    def test_chebyshev_radius(self):
        self.assertTrue(close((74, 66), (70, 70), 4))
        self.assertFalse(close((76, 70), (70, 70), 5))

    def test_new_alignment_requires_absence_in_previous_step(self):
        message = {"event_id": 1, "step": 4, "source": "a", "target": "b",
                   "direct_recipient": "2", "members": ("2",),
                   "target_members": ("2",), "coords": ((70.0, 70.0),)}
        result = score([message], [message["coords"]],
                       {3: {"2": (10, 10)}, 4: {"2": (68, 70)}}, 3)
        self.assertEqual(result["new_alignment_count"], 1)
        repeated = score([message], [message["coords"]],
                         {3: {"2": (69, 70)}, 4: {"2": (68, 70)}}, 3)
        self.assertEqual(repeated["new_alignment_count"], 0)

    def test_persistence_counts_consecutive_aligned_actions(self):
        targets = {4: {"2": (70, 70)}, 5: {"2": (71, 70)},
                   6: {"2": (20, 20)}, 7: {"2": (70, 70)}}
        self.assertEqual(max_persistence(((70, 70),), ("2",), targets, 4, 2), 2)

    def test_distance_uses_nearest_message_coordinate(self):
        self.assertEqual(distance_to_coords((68, 72), ((10, 10), (70, 70))), 2)

    def test_only_direct_recipient_and_exact_coordinate_relay_are_informed(self):
        events = [
            {"event_id": 1, "event_type": "TASK_GRAPH_COMMITTED",
             "payload": {"edges": [{"id": "a", "members": ["1"], "leader": "1"},
                                    {"id": "b", "members": ["2", "3", "4"], "leader": "2"}]}},
            {"event_id": 2, "event_type": "TASK_MESSAGE_DELIVERED",
             "payload": {"step": 4, "message_type": "LEADER", "sender": "1", "recipient": "2",
                         "source": "a", "target": "b", "content": "Fire at 70,70"}},
            {"event_id": 3, "event_type": "TASK_MESSAGE_DELIVERED",
             "payload": {"step": 4, "message_type": "GROUP", "sender": "2", "recipient": "3",
                         "source": "b", "target": "b", "content": "Go to 70,70"}},
            {"event_id": 4, "event_type": "TASK_MESSAGE_DELIVERED",
             "payload": {"step": 4, "message_type": "GROUP", "sender": "2", "recipient": "4",
                         "source": "b", "target": "b", "content": "Continue your work"}},
        ]
        message = leader_deliveries(events)[0]
        self.assertEqual(message["members"], ("2", "3"))
        self.assertEqual(message["target_members"], ("2", "3", "4"))


if __name__ == "__main__":
    unittest.main()
