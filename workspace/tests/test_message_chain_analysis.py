"""Regression tests for the uniform 15-run message-chain audit."""
from pathlib import Path
import json
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "bottom_up_reports"))
from analyze_message_chains import analyze_run, coordinates, typed_messages  # noqa: E402


class MessageChainAnalysisTests(unittest.TestCase):
    def test_tag_attributes_and_coordinates(self):
        messages = typed_messages('<LEADER edge="a" to="b">Fire at (70, 71)</LEADER>')
        self.assertEqual(messages[0]["attrs"], {"edge": "a", "to": "b"})
        self.assertEqual(coordinates(messages[0]["content"]), {"70,71"})

    def test_self_report_and_coordinate_relay_are_separate(self):
        events = [
            {"event_id": 1, "task_id": "x", "event_type": "TASK_GRAPH_COMMITTED",
             "payload": {"step": 0, "edges": [{"id": "a", "leader": "1", "members": ["1", "2"]}],
                         "proposal": {"active": {"1": "a", "2": "a"}}}},
            {"event_id": 2, "task_id": "x", "event_type": "COMMUNICATION_GENERATED", "agent_id": "1",
             "payload": {"timestep": 0, "raw_output": '<REPORT edge="a">At 1,2</REPORT>'}},
            {"event_id": 3, "task_id": "x", "event_type": "COMMUNICATION_GENERATED", "agent_id": "2",
             "payload": {"timestep": 0, "raw_output": '<REPORT edge="a">Fire at 70,71</REPORT>'}},
            {"event_id": 4, "task_id": "x", "event_type": "TASK_MESSAGE_DELIVERED",
             "payload": {"step": 0, "sender": "2", "recipient": "1", "message_type": "REPORT",
                         "content": "Fire at 70,71"}},
            {"event_id": 5, "task_id": "x", "event_type": "COMMUNICATION_GENERATED", "agent_id": "1",
             "payload": {"timestep": 0,
                         "raw_output": '<ORGANIZER edge="a">Confirmed fire at 70,71</ORGANIZER>'}},
            {"event_id": 6, "task_id": "x", "event_type": "TASK_LEADER_REPORT",
             "payload": {"step": 0, "sender": "1", "source": "a", "content": "Confirmed fire at 70,71"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
            result = analyze_run(path)
        self.assertEqual(result["generated_report_tags_silently_addressed_to_self"], 1)
        self.assertEqual(result["delivered_recipient_events"]["REPORT"], 1)
        self.assertEqual(result["coordinate_chain_proxy"]["coordinate_reports_preserved_outward"], 1)


if __name__ == "__main__":
    unittest.main()
