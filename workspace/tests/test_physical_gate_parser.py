import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_structure_fire_events.py'
spec = importlib.util.spec_from_file_location('physical_gate', SCRIPT)
physical_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(physical_gate)


class PhysicalGateParserTests(unittest.TestCase):
    def test_rejected_spawn_candidates_are_not_original_fire(self):
        log = ('fire location31, 40\nfire start False\n'
               'fire location82, 34\nfire location61, 75\n'
               'fire start True\nfire start True\n')
        self.assertEqual(physical_gate.first_successful_fire_location(log), [61, 75])

    def test_no_success_returns_none(self):
        self.assertIsNone(physical_gate.first_successful_fire_location(
            'fire location31, 40\nfire start False\n'))

    def test_composite_gate_requires_same_initial_goals_and_separation(self):
        summary_spec = importlib.util.spec_from_file_location(
            'physical_summary', SCRIPT.with_name('summarize_physical_gates.py'))
        summary_module = importlib.util.module_from_spec(summary_spec)
        summary_spec.loader.exec_module(summary_module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for scarce, water in ((0, [20, 20]), (1, [21, 20])):
                case = root / f'seed7_R{scarce}'
                case.mkdir()
                (case / 'report.json').write_text(json.dumps({
                    'original_fire': [20, 20], 'new_fire': [80, 80],
                    'event_ignition_supported': True}))
                raw = [0] * 64
                raw[16:22] = [20, 20, *water, 40, 40]
                (case / 'manager_observation.json').write_text(json.dumps({
                    'raw_manager_prefix': raw}))
            result = summary_module.summarize(root, [7], 'composite')
            self.assertEqual(result['selected_seeds'], [])
            self.assertFalse(result['candidates'][0]['same_initial_goals'])


if __name__ == '__main__':
    unittest.main()
