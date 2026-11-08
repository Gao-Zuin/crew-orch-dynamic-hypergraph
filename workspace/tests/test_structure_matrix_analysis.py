import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ORCH/crew-algorithms/crew_algorithms/wildfire_alg/config/resource_scheduling'))
from analyze_matrix import analyze


class MatrixAnalysisTests(unittest.TestCase):
    def test_family_defaults_use_separately_gated_seeds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(analyze(root, family='structure')['seeds'], [42, 256, 503, 819])
            self.assertEqual(analyze(root, family='composite')['seeds'], [42, 256, 503, 314])

    def test_only_identical_completed_pair_is_matched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('fixed', 'adaptive'):
                case = root / f'Structure_D0_R0_seed42_{arm}_local1'
                case.mkdir()
                def evt(kind, payload):
                    return {'event_type': kind, 'task_id': 'Structure_D0_R0',
                            'task_seed': 42, 'payload': payload}
                proposal = {'edges': [{'id': 'one', 'members': ['1'], 'leader': '1'}],
                            'active': {'1': 'one'}}
                events = [
                    evt('RUN_STARTED', {'model': 'test', 'max_steps': 2,
                                        'intervention': 'none', 'context_profile': 'v5'}),
                    evt('TASK_HYPERGRAPH_STARTED', {'fixed_groups': arm == 'fixed',
                        'local_event_info': True, 'local_event_radius': 10,
                        'structural_initial_plan': True, 'round_delivery': True}),
                    evt('TASK_STRUCTURAL_INITIAL_PLAN', {'proposal': proposal}),
                    evt('TASK_WORLD_SNAPSHOT', {'step': 1, 'phase': 'after_action',
                                                'fire_active': True}),
                    evt('RUN_FINISHED', {}),
                ]
                (case / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
            result = analyze(root, seeds=(42,))
            self.assertEqual(result['matched_pairs'], 1)
            bad = root / 'Structure_D0_R0_seed42_adaptive_local1/events.jsonl'
            events = [json.loads(line) for line in bad.read_text().splitlines()]
            events[0]['payload']['model'] = 'different'
            bad.write_text(''.join(json.dumps(e) + '\n' for e in events))
            self.assertEqual(analyze(root, seeds=(42,))['pairs'][0]['reason'],
                             'run configuration mismatch')


if __name__ == '__main__':
    unittest.main()
