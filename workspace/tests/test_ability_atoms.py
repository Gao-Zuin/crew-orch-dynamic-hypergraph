import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ORCH/crew-algorithms'))
from crew_algorithms.wildfire_alg.coordination.ability_atoms import catalog_for_nodes
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph


class AbilityAtomsTests(unittest.TestCase):
    def test_catalog_explains_scarce_expert_without_leaking_live_state(self):
        nodes = {
            '1': {'online': True, 'facts': {'agent_type': 0}, 'position': [11, 17],
                  'resources': {'water': 2}},
            '2': {'online': True, 'facts': {'agent_type': 2}, 'position': [77, 88]},
            '3': {'online': True, 'facts': {'agent_type': 3}, 'position': [30, 40]},
        }
        keys, catalog = catalog_for_nodes(nodes)
        self.assertIn('fly_scout', keys['2'])
        self.assertNotIn('carry_firefighters', keys['2'])
        self.assertIn('carry_firefighters', keys['3'])
        self.assertIn('not civilians', catalog['carry_firefighters'])
        graph = SoftTaskGraph(lambda kind, payload: {'event_id': 1}, report_driven=True)
        graph.observe({'step': 0, 'evidence_id': 1, 'mission': 'fire', 'nodes': nodes})
        state = graph.decision_state()
        self.assertIn('ability_sharing', state)
        self.assertIn('one physical action', state['ability_sharing'])
        self.assertNotIn('resources', state['agents']['1'])
        self.assertNotIn('position', state['agents']['2'])


if __name__ == '__main__':
    unittest.main()
