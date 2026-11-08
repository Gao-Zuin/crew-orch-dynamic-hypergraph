import importlib.util
from pathlib import Path
import sys
import unittest


REPORTS = Path(__file__).parents[1] / "research/bottom_up_reports"
sys.path.insert(0, str(REPORTS))
MODULE = REPORTS / "derive_responsibility_events.py"
SPEC = importlib.util.spec_from_file_location("derive_responsibility_events", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ResponsibilityEventTests(unittest.TestCase):
    def test_direct_and_arrow_assignments(self):
        targets = {(8, 26), (9, 28), (10, 27)}
        parsed = AUDIT.leader_assignments(
            "Assignments: 2→(8,26). You take (9,28),(10,27).", "3", "1", targets)
        self.assertEqual(parsed["2"], [(8, 26)])
        self.assertEqual(parsed["3"], [(9, 28), (10, 27)])

    def test_negative_directive_is_not_assignment(self):
        parsed = AUDIT.leader_assignments(
            "Do not go to (8,26); avoid (9,28).", "3", "1", {(8, 26), (9, 28)})
        self.assertEqual(parsed, {})

    def test_broadcast_does_not_apply_youless_take_to_every_recipient(self):
        parsed = AUDIT.leader_assignments(
            "Then take (8,26).", "3", "1", {(8, 26)}, allow_direct=False)
        self.assertEqual(parsed, {})

    def test_named_directive(self):
        parsed = AUDIT.leader_assignments(
            "AGENT_3: move to (12,31) and verify it.", "3", "1", {(12, 31)})
        self.assertEqual(parsed, {"3": [(12, 31)]})

    def test_explanatory_coordinates_are_not_swallowed(self):
        text = ("AGENT_5: after confirming it, please take (21,42) as proposed — "
                "that keeps you clear of my (20,33) and AGENT_2's (17,43)/(14,42).")
        parsed = AUDIT.leader_assignments(
            text, "5", "1", {(21, 42), (20, 33), (17, 43), (14, 42)})
        self.assertEqual(parsed, {"5": [(21, 42)]})

    def test_continuation_confirmation(self):
        parsed = AUDIT.leader_assignments(
            "After you verify (20,49) is clear, proceed to (22,50).",
            "8", "6", {(20, 49), (22, 50)})
        self.assertEqual(parsed, {"8": [(20, 49), (22, 50)]})

    def test_leader_self_assignment_not_given_to_named_agent_or_recipient(self):
        text = "AGENT_5 handles (21,42), and I take (12,31),(20,33),(27,30)."
        parsed = AUDIT.leader_assignments(
            text, "6", "1", {(21, 42), (12, 31), (20, 33), (27, 30)})
        self.assertEqual(parsed, {"1": [(12, 31), (20, 33), (27, 30)]})


if __name__ == "__main__":
    unittest.main()
