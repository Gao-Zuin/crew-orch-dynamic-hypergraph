"""Regressions from real HT-R2 traces: routing and proposed-action memory."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_task_runtime as fixtures
from crew_algorithms.wildfire_alg.algorithms.Embodied import utils
from crew_algorithms.wildfire_alg.coordination.task_guidance import orch_knowledge_context, observed_key_features
from crew_algorithms.wildfire_alg.coordination.soft_task_policy import SoftTaskPolicy


class RevisionTests(unittest.TestCase):
    setUp = fixtures.TaskRuntimeTests.setUp

    def test_original_knowledge_reaches_worker_and_actual_organizer_request(self):
        shared = orch_knowledge_context('Rescue_Civilians_Search_Rescue_Transport')
        for prompt in (self.bridge.prompt('2', '<action>one action</action>'),
                       self.bridge.communication_prompt('1', 'Communicate')):
            self.assertIn('Do not refill water until you are fully out of water.', prompt)
            self.assertIn('can pick up and deploy firefighters with civilians', prompt)
            self.assertIn('BULLDOZER:', prompt)
            self.assertIn('HELICOPTER:', prompt)
        captured = []
        def transport(messages):
            captured.extend(messages)
            proposal = deepcopy(self.proposal)
            proposal['based_on_version'] = self.bridge.graph.version
            return json.dumps(proposal), {'prompt_tokens': 1, 'completion_tokens': 1}
        policy = SoftTaskPolicy('test', 'unused', 'unused', self.bridge.c.emit, transport,
                                static_context=shared)
        self.bridge.graph.last_planned_step = -99
        self.assertTrue(policy.decide(self.bridge.graph,
                                     {'api_calls': 0, 'input_tokens': 0, 'output_tokens': 0}))
        self.assertIn(shared, captured[0]['content'])
        state = json.loads(captured[-1]['content'])
        self.assertFalse({'rewards', 'fire_active', 'events'} & state.keys())

    def test_feature_coordinates_use_grid_origin_without_inventing_visible_cells(self):
        text = observed_key_features('0,C,0\nw,0,0\n0,0,\'f\'', [10, 20], 3)
        self.assertIn('Civilians (1): (10, 19)', text)
        self.assertIn('Water sources (1): (9, 20)', text)
        self.assertIn('On Fire (1): (11, 21)', text)
        self.assertNotIn('region', text)

    def observe_worker(self, water=0):
        self.bridge.c.observe({"agent_id": "1", "task_id": self.bridge.c.task_id,
            "session_epoch": self.bridge.session, "observed_at": self.bridge.c.clock(),
            "resources": {"water": water}, "capabilities": ["navigate", "cut", "spray"],
            "position": [13, 49], "facts": {"agent_type": 0, "current_cell": "2"},
            "online": True})

    def test_api_latency_does_not_cancel_current_synchronous_step(self):
        clock = [100.0]
        self.bridge.c.clock = lambda: clock[0]
        self.observe_worker()
        clock[0] += 900
        self.assertFalse(self.bridge.c.fresh("1"))
        self.assertEqual(self.bridge.guard(self.agents['1'], [1, 0, 0], None), [1, 0, 0])
        self.assertFalse(any(e['event_type'] == 'TASK_ACTION_HELD' for e in self.bridge.c.events))

    def test_reassigned_worker_gets_current_routes_and_local_format_feedback(self):
        self.bridge.dispatch(self.agents['1'], '<GROUP edge="scout">old order</GROUP>', {})
        proposal = deepcopy(self.proposal)
        proposal['based_on_version'] = self.bridge.graph.version
        proposal['edges'][0]['members'] = ['1']
        proposal['active']['2'] = 'support'
        self.bridge.graph.apply(proposal)
        context = self.bridge.graph.context('2')
        self.assertEqual(context['leader'], '3')
        self.assertFalse(any('edge="scout"' in r for r in context['current_route_examples']))
        self.assertTrue(any('<REPORT edge="support">' in r for r in context['current_route_examples']))
        self.bridge.dispatch(self.agents['2'], '<GROUP edge="scout" to="1">old channel</GROUP>', {})
        self.assertIn('Not sent', self.agents['2'].chat_history['ENVIRONMENT'][-1][1])
        self.bridge.dispatch(self.agents['2'], '<REPORT edge="support">need old team help</REPORT>', {})
        self.assertIn('need old team help', self.agents['3'].chat_history['EDGE:support'][-1][1])
        self.assertFalse(any(e['event_type'] == 'TASK_ACTION_HELD' for e in self.bridge.c.events))

    def test_local_format_error_is_not_presented_as_public_mission_event(self):
        self.agents['2'].add_message('ENVIRONMENT', 'COMMUNICATION_FORMAT', 'Not sent: wrong group', 0)
        prompt = self.bridge.communication_prompt('2', 'Original chat includes local error')
        self.assertFalse(prompt.startswith('[RECENT PUBLIC NOTICES'))
        self.agents['2'].add_message('ENVIRONMENT', 'PUBLIC_ANNOUNCEMENT', 'New fire at 70,70', 0)
        prompt = self.bridge.communication_prompt('2', 'Original chat includes local error')
        self.assertTrue(prompt.startswith('[RECENT PUBLIC NOTICES'))
        self.assertIn('New fire at 70,70', prompt)

    def test_proposal_replaced_by_guard_is_not_recorded_as_executed(self):
        self.observe_worker(water=0)
        agent = self.agents['1']
        agent.cfg = SimpleNamespace(envs=SimpleNamespace(llm_model='custom', llm_url='unused', map_size=80))
        agent.type = 0
        agent.api_key = 'test'
        agent.past_actions = []
        agent.last_perception = 'At (13,49), 2 trees, water=0'
        agent.current_task = 'Cut trees'
        agent.extra_variables = [0, 0, 0]
        agent.log_chat = Mock()
        response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            choices=[SimpleNamespace(message=SimpleNamespace(content='<action>Spray water</action>'))])
        data = dict(large_model='test', api_calls=0, input_tokens=0, output_tokens=0,
                    hypergraph_bridge=self.bridge)
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(Path(__file__).resolve().parents[1] / 'ORCH/crew-algorithms')
        with patch.object(utils, 'OpenAI'), patch.object(utils, 'guarded_chat_completion', return_value=response), \
             patch.object(utils, 'translate_action', return_value=utils.Action(type=5, param_1=20, param_2=50, description='Spray water')):
            proposed = utils.action_round(agent, data)
        self.assertEqual(proposed, [3, 20, 50])
        self.assertEqual(agent.past_actions, [])
        actual = self.bridge.guard(agent, proposed, None)
        self.assertEqual(actual, [0, 13, 49])
        self.bridge.action_started(agent, actual)
        self.assertEqual(agent.past_actions, [])  # env.step has not returned.
        self.bridge.tokens_before = (0, 0)
        with patch.object(self.bridge, 'observe', return_value=None):
            self.bridge.after_step({}, list(self.agents.values()), {}, data)
        record = json.loads(agent.past_actions[-1])
        self.assertEqual(record['submitted_command'], actual)
        self.assertEqual(record['resources']['water'], 0)
        self.assertEqual(record['current_cell'], '2')
        self.assertIn('completion not inferred', record['status'])


if __name__ == '__main__':
    unittest.main()
