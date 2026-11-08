"""Runtime integration checks for the advisory task graph (offline)."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ORCH/crew-algorithms"))
from crew_algorithms.wildfire_alg.coordination.runtime import RuntimeBridge
from crew_algorithms.wildfire_alg.coordination.task_runtime import TaskRuntimeBridge


class TaskRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = SimpleNamespace(envs=SimpleNamespace(timestamp="test", level="Scout_Fire_small",
            seed=1, model_name="test", llm_url="unused", game_type=1, max_steps=2,
            scheduled_events=[]))
        self.bridge = TaskRuntimeBridge(self.cfg, self.tmp.name)
        self.agents = {}
        for aid in ("1", "2", "3"):
            agent = SimpleNamespace(id=int(aid), last_position=[int(aid), 0],
                                    chat_history={"GLOBAL": []})
            agent.add_message = lambda channel, speaker, content, step, a=agent: a.chat_history.setdefault(channel, []).append((speaker, content, step))
            self.agents[aid] = agent
        self.bridge.runtime_agents = self.agents
        self.world = {"evidence_id": 1, "step": 0, "mission": "Find the fire",
                      "rewards": [0] * 13, "event_commands_and_announcements": [],
                      "nodes": {a: {"online": True, "position": [int(a), 0],
                                    "resources": {"water": 1}}
                                for a in self.agents}}
        self.bridge.graph.observe(self.world)
        self.proposal = {"based_on_version": 0, "evidence_id": 1,
            "edges": [{"id": "scout", "goal": "Find fire", "members": ["1", "2"],
                       "leader": "1", "tasks": {"1": "scan north"}, "advice": "Compare sightings"},
                      {"id": "support", "goal": "Support scouts", "members": ["2", "3"],
                       "leader": "3", "tasks": {}, "advice": ""}],
            "active": {"1": "scout", "2": "scout", "3": "support"}}
        self.bridge.graph.apply(self.proposal)

    def test_factory_uses_soft_task_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"CREW_HYPERGRAPH_ARM": "HT"}):
                bridge = RuntimeBridge.from_environment(self.cfg, directory)
                self.assertIsInstance(bridge, TaskRuntimeBridge)
        self.assertEqual(bridge.c.events[-1]["payload"]["context_profile"], "task_hypergraph_reports_v5")

    def test_group_routes_and_shared_member(self):
        self.bridge.dispatch(self.agents["1"], '<GROUP edge="scout">fire north</GROUP>', {})
        self.assertEqual(len(self.agents["2"].chat_history["EDGE:scout"]), 1)
        self.assertNotIn("EDGE:scout", self.agents["3"].chat_history)
        self.bridge.dispatch(self.agents["2"], '<GROUP edge="support" to="3">fire north</GROUP>', {})
        self.assertIn("fire north", self.agents["3"].chat_history["EDGE:support"][0][1])

    def test_both_memberships_receive_messages_without_changing_active(self):
        self.bridge.dispatch(self.agents["1"], '<GROUP edge="scout" to="2">scout work</GROUP>', {})
        self.bridge.dispatch(self.agents["3"], '<GROUP edge="support" to="2">support work</GROUP>', {})
        context = self.bridge.graph.context("2")
        self.assertEqual({m["source"] for m in context["message_history"]}, {"scout", "support"})
        self.assertEqual(self.bridge.graph.active["2"], "scout")
        self.assertEqual(len(context["memberships"]), 2)

    def test_invalid_edge_does_not_swallow_valid_group_broadcast(self):
        self.bridge.dispatch(self.agents["1"],
            '<GROUP edge="unknown">bad</GROUP><GROUP edge="scout">valid local update</GROUP>', {})
        self.assertIn("valid local update", self.agents["2"].chat_history["EDGE:scout"][0][1])
        self.assertNotIn("EDGE:scout", self.agents["3"].chat_history)
        self.assertTrue(any(e["event_type"] == "TASK_MESSAGE_INVALID" for e in self.bridge.c.events))

    def test_invalid_new_plan_does_not_hold_actions(self):
        self.bridge.policy = SimpleNamespace(decide=lambda graph, data: False)
        self.assertFalse(self.bridge._organize({}))
        self.assertTrue(self.bridge.graph.ready("1"))
        self.assertTrue(self.bridge.allows_inference(self.agents["1"]))

    def test_prompt_is_advisory_and_compact(self):
        prompt = self.bridge.prompt("1", "original prompt")
        self.assertIn("ADVISORY", prompt)
        self.assertIn("scan north", prompt)
        self.assertNotIn("authorized_routes", prompt)

    def test_prompt_distinguishes_historical_message_time_from_current_step(self):
        self.bridge.dispatch(self.agents["1"], '<GROUP edge="scout">status at the old stage</GROUP>', {})
        self.world["step"] = 99
        self.world["evidence_id"] = 2
        self.bridge.graph.observe(self.world)
        prompt = self.bridge.prompt("2", "original")
        self.assertIn('"step": 99', prompt)
        self.assertIn('"step": 0', prompt)
        self.assertIn('"message_history"', prompt)
        self.assertNotIn('"recent_messages"', prompt)

    def test_replan_does_not_erase_chat_history(self):
        self.agents["1"].chat_history["GLOBAL"].append(("2", "water is empty", 0))
        game = {"task_description": "Find the fire"}
        self.bridge.policy = SimpleNamespace(decide=lambda graph, data: True)
        with patch.object(RuntimeBridge, "before_step", return_value=None):
            self.bridge.before_step({}, list(self.agents.values()), game, 0, {})
        self.assertEqual(self.agents["1"].chat_history["GLOBAL"][0][1], "water is empty")

    def test_action_uses_environment_preconditions_not_stage_checks(self):
        self.bridge.c.observe({"agent_id": "1", "task_id": self.bridge.c.task_id,
            "session_epoch": self.bridge.session, "observed_at": self.bridge.c.clock(),
            "resources": {"water": 1}, "capabilities": ["navigate"],
            "position": [1, 0], "facts": {"agent_type": 0}})
        self.assertEqual(self.bridge.guard(self.agents["1"], [0, 9, 9], None), [0, 9, 9])

    def test_finish_records_organization_usage_without_a_physical_step(self):
        # before_step can call the organizer, then the runner exits on success.
        self.bridge.tokens_before = (100, 20)
        self.bridge.finish({"input_tokens": 107, "output_tokens": 23, "api_calls": 1})
        usage = [e for e in self.bridge.c.events if e["event_type"] == "LLM_USAGE"]
        self.assertEqual([(e["input_tokens"], e["output_tokens"]) for e in usage], [(7, 3)])

    def test_finish_does_not_count_completed_round_usage_twice(self):
        data = {"input_tokens": 7, "output_tokens": 3, "api_calls": 1}
        self.bridge.tokens_before = (0, 0)
        with patch.object(self.bridge, "observe", return_value=None):
            self.bridge.after_step({}, [], {}, data)
        self.bridge.finish(data)
        usage = [e for e in self.bridge.c.events if e["event_type"] == "LLM_USAGE"]
        self.assertEqual(sum(e["input_tokens"] for e in usage), 7)
        self.assertEqual(sum(e["output_tokens"] for e in usage), 3)
        self.assertEqual(len(usage), 1)

    def test_manual_regroup_changes_members_only_once(self):
        self.bridge.graph.fixed_groups = True
        self.bridge.graph.group_lock = self.bridge.graph._topology(
            self.bridge.graph.edges, self.bridge.graph.active)
        path = Path(self.tmp.name) / "regroup.json"
        path.write_text(json.dumps({"members": {"scout": ["1", "3"],
                                                "support": ["2", "3"]},
                                    "active": {"1": "scout", "2": "support",
                                               "3": "support"}}))
        self.bridge.regroup_path = str(path)
        self.bridge.regroup_step = 0
        self.bridge.policy = SimpleNamespace(decide=lambda graph, data: True)
        game = {"task_description": "Find the fire"}
        with patch.object(RuntimeBridge, "before_step", return_value=None):
            self.bridge.before_step({}, list(self.agents.values()), game, 0, {})
            version = self.bridge.graph.version
            self.bridge.before_step({}, list(self.agents.values()), game, 0, {})
        self.assertEqual(self.bridge.graph.version, version)
        self.assertEqual(self.bridge.graph.active["2"], "support")
        self.assertEqual(self.bridge.graph.edges["scout"]["goal"], "Find fire")

    def test_local_event_cue_arrives_when_worker_enters_later(self):
        self.bridge.local_event_info = True
        self.bridge.step = 8
        self.bridge.c.nodes = {'2': {'online': True, 'position': [10, 10]}}
        event = {'timestep': 8, 'action': 'start_fire', 'x': 80, 'y': 80}
        with patch.object(RuntimeBridge, 'after_step', return_value=None):
            self.bridge.after_step({}, [], {}, {'submitted_events': [event]})
            self.assertNotIn('ENVIRONMENT', self.agents['2'].chat_history)
            self.assertEqual(len(self.bridge.local_event_candidates), 1)
            self.bridge.step = 9
            self.bridge.c.nodes['2']['position'] = [75, 80]
            self.bridge.after_step({}, [], {}, {'submitted_events': []})
            self.assertEqual(len(self.agents['2'].chat_history['ENVIRONMENT']), 1)
            self.bridge.step = 10
            self.bridge.after_step({}, [], {}, {'submitted_events': []})
            self.assertEqual(len(self.agents['2'].chat_history['ENVIRONMENT']), 1)
        cues = [e for e in self.bridge.c.events
                if e['event_type'] == 'TASK_LOCAL_EVENT_CUE_DELIVERED']
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0]['payload']['step'], 9)

    def test_fire_sighting_requires_own_source_view_not_shared_cache(self):
        self.bridge.step = 8
        self.bridge.c.nodes = {'2': {'online': True, 'position': [70, 80],
            'facts': {'map_memory': {'cells': {'fire': [[80, 80]]}},
                      'own_view_source_candidate': {'radius': 15, 'cells': {'fire': []}}}}}
        event = {'timestep': 8, 'action': 'start_fire', 'x': 80, 'y': 80}
        with patch.object(RuntimeBridge, 'after_step', return_value=None):
            self.bridge.after_step({}, [], {}, {'submitted_events': [event]})
            self.assertFalse(any(e['event_type'] == 'TASK_SOURCE_VIEW_FIRE_SIGHTING'
                                 for e in self.bridge.c.events))
            self.bridge.step = 9
            self.bridge.c.nodes['2']['facts']['own_view_source_candidate']['cells']['fire'] = [[80, 80]]
            self.bridge.after_step({}, [], {}, {'submitted_events': []})
            self.bridge.step = 10
            self.bridge.after_step({}, [], {}, {'submitted_events': []})
        sightings = [e for e in self.bridge.c.events
                     if e['event_type'] == 'TASK_SOURCE_VIEW_FIRE_SIGHTING']
        self.assertEqual(len(sightings), 1)
        self.assertEqual(sightings[0]['payload']['step'], 9)


if __name__ == "__main__":
    unittest.main()
