"""Worker-to-worker messages cross at most one edge hop per decision step."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_task_runtime as fixtures


class RoundDeliveryTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {'CREW_HT_ROUND_DELIVERY': '1'}):
            fixtures.TaskRuntimeTests.setUp(self)

    def test_report_then_leader_relay_requires_two_deliveries(self):
        self.bridge.step = 0
        self.bridge.dispatch(self.agents['2'],
                             '<REPORT edge="scout">Fire at 70,70.</REPORT>', {})
        self.assertNotIn('EDGE:scout', self.agents['1'].chat_history)
        self.assertEqual(len(self.bridge.routed_messages), 1)
        self.assertFalse(any(e['event_type'] == 'TASK_MESSAGE_DELIVERED'
                             for e in self.bridge.c.events))
        self.bridge.step = 1
        self.world['step'] = 1
        self.bridge.graph.observe(self.world)
        self.bridge._flush_routed_messages()
        self.assertEqual(len(self.agents['1'].chat_history['EDGE:scout']), 1)
        self.bridge.dispatch(self.agents['1'],
                             '<LEADER edge="scout" to="support">Fire at 70,70.</LEADER>', {})
        self.assertNotIn('EDGE:support', self.agents['3'].chat_history)
        self.bridge.step = 2
        self.world['step'] = 2
        self.bridge.graph.observe(self.world)
        self.bridge._flush_routed_messages()
        self.assertEqual(len(self.agents['3'].chat_history['EDGE:support']), 1)
        self.assertEqual(len([e for e in self.bridge.c.events
                              if e['event_type'] == 'TASK_MESSAGE_DELIVERED']), 2)

    def test_organizer_report_is_not_available_until_next_step(self):
        self.bridge.step = 0
        self.bridge.dispatch(self.agents['1'],
                             '<ORGANIZER edge="scout">Need drone with support team.</ORGANIZER>', {})
        self.assertEqual(self.bridge.graph.reports, [])
        self.assertEqual(len(self.bridge.queued_organizer_reports), 1)
        self.bridge.step = 1
        self.world['step'] = 1
        self.bridge.graph.observe(self.world)
        self.bridge._flush_organizer_reports()
        self.assertEqual(self.bridge.graph.reports[-1]['content'],
                         'Need drone with support team.')

    def test_offline_recipient_suppressed(self):
        self.bridge.step = 0
        self.bridge.dispatch(self.agents['2'],
                             '<REPORT edge="scout">Fire at 70,70.</REPORT>', {})
        self.bridge.step = 1
        self.world['step'] = 1
        self.world['nodes']['1']['online'] = False
        self.bridge.graph.observe(self.world)
        offline_agent = self.agents['1']
        self.bridge.runtime_agents.pop('1')
        self.bridge._flush_routed_messages()
        self.assertNotIn('EDGE:scout', offline_agent.chat_history)
        self.assertTrue(any(e['event_type'] == 'TASK_QUEUED_MESSAGE_SUPPRESSED'
                            for e in self.bridge.c.events))


if __name__ == '__main__':
    unittest.main()
