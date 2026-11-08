"""Report chain, center information boundary and typed-message semantics."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_task_runtime as fixtures
from crew_algorithms.wildfire_alg.coordination.soft_task_policy import SoftTaskPolicy

class BottomUpTests(unittest.TestCase):
    setUp = fixtures.TaskRuntimeTests.setUp

    def test_worker_report_is_an_input_to_leader_not_an_automatic_escalation(self):
        self.bridge.dispatch(self.agents['2'], '<REPORT edge="scout">New fire at 70,70; no water</REPORT>', {})
        self.assertIn('New fire',self.agents['1'].chat_history['EDGE:scout'][0][1])
        self.assertEqual(self.bridge.graph.reports,[])
        self.assertFalse(self.bridge.graph.needs_plan())
        self.bridge.dispatch(self.agents['1'], '<justification>I can refill and handle it locally.</justification><GROUP edge="scout" to="2">Continue scouting; I will refill</GROUP>', {})
        self.assertEqual(self.bridge.graph.reports,[])
        self.assertTrue(any(e['event_type']=='TASK_LEADER_ANALYSIS' and 'locally' in e['payload']['analysis'] for e in self.bridge.c.events))

    def test_leader_can_consult_then_send_analysis_to_center(self):
        self.bridge.dispatch(self.agents['1'], '<LEADER edge="scout" to="support">Can you provide water?</LEADER>', {})
        self.assertIn('provide water',self.agents['3'].chat_history['EDGE:support'][0][1])
        self.bridge.dispatch(self.agents['1'], '<ORGANIZER edge="scout">New fire 70,70; our team lacks suppression. Keep scout 2 here; assign support firefighter.</ORGANIZER>', {})
        self.assertTrue(self.bridge.graph.needs_plan())
        captured=[]
        def transport(messages):
            captured.extend(messages)
            p=deepcopy(self.proposal);p['based_on_version']=self.bridge.graph.version
            return json.dumps(p),{'prompt_tokens':10,'completion_tokens':5}
        self.bridge.policy=SoftTaskPolicy('test','unused','unused',self.bridge.c.emit,transport)
        data={'api_key':'unused','api_calls':0,'input_tokens':0,'output_tokens':0,
              'game_data':{'task_description':'Find the fire'}}
        self.bridge.after_communication(data)
        state=json.loads(captured[-1]['content'])
        self.assertEqual(len(state['leader_reports']),1)
        self.assertIn('70,70',state['leader_reports'][0]['content'])
        self.assertEqual(data['api_calls'],1)
        self.assertFalse(self.bridge.graph.needs_plan())

    def test_center_has_no_live_position_resource_reward_or_event_feed(self):
        self.world.update(rewards=[999]*13,fire_active=True,
            event_commands_and_announcements=[{'action':'start_fire','x':77,'y':88}])
        self.world['nodes']['2']['position']=[77,88]
        self.bridge.graph.observe(self.world)
        state=self.bridge.graph.decision_state()
        self.assertFalse({'rewards','fire_active','events'} & state.keys())
        for node in state['agents'].values():
            self.assertEqual(set(node),{'capabilities','ability_atoms','online'})
        self.assertNotIn('77',json.dumps(state))
        self.assertFalse(self.bridge.graph.needs_plan())

    def test_worker_cannot_bypass_leader_or_impersonate_other_group(self):
        self.bridge.dispatch(self.agents['2'], '<ORGANIZER edge="scout">bypass</ORGANIZER><LEADER edge="scout" to="support">bypass</LEADER>', {})
        self.bridge.dispatch(self.agents['1'], '<GROUP edge="support">outsider</GROUP>', {})
        self.assertEqual(self.bridge.graph.reports,[])
        self.assertNotIn('EDGE:support',self.agents['3'].chat_history)
        self.assertEqual(sum(e['event_type']=='TASK_MESSAGE_INVALID' for e in self.bridge.c.events),3)

    def test_global_is_not_reinterpreted_as_group_and_reasoning_is_not_sent(self):
        self.bridge.dispatch(self.agents['1'], '<GLOBAL>ambiguous</GLOBAL><justification><ORGANIZER edge="scout">hypothetical</ORGANIZER></justification>', {})
        self.assertEqual(self.bridge.graph.messages,[])
        self.assertEqual(self.bridge.graph.reports,[])
        prompt=self.bridge.communication_prompt('1','status\nYou may send messages to individual agents or in a global channel. OLD FORMAT')
        self.assertNotIn('OLD FORMAT',prompt)
        self.assertIn('<REPORT edge=',prompt)

    def test_action_request_keeps_action_format_without_communication_output_instructions(self):
        original = 'Choose one physical action. Return <action>...</action>.'
        action_prompt = self.bridge.prompt('2', original)
        communication_prompt = self.bridge.communication_prompt('2', original)
        self.assertIn('<action>...</action>', action_prompt)
        self.assertIn('ADVISORY', action_prompt)
        self.assertNotIn('then zero or more message tags', action_prompt)
        self.assertNotIn('Communication uses these tags only', action_prompt)
        self.assertIn('Communication uses these tags only', communication_prompt)

    def test_worker_chat_is_not_promoted_to_an_official_environment_notice(self):
        original = 'status\nYou may send messages to individual agents or in a global channel. OLD'
        before = self.bridge.communication_prompt('2', original)
        self.agents['2'].add_message('ENVIRONMENT','PUBLIC_ANNOUNCEMENT','New civilians at 70,70',9)
        after = self.bridge.communication_prompt('2', original)
        self.assertTrue(after.startswith('[RECENT PUBLIC NOTICES'))
        self.assertIn('70,70',after)
        self.assertIn('Escalation is optional',after)
        self.assertNotIn('70,70',json.dumps(self.bridge.graph.decision_state()))
        self.assertEqual(self.bridge.graph.reports,[])
        self.agents['2'].chat_history['ENVIRONMENT'].clear()
        self.assertEqual(self.bridge.communication_prompt('2', original),before)

    def test_communication_order_and_overlap_context_keep_active_assignment(self):
        self.assertEqual([a.id for a in self.bridge.communication_order(list(self.agents.values()))],[2,1,3])
        self.bridge.dispatch(self.agents['1'], '<GROUP edge="scout" to="2">north</GROUP>', {})
        self.bridge.dispatch(self.agents['3'], '<GROUP edge="support" to="2">south</GROUP>', {})
        # Runtime action logging requires observed nodes and a pending action id.
        self.bridge.c.nodes=deepcopy(self.world['nodes'])
        self.bridge.action_started(self.agents['2'],[0,2,0])
        overlap=next(e['payload'] for e in self.bridge.c.events if e['event_type']=='TASK_OVERLAP_ACTION')
        self.assertEqual(overlap['active'],'scout')
        self.assertEqual({m['source'] for m in overlap['received_messages']},{'scout','support'})
        self.assertEqual(self.bridge.graph.active,self.proposal['active'])

    def test_leader_report_to_self_gets_local_correction(self):
        leader = self.agents['1']
        before = len(self.bridge.graph.reports)
        self.bridge.dispatch(
            leader,
            '<REPORT edge="scout">Fire at 70,70 needs another group.</REPORT>', {})
        self.assertEqual(len(self.bridge.graph.reports), before)
        self.assertIn('sent to yourself', leader.chat_history['ENVIRONMENT'][-1][1])
        self.assertIn('ORGANIZER', leader.chat_history['ENVIRONMENT'][-1][1])
        invalid = [event for event in self.bridge.c.events
                   if event['event_type'] == 'TASK_MESSAGE_INVALID']
        self.assertTrue(invalid)
        self.assertEqual(invalid[-1]['payload']['message_type'], 'REPORT')

if __name__=='__main__':unittest.main()
