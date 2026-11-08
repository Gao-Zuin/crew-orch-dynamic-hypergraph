import json
from pathlib import Path
import tempfile
import unittest

from episode_timeline import read_events, render


class TimelineTests(unittest.TestCase):
    def test_after_action_not_claim_is_displayed(self):
        events = [
            dict(event_type="ACTION_STARTED", agent_id="7", payload=dict(timestep=4, action=[0,54,77])),
            dict(event_type="COMMUNICATION_GENERATED", agent_id="7", payload=dict(raw_output="drop complete")),
            dict(event_type="STATE_OBSERVED", agent_id="7", payload=dict(position=[29,37], resources={"firefighters_carried":5})),
            dict(event_type="TASK_VALIDATED", event_id=606, payload=dict(timestep=4, observation_phase="after_action", success=False, rewards=[0]*13)),
        ]
        result = render(events, agents=["7"])
        self.assertIn('[29, 37]', result)
        self.assertIn('"firefighters_carried": 5', result)
        self.assertIn('Run finished: False', result)
        self.assertNotIn('drop complete', result)

    def test_only_partial_final_line_is_tolerated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"events.jsonl"
            path.write_text('{"event_type":"TEST"}\n{')
            events, partial = read_events(path)
            self.assertEqual(len(events), 1)
            self.assertTrue(partial)
            path.write_text('{\n{"event_type":"TEST"}\n')
            with self.assertRaises(json.JSONDecodeError):
                read_events(path)


if __name__ == "__main__":
    unittest.main()
