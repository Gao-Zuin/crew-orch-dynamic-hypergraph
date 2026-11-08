import importlib.util
from pathlib import Path
import sys
import unittest


REPORTS = Path(__file__).parents[1] / "research/bottom_up_reports"
sys.path.insert(0, str(REPORTS))
MODULE = REPORTS / "analyze_target_responsibility_shadow.py"
SPEC = importlib.util.spec_from_file_location("target_responsibility_shadow", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class TargetResponsibilityShadowTests(unittest.TestCase):
    def test_task_parser_separates_primary_conditional_and_scout(self):
        targets = {(1, 2), (3, 4)}
        self.assertEqual(AUDIT.task_assignment("Cut trees at (1,2), then (3,4)", targets),
                         {"primary": [(1, 2), (3, 4)], "conditional": []})
        self.assertEqual(AUDIT.task_assignment(
            "Cut (1,2) only if team A releases it; otherwise scout", targets),
            {"primary": [], "conditional": [(1, 2)]})
        self.assertEqual(AUDIT.task_assignment("Scout toward (1,2)", targets),
                         {"primary": [], "conditional": []})

    def test_index_detects_primary_collision(self):
        edges = [{"id": "a", "tasks": {"1": "Cut (1,2)", "2": "Cut (1,2)"}}]
        index = AUDIT.index_graph(edges, {(1, 2)})
        snap = AUDIT.snapshot_index(index)
        self.assertIn("1,2", snap["primary_collisions"])
        self.assertEqual(AUDIT.ownership_class(index, (1, 2), "1"), "OWN_PRIMARY")
        self.assertEqual(AUDIT.ownership_class(index, (1, 2), "3"), "OTHER_PRIMARY_OWNER")

    def test_recent_message_evidence_requires_coordinate_and_assignment_language(self):
        messages = {"2": [
            {"step": 4, "content": "You take (8,26) and verify it.", "event_id": 1},
            {"step": 5, "content": "I saw water near (9,28).", "event_id": 2},
        ]}
        self.assertEqual(len(AUDIT.recent_message_evidence(messages, "2", (8, 26), 7)), 1)
        self.assertEqual(AUDIT.recent_message_evidence(messages, "2", (9, 28), 7), [])


if __name__ == "__main__":
    unittest.main()
