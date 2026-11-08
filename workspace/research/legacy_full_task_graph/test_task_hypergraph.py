"""Task-led organization, lifecycle, overlap and LLM-controller tests (offline)."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research"))
from legacy_full_task_graph.task_hypergraph import TaskHypergraph, ProposalError
from legacy_full_task_graph.task_policy import LLMTaskPolicy


def edge(eid, members, goal="Refill before suppression", pending=None):
    return {"id": eid, "stage": "prepare", "goal": goal,
            "reason": "water acquisition is prerequisite for spraying", "members": members,
            "leader": members[0], "tasks": {a: "refill and report water" for a in members},
            "rules": ["do not claim refill before observing water"], "communication": "all_to_all",
            "context": {"summary": "no verified refill yet", "pending": pending or []},
            "checks": [{"id": "water", "description": "leader has water", "kind": "resource",
                        "subject": members[0], "field": "water", "op": "ge", "value": 1}],
            "depends_on": []}


class TaskGraphTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        def emit(kind, payload):
            event = {"event_id": 100 + len(self.events), "event_type": kind, "payload": deepcopy(payload)}
            self.events.append(event)
            return event
        self.g = TaskHypergraph(emit)
        self.world = {"evidence_id": 1, "rewards": [0] * 13,
                      "nodes": {a: {"online": True, "position": [int(a)*100, 0], "resources": {"water": 0}}
                                for a in ["1", "2", "3"]}}
        self.g.observe(self.world)

    def proposal(self, edges=None):
        edges = edges if edges is not None else [edge("prepare", ["1", "2", "3"])]
        return {"based_on_version": self.g.version, "evidence_id": self.g.world["evidence_id"],
                "reason": "organize by prerequisite and capabilities, not distance", "reviews": [],
                "edges": deepcopy(edges), "active": {a: e["id"] for e in edges for a in e["members"]},
                "links": [], "handoffs": [], "resolved": []}

    def review(self, verdict="continue", check="unmet"):
        return {"edge_id": "prepare", "verdict": verdict, "reason": "review current water",
                "evidence": [self.g.world["evidence_id"]],
                "checks": [{"id": "water", "verdict": check, "evidence": [self.g.world["evidence_id"]]}]}

    def test_task_formation_is_not_distance_partition(self):
        self.g.apply(self.proposal())
        self.assertEqual(self.g.edges["prepare"]["members"], ["1", "2", "3"])
        self.assertTrue(self.g.ready("3"))
        self.assertEqual(self.g.edges["prepare"]["revision"], 1)

    def test_invalid_candidate_is_atomic(self):
        self.g.apply(self.proposal())
        before = self.g.decision_state()
        p = self.proposal()
        p["reviews"] = [self.review()]
        p["edges"][0]["leader"] = "missing"
        with self.assertRaises(ProposalError): self.g.apply(p)
        self.assertEqual(self.g.decision_state(), before)

    def test_world_and_graph_versions_are_checked(self):
        p = self.proposal()
        self.g.apply(p)
        with self.assertRaises(ProposalError): self.g.apply(p)
        p = self.proposal()
        p["evidence_id"] = 0
        with self.assertRaises(ProposalError): self.g.apply(p)

    def test_overlap_with_one_execution_owner_and_directed_links(self):
        p = self.proposal([edge("water", ["1", "2"]), edge("fire", ["2", "3"])])
        p["active"]["2"] = "water"
        p["links"] = [{"source": "water", "target": "fire", "mode": "shared",
                       "shared_agent": "2", "rule": "relay water readiness"}]
        self.g.apply(p)
        self.assertEqual(len(self.g.context("2")["memberships"]), 2)
        self.assertEqual(self.g.active["2"], "water")
        self.assertTrue(self.g.route("2", "3", "water", "fire")[0])
        self.assertFalse(self.g.route("3", "1", "fire", "water")[0])
        self.assertFalse(self.g.route("1", "3", "water")[0])

    def test_leader_star_and_cross_leaders(self):
        p = self.proposal([edge("water", ["1", "2", "3"]), edge("support", ["3"])])
        p["edges"][0]["communication"] = "leader_star"
        p["links"] = [{"source": "water", "target": "support", "mode": "leaders", "rule": "request support"}]
        self.g.apply(p)
        self.assertFalse(self.g.route("2", "3", "water")[0])
        self.assertTrue(self.g.route("2", "1", "water")[0])
        self.assertTrue(self.g.route("1", "3", "water", "support")[0])

    def test_cross_edge_link_needs_distinct_recipient(self):
        proposal = self.proposal([edge("original", ["1", "2", "3"]), edge("new", ["1"])])
        proposal["active"]["1"] = "new"
        proposal["links"] = [{"source": "original", "target": "new", "mode": "leaders",
                              "rule": "relay status"}]
        with self.assertRaisesRegex(ProposalError, "no distinct receiver"):
            self.g.apply(proposal)
        proposal["links"] = [{"source": "new", "target": "original", "mode": "shared",
                              "shared_agent": "1", "rule": "relay status to agent 2"}]
        self.g.apply(proposal)
        self.assertTrue(self.g.route("1", "2", "new", "original")[0])

    def test_checks_cannot_claim_completion_against_resource_evidence(self):
        self.g.apply(self.proposal())
        p = self.proposal([edge("suppress", ["1", "2", "3"])])
        p["reviews"] = [self.review("complete", "met")]
        p["handoffs"] = [{"source": "prepare", "target": "suppress", "context": "ready", "pending": []}]
        with self.assertRaisesRegex(ProposalError, "contradicts"): self.g.apply(p)
        self.assertIn("prepare", self.g.edges)

    def test_exact_check_cannot_describe_an_unmodeled_or(self):
        proposal = self.proposal()
        proposal["edges"][0]["checks"][0]["description"] = (
            "Agent 1 has water OR is already moving toward the fire")
        with self.assertRaisesRegex(ProposalError, "unmodeled OR alternative"):
            self.g.apply(proposal)
        proposal["edges"][0]["checks"][0]["description"] = "Agent 1 has water"
        self.g.apply(proposal)

    def test_transition_retires_old_stage_and_delivers_context(self):
        self.g.apply(self.proposal())
        world = deepcopy(self.world)
        world["evidence_id"] = 2
        world["nodes"]["1"]["resources"]["water"] = 5
        self.g.observe(world)
        successor = edge("suppress", ["1", "2", "3"], "suppress reachable fire")
        successor["depends_on"] = ["prepare"]
        p = self.proposal([successor])
        p["reviews"] = [self.review("complete", "met")]
        p["handoffs"] = [{"source": "prepare", "target": "suppress", "context": "leader refilled to 5; other members not yet verified", "pending": []}]
        self.g.apply(p)
        self.assertNotIn("prepare", self.g.edges)
        self.assertEqual(self.g.archive[0]["verdict"], "complete")
        self.assertEqual(self.g.context("2")["incoming_handoffs"][0]["source"], "prepare")

    def test_incomplete_retirement_must_preserve_pending_work(self):
        self.g.apply(self.proposal([edge("prepare", ["1", "2", "3"], pending=["pick up sixth firefighter"])]))
        p = self.proposal([edge("transport", ["1", "2", "3"])])
        p["reviews"] = [self.review("revise")]
        p["handoffs"] = [{"source": "prepare", "target": "transport", "context": "split into batches", "pending": []}]
        with self.assertRaisesRegex(ProposalError, "all pending"): self.g.apply(p)
        p["edges"][0]["context"]["pending"] = ["pick up sixth firefighter"]
        p["handoffs"][0]["pending"] = ["pick up sixth firefighter"]
        self.g.apply(p)
        self.assertEqual(self.g.archive[0]["verdict"], "revise")

    def test_no_silent_erase_or_drop(self):
        self.g.apply(self.proposal([edge("prepare", ["1", "2", "3"], pending=["deliver passenger"])]))
        p = self.proposal()
        p["reviews"] = [self.review()]
        with self.assertRaisesRegex(ProposalError, "erase"): self.g.apply(p)
        p = self.proposal([edge("new", ["1", "2", "3"])])
        p["reviews"] = [self.review()]
        with self.assertRaisesRegex(ProposalError, "silently"): self.g.apply(p)

    def test_explicit_evidence_resolution(self):
        self.g.apply(self.proposal([edge("prepare", ["1", "2", "3"], pending=["confirm water source"])]))
        p = self.proposal()
        p["reviews"] = [self.review()]
        p["resolved"] = [{"edge_id": "prepare", "obligation": "confirm water source", "reason": "source observed", "evidence": [1]}]
        self.g.apply(p)
        self.assertEqual(self.g.edges["prepare"]["context"]["pending"], [])

    def test_offline_leader_blocks_until_llm_reassigns(self):
        self.g.apply(self.proposal())
        world = deepcopy(self.world)
        world["nodes"]["1"]["online"] = False
        world["evidence_id"] = 2
        self.g.observe(world)
        self.assertFalse(self.g.ready("2"))
        p = self.proposal([edge("prepare", ["2", "3"])])
        p["reviews"] = [self.review("revise", "unknown")]
        self.g.apply(p)
        self.assertEqual(self.g.edges["prepare"]["leader"], "2")
        self.assertTrue(self.g.ready("2"))

    def test_review_every_check_with_real_evidence(self):
        self.g.apply(self.proposal())
        p = self.proposal()
        p["reviews"] = [self.review()]
        p["reviews"][0]["checks"][0]["evidence"] = [9999]
        with self.assertRaisesRegex(ProposalError, "unknown evidence"): self.g.apply(p)
        p["reviews"][0]["checks"] = []
        with self.assertRaisesRegex(ProposalError, "every edge check"): self.g.apply(p)

    def test_old_world_snapshot_remains_citable_for_history(self):
        self.g.apply(self.proposal())
        world = deepcopy(self.world)
        world["evidence_id"] = 2
        self.g.observe(world)
        p = self.proposal()
        p["evidence_id"] = 2
        p["based_on_version"] = self.g.version
        p["reviews"] = [self.review("continue")]
        p["reviews"][0]["evidence"] = [1, 2]
        p["reviews"][0]["checks"][0]["evidence"] = [2]
        self.g.apply(p)

    def test_new_environment_event_requires_explicit_worker_instruction(self):
        self.g.apply(self.proposal())
        command = {"timestep": 4, "action": "start_fire", "x": 70, "y": 70,
                   "announcement": "Second fire at 70,70"}
        world = deepcopy(self.world)
        world["evidence_id"] = 2
        world["event_commands_and_announcements"] = [command]
        self.g.observe(world)
        p = self.proposal()
        p["reviews"] = [self.review()]
        with self.assertRaisesRegex(ProposalError, "acknowledge each new environment event"):
            self.g.apply(p)
        p["event_acknowledgements"] = [{"command": command, "decision": "replan",
            "reason": "new fire announced, physical extent uncertain", "instruction": "Investigate the new fire at 70,70",
            "affected_edges": ["prepare"], "evidence": [2]}]
        with self.assertRaisesRegex(ProposalError, "active execution owner"):
            self.g.apply(p)
        p["edges"][0]["tasks"]["1"] = "Investigate new fire at 70,70"
        p["reviews"][0]["verdict"] = "revise"
        self.g.apply(p)
        self.assertIn("Investigate the new fire", self.g.context("1")["event_responses"][0]["instruction"])
        world["evidence_id"] = 3
        self.g.observe(world)
        p = self.proposal()
        p["reviews"] = [self.review()]
        p["edges"][0]["tasks"]["1"] = "Investigate new fire at 70,70"
        self.g.apply(p)

    def test_urgent_new_fire_requires_both_fire_owners_and_logs_advisory_rejection(self):
        self.g.apply(self.proposal())
        command = {"timestep": 4, "action": "start_fire", "x": 70, "y": 70,
                   "announcement": "second fire"}
        world = deepcopy(self.world)
        world.update(evidence_id=2, event_commands_and_announcements=[command],
                     task_parameters={"fire_known": True, "fire_x": 16, "fire_y": 41},
                     mission_rules={"game_type": 3})
        self.g.observe(world)
        proposal = self.proposal()
        proposal["reviews"] = [self.review("revise")]
        proposal["edges"][0]["tasks"]["1"] = "Investigate second fire at 70,70"
        proposal["event_acknowledgements"] = [{"command": command, "decision": "replan",
            "reason": "new incident", "instruction": "Investigate second fire",
            "affected_edges": ["prepare"], "evidence": [2]}]
        with self.assertRaisesRegex(ProposalError, "original known fire"):
            self.g.apply(proposal)
        proposal["edges"][0]["tasks"]["2"] = "Continue work at original fire 16,41"
        responses = iter([json.dumps(proposal), json.dumps({"accepted": False,
            "issues": ["local future observation uncertain"],
            "edge_reviews": [{"edge_id": "prepare", "accepted": False, "reason": "uncertain"}]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertTrue(any(e["event_type"] == "TASK_VERIFIER_ADVISORY_REJECTION" for e in self.events))

    def test_urgent_fire_can_advisory_complete_only_exact_checked_stage(self):
        self.g.apply(self.proposal())
        command = {"timestep": 4, "action": "start_fire", "x": 70, "y": 70,
                   "announcement": "second fire"}
        world = deepcopy(self.world)
        world.update(evidence_id=2, fire_active=True,
                     event_commands_and_announcements=[command],
                     task_parameters={"fire_known": True, "fire_x": 16, "fire_y": 41},
                     mission_rules={"game_type": 3})
        world["nodes"]["1"]["resources"]["water"] = 1
        self.g.observe(world)
        new = edge("new-fire", ["1"], "Respond to 70,70")
        new["tasks"]["1"] = "Investigate and suppress at 70,70"
        old = edge("old-fire", ["2", "3"], "Suppress original fire 16,41")
        old["tasks"]["2"] = "Suppress original fire at 16,41"
        proposal = self.proposal([new, old])
        proposal["reviews"] = [self.review("complete", "met")]
        proposal["handoffs"] = [{"source": "prepare", "target": "old-fire",
                                 "context": "Water was refilled; suppression remains", "pending": []}]
        proposal["event_acknowledgements"] = [{"command": command, "decision": "replan",
            "reason": "new incident", "instruction": "Agent 1 respond at 70,70",
            "affected_edges": ["new-fire", "old-fire"], "evidence": [2]}]
        responses = iter([json.dumps(proposal), json.dumps({"accepted": False,
            "issues": ["reviewer questions old stage"],
            "edge_reviews": [{"edge_id": edge_id, "accepted": False, "reason": "questioned"}
                             for edge_id in ("new-fire", "old-fire")]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertEqual(self.g.archive[-1]["verdict"], "complete")
        self.assertTrue(any(e["event_type"] == "TASK_VERIFIER_ADVISORY_REJECTION" for e in self.events))

    def test_new_fire_edge_cannot_exist_only_as_waiting_work(self):
        self.g.apply(self.proposal())
        command = {"timestep": 4, "action": "start_fire", "x": 70, "y": 70,
                   "announcement": "second fire"}
        world = deepcopy(self.world)
        world.update(evidence_id=2, event_commands_and_announcements=[command],
                     task_parameters={"fire_known": True, "fire_x": 16, "fire_y": 41},
                     mission_rules={"game_type": 3})
        self.g.observe(world)
        old = edge("prepare", ["1", "2", "3"])
        old["tasks"]["1"] = "Investigate second fire at 70,70"
        old["tasks"]["2"] = "Continue original fire at 16,41"
        new = edge("new-fire", ["3"], "Respond to second fire at 70,70")
        new["tasks"]["3"] = "Investigate second fire at 70,70"
        proposal = self.proposal([old, new])
        proposal["active"]["3"] = "prepare"
        proposal["reviews"] = [self.review("revise")]
        proposal["event_acknowledgements"] = [{"command": command, "decision": "replan",
            "reason": "new incident", "instruction": "Investigate second fire now",
            "affected_edges": ["prepare", "new-fire"], "evidence": [2]}]
        with self.assertRaisesRegex(ProposalError, "new fire cooperation edge must have an active owner"):
            self.g.apply(proposal)
        proposal["active"]["3"] = "new-fire"
        self.g.apply(proposal)
        self.assertEqual(self.g.active["3"], "new-fire")

    def test_announced_fire_keeps_active_owner_on_later_revisions(self):
        self.g.apply(self.proposal())
        command = {"timestep": 4, "action": "start_fire", "x": 70, "y": 70,
                   "announcement": "second fire"}
        world = deepcopy(self.world)
        world.update(evidence_id=2, fire_active=True,
                     event_commands_and_announcements=[command],
                     task_parameters={"fire_known": True, "fire_x": 16, "fire_y": 41},
                     mission_rules={"game_type": 3})
        self.g.observe(world)
        new = edge("new-fire", ["1"], "Respond to 70,70")
        new["tasks"]["1"] = "Investigate and suppress at 70,70"
        old = edge("prepare", ["2", "3"], "Suppress original fire 16,41")
        old["tasks"]["2"] = "Suppress original fire at 16,41"
        proposal = self.proposal([new, old])
        proposal["reviews"] = [self.review("revise")]
        proposal["event_acknowledgements"] = [{"command": command, "decision": "replan",
            "reason": "new incident", "instruction": "Agent 1 respond at 70,70",
            "affected_edges": ["new-fire", "prepare"], "evidence": [2]}]
        self.g.apply(proposal)
        world["evidence_id"] = 3
        self.g.observe(world)
        followup = self.proposal([new, old])
        followup["reviews"] = [
            {"edge_id": "new-fire", "verdict": "revise", "reason": "continue response",
             "evidence": [3], "checks": [{"id": "water", "verdict": "unmet", "evidence": [3]}]},
            {"edge_id": "prepare", "verdict": "continue", "reason": "continue original fire",
             "evidence": [3], "checks": [{"id": "water", "verdict": "unmet", "evidence": [3]}]}]
        followup["edges"][0]["tasks"]["1"] = "Refill at 15,22; postpone new-fire response"
        with self.assertRaisesRegex(ProposalError, "new/ongoing fire needs an active execution owner"):
            self.g.apply(followup)

    def test_semantic_unknown_cannot_complete(self):
        initial = self.proposal()
        initial["edges"][0]["checks"] = [{"id": "water", "kind": "semantic", "description": "safe access confirmed"}]
        self.g.apply(initial)
        p = self.proposal([edge("new", ["1", "2", "3"])])
        p["reviews"] = [self.review("complete", "unknown")]
        with self.assertRaisesRegex(ProposalError, "unknown check"): self.g.apply(p)

    def test_repair_prompt_and_usage_are_recorded(self):
        valid = self.proposal()
        outputs = iter(["not json", json.dumps(valid), json.dumps({"accepted": True, "issues": [],
            "edge_reviews": [{"edge_id": "prepare", "accepted": True, "reason": "supported"}]})])
        def transport(messages):
            return next(outputs), {"prompt_tokens": 10, "completion_tokens": 5}
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit, transport)
        usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.assertTrue(policy.decide(self.g, usage))
        self.assertEqual(usage, {"api_calls": 3, "input_tokens": 30, "output_tokens": 15})
        self.assertTrue(any(e["event_type"] == "TASK_PROPOSAL_REJECTED" for e in self.events))

    def test_no_spatial_fallback_after_llm_rejection(self):
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: ("{}", {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertFalse(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertEqual(self.g.edges, {})

    def test_model_task_revision_with_continue_label_is_reviewed_as_revision(self):
        self.g.apply(self.proposal())
        proposal = self.proposal()
        proposal["reviews"] = [self.review("continue")]
        proposal["edges"][0]["tasks"]["2"] = "cover a newly assigned search sector"
        responses = iter([json.dumps(proposal), json.dumps({"accepted": True, "issues": [],
            "edge_reviews": [{"edge_id": "prepare", "accepted": True, "reason": "revised task grounded"}]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertEqual(self.g.edges["prepare"]["tasks"]["2"], "cover a newly assigned search sector")
        self.assertTrue(any(e["event_type"] == "TASK_REVIEW_LABEL_NORMALIZED" for e in self.events))

    def test_verifier_extra_retired_edge_review_does_not_hide_candidate_review(self):
        proposal = self.proposal()
        responses = iter([json.dumps(proposal), json.dumps({"accepted": True, "issues": [],
            "edge_reviews": [{"edge_id": "retired_old_edge", "accepted": False, "reason": "no longer active"},
                             {"edge_id": "prepare", "accepted": True, "reason": "current candidate valid"}]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertTrue(any(e["event_type"] == "TASK_VERIFIER_EXTRA_REVIEWS_IGNORED" for e in self.events))

    def test_controller_preserves_omitted_pending_duty_on_retained_edge(self):
        initial = self.proposal([edge("prepare", ["1", "2", "3"], pending=["finish shared supply check"])])
        self.g.apply(initial)
        proposal = self.proposal()
        proposal["reviews"] = [self.review()]
        responses = iter([json.dumps(proposal), json.dumps({"accepted": True, "issues": [],
            "edge_reviews": [{"edge_id": "prepare", "accepted": True, "reason": "duty kept"}]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertEqual(self.g.edges["prepare"]["context"]["pending"], ["finish shared supply check"])
        self.assertTrue(any(e["event_type"] == "TASK_PENDING_NORMALIZED" for e in self.events))

    def test_controller_corrects_exact_check_verdict_from_current_world(self):
        self.g.apply(self.proposal())
        proposal = self.proposal()
        proposal["reviews"] = [self.review("continue", "met")]
        proposal["reviews"][0]["checks"][0]["evidence"] = [1]
        responses = iter([json.dumps(proposal), json.dumps({"accepted": True, "issues": [],
            "edge_reviews": [{"edge_id": "prepare", "accepted": True, "reason": "current water is zero"}]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        committed = next(e for e in self.events if e["event_type"] == "TASK_GRAPH_COMMITTED" and e["payload"]["version"] == 2)
        self.assertEqual(committed["payload"]["proposal"]["reviews"][0]["checks"][0]["verdict"], "unmet")
        self.assertTrue(any(e["event_type"] == "TASK_EXACT_CHECK_NORMALIZED" for e in self.events))

    def test_controller_transfers_retired_duties_to_model_chosen_successor(self):
        self.g.apply(self.proposal([edge("prepare", ["1", "2", "3"], pending=["suppress active fire"])]))
        proposal = self.proposal([edge("successor", ["1", "2", "3"])])
        proposal["reviews"] = [self.review("revise")]
        proposal["handoffs"] = [{"source": "prepare", "target": "successor",
                                  "context": "resource stage changed", "pending": []}]
        responses = iter([json.dumps(proposal), json.dumps({"accepted": True, "issues": [],
            "edge_reviews": [{"edge_id": "successor", "accepted": True, "reason": "duty preserved"}]})])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(responses), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertTrue(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertIn("suppress active fire", self.g.edges["successor"]["context"]["pending"])
        self.assertIn("suppress active fire", self.g.handoffs[-1]["pending"])
        self.assertTrue(any(e["event_type"] == "TASK_HANDOFF_PENDING_NORMALIZED" for e in self.events))

    def test_unknown_resource_is_not_zero(self):
        del self.g.world["nodes"]["1"]["resources"]["water"]
        self.assertIsNone(self.g.evaluate(edge("e", ["1"])["checks"][0]))

    def test_quantified_checks_require_all_subjects(self):
        check = {"id": "all", "description": "all have water", "kind": "resource",
                 "subjects": ["1", "2"], "quantifier": "all", "field": "water", "op": "ge", "value": 1}
        self.g.world["nodes"]["1"]["resources"]["water"] = 5
        self.assertFalse(self.g.evaluate(check))
        del self.g.world["nodes"]["2"]["resources"]["water"]
        self.assertIsNone(self.g.evaluate(check))
        check["quantifier"] = "any"
        self.assertTrue(self.g.evaluate(check))

    def test_validation_does_not_commit(self):
        before = self.g.decision_state()
        self.g.validate(self.proposal())
        self.assertEqual(self.g.decision_state(), before)
        self.assertEqual(self.events, [])

    def test_stage_change_requires_successor_not_label_overwrite(self):
        self.g.apply(self.proposal())
        p = self.proposal()
        p["reviews"] = [self.review("revise")]
        p["edges"][0]["stage"] = "suppression"
        with self.assertRaisesRegex(ProposalError, "successor edge id"): self.g.apply(p)

    def test_waiting_overlap_edge_activates_only_after_dependency_completed(self):
        first = edge("prepare", ["1", "2"])
        second = edge("suppress", ["2", "3"])
        second["depends_on"] = ["prepare"]
        p = self.proposal([first, second])
        p["active"]["2"] = "prepare"
        self.g.apply(p)
        self.assertTrue(self.g.ready("2"))
        self.assertFalse(self.g.ready("3"))
        self.g.world["nodes"]["1"]["resources"]["water"] = 5
        successor = edge("support", ["1"])
        p = self.proposal([second, successor])
        p["reviews"] = [self.review("complete", "met"), {"edge_id": "suppress", "verdict": "continue",
            "reason": "waiting until prerequisite committed", "evidence": [1],
            "checks": [{"id": "water", "verdict": "unmet", "evidence": [1]}]}]
        p["handoffs"] = [{"source": "prepare", "target": "suppress", "context": "water ready", "pending": []}]
        self.g.apply(p)
        self.assertTrue(self.g.ready("3"))
        self.assertEqual(self.g.active["2"], "suppress")

    def test_dependency_cycles_and_unknown_predecessors_rejected(self):
        first, second = edge("a", ["1", "2"]), edge("b", ["2", "3"])
        first["depends_on"], second["depends_on"] = ["b"], ["a"]
        with self.assertRaisesRegex(ProposalError, "cyclic"): self.g.apply(self.proposal([first, second]))
        first["depends_on"] = ["missing"]
        with self.assertRaisesRegex(ProposalError, "dependency must"): self.g.apply(self.proposal([first, second]))

    def test_world_fire_and_boarding_checks_keep_unknown_distinct(self):
        check = {"id": "clear", "kind": "world", "description": "fire clear", "field": "fire_active", "op": "eq", "value": False}
        self.assertIsNone(self.g.evaluate(check))
        self.g.world["fire_active"] = False
        self.assertTrue(self.g.evaluate(check))
        boarding = {"id": "aboard", "kind": "fact", "description": "all aboard", "subjects": ["1", "2"], "quantifier": "all", "field": "in_helicopter", "op": "eq", "value": True}
        self.g.world["nodes"]["1"]["facts"] = {"in_helicopter": True}
        self.assertIsNone(self.g.evaluate(boarding))
        self.g.world["nodes"]["2"]["facts"] = {"in_helicopter": False}
        self.assertFalse(self.g.evaluate(boarding))

    def test_semantic_verifier_can_reject_structurally_valid_plan(self):
        outputs = iter([json.dumps(self.proposal()), json.dumps({"accepted": False,
            "issues": ["goal says all passengers but check only covers leader"],
            "edge_reviews": [{"edge_id": "prepare", "accepted": False, "reason": "incomplete coverage"}]}), "{}", "{}"])
        policy = LLMTaskPolicy("test", "unused", "unused", self.g.emit,
                               lambda messages: (next(outputs), {"prompt_tokens": 1, "completion_tokens": 1}))
        self.assertFalse(policy.decide(self.g, {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}))
        self.assertEqual(self.g.edges, {})


if __name__ == "__main__":
    unittest.main()
