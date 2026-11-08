"""No Unity, LLM or credentials needed; invariant tests for portable state layer."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ORCH/crew-algorithms"))
from crew_algorithms.wildfire_alg.coordination.hypergraph import Coordinator
from crew_algorithms.wildfire_alg.coordination.crew_adapter import (
    encode_observation, SpatialPolicy, validate_low_level_action,
)
from crew_algorithms.wildfire_alg.coordination.runtime import RuntimeBridge


class HypergraphTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.
        self.c = Coordinator("episode", "task", 42, clock=lambda: self.now, stale_seconds=10)

    def node(self, agent, resources=None, session="s1", **extra):
        return self.c.observe(dict(agent_id=agent, task_id="task", session_epoch=session,
            observed_at=self.now, resources=resources if resources is not None else {"water": 0},
            capabilities=["navigate"], position=[int(agent), 0], **extra))

    def topology(self, contract=None):
        self.c.commit_topology(dict(based_on_state_version=self.c.state_version,
            edges=[dict(id="e", scope="work", leader="1", members=["1", "2"], contract=contract)],
            active={"1": "e", "2": "e"}))

    def test_claim_cannot_replace_runtime_water(self):
        self.node("1")
        self.c.claim("1", "1", "water", 5)
        self.assertEqual(self.c.nodes["1"]["resources"]["water"], 0)
        self.assertTrue(self.c.claims[0]["contradicted"])
        self.assertEqual(self.c.events[-1]["event_type"], "FACT_CONTRADICTED")

    def test_correct_historical_claim_not_false_contradiction(self):
        self.node("1", {"water": 5})
        self.c.claim("1", "1", "water", 5)
        self.now += 1
        self.node("1", {"water": 4})
        self.assertFalse(self.c.claims[0]["contradicted"])
        self.assertTrue(self.c.claims[0]["superseded"])

    def test_missing_is_unknown_and_old_snapshot_rejected(self):
        self.node("1", {})
        self.c.claim("1", "1", "water", 5)
        self.assertFalse(self.c.claims[-1]["contradicted"])
        self.assertNotIn("water", self.c.nodes["1"]["resources"])
        self.now -= 1
        with self.assertRaises(ValueError):
            self.node("1")

    def test_stale_and_session_invalidation(self):
        self.node("1", {"water": 5})
        self.node("2")
        self.topology()
        self.now += 11
        self.assertFalse(self.c.fresh("1"))
        self.assertNotIn('"water": 5', self.c.context("2"))
        self.node("1", {}, session="s2")
        self.assertNotIn("water", self.c.nodes["1"]["resources"])
        self.assertTrue(any(e["event_type"] == "NODE_SESSION_INVALIDATED" for e in self.c.events))

    def test_proposal_version_and_active_membership(self):
        self.node("1")
        self.node("2")
        self.topology()
        previous = self.c.topology_version
        with self.assertRaises(ValueError):
            self.c.commit_topology(dict(based_on_state_version=0, edges=[], active={}))
        self.assertEqual(previous, self.c.topology_version)
        with self.assertRaises(ValueError):
            self.c.commit_topology(dict(based_on_state_version=self.c.state_version,
                edges=[dict(id="x", scope="x", leader="1", members=["1", "2"])], active={"1": "x"}))

    def test_sticky_empty_proposal(self):
        self.node("1")
        self.node("2")
        self.topology()
        self.assertFalse(self.c.commit_topology(dict(based_on_state_version=self.c.state_version,
                                                    edges=[], active={})))
        self.assertIn("e", self.c.edges)

    def test_overlapping_membership_and_routing(self):
        for i in range(1, 8):
            self.node(str(i))
        self.c.commit_topology(SpatialPolicy().predict(self.c))
        self.assertEqual(len(self.c.active), 7)
        memberships = [e for e in self.c.edges.values() if "3" in e["members"]]
        self.assertEqual(len(memberships), 2)
        self.assertIn('"passive_scopes": [{', self.c.context("3"))
        first, last = self.c.edges["local:0"], self.c.edges["local:2"]
        self.assertFalse(self.c.allowed(first["leader"], last["leader"]))
        self.assertTrue(self.c.allowed("1", first["leader"]))
        self.assertTrue(self.c.allowed("1", "7", hard_event=True))

    def test_delivery_failure_not_ack(self):
        self.node("1")
        self.node("2")
        self.topology()
        def fail():
            raise RuntimeError("lost")
        ok, reason = self.c.send("1", "2", "hello", fail)
        self.assertFalse(ok)
        self.assertEqual(reason, "lost")
        self.assertEqual([e["event_type"] for e in self.c.events[-2:]], ["MESSAGE_SENT", "MESSAGE_FAILED"])

    def test_contract_consolidation_and_progress_credit(self):
        self.node("1", {"paper": 2, "book": 0})
        self.node("2", {"paper": 2, "book": 0})
        contract = {"requirements": {"paper": 4}, "completion": {"book": 2},
                    "progress": {"output": "book", "inputs_per_output": {"paper": 2}}}
        self.topology(contract)
        self.assertEqual(self.c.edges["e"]["phase"], "CONSOLIDATING")
        self.node("1", {"paper": 4, "book": 0})
        self.node("2", {"paper": 0, "book": 0})
        self.c.reduce()
        self.assertEqual(self.c.edges["e"]["phase"], "READY_TO_EXECUTE")
        self.node("1", {"paper": 2, "book": 1})
        self.c.reduce()
        self.assertEqual(self.c.edges["e"]["phase"], "READY_TO_EXECUTE")
        self.node("1", {"paper": 0, "book": 2})
        self.c.reduce()
        self.assertEqual(self.c.edges["e"]["phase"], "COMPLETED")
        self.node("1", {}, session="restart")
        self.c.reduce()
        self.assertEqual(self.c.edges["e"]["phase"], "COMPLETED")

    def test_handoff_requires_receiver_evidence(self):
        self.node("1", {"item": 2})
        self.node("2", {"item": 0})
        self.topology({"completion": {"item": 2}, "handoff_to": "downstream", "receiver": "2"})
        tx = self.c.plan_handoff("e", "1", "2", "item", 2)
        self.c.handoff_sent(tx)
        self.c.claim("1", "2", "item", 2)
        self.assertFalse(self.c.receiver_commit(tx, "2"))
        self.node("2", {"item": 2})
        self.assertTrue(self.c.receiver_commit(tx, "2"))
        self.assertEqual(self.c.edges["e"]["phase"], "COMPLETED")

    def test_partial_receipt_not_completion_or_double_credit(self):
        self.node("1", {"item": 2})
        self.node("2", {"item": 0})
        self.topology({"completion": {"item": 2}, "handoff_to": "downstream", "receiver": "2"})
        tx1 = self.c.plan_handoff("e", "1", "2", "item", 1)
        self.node("1", {"item": 2})  # stateVersion changes, receiver baseline does not.
        tx2 = self.c.plan_handoff("e", "1", "2", "item", 1)
        self.c.handoff_sent(tx1)
        self.c.handoff_sent(tx2)
        self.node("2", {"item": 1})
        self.assertTrue(self.c.receiver_commit(tx1, "2"))
        self.assertNotEqual(self.c.edges["e"]["phase"], "COMPLETED")
        self.assertFalse(self.c.receiver_commit(tx2, "2"))
        self.node("2", {"item": 2})
        self.assertTrue(self.c.receiver_commit(tx2, "2"))
        self.assertEqual(self.c.edges["e"]["phase"], "COMPLETED")

    def test_retired_session_cannot_resurrect(self):
        self.node("1", {"water": 5}, "s1")
        self.node("1", {}, "s2")
        with self.assertRaises(ValueError):
            self.node("1", {"water": 5}, "s1")

    def test_restart_and_wrong_collector_never_commit(self):
        self.node("1", {"item": 2})
        self.node("2", {"item": 0})
        self.topology()
        tx = self.c.plan_handoff("e", "1", "2", "item", 2)
        self.c.handoff_sent(tx)
        self.node("2", {"item": 2}, session="new")
        self.assertEqual(self.c.transactions[tx]["status"], "UNKNOWN")
        with self.assertRaises(ValueError):
            self.c.receiver_commit(tx, "2")
        tx2 = self.c.plan_handoff("e", "1", "2", "item", 2)
        self.c.handoff_sent(tx2)
        self.assertFalse(self.c.receiver_commit(tx2, "3"))
        self.assertEqual(self.c.transactions[tx2]["status"], "WRONG_COLLECTOR")

    def test_adapter_grid_and_guard_abstention(self):
        observation = dict(agent_type=0, position=(10, 10), map_range=3,
                           current_cell="3", extra_variables=[0, 0, 0],
                           perception_grid="-,w,-,\n-,*3*,f,\n-,C,-,\n")
        snapshot = encode_observation("1", observation, "task", "s", self.now)
        self.assertEqual(snapshot["facts"]["map_memory"]["cells"],
                         {"fire": [[11., 10.]], "water": [[10., 9.]], "civilian": [[10., 11.]]})
        self.assertFalse(validate_low_level_action(snapshot, [3, 11, 10])[0])
        self.assertTrue(validate_low_level_action(snapshot, [4, 10, 10])[0])
        snapshot["facts"]["current_cell_source"] = "direct_runtime"
        self.assertFalse(validate_low_level_action(snapshot, [4, 10, 10])[0])
        snapshot["resources"] = {}
        snapshot["facts"]["current_cell"] = None
        self.assertTrue(validate_low_level_action(snapshot, [3, 11, 10])[0])
        self.assertTrue(validate_low_level_action(snapshot, [4, 10, 10])[0])

    def test_source_own_view_excludes_shared_cache_outer_crop(self):
        rows = [['-'] * 51 for _ in range(51)]
        rows[25][39] = 'f'  # 14 cells east: inside drone's own view.
        rows[25][45] = 'f'  # 20 cells east: only in accumulated crop.
        observation = dict(agent_type=2, position=(50, 50), map_range=51,
                           perception_grid='\n'.join(','.join(row) + ',' for row in rows))
        snapshot = encode_observation('1', observation, 'task', 's', self.now)
        self.assertEqual(snapshot['facts']['map_memory']['cells']['fire'],
                         [[64.0, 50.0], [70.0, 50.0]])
        self.assertEqual(snapshot['facts']['own_view_source_candidate']['cells']['fire'],
                         [[64.0, 50.0]])

    def test_structured_event_schema_and_monotonic_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            c = Coordinator("e", "task", 42, event_path=path, clock=lambda: self.now)
            c.emit("TEST", {"verified": True})
            event = json.loads(path.read_text())
            for field in ("episode_id", "task_id", "task_seed", "arm", "agent_id", "session_epoch",
                          "event_id", "state_version", "timestamp_monotonic", "event_type",
                          "edge_id", "topology_version", "action_id", "message_id", "transaction_id",
                          "payload", "input_tokens", "output_tokens"):
                self.assertIn(field, event)
            self.assertEqual(event["timestamp_monotonic"], self.now)

    def test_runtime_prompt_and_message_parity(self):
        # Both plain baseline and instrumented P/SHADOW must see exact same text.
        bridge = RuntimeBridge.__new__(RuntimeBridge)
        bridge.c = self.c
        bridge.intervention = "none"
        bridge.recovery_feedback = {}
        for i in range(1, 4):
            self.node(str(i))
        self.c.commit_topology(SpatialPolicy().predict(self.c))
        class Agent:
            def __init__(self, agent_id):
                self.id, self.messages = agent_id, []
            def add_message(self, *args):
                if args[0] not in {"GLOBAL", *[f"AGENT_{i}" for i in range(1, 4) if i != self.id]}:
                    raise KeyError(args[0])
                self.messages.append(args)
        for arm in ("P", "SHADOW"):
            bridge.arm = arm
            self.assertEqual(bridge.prompt(1, "ORIGINAL PROMPT"), "ORIGINAL PROMPT")
            agents = [Agent(i) for i in range(1, 4)]
            bridge.dispatch(agents[0], "<GLOBAL>hi</GLOBAL><AGENT_2>private</AGENT_2>",
                            {"agents": agents, "time": 0})
            self.assertEqual(agents[0].messages, [("GLOBAL", "AGENT_1", "hi", 0),
                                                  ("AGENT_2", "AGENT_1", "private", 0)])
            self.assertEqual(agents[1].messages, [("AGENT_1", "AGENT_1", "private", 0),
                                                  ("GLOBAL", "AGENT_1", "hi", 0)])
            self.assertEqual(agents[2].messages, [("GLOBAL", "AGENT_1", "hi", 0)])
        bridge.arm = "HR"
        agents = [Agent(i) for i in range(1, 4)]
        bridge.dispatch(agents[0], "<GLOBAL>hi</GLOBAL>", {"agents": agents, "time": 0})
        self.assertTrue(any(m[1] == "ROUTING_FEEDBACK" for m in agents[0].messages))
        bridge.arm = "HA"
        self.assertIn("latest runtime evidence", bridge.prompt(1, "ORIGINAL PROMPT"))
        bridge.intervention = "projector_off"
        self.assertNotIn("latest runtime evidence", bridge.prompt(1, "ORIGINAL PROMPT"))

    def test_spatial_topology_changes_with_positions(self):
        for i in range(1, 8):
            self.node(str(i))
        policy = SpatialPolicy()
        first = policy.predict(self.c)
        self.c.commit_topology(first)
        snapshot = dict(self.c.nodes["7"], position=[0, 0])
        self.c.observe(snapshot)
        second = policy.predict(self.c)
        self.assertNotEqual(first["edges"][0]["members"], second["edges"][0]["members"])

    def test_member_order_is_not_topology_churn(self):
        self.node("1")
        self.node("2")
        self.topology()
        version = self.c.topology_version
        proposal = dict(based_on_state_version=self.c.state_version,
            edges=[dict(id="e", scope="work", leader="1", members=["2", "1"], contract=None)],
            active={"1": "e", "2": "e"})
        self.assertFalse(self.c.commit_topology(proposal))
        self.assertEqual(self.c.topology_version, version)
        self.assertEqual(self.c.edges["e"]["members"], ["2", "1"])
        proposal["edges"][0]["leader"] = "2"
        self.assertTrue(self.c.commit_topology(proposal))
        self.assertEqual(self.c.topology_version, version + 1)

    def test_map_cache_provenance_reaches_context(self):
        obs = dict(agent_type=2, position=(10,10), map_range=3,
                   perception_grid="f,-,-,\n-,-,-,\n-,-,-,\n")
        self.c.observe(encode_observation("1", obs, "task", "s", self.now))
        self.node("2")
        self.topology()
        facts = self.c.nodes["1"]["facts"]
        self.assertNotIn("observed_cells", facts)
        self.assertIsNone(facts["map_memory"]["cell_last_seen_at"])
        self.assertEqual(facts["map_memory"]["direct_visibility"], "unknown")
        context = self.c.context("2")
        self.assertIn('"runtime_observations"', context)
        self.assertNotIn('"verified_evidence"', context)
        self.assertIn('environment_shared_accumulated_map_crop', context)
        self.assertIn('snapshot age does not establish cell-level freshness', context)

    def test_unknown_cell_provenance_cannot_veto_refill(self):
        snapshot = {"facts": {"agent_type": 0, "current_cell": "3"}, "resources": {"water": 0}}
        self.assertTrue(validate_low_level_action(snapshot, [4,0,0])[0])
        self.assertFalse(validate_low_level_action(snapshot, [3,0,0])[0])

    def test_default_runtime_is_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(RuntimeBridge.from_environment(None, None))

    def test_unsupported_and_stress_arms_fail_before_runtime_access(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "not observable"):
                RuntimeBridge(None, None, "HF")
            with self.assertRaisesRegex(ValueError, "protocol-stress"):
                RuntimeBridge(None, None, "HG")

    def test_guard_recovery_is_llm_owned(self):
        bridge = RuntimeBridge.__new__(RuntimeBridge)
        bridge.c, bridge.arm, bridge.recovery_feedback = self.c, "HG", {}
        for i in ("1", "2"):
            self.node(i, facts={"agent_type": 0, "current_cell": "3"})
        self.topology()
        agent = SimpleNamespace(id=1)
        retries = []
        def retry():
            retries.append(bridge.recovery_feedback["1"])
            return [0, 9, 9]
        self.assertEqual(bridge.guard(agent, [3, 10, 10], retry), [0, 9, 9])
        self.assertEqual(len(retries), 1)
        self.assertEqual(self.c.events[-1]["event_type"], "RECOVERY_ACTION_SELECTED")

    def test_helicopter_unload_not_mistaken_for_spray(self):
        snapshot = {"facts": {"agent_type": 3, "current_cell": "3"},
                    "resources": {"water": 0, "firefighters_carried": 5}}
        self.assertTrue(validate_low_level_action(snapshot, [3, 0, 0])[0])

    def test_successful_early_exit_emits_final_validator(self):
        bridge = RuntimeBridge.__new__(RuntimeBridge)
        bridge.c = self.c
        bridge.step, bridge.tokens_before = 2, (0, 0)
        bridge.last_validation = {"timestep": 2, "observation_phase": "before_action", "success": True}
        bridge.finish({"input_tokens": 10, "output_tokens": 2, "api_calls": 1})
        self.assertEqual(self.c.events[-2]["event_type"], "TASK_VALIDATED")
        self.assertEqual(self.c.events[-2]["payload"]["observation_phase"], "episode_end")
        self.assertTrue(self.c.events[-2]["payload"]["success"])

    def test_malformed_contract_does_not_commit(self):
        self.node("1")
        self.node("2")
        self.topology()
        previous = self.c.topology_version
        with self.assertRaises(ValueError):
            self.topology({"requirements": {"water": -1}})
        self.assertEqual(self.c.topology_version, previous)
        self.assertIsNone(self.c.edges["e"]["contract"])

    def test_compact_context_preserves_resources_without_map_or_empty_stages(self):
        self.node("1", resources={"water": 0}, facts={"agent_type": 0,
            "in_helicopter": False, "map_memory": {"cells": {"fire": [[9, 9]]}}})
        self.node("2")
        self.topology()
        context = self.c.compact_context("2")
        self.assertIn('"water": 0', context)
        self.assertIn('"in_helicopter": false', context)
        for field in ('"map_memory"', '"contract"', '"phase"', '"session_epoch"', '"passive_scopes"'):
            self.assertNotIn(field, context)
        self.assertNotIn("leader", context)
        self.assertLess(len(context), len(self.c.context("2")))

    def test_compact_routing_lists_exact_live_recipients(self):
        for i in range(1, 8):
            self.node(str(i))
        self.c.commit_topology(SpatialPolicy().predict(self.c))
        for agent in self.c.nodes:
            data = json.loads(self.c.compact_context(agent, routing=True).split("\n", 1)[1])
            expected = sorted(a for a in self.c.nodes if a != agent and self.c.allowed(agent, a))
            self.assertEqual(data["allowed_recipients"], expected)
        self.c.offline("2")
        self.assertNotIn('"2"', json.loads(self.c.compact_context("1", True).split("\n",1)[1])["allowed_recipients"])

    def test_routing_feedback_aggregates_without_losing_recipient_events(self):
        for i in range(1, 5):
            self.node(str(i))
        self.c.commit_topology(SpatialPolicy().predict(self.c))
        bridge = RuntimeBridge.__new__(RuntimeBridge)
        bridge.c, bridge.arm, bridge.recovery_feedback = self.c, "HR", {}
        messages = {i: [] for i in range(1, 5)}
        agents = [SimpleNamespace(id=i, add_message=lambda *args, i=i: messages[i].append(args))
                  for i in range(1, 5)]
        bridge.dispatch(agents[0], "<GLOBAL>update</GLOBAL>", {"agents": agents, "time": 0})
        feedback = [m for m in messages[1] if m[1] == "ROUTING_FEEDBACK"]
        self.assertEqual(len(feedback), 1)
        suppressed = [e for e in self.c.events if e["event_type"] == "MESSAGE_SUPPRESSED"]
        self.assertEqual(len(suppressed), 2)
        for e in suppressed:
            self.assertIn('"'+e["payload"]["recipient"]+'"', feedback[0][2])

    def test_hr_no_local_delta_is_logged_without_automatic_leader_notice(self):
        self.node("1")
        bridge = RuntimeBridge.__new__(RuntimeBridge)
        bridge.c, bridge.arm, bridge.step = self.c, "HR", 0
        bridge.recovery_feedback, bridge.tokens_before = {}, (0, 0)
        bridge.pending_actions = {"1": ("a1", [1, 9, 9], dict(self.c.nodes["1"]))}
        with patch.object(bridge, "observe"), patch.object(bridge, "hard_notice") as notice:
            bridge.after_step(None, [], {}, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0})
            notice.assert_not_called()
        self.assertTrue(any(e["event_type"] == "ACTION_NO_EFFECT" for e in self.c.events))

    def test_compact_context_omits_stale_peer(self):
        self.node("1", resources={"water": 5})
        self.node("2")
        self.topology()
        self.now += 11
        self.node("2")
        self.assertNotIn('"water": 5', self.c.compact_context("2"))

    def test_hard_notice_really_delivered(self):
        self.node("1")
        self.node("2")
        self.topology()
        messages = []
        bridge = RuntimeBridge.__new__(RuntimeBridge)
        bridge.c, bridge.step = self.c, 0
        bridge.runtime_agents = {"1": SimpleNamespace(add_message=lambda *args: messages.append(args))}
        bridge.hard_notice("2", "ACTION_NO_EFFECT", {"action": [1, 0, 0]})
        self.assertEqual(len(messages), 1)
        self.assertEqual(self.c.events[-2]["event_type"], "MESSAGE_DELIVERED")
        self.assertEqual(self.c.events[-1]["event_type"], "ESCALATION_SENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
