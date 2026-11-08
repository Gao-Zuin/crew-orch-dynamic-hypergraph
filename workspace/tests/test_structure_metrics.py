import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ORCH/crew-algorithms/crew_algorithms/wildfire_alg/config/resource_scheduling'))
from structure_metrics import summarize


class StructureMetricsTests(unittest.TestCase):
    def test_two_distinct_live_firefighters_and_deadline(self):
        def event(kind, payload):
            return {'event_type': kind, 'payload': payload}
        def world(step, positions):
            return event('TASK_WORLD_SNAPSHOT', {'step': step, 'phase': 'after_action',
                'event_commands_and_announcements': [],
                'nodes': {str(i): {'online': live, 'position': pos,
                         'facts': {'agent_type': 0}} for i, (pos, live) in positions.items()}})
        records = [
            event('TASK_ENVIRONMENT_NOTICE', {'step': 8, 'event': {'action': 'fire_alert'}}),
            world(8, {1: ([80, 80], True), 2: ([80, 80], False)}),
            event('TASK_SOURCE_VIEW_FIRE_SIGHTING', {'step': 9, 'recipient': '1',
                  'observed_fire_cells_near_event': [[80, 80]]}),
            world(9, {1: ([80, 80], True), 2: ([79, 80], True)}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            path.write_text(''.join(json.dumps(x) + '\n' for x in records))
            result = summarize(path, deployment_budget=1)
            self.assertEqual(result['first_firefighter_entry_step'], 8)
            self.assertEqual(result['first_two_firefighters_in_region_step'], 9)
            self.assertEqual(result['first_source_view_fire_step'], 9)
            self.assertEqual(result['notice_to_source_view_fire'], 1)
            self.assertEqual(result['new_fire_physical_effect'],
                             'fire_cell_seen_near_event_in_source_defined_own_view')
            self.assertTrue(result['deployment_by_deadline'])
            self.assertFalse(summarize(path, deployment_budget=0)['deployment_by_deadline'])
            self.assertEqual(summarize(path)['deployment_by_deadline'], 'unknown')


if __name__ == '__main__':
    unittest.main()
