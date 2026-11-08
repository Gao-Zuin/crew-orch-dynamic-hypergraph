from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/structure_calibration'))
from sim import Scenario, simulate


class StructureCalibrationTests(unittest.TestCase):
    def test_only_dynamic_scarce_case_needs_new_edge_for_both_deadlines(self):
        outcomes = {}
        for dynamic in (False, True):
            for scarce in (False, True):
                for adaptive in (False, True):
                    result = simulate(Scenario(dynamic, scarce, adaptive))
                    outcomes[(dynamic, scarce, adaptive)] = result
                    self.assertTrue(result['original_finished'])
        self.assertEqual(outcomes[(True, True, False)]['east_finished_step'], 10)
        self.assertEqual(outcomes[(True, True, True)]['east_finished_step'], 9)
        self.assertFalse(outcomes[(True, True, False)]['both_objectives_met'])
        self.assertTrue(outcomes[(True, True, True)]['both_objectives_met'])
        self.assertEqual(outcomes[(True, False, False)]['east_finished_step'],
                         outcomes[(True, False, True)]['east_finished_step'])
        self.assertTrue(all(outcomes[(False, scarce, adaptive)]['both_objectives_met']
                            for scarce in (False, True) for adaptive in (False, True)))

    def test_structure_changes_route_not_agent_count_or_physical_speed(self):
        fixed = simulate(Scenario(True, True, False))
        adaptive = simulate(Scenario(True, True, True))
        self.assertEqual(fixed['roster_size'], adaptive['roster_size'])
        self.assertEqual(fixed['initial_edges'], adaptive['initial_edges'])
        self.assertEqual(len(fixed['east_report_route']), 3)
        self.assertEqual(len(adaptive['east_report_route']), 2)
        self.assertEqual(fixed['east_report_step'] - adaptive['east_report_step'], 1)
        self.assertFalse(any(e['event'] == 'edge_added' for e in fixed['events']))
        self.assertTrue(any(e['event'] == 'edge_added' for e in adaptive['events']))


if __name__ == '__main__':
    unittest.main()
