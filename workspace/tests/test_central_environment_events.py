"""Official events reach the center without actor discovery; field reports remain."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_task_runtime as fixtures
from crew_algorithms.wildfire_alg.coordination.runtime import RuntimeBridge
from crew_algorithms.wildfire_alg.coordination.soft_task_policy import SoftTaskPolicy


class CentralEnvironmentEventTests(unittest.TestCase):
    setUp = fixtures.TaskRuntimeTests.setUp

    def test_executed_notice_triggers_center_then_downlink_without_worker_reports(self):
        event = {"timestep": 18, "action": "start_fire", "x": 70, "y": 70,
                 "announcement": "A second fire has broken out at (70,70)!"}
        self.bridge.step = 18
        self.world["step"] = 18
        self.bridge.graph.observe(self.world)
        self.bridge.graph.last_planned_step = 18
        self.assertFalse(self.bridge.graph.needs_plan())
        with patch.object(RuntimeBridge, "after_step"):
            self.bridge.after_step({}, list(self.agents.values()), {}, {"submitted_events": [event]})
        self.assertEqual(self.bridge.graph.reports, [])
        self.assertTrue(self.bridge.graph.needs_plan())
        self.assertTrue(all(not a.chat_history.get("ENVIRONMENT") for a in self.agents.values()))
        captured = []

        def transport(messages):
            captured.extend(messages)
            proposal = deepcopy(self.proposal)
            proposal.update(based_on_version=self.bridge.graph.version, evidence_id=2)
            proposal["edges"][1]["goal"] = "Investigate the announced second fire"
            return json.dumps(proposal), {"prompt_tokens": 10, "completion_tokens": 5}

        self.bridge.policy = SoftTaskPolicy("test", "unused", "unused", self.bridge.c.emit, transport)
        world = deepcopy(self.world)
        world.update(step=19, evidence_id=2)
        self.bridge.graph.observe(world)
        self.bridge.step = 19
        data = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0,
                "game_data": {"task_description": "Find the fire"}}
        with patch.object(RuntimeBridge, "before_step"):
            self.bridge.before_step({}, list(self.agents.values()), data["game_data"], 19, data)
        state = json.loads(captured[-1]["content"])
        self.assertEqual(state["environment_notices"][0]["event"], event)
        self.assertEqual(state["leader_reports"], [])
        self.assertFalse({"rewards", "fire_active", "events"} & state.keys())
        self.assertTrue(all(set(a) == {"capabilities", "ability_atoms", "online"} for a in state["agents"].values()))
        self.assertIn("do not require a worker", captured[0]["content"])
        for a in self.agents.values():
            self.assertEqual(a.chat_history["ENVIRONMENT"][0],
                             ("CENTRAL_EVENT_NOTICE", event["announcement"], 19))
            self.assertIn("already received these official event notices directly",
                          self.bridge.communication_prompt(str(a.id), "Communicate"))
            self.assertIn("Investigate the announced second fire" if a.id == 3 else "Find fire",
                          a.current_task)
        self.assertFalse(self.bridge.graph.needs_plan())
        with patch.object(RuntimeBridge, "before_step"):
            self.bridge.before_step({}, list(self.agents.values()), data["game_data"], 19, data)
        self.assertEqual(data["api_calls"], 1)
        self.assertTrue(all(len(a.chat_history["ENVIRONMENT"]) == 1 for a in self.agents.values()))
        kinds = [e["event_type"] for e in self.bridge.c.events]
        self.assertLess(kinds.index("TASK_ENVIRONMENT_NOTICE"), kinds.index("TASK_ORGANIZER_REQUEST"))
        self.assertLess(kinds.index("TASK_GRAPH_COMMITTED", kinds.index("TASK_ORGANIZER_REQUEST")),
                        kinds.index("TASK_CENTRAL_NOTICE_DELIVERED"))
        self.assertEqual(self.bridge.graph.decision_state()["environment_notices"], state["environment_notices"])

    def test_future_schedule_and_unsubmitted_events_do_not_reach_center(self):
        self.cfg.envs.scheduled_events = [{"timestep": 18, "action": "start_fire", "x": 70, "y": 70}]
        self.world["event_commands_and_announcements"] = self.cfg.envs.scheduled_events
        self.bridge.graph.observe(self.world)
        self.bridge.step = 17
        with patch.object(RuntimeBridge, "after_step"):
            self.bridge.after_step({}, list(self.agents.values()), {}, {"submitted_events": []})
        self.assertEqual(self.bridge.graph.decision_state()["environment_notices"], [])
        self.assertNotIn("70", json.dumps(self.bridge.graph.decision_state()))
        self.assertFalse(self.bridge.graph.needs_plan())

    def test_duplicate_event_is_not_redelivered_and_field_reports_still_trigger(self):
        event = {"timestep": 0, "action": "add_water", "x": 3, "y": 4,
                 "announcement": "A water source appeared at (3,4)."}
        self.bridge.graph.receive_environment_event(event)
        self.bridge.graph.receive_environment_event(event)
        self.assertEqual(len(self.bridge.graph.environment_notices), 1)
        proposal = deepcopy(self.proposal)
        proposal["based_on_version"] = self.bridge.graph.version
        self.bridge.graph.apply(proposal)
        self.assertFalse(self.bridge.graph.needs_plan())
        self.bridge.dispatch(self.agents["2"], '<REPORT edge="scout">Observed blocked route at 5,6.</REPORT>', {})
        self.bridge.dispatch(self.agents["1"], '<ORGANIZER edge="scout">Worker reports blocked route at 5,6.</ORGANIZER>', {})
        self.assertTrue(self.bridge.graph.needs_plan())
        self.assertEqual(self.bridge.graph.decision_state()["leader_reports"][-1]["content"],
                         "Worker reports blocked route at 5,6.")


if __name__ == "__main__":
    unittest.main()
