"""Task hypergraph adapter for CREW's physical execution loop (HT mode)."""
from copy import deepcopy
import hashlib
import os
import json
import re
import time
from pathlib import Path

from .runtime import RuntimeBridge
from .crew_adapter import encode_observation, validate_low_level_action
from .soft_task_graph import SoftTaskGraph
from .soft_task_policy import SoftTaskPolicy
from .task_communication import INSTRUCTIONS, dispatch
from .task_guidance import orch_knowledge_context, observed_key_features


class TaskRuntimeBridge(RuntimeBridge):
    records_returned_actions = True

    def __init__(self, cfg, path, policy=None):
        super().__init__(cfg, path, "HT")
        self.fixed_groups = os.getenv("CREW_HT_FIXED_GROUPS") == "1"
        self.local_event_info = os.getenv("CREW_HT_LOCAL_EVENT_INFO") == "1"
        self.local_event_radius = float(os.getenv("CREW_HT_LOCAL_EVENT_RADIUS", "10"))
        if self.local_event_radius <= 0:
            raise ValueError("CREW_HT_LOCAL_EVENT_RADIUS must be positive")
        self.local_cues_sent = set()
        self.local_event_candidates = []
        self.source_view_fire_sightings_sent = set()
        self.structural_initial_plan = os.getenv("CREW_HT_STRUCTURAL_INITIAL_PLAN") == "1"
        self.round_delivery = os.getenv("CREW_HT_ROUND_DELIVERY") == "1"
        self.routed_messages = []
        self.queued_organizer_reports = []
        self.graph = SoftTaskGraph(self.c.emit, fixed_groups=self.fixed_groups, report_driven=True,
                                   direct_environment_events=True)
        self.forwarded_notice_count = 0
        self.initial_plan_path = os.getenv("CREW_HT_INITIAL_PLAN_PATH")
        if self.structural_initial_plan and self.initial_plan_path:
            raise ValueError("structural initial plan and replay plan are mutually exclusive")
        self.regroup_path = os.getenv("CREW_HT_REGROUP_PATH")
        regroup_step = os.getenv("CREW_HT_REGROUP_STEP")
        self.regroup_step = int(regroup_step) if regroup_step is not None else None
        if self.regroup_path and not self.fixed_groups:
            raise ValueError("manual regroup requires CREW_HT_FIXED_GROUPS=1")
        if bool(self.regroup_path) != (self.regroup_step is not None):
            raise ValueError("regroup path and step must be set together")
        self.regroup_done = False
        self.policy = policy
        self.bindings = {}
        self.global_data = None
        self.observed_ignition = False
        base = Path(__file__).resolve().parents[1] / "algorithms"
        knowledge = json.loads((base / "ORCH/prompts/management/knowledge_base.json").read_text())
        self.task_knowledge = knowledge["knowledge_base"].get(cfg.envs.level, {}).get("information", [])
        self.worker_abilities = {kind: (base / f"Embodied/prompts/descriptions/{kind}_description.txt").read_text()
                                 for kind in ("firefighter", "bulldozer", "drone", "helicopter")}
        self.static_context = orch_knowledge_context(cfg.envs.level)
        self.c.emit("TASK_HYPERGRAPH_STARTED", {"organization": "llm_task_stage",
                     "physical_execution": "single owner, multiple cooperation memberships",
                     "context_profile": "task_hypergraph_reports_v5",
                     "static_knowledge_source": "ORCH general + mission notes + actual Embodied action menus",
                     "communication_protocol": "typed_group_reports_v1",
                     "organizer_input": "initial mission, roster, official environment event notices, leader reports",
                     "fixed_groups": self.fixed_groups,
                     "local_event_info": self.local_event_info,
                     "local_event_radius": self.local_event_radius,
                     "structural_initial_plan": self.structural_initial_plan,
                     "round_delivery": self.round_delivery,
                     "initial_plan_replay": bool(self.initial_plan_path),
                     "manual_regroup_step": self.regroup_step})

    def observe(self, state, agents, game_data, phase):
        from crew_algorithms.wildfire_alg.core.alg_utils import get_agent_observations, check_game_done
        observed_at = time.monotonic()
        live_ids = {str(a.id) for a in agents}
        for missing in set(self.c.nodes) - live_ids:
            if self.c.nodes[missing]["online"]:
                self.c.offline(missing, "REMOVED_FROM_RUNTIME")
        for agent in agents:
            obs = get_agent_observations(state, agent.id)
            if obs["agent_type"] >= 4:
                self.c.offline(str(agent.id), "DESTROYED")
            else:
                self.c.observe(encode_observation(str(agent.id), obs, self.c.task_id,
                                                  self.session, observed_at))
        nodes = deepcopy(self.c.nodes)
        for node in nodes.values():
            # Preserve provenance: accumulated shared map is not fresh visibility.
            memory = node.get("facts", {}).get("map_memory", {})
            memory["total_cached_cells_by_kind"] = {k: len(values) for k, values in memory.get("cells", {}).items()}
            memory["prompt_cells_limit_per_kind"] = 64
            memory["cells"] = {k: values[:64] for k, values in memory.get("cells", {}).items()}
            own_view = node.get("facts", {}).get("own_view_source_candidate", {})
            own_view["total_cells_by_kind"] = {k: len(values) for k, values in own_view.get("cells", {}).items()}
            own_view["snapshot_cells_limit_per_kind"] = 64
            own_view["cells"] = {k: values[:64] for k, values in own_view.get("cells", {}).items()}
        # reward[8] is Unity's count of agents concurrently seeing fire.  The
        # global fire_active bit only says fire exists somewhere on the map.
        self.observed_ignition = self.observed_ignition or game_data["rewards"][8] >= 1
        # Event command/announcement is a report of what was injected, not proof
        # of its physical effect; actual node/reward changes remain separate.
        announcements = [dict(e) for e in (getattr(self.cfg.envs, "scheduled_events", None) or [])
                         if e["timestep"] < self.step or (phase == "after_action" and e["timestep"] == self.step)]
        civilian_target = (self.global_data or {}).get("civilian_target",
            getattr(self.cfg.envs, "civilian_count", 0) * getattr(self.cfg.envs, "civilian_clusters", 0))
        success_rules = {
            0: "reward[4] reaches the required target-tree clearing count",
            1: "reward[8] >= 2 agents concurrently see fire",
            2: "reward[6] >= starting_firefighter_agents delivered",
            3: "after a fire has begun (reward[1] > 0), fire_active=false globally: all active fires are gone",
            4: "reward[5] reaches civilian_target rescued (initial civilians plus submitted spawn events)",
            5: "after a fire has begun (reward[1] > 0), fire_active=false globally: all active fires are gone",
        }
        world = {"step": self.step, "phase": phase, "mission": game_data["task_description"],
                 "rewards": game_data["rewards"], "fire_active": game_data.get("fire_active"),
                 "reward_schema": ["exploration", "trees_burned", "trees_cut", "fire_extinguished",
                                   "correct_trees_cut", "civilians_rescued", "firefighters_transported",
                                   "civilians_scouted", "fire_scouted", "water_scouted", "agents_destroyed",
                                   "civilians_destroyed", "buildings_destroyed"],
                 "fire_has_been_observed": self.observed_ignition,
                 "event_commands_and_announcements": announcements,
                 "nodes": nodes, "task_parameters": game_data.get("task_parameters", {}),
                 "domain_knowledge": self.task_knowledge, "worker_abilities": self.worker_abilities,
                 "mission_rules": {**{key: getattr(self.cfg.envs, key, None) for key in
                     ("game_type", "map_size", "tree_count", "trees_per_line", "civilian_count",
                      "civilian_clusters", "starting_firefighter_agents")},
                      "validator_success_rule": success_rules.get(getattr(self.cfg.envs, "game_type", None))}}
        if getattr(self.cfg.envs, "game_type", None) == 4:
            world["mission_rules"]["civilian_target"] = civilian_target
        event = self.c.emit("TASK_WORLD_SNAPSHOT", world)
        world["evidence_id"] = event["event_id"]
        self.graph.observe(world)
        validator_data = {"rewards": game_data["rewards"], "game_data": game_data, "score": game_data["score"]}
        validator_data["civilian_target"] = civilian_target
        success = check_game_done(validator_data, self.cfg.envs, game_data["score"])
        self.last_validation = {"timestep": self.step, "observation_phase": phase, "success": bool(success),
                                "rewards": game_data["rewards"], "fire_active": game_data.get("fire_active"),
                                "civilian_target": validator_data.get("civilian_target"),
                                "validator": "core.alg_utils.check_game_done"}
        self.c.emit("TASK_VALIDATED", self.last_validation)
        return success

    def _organize(self, global_data):
        if self.policy is None:
            self.policy = SoftTaskPolicy(self.cfg.envs.model_name, self.cfg.envs.llm_url,
                                        global_data["api_key"], self.c.emit,
                                        static_context=self.static_context)
        try:
            accepted = self.policy.decide(self.graph, global_data)
        except Exception as exc:
            self.c.emit("TASK_ORGANIZER_FAILED", {"exception_type": type(exc).__name__})
            accepted = False
        if not accepted:
            self.graph.ensure_fallback()
        return accepted

    def allows_inference(self, agent):
        return self.graph.ready(str(agent.id))

    def requires_hold(self, agent):
        node = self.c.nodes.get(str(agent.id), {})
        return not self.graph.ready(str(agent.id)) or bool(node.get("facts", {}).get("in_helicopter"))

    def before_step(self, state, agents, game_data, step, global_data):
        super().before_step(state, agents, game_data, step, global_data)
        self.global_data = global_data
        self._flush_routed_messages()
        self._flush_organizer_reports()
        if step == 0 and self.structural_initial_plan:
            if self.graph.version:
                raise ValueError("structural initial plan requires an empty graph")
            from ..config.resource_scheduling.initial_structure import build_initial_structure
            proposal = build_initial_structure(
                self.graph.world["nodes"], self.graph.world["evidence_id"],
                composite=getattr(self.cfg.envs, "game_type", None) == 5)
            self.graph.apply(proposal)
            self.c.emit("TASK_STRUCTURAL_INITIAL_PLAN", {
                "step": step, "proposal": proposal,
                "roster_source": "first live world snapshot"})
        if step == 0 and self.initial_plan_path:
            if self.graph.version:
                raise ValueError("initial plan replay requires an empty graph")
            initial_bytes = Path(self.initial_plan_path).read_bytes()
            proposal = json.loads(initial_bytes)
            proposal["based_on_version"] = 0
            proposal["evidence_id"] = self.graph.world["evidence_id"]
            self.graph.apply(proposal)
            self.c.emit("TASK_INITIAL_PLAN_REPLAYED", {"step": step,
                        "source": self.initial_plan_path,
                        "sha256": hashlib.sha256(initial_bytes).hexdigest()})
        if self.regroup_step == step and not self.regroup_done:
            regroup_bytes = Path(self.regroup_path).read_bytes()
            specification = json.loads(regroup_bytes)
            self.graph.regroup(specification)
            self.regroup_done = True
            self.c.emit("TASK_MANUAL_REGROUP_APPLIED", {"step": step,
                        "source": self.regroup_path, "members": specification["members"],
                        "active": specification["active"],
                        "sha256": hashlib.sha256(regroup_bytes).hexdigest()})
        accepted = True if step == 0 and self.structural_initial_plan else self._organize(global_data)
        self._bind_tasks(agents, game_data)
        # The center sees the event first; its current task suggestions and the
        # source notice reach workers before their next inference/action round.
        for notice in self.graph.environment_notices[self.forwarded_notice_count:]:
            event = notice["event"]
            text = event.get("announcement", f"Game event: {event['action']}")
            for agent in agents:
                if str(agent.id) not in self.graph.live_agents():
                    continue
                agent.add_message("ENVIRONMENT", "CENTRAL_EVENT_NOTICE", text, self.step)
                self.c.emit("TASK_CENTRAL_NOTICE_DELIVERED", {
                    "step": self.step, "recipient": str(agent.id),
                    "source_notice_event_id": notice["event_id"], "content": text,
                    "graph_version": self.graph.version, "plan_update_accepted": accepted,
                    "provenance": "official environment event relayed by center; not a worker observation"})
        self.forwarded_notice_count = len(self.graph.environment_notices)

    def _bind_tasks(self, agents, game_data):
        for agent in agents:
            aid = str(agent.id)
            eid = self.graph.active.get(aid)
            edge = self.graph.edges.get(eid)
            binding = (eid, edge["revision"]) if edge else None
            if self.bindings.get(aid) != binding:
                self.c.emit("TASK_EXECUTION_REBOUND", {"previous": self.bindings.get(aid), "current": binding,
                                                       "advisory_rebound": True}, aid)
            self.bindings[aid] = binding
            agent.current_task = (f"Mission: {game_data['task_description']}\n"
                                  f"Suggested group goal: {edge['goal']}\n"
                                  f"Suggested next work: {edge['tasks'].get(aid, '')}\n"
                                  f"Coordination advice: {edge['advice']}\n"
                                  "This group plan is advice; revise it when observations disagree.") if edge else game_data['task_description']

    def prompt(self, agent_id, original):
        context = self.graph.context(str(agent_id))
        return (original + "\n\n" + self.static_context +
                "\n[TASK GROUP — ADVISORY]\nCurrent membership and routes override old chat roles. "
                "Active is an advisory work focus, not a ban on helping other groups.\n" +
                json.dumps(context, ensure_ascii=False))

    def perception_context(self, agent):
        if agent.type == 0 and agent.extra_variables[2] == 1:
            return ""
        return observed_key_features(agent.last_observation, agent.last_position, agent.map_range)

    def communication_prompt(self, agent_id, original):
        # Replace the base communication format instead of appending conflicting
        # GLOBAL instructions. The unmodified Embodied baseline keeps its format.
        original = original.split("You may send messages to individual agents or in a global channel.")[0]
        agent = self.runtime_agents.get(str(agent_id))
        notices = [m for m in agent.chat_history.get("ENVIRONMENT", [])
                   if m[0] in {"PUBLIC_ANNOUNCEMENT", "CENTRAL_EVENT_NOTICE", "LOCAL_EVENT_CUE"}] if agent else []
        if notices:
            central = any(m[0] == "CENTRAL_EVENT_NOTICE" for m in notices)
            local_cue = any(m[0] == "LOCAL_EVENT_CUE" for m in notices)
            original = (("[RECENT CENTRAL NOTICES — assess before the old group suggestion]\n" if central else
                         "[RECENT PUBLIC NOTICES — assess before the old group suggestion]\n") +
                        json.dumps(notices, ensure_ascii=False) + "\n"
                        "In your justification, assess these notices and any new REPORT messages first. "
                        "Extra targets can lie outside your current group goal. Members should REPORT "
                        "relevant implications to their leader: reporting new work outside the old group "
                        "goal is allowed even if you are not a leader. A REPORT to your leader is not "
                        "escalation to the center. Leaders should decide whether local work, "
                        "another leader, or the organizer can cover them. A notice is public information, "
                        "not proof you have observed the target. Escalation is optional; do not forget "
                        "ongoing deliveries.\n\n" + original)
            if local_cue:
                original = ("A LOCAL_EVENT_CUE gives only you a proximity-based reported location. "
                            "The organizer did not receive its coordinates. Report useful findings "
                            "through your group; verify active fire independently.\n" + original)
            if central and not self.local_event_info:
                original = ("The center already received these official event notices directly. "
                            "You need not discover or relay them to make the center aware. "
                            "Continue reporting your own observations, local conditions, resource gaps "
                            "and implications through your leader.\n" + original)
        return self.prompt(agent_id, original) + "\n" + INSTRUCTIONS

    def communication_order(self, agents):
        leaders = {e["leader"] for e in self.graph.edges.values()}
        return sorted(agents, key=lambda a: str(a.id) in leaders)

    def after_communication(self, global_data):
        if len(self.graph.reports) > self.graph.planned_report_count:
            self._organize(global_data)
            self._bind_tasks(list(self.runtime_agents.values()), global_data["game_data"])

    def deliver_routed_message(self, sender, recipient, source, target, content, kind):
        """Optional one-decision-step delay for worker-to-worker messages."""
        tagged = f"[{kind} edge={source} target={target} step={self.step}] {content}"
        if not self.round_delivery:
            self.runtime_agents[recipient].add_message(
                f"EDGE:{target}", f"AGENT_{sender}", tagged, self.step)
            self.graph.record_message(sender, recipient, source, target, content, kind)
            return
        queued = self.c.emit("TASK_MESSAGE_QUEUED", {
            "sender": sender, "recipient": recipient, "source": source,
            "target": target, "message_type": kind,
            "sent_step": self.step, "delivery_step": self.step + 1})
        self.routed_messages.append({"sender": sender, "recipient": recipient,
                                     "source": source, "target": target,
                                     "content": content, "kind": kind, "tagged": tagged,
                                     "delivery_step": self.step + 1,
                                     "queue_event_id": queued["event_id"]})

    def deliver_organizer_report(self, sender, source, content):
        if not self.round_delivery:
            self.graph.report(sender, source, content)
            return
        queued = self.c.emit("TASK_ORGANIZER_REPORT_QUEUED", {
            "sender": sender, "source": source,
            "sent_step": self.step, "delivery_step": self.step + 1})
        self.queued_organizer_reports.append({"sender": sender, "source": source,
                                               "content": content,
                                               "delivery_step": self.step + 1,
                                               "queue_event_id": queued["event_id"]})

    def _flush_organizer_reports(self):
        from .soft_task_graph import PlanError
        remaining = []
        for item in self.queued_organizer_reports:
            if item["delivery_step"] > self.step:
                remaining.append(item)
                continue
            try:
                self.graph.report(item["sender"], item["source"], item["content"])
            except PlanError:
                self.c.emit("TASK_QUEUED_REPORT_SUPPRESSED", {
                    "queue_event_id": item["queue_event_id"],
                    "reason": "sender_no_longer_current_leader"})
        self.queued_organizer_reports = remaining

    def _flush_routed_messages(self):
        remaining = []
        for item in self.routed_messages:
            if item["delivery_step"] > self.step:
                remaining.append(item)
                continue
            recipient = self.runtime_agents.get(item["recipient"])
            if recipient is None or item["recipient"] not in self.graph.live_agents():
                self.c.emit("TASK_QUEUED_MESSAGE_SUPPRESSED", {
                    "queue_event_id": item["queue_event_id"],
                    "recipient": item["recipient"], "reason": "recipient_offline"})
                continue
            recipient.add_message(f"EDGE:{item['target']}",
                                  f"AGENT_{item['sender']}", item["tagged"], self.step)
            self.graph.record_message(item["sender"], item["recipient"],
                                      item["source"], item["target"],
                                      item["content"], item["kind"])
        self.routed_messages = remaining

    def dispatch(self, agent, content, global_data):
        dispatch(self, agent, content)

    def after_step(self, state, agents, game_data, global_data):
        returned_actions = dict(self.pending_actions)
        super().after_step(state, agents, game_data, global_data)
        # Only a returned physical command belongs in this local history. The
        # proposed text may have been replaced by guard(), or env.step may fail.
        # This is observation feedback, not a task/receipt resolution machine.
        for aid, (_, action, before) in returned_actions.items():
            agent = self.runtime_agents.get(aid)
            after = self.c.nodes.get(aid)
            if agent is None or not hasattr(agent, "past_actions") or not before or not after:
                continue
            record = {"step": self.step, "submitted_command": action,
                      "position": [before.get("position"), after.get("position")],
                      "resources": after.get("resources"),
                      "current_cell": after.get("facts", {}).get("current_cell"),
                      "status": "env.step returned; task completion not inferred"}
            agent.past_actions.append(json.dumps(record, ensure_ascii=False))
        submitted = global_data.get("submitted_events", [])
        for event in submitted:
            if event.get("timestep") == self.step:
                if self.local_event_info and event.get("action") == "start_fire":
                    notice = {"timestep": event["timestep"], "action": "fire_alert",
                              "announcement": "Possible new fire reported; location unconfirmed. "
                                              "Scout locally and report coordinates through group communication."}
                    self.graph.receive_environment_event(notice)
                    self.c.emit("TASK_EVENT_LOCATION_WITHHELD", {
                        "step": self.step, "source_action": "start_fire",
                        "reason": "local_information_condition",
                        "world_event_still_submitted": True})
                else:
                    self.graph.receive_environment_event(event)
        for event in submitted:
            if event.get("action") != "start_fire":
                continue
            key = (event["timestep"], event.get("x"), event.get("y"))
            if not any((candidate["timestep"], candidate.get("x"), candidate.get("y")) == key
                       for candidate in self.local_event_candidates):
                self.local_event_candidates.append(dict(event))
        self._deliver_local_event_cues(self.local_event_candidates)
        self._record_source_view_fire_sightings()

    def _deliver_local_event_cues(self, events):
        """Give a coordinate cue only to a nearby worker; it is not proof of fire."""
        if not self.local_event_info:
            return
        for event in events:
            if event.get("action") != "start_fire":
                continue
            target = (float(event["x"]), float(event["y"]))
            for aid, node in self.c.nodes.items():
                key = (event["timestep"], aid)
                if key in self.local_cues_sent or not node.get("online"):
                    continue
                position = node.get("position")
                if position is None or ((position[0] - target[0]) ** 2 +
                                        (position[1] - target[1]) ** 2) ** .5 > self.local_event_radius:
                    continue
                agent = self.runtime_agents.get(aid)
                if agent is None:
                    continue
                content = (f"Nearby fire alert location: ({event['x']}, {event['y']}). "
                           "This is a reported event coordinate, not confirmation of active fire. "
                           "Inspect locally and report findings through your group.")
                agent.add_message("ENVIRONMENT", "LOCAL_EVENT_CUE", content, self.step)
                self.local_cues_sent.add(key)
                self.c.emit("TASK_LOCAL_EVENT_CUE_DELIVERED", {
                    "step": self.step, "recipient": aid, "event_timestep": event["timestep"],
                    "event_action": "start_fire", "coordinate": list(target),
                    "worker_position": position, "radius": self.local_event_radius,
                    "provenance": "proximity to submitted event coordinate; ignition unverified"})

    def _record_source_view_fire_sightings(self):
        """Audit local fire cells, excluding the outer shared-memory crop."""
        for event in self.local_event_candidates:
            target = (float(event['x']), float(event['y']))
            for aid, node in self.c.nodes.items():
                key = (event['timestep'], aid)
                if key in self.source_view_fire_sightings_sent or not node.get('online'):
                    continue
                view = node.get('facts', {}).get('own_view_source_candidate', {})
                cells = [cell for cell in view.get('cells', {}).get('fire', [])
                         if ((cell[0] - target[0]) ** 2 + (cell[1] - target[1]) ** 2) ** .5 <= 12]
                if not cells:
                    continue
                self.source_view_fire_sightings_sent.add(key)
                self.c.emit('TASK_SOURCE_VIEW_FIRE_SIGHTING', {
                    'step': self.step, 'recipient': aid,
                    'event_timestep': event['timestep'],
                    'event_coordinate': list(target),
                    'observed_fire_cells_near_event': cells[:16],
                    'worker_position': node.get('position'),
                    'own_view_radius': view.get('radius'),
                    'provenance': 'fire cells inside source-defined own update square; outer shared cache excluded; deployed-build equivalence not independently attested'})

    def action_started(self, agent, action):
        super().action_started(agent, action)
        aid = str(agent.id)
        memberships = [e for e in self.graph.edges.values() if aid in e["members"]]
        if len(memberships) > 1:
            self.c.emit("TASK_OVERLAP_ACTION", {"step": self.step,
                "memberships": [{"id": e["id"], "leader": e["leader"]} for e in memberships],
                "active": self.graph.active.get(aid), "action": action,
                "received_messages": [m for m in self.graph.messages if m["recipient"] == aid
                                      and m["step"] >= self.step - 1]}, aid)

    def guard(self, agent, action, retry):
        aid = str(agent.id)
        node = self.c.nodes.get(aid, {})
        # This is a synchronous simulation step. API wall-clock latency alone
        # does not advance the world or invalidate this step's observation.
        if self.requires_hold(agent):
            self.c.emit("TASK_ACTION_HELD", {"reason": "aboard" if node.get("facts", {}).get("in_helicopter") else "blocked/unassigned/stale task edge", "proposed": action}, aid)
            return [0, *node.get("position", agent.last_position)]
        allowed, reason = validate_low_level_action(node, action) if action is not None else (False, "no action")
        if not allowed:
            agent.add_message("ENVIRONMENT", "TASK_ACTION_FEEDBACK", reason, self.step)
            self.c.emit("TASK_ACTION_HELD", {"reason": reason, "proposed": action}, aid)
            return [0, *node["position"]]
        eid = self.graph.active.get(aid)
        self.c.emit("TASK_ACTION_AUTHORIZED", {"edge": eid,
                    "revision": self.graph.edges[eid]["revision"] if eid else None, "action": action}, aid)
        return action

    def finish(self, global_data):
        self.c.emit("TASK_HYPERGRAPH_FINISHED", {"edges": list(self.graph.edges.values()),
                    "archive": self.graph.archive, "graph_version": self.graph.version})
        super().finish(global_data)
        if hasattr(self.policy, "close"):
            self.policy.close()
