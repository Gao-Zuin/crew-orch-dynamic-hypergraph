"""Dynamic task accounting and real runner call-site checks; no Unity/LLM."""
import ast
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'ORCH/crew-algorithms'
sys.path.insert(0, str(PACKAGE))
from crew_algorithms.wildfire_alg.core.alg_utils import (
    check_game_done, update_task_progress, write_task_outcome)
from crew_algorithms.wildfire_alg.config.build_config import create_level_presets
from crew_algorithms.wildfire_alg.coordination.task_runtime import TaskRuntimeBridge
from crew_algorithms.wildfire_alg.coordination.runtime import RuntimeBridge


def game(**counts):
    data = {'rewards': [0]*13, 'score': 0, 'fire_active': True,
            'task_description': 'test', 'task_parameters': {}}
    for index, value in counts.items():
        data['rewards'][int(index.removeprefix('r'))] = value
    return data


class DynamicTaskOutcomeTests(unittest.TestCase):
    def cfg(self, level):
        preset = create_level_presets()[level]
        return SimpleNamespace(**{**dict(timestamp='test', level=level, seed=42,
            model_name='test', llm_url='unused', civilian_count=0, civilian_clusters=0), **preset})

    def test_all_six_preset_goals_after_event(self):
        cases = [
            ('Scout_Fire_Drone_Lost', 8, 1, 2),
            ('Transport_Helicopter_Down', 6, 9, 10),
            ('Rescue_Civilians_Surprise', 5, 10, 15),
        ]
        for level, index, before, after in cases:
            with self.subTest(level=level):
                cfg = self.cfg(level); data = {}; observed = game()
                observed['rewards'][index] = before
                update_task_progress(data, observed, cfg, cfg.scheduled_events[0])
                self.assertFalse(check_game_done(data, cfg, 0))
                observed['rewards'][index] = after
                self.assertTrue(check_game_done(data, cfg, 0))
        for suffix in ['Second_Fire', 'Rapid_Growth']:
            self.assert_fire_goal('Suppress_Fire_Extinguish_' + suffix)
        self.assert_fire_goal('Suppress_Fire_Contain_Water_Source')

    def assert_fire_goal(self, level):
        cfg = self.cfg(level); observed = game(r1=3); data = {}
        update_task_progress(data, observed, cfg, cfg.scheduled_events[0])
        self.assertFalse(check_game_done(data, cfg, 0))
        observed['fire_active'] = False
        self.assertTrue(check_game_done(data, cfg, 0))
        # No ignition evidence yet must not be counted as suppression success.
        observed['rewards'][1] = 0
        self.assertFalse(check_game_done(data, cfg, 0))

    def test_spawn_accumulates_and_observation_does_not_increment(self):
        cfg = self.cfg('Rescue_Civilians_Surprise'); data = {}; observed = game(r5=10)
        update_task_progress(data, observed, cfg)
        self.assertTrue(check_game_done(data, cfg, 0))
        update_task_progress(data, observed, cfg, {'action': 'spawn_civilians_5'})
        self.assertEqual(data['civilian_target'], 15)
        self.assertFalse(check_game_done(data, cfg, 0))
        update_task_progress(data, observed, cfg)
        self.assertEqual(data['civilian_target'], 15)
        update_task_progress(data, observed, cfg, {'action': 'spawn_civilian'})
        self.assertEqual(data['civilian_target'], 16)

    def test_all_runner_returned_step_paths_and_failed_submission(self):
        # Execute the actual step->observation->accounting statements, bypassing
        # expensive imports/agent decisions, for all five runners.
        for name in ['Embodied', 'ORCH', 'CAMON', 'COELA', 'HMAS_2']:
            with self.subTest(runner=name):
                path = PACKAGE / f'crew_algorithms/wildfire_alg/algorithms/{name}/__main__.py'
                tree = ast.parse(path.read_text())
                loops = [n for n in ast.walk(tree) if isinstance(n, ast.For)]
                loop = next(n for n in loops if any(isinstance(s, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == 'newstate' for t in s.targets) for s in n.body))
                start = next(i for i,s in enumerate(loop.body) if isinstance(s, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == 'newstate' for t in s.targets))
                end = next(i for i,s in enumerate(loop.body) if isinstance(s, ast.Expr) and
                    isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name) and
                    s.value.func.id == 'update_task_progress')
                code = compile(ast.Module(body=loop.body[start:end+1], type_ignores=[]), str(path), 'exec')
                cfg = self.cfg('Rescue_Civilians_Surprise'); observed = game(r5=15)
                data = {}; env = Mock(); env.step.return_value = {'next': {'agents': {'observation': 'returned'}}}
                scope = dict(env=env, state={'agents': {}}, cfg=SimpleNamespace(envs=cfg),
                    global_data=data, parse_game_data=lambda state,cfg: observed,
                    update_task_progress=update_task_progress, events_this_step=cfg.scheduled_events,
                    scheduled_event_action=[10,70,70])
                exec(code, scope)
                self.assertEqual(data['civilian_target'], 15)
                self.assertIs(data['game_data'], observed)
                with tempfile.TemporaryDirectory() as directory:
                    outcome = write_task_outcome(data, cfg, directory)
                    self.assertTrue(outcome['success'])
                    self.assertTrue(outcome['all_scheduled_events_submitted'])
                    self.assertEqual(json.loads((Path(directory)/'task_outcome.json').read_text()), outcome)
                data.clear(); env.step.side_effect = RuntimeError('step failed')
                with self.assertRaises(RuntimeError): exec(code, scope)
                self.assertEqual(data, {})
                # The pre-action termination path also gets the global fire bit.
                updates = [n for n in ast.walk(loop) if isinstance(n, ast.Dict)]
                self.assertTrue(any('game_data' in [getattr(k,'value',None) for k in n.keys] for n in updates))
                self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and
                    n.func.id == 'write_task_outcome' for n in ast.walk(tree)))

    def test_both_bridge_validators_use_same_spawn_target(self):
        cfg = self.cfg('Rescue_Civilians_Surprise')
        for cls, args in [(TaskRuntimeBridge, ()), (RuntimeBridge, ('P',))]:
            with self.subTest(bridge=cls.__name__), tempfile.TemporaryDirectory() as directory:
                bridge = cls(SimpleNamespace(envs=cfg), directory, *args)
                bridge.global_data = {'civilian_target': 15}; bridge.step = 10
                observed = game(r5=10)
                self.assertFalse(bridge.observe({}, [], observed, 'before_action'))
                self.assertFalse(bridge.observe({}, [], observed, 'after_action'))
                self.assertEqual(bridge.global_data['civilian_target'], 15)
                observed['rewards'][5] = 15
                self.assertTrue(bridge.observe({}, [], observed, 'after_action'))
                if cls is TaskRuntimeBridge:
                    self.assertEqual(bridge.graph.world['mission_rules']['civilian_target'], 15)

    def test_orch_spawn_step_preserves_existing_pre_action_check(self):
        path = PACKAGE / 'crew_algorithms/wildfire_alg/algorithms/ORCH/__main__.py'
        tree = ast.parse(path.read_text())
        body = next(n.body for n in ast.walk(tree) if isinstance(n, ast.For) and
            any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and
                t.id == 'completion_data' for t in s.targets) for s in n.body))
        index = next(i for i,s in enumerate(body) if isinstance(s, ast.Assign) and
            any(isinstance(t, ast.Name) and t.id == 'completion_data' for t in s.targets))
        code = compile(ast.Module(body=body[index:index+2], type_ignores=[]), str(path), 'exec')
        cfg = self.cfg('Rescue_Civilians_Surprise'); data = {}
        update_task_progress(data, game(r5=10), cfg)
        scope = dict(global_data=data, events_this_step=cfg.scheduled_events, cfg=SimpleNamespace(envs=cfg))
        exec(code, scope)
        self.assertFalse(check_game_done(scope['completion_data'], cfg, 0))
        self.assertEqual(data['civilian_target'], 10)  # Not committed before submission.

    def test_early_completion_and_full_game_are_reported_without_redefining_goals(self):
        cfg = self.cfg('Suppress_Fire_Extinguish_Second_Fire'); data = {}; observed = game(r1=3)
        observed['fire_active'] = False
        update_task_progress(data, observed, cfg)
        with tempfile.TemporaryDirectory() as directory:
            outcome = write_task_outcome(data, cfg, directory)
        self.assertTrue(outcome['success'])  # Original predicate can finish before t18.
        self.assertFalse(outcome['all_scheduled_events_submitted'])
        cfg.game_type = 5
        self.assertTrue(check_game_done(data, cfg, 0))  # Original Full_Game is fire-only.


if __name__ == '__main__':
    unittest.main()
