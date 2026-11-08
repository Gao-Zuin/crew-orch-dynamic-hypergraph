"""Tests for the cross-group message/action spatial response proxy."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "bottom_up_reports"))
from analyze_message_action_alignment import close, max_persistence, score  # noqa: E402


class MessageActionAlignmentTests(unittest.TestCase):
    def test_chebyshev_radius(self):
        self.assertTrue(close((74, 66), (70, 70), 4))
        self.assertFalse(close((76, 70), (70, 70), 5))

    def test_new_alignment_requires_absence_in_previous_step(self):
        message = {"event_id": 1, "step": 4, "source": "a", "target": "b",
                   "members": ("2",), "coords": ((70.0, 70.0),)}
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


if __name__ == "__main__":
    unittest.main()
