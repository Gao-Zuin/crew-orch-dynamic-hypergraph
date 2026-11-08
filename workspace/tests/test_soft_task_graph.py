"""Offline checks for the advisory HT profile."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ORCH/crew-algorithms"))
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph, PlanError
from crew_algorithms.wildfire_alg.coordination.soft_task_policy import SoftTaskPolicy


class SoftTaskGraphTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.graph = SoftTaskGraph(lambda kind, payload: self._emit(kind, payload))
        self.world = {"evidence_id": 1, "step": 0, "mission": "Suppress both fires",
                      "rewards": [0] * 13, "fire_active": True,
                      "event_commands_and_announcements": [],
                      "nodes": {a: {"online": True, "position": [0, 0],
                                    "resources": {"water": 0}, "capabilities": ["navigate"]}
                                for a in ("1", "2", "3")}}
        self.graph.observe(self.world)

    def _emit(self, kind, payload):
        event = {"event_id": len(self.events) + 1, "event_type": kind, "payload": payload}
        self.events.append(event)
        return event

    def proposal(self):
        return {"based_on_version": self.graph.version,
                "evidence_id": self.graph.world["evidence_id"],
                "edges": [{"id": "fire", "goal": "Suppress known fire",
                           "members": ["1", "2", "3"], "leader": "1",
                           "tasks": {"1": "refill"}, "advice": "Coordinate water supply"}],
                "active": {a: "fire" for a in ("1", "2", "3")}}

    def test_plan_is_advisory_and_stable(self):
        self.graph.apply(self.proposal())
        self.assertTrue(self.graph.ready("2"))
        self.assertFalse(self.graph.needs_plan())
        self.assertEqual(self.graph.context("1")["suggestion"], "refill")
        self.world["step"] = 1
        self.world["evidence_id"] = 2
        self.graph.observe(self.world)
        self.assertFalse(self.graph.needs_plan())

    def test_bad_plan_retains_current_work_and_event_replans(self):
        self.graph.apply(self.proposal())
        bad = self.proposal()
        bad["edges"][0]["leader"] = "unknown"
        with self.assertRaises(PlanError):
            self.graph.apply(bad)
        self.graph.ensure_fallback()
        self.assertEqual(self.graph.active["2"], "fire")
        self.assertTrue(self.graph.ready("2"))
        self.world["event_commands_and_announcements"] = [{"action": "start_fire", "x": 70, "y": 70}]
        self.graph.observe(self.world)
        self.assertTrue(self.graph.needs_plan())

    def test_dynamic_fallback_after_leader_loss_preserves_surviving_groups(self):
        proposal = self.proposal()
        proposal['edges'] = [
            {'id':'a','goal':'Continue local work','members':['1','2'],'leader':'1','tasks':{'1':'old leader work','2':'continue'}},
            {'id':'b','goal':'Support work','members':['2','3'],'leader':'3','tasks':{}}]
        proposal['active'] = {'1':'a','2':'a','3':'b'}
        self.graph.apply(proposal)
        self.world['nodes']['1']['online'] = False
        self.world.update(step=4,evidence_id=5)
        self.graph.observe(self.world)
        bad = self.proposal()  # Still includes destroyed agent1.
        with self.assertRaises(PlanError):
            self.graph.apply(bad)
        self.graph.ensure_fallback()
        self.assertEqual(set(self.graph.edges),{'a','b'})
        self.assertEqual(self.graph.edges['a']['members'],['2'])
        self.assertEqual(self.graph.edges['a']['leader'],'2')
        self.assertEqual(self.graph.edges['b']['members'],['2','3'])
        self.assertEqual(self.graph.edges['b']['leader'],'3')
        self.assertEqual(self.graph.active,{'2':'a','3':'b'})
        self.assertEqual(self.graph.edges['a']['tasks'],{'2':'continue'})
        self.assertTrue(self.events[-2]['payload']['attrition'])
        self.assertTrue(all(self.graph.ready(a) for a in ['2','3']))

    def test_initial_failure_uses_mission_fallback(self):
        self.graph.ensure_fallback()
        self.assertEqual(set(self.graph.active), {"1", "2", "3"})
        self.assertTrue(self.graph.ready("3"))

    def test_no_online_workers_retire_once_without_model_calls(self):
        for fixed in (False, True):
            with self.subTest(fixed=fixed):
                self.setUp()
                self.graph.fixed_groups = fixed
                self.graph.apply(self.proposal())
                def forbidden_call(messages):
                    self.fail("no workers can execute an organizer suggestion")
                policy = SoftTaskPolicy("test", "unused", "unused", self.graph.emit,
                                        forbidden_call)
                usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
                for node in self.world["nodes"].values():
                    node["online"] = False
                for step in (1, 2, 10, 99):
                    self.world.update(step=step, evidence_id=step + 1)
                    self.graph.observe(self.world)
                    self.assertTrue(policy.decide(self.graph, usage))
                    self.assertEqual(self.graph.edges, {})
                    self.assertEqual(self.graph.active, {})
                    self.assertFalse(self.graph.needs_plan())
                self.assertEqual(self.graph.version, 2)
                self.assertEqual(len(self.graph.archive), 1)
                self.assertEqual(usage, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0})

    def test_initial_empty_world_and_returning_worker(self):
        for node in self.world["nodes"].values():
            node["online"] = False
        self.graph.observe(self.world)
        requests = []
        def transport(messages):
            requests.append(messages)
            proposal = {"based_on_version": self.graph.version,
                        "evidence_id": self.graph.world["evidence_id"],
                        "edges": [{"id": "returned", "goal": "Resume work",
                                   "members": ["2"], "leader": "2"}],
                        "active": {"2": "returned"}}
            return json.dumps(proposal), {"prompt_tokens": 10, "completion_tokens": 5}
        policy = SoftTaskPolicy("test", "unused", "unused", self.graph.emit, transport)
        usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.assertTrue(policy.decide(self.graph, usage))
        self.assertEqual(requests, [])
        self.assertEqual(self.graph.version, 0)
        self.world["nodes"]["2"]["online"] = True
        self.world.update(step=1, evidence_id=2)
        self.graph.observe(self.world)
        self.assertTrue(self.graph.needs_plan())
        self.assertTrue(policy.decide(self.graph, usage))
        self.assertEqual(usage["api_calls"], 1)
        self.assertEqual(self.graph.active, {"2": "returned"})

    def test_historical_messages_retain_send_time_after_membership_changes(self):
        self.world["step"] = 2
        self.graph.observe(self.world)
        self.graph.apply(self.proposal())
        self.graph.record_message("1", "2", "fire", None, "Hold for my resupply request")
        self.world["step"] = 72
        self.world["evidence_id"] = 2
        self.world["nodes"]["1"]["online"] = False
        self.graph.observe(self.world)
        changed = self.proposal()
        changed["edges"][0].update(members=["2", "3"], leader="2", tasks={})
        changed["active"] = {"2": "fire", "3": "fire"}
        self.graph.apply(changed)
        context = self.graph.context("2")
        self.assertEqual(context["step"], 72)
        self.assertEqual(context["graph_version"], 2)
        self.assertNotIn("recent_messages", context)
        history = context["message_history"]
        self.assertEqual(len(history), 1)  # retain useful history, not a TTL ban
        self.assertEqual(history[0]["step"], 2)
        self.assertEqual(history[0]["graph_version"], 1)
        self.assertEqual(history[0]["content"], "Hold for my resupply request")

    def test_no_verifier_and_single_attempt(self):
        outputs = iter([json.dumps(self.proposal())])
        policy = SoftTaskPolicy("test", "unused", "unused", self.graph.emit,
                                lambda messages: (next(outputs), {"prompt_tokens": 10, "completion_tokens": 5}))
        usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.assertTrue(policy.decide(self.graph, usage))
        self.assertEqual(usage["api_calls"], 1)
        self.assertFalse(any(e["event_type"] == "TASK_VERIFIER_REQUEST" for e in self.events))

    def test_organizer_receives_reward_names_in_runtime_order(self):
        # The recorded world has names, but the old organizer request lost them.
        schema = ["exploration", "trees_burned", "trees_cut", "fire_extinguished",
                  "correct_trees_cut", "civilians_rescued", "firefighters_transported",
                  "civilians_scouted", "fire_scouted", "water_scouted", "agents_destroyed",
                  "civilians_destroyed", "buildings_destroyed"]
        self.world["reward_schema"] = schema
        self.world["rewards"] = [0, 900, 0, 18, 0, 0, 0, 0, 2, 1, 0, 0, 0]
        self.graph.observe(self.world)
        requests = []

        def transport(messages):
            requests.append(json.loads(messages[-1]["content"]))
            return json.dumps(self.proposal()), {"prompt_tokens": 10, "completion_tokens": 5}

        policy = SoftTaskPolicy("test", "unused", "unused", self.graph.emit, transport)
        self.assertTrue(policy.decide(self.graph, {"api_calls": 0, "input_tokens": 0,
                                                 "output_tokens": 0}))
        self.assertEqual(requests[0]["reward_schema"], schema)
        self.assertEqual(dict(zip(requests[0]["reward_schema"], requests[0]["rewards"])),
                         dict(zip(schema, self.world["rewards"])))

    def test_fixed_groups_accept_new_work_but_reject_membership_change(self):
        self.graph.fixed_groups = True
        self.graph.apply(self.proposal())
        revised = self.proposal()
        revised["edges"][0]["goal"] = "Suppress newly observed fire"
        self.graph.apply(revised)
        changed = self.proposal()
        changed["edges"][0]["members"] = ["1", "2"]
        changed["active"]["3"] = "fire"
        with self.assertRaises(PlanError):
            self.graph.apply(changed)
        self.assertEqual(self.graph.edges["fire"]["goal"], "Suppress newly observed fire")

    def test_one_manual_regroup_preserves_sizes_leaders_and_work(self):
        self.graph.fixed_groups = True
        self.world["nodes"]["4"] = {"online": True, "position": [0, 0],
                                      "resources": {}, "capabilities": ["navigate"]}
        self.graph.observe(self.world)
        initial = self.proposal()
        initial["edges"] = [
            {"id": "a", "goal": "Scout", "members": ["1", "2"], "leader": "1",
             "tasks": {"1": "lead", "2": "scan"}, "advice": "coordinate"},
            {"id": "b", "goal": "Support", "members": ["3", "4"], "leader": "3",
             "tasks": {"3": "support"}, "advice": "wait"},
        ]
        initial["active"] = {"1": "a", "2": "a", "3": "b", "4": "b"}
        self.graph.apply(initial)
        self.graph.regroup({"members": {"a": ["1", "4"], "b": ["3", "2"]},
                            "active": {"1": "a", "2": "b", "3": "b", "4": "a"}})
        self.assertEqual(self.graph.edges["a"]["goal"], "Scout")
        self.assertEqual(self.graph.edges["b"]["leader"], "3")
        self.assertNotIn("2", self.graph.edges["a"]["tasks"])
        with self.assertRaises(PlanError):
            self.graph.regroup({"members": {"a": ["2", "4"], "b": ["3", "1"]},
                                "active": {"1": "b", "2": "a", "3": "b", "4": "a"}})
        self.assertEqual(self.graph.active["1"], "a")

    def test_fixed_replan_keeps_work_updates_available(self):
        self.graph.fixed_groups = True
        self.graph.apply(self.proposal())
        self.world["step"] = 5
        self.world["evidence_id"] = 2
        self.graph.observe(self.world)
        seen = []
        revised = self.proposal()
        revised["edges"][0]["tasks"] = {"1": "refill", "2": "approach fire"}
        revised["evidence_id"] = 2
        policy = SoftTaskPolicy("test", "unused", "unused", self.graph.emit,
            lambda messages: (seen.extend(messages) or json.dumps(revised),
                              {"prompt_tokens": 10, "completion_tokens": 5}))
        self.assertTrue(policy.decide(self.graph, {"api_calls": 0, "input_tokens": 0,
                                                    "output_tokens": 0}))
        self.assertIn("freezes existing group IDs", seen[1]["content"])
        self.assertEqual(self.graph.context("2")["suggestion"], "approach fire")


if __name__ == "__main__":
    unittest.main()
