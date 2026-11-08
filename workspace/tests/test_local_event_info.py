"""The local-information arm must not broadcast future fire coordinates."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_task_runtime as fixtures
from crew_algorithms.wildfire_alg.coordination.runtime import RuntimeBridge
from crew_algorithms.wildfire_alg.coordination.soft_task_policy import SoftTaskPolicy


class LocalEventInfoTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {'CREW_HT_LOCAL_EVENT_INFO': '1'}):
            fixtures.TaskRuntimeTests.setUp(self)

    def test_proximity_cue_goes_only_to_nearby_worker_once(self):
        event = {'timestep': 8, 'action': 'start_fire', 'x': 80, 'y': 80}
        self.bridge.step = 8
        self.bridge.c.nodes = {
            '1': {'online': True, 'position': [79, 80]},
            '2': {'online': True, 'position': [20, 20]},
            '3': {'online': False, 'position': [80, 80]},
        }
        self.bridge._deliver_local_event_cues([event])
        self.bridge._deliver_local_event_cues([event])
        self.assertEqual(len(self.agents['1'].chat_history['ENVIRONMENT']), 1)
        self.assertNotIn('ENVIRONMENT', self.agents['2'].chat_history)
        self.assertNotIn('ENVIRONMENT', self.agents['3'].chat_history)
        self.assertEqual(self.bridge.c.events[-1]['event_type'], 'TASK_LOCAL_EVENT_CUE_DELIVERED')
        self.assertEqual(self.bridge.c.events[-1]['payload']['recipient'], '1')
        self.assertIn('80', self.bridge.communication_prompt('1', 'Communicate'))
        self.assertNotIn('80', json.dumps(self.bridge.graph.decision_state()))
        self.bridge.step = 9
        self.bridge.c.nodes['2']['position'] = [74, 80]
        self.bridge._deliver_local_event_cues([event])
        self.assertEqual(len(self.agents['2'].chat_history['ENVIRONMENT']), 1)

    def test_organizer_prompt_requires_worker_report_for_coordinate(self):
        event = {'timestep': 8, 'action': 'start_fire', 'x': 80, 'y': 80}
        self.bridge.step = 8
        self.world['step'] = 8
        self.bridge.graph.observe(self.world)
        with patch.object(RuntimeBridge, 'after_step'):
            self.bridge.after_step({}, list(self.agents.values()), {}, {'submitted_events': [event]})
        self.world.update(step=9, evidence_id=2)
        self.bridge.graph.observe(self.world)
        captured = []
        def transport(messages):
            captured.extend(messages)
            proposal = deepcopy(self.proposal)
            proposal.update(based_on_version=self.bridge.graph.version, evidence_id=2)
            return json.dumps(proposal), {'prompt_tokens': 10, 'completion_tokens': 5}
        policy = SoftTaskPolicy('test', 'unused', 'unused', self.bridge.c.emit, transport)
        data = {'api_calls': 0, 'input_tokens': 0, 'output_tokens': 0}
        self.assertTrue(policy.decide(self.bridge.graph, data))
        self.assertIn('obtain coordinates from worker reports', captured[0]['content'])
        self.assertNotIn('80', captured[1]['content'])

    def test_fire_coordinates_stay_out_of_center_and_downlink(self):
        event = {'timestep': 8, 'action': 'start_fire', 'x': 80, 'y': 80,
                 'announcement': 'A new fire at (80,80)!'}
        self.bridge.step = 8
        self.world['step'] = 8
        self.bridge.graph.observe(self.world)
        with patch.object(RuntimeBridge, 'after_step'):
            self.bridge.after_step({}, list(self.agents.values()), {}, {'submitted_events': [event]})
        notice = self.bridge.graph.environment_notices[-1]['event']
        self.assertEqual(notice['action'], 'fire_alert')
        self.assertNotIn('80', json.dumps(notice))
        self.assertNotIn('80', json.dumps(self.bridge.graph.decision_state()))
        self.assertTrue(self.bridge.graph.needs_plan())
        self.bridge.forwarded_notice_count = 0
        self.bridge.policy = None
        self.bridge.step = 9
        self.world.update(step=9, evidence_id=2)
        self.bridge.graph.observe(self.world)
        data = {'api_calls': 0, 'input_tokens': 0, 'output_tokens': 0,
                'game_data': {'task_description': 'Find the fire'}}
        with patch.object(RuntimeBridge, 'before_step'), patch.object(self.bridge, '_organize', return_value=False):
            self.bridge.before_step({}, list(self.agents.values()), data['game_data'], 9, data)
        for agent in self.agents.values():
            messages = agent.chat_history.get('ENVIRONMENT', [])
            self.assertEqual(len(messages), 1)
            self.assertNotIn('80', json.dumps(messages))
        self.assertTrue(any(e['event_type'] == 'TASK_EVENT_LOCATION_WITHHELD' for e in self.bridge.c.events))


if __name__ == '__main__':
    unittest.main()
