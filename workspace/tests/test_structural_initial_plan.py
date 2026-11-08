import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ORCH/crew-algorithms'))
from crew_algorithms.wildfire_alg.config.resource_scheduling.initial_structure import build_initial_structure
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph, PlanError


class StructuralInitialPlanTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {str(i): {'online': True, 'facts': {'agent_type':
            0 if i <= 8 else 1 if i == 9 else 2 if i <= 11 else 3}}
            for i in range(1, 13)}
        self.world = {'step': 0, 'evidence_id': 42, 'mission': 'Contain fire',
                      'nodes': self.nodes, 'event_commands_and_announcements': []}

    def test_roster_split_is_disjoint_and_identical_across_arms(self):
        proposal = build_initial_structure(self.nodes, 42)
        self.assertEqual({e['id'] for e in proposal['edges']},
                         {'original_fire', 'support', 'recon'})
        self.assertEqual(set(proposal['active']), set(self.nodes))
        recon = next(e for e in proposal['edges'] if e['id'] == 'recon')
        self.assertEqual(recon['members'], ['5', '10'])
        self.assertEqual(recon['leader'], '5')
        support = next(e for e in proposal['edges'] if e['id'] == 'support')
        self.assertIn('11', support['members'])
        signatures = []
        for fixed in (False, True):
            graph = SoftTaskGraph(lambda kind, payload: {'event_id': 1}, fixed_groups=fixed)
            graph.observe(self.world)
            graph.apply(proposal)
            signatures.append(json.dumps(graph.edges, sort_keys=True))
            self.assertEqual(graph.active['10'], 'recon')
            self.assertEqual(graph.active['11'], 'support')
            self.assertFalse(any('10' in e['members'] for e in graph.edges.values()
                                 if e['id'] != 'recon'))
            self.assertTrue(graph.route('11', '6', 'support')[0])
        self.assertEqual(*signatures)

    def test_scarce_roster_has_no_support_scout(self):
        nodes = {a: n for a, n in self.nodes.items() if a != '11'}
        proposal = build_initial_structure(nodes, 42, composite=True)
        recon = next(e for e in proposal['edges'] if e['id'] == 'recon')
        support = next(e for e in proposal['edges'] if e['id'] == 'support')
        self.assertEqual(recon['members'], ['5', '10'])
        self.assertFalse(any(nodes[a]['facts']['agent_type'] == 2
                             for a in support['members']))
        self.assertEqual(set(proposal['active']), set(nodes))

    def test_real_route_needs_relay_until_expert_joins_consumer_edge(self):
        from copy import deepcopy
        proposal = build_initial_structure(self.nodes, 42)
        graphs = {}
        for fixed in (True, False):
            graph = SoftTaskGraph(lambda kind, payload: {'event_id': 1}, fixed_groups=fixed)
            graph.observe(self.world)
            graph.apply(proposal)
            graphs[fixed] = graph
            self.assertFalse(graph.route('10', '6', 'recon', 'support')[0])
            self.assertTrue(graph.route('10', '5', 'recon')[0])
            self.assertTrue(graph.route('5', '6', 'recon', 'support')[0])
            self.assertTrue(graph.route('6', '7', 'support')[0])
        for fixed, graph in graphs.items():
            changed = deepcopy(proposal)
            changed['based_on_version'] = graph.version
            next(edge for edge in changed['edges'] if edge['id'] == 'support')['members'].append('10')
            if fixed:
                with self.assertRaises(PlanError):
                    graph.apply(changed)
            else:
                graph.apply(changed)
                self.assertTrue(graph.route('10', '6', 'recon', 'support')[0])

    def test_missing_expert_fails_explicitly(self):
        nodes = {a: n for a, n in self.nodes.items()
                 if n['facts']['agent_type'] != 2}
        with self.assertRaises(ValueError):
            build_initial_structure(nodes, 42)


if __name__ == '__main__':
    unittest.main()
