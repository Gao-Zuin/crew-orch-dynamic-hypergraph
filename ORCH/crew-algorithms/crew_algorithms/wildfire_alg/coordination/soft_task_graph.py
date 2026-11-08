"""Small, advisory task hypergraph for embodied workers.

The graph coordinates prompts and message recipients. It is not an action
authorization system: an imperfect plan must not stop physical work.
"""
from copy import deepcopy
import json
from .ability_atoms import catalog_for_nodes, SHARING_SEMANTICS


class PlanError(ValueError):
    pass


class SoftTaskGraph:
    def __init__(self, emit, fixed_groups=False, report_driven=False, direct_environment_events=False):
        self.emit = emit
        self.fixed_groups = fixed_groups
        self.group_lock = None
        self.version = 0
        self.world = None
        self.edges = {}
        self.active = {}
        self.archive = []
        self.messages = []
        self.last_planned_step = -1
        self.planned_events = set()
        self.report_driven = report_driven
        self.reports = []
        self.planned_report_count = 0
        self.initial_mission = None
        self.direct_environment_events = direct_environment_events
        self.environment_notices = []
        self.planned_notice_count = 0

    def receive_environment_event(self, event):
        """Record an executed event's official notice, not the future schedule/world."""
        announced = {key: deepcopy(event[key]) for key in
                     ("timestep", "action", "x", "y", "announcement") if key in event}
        if any(n["event"] == announced for n in self.environment_notices):
            return
        payload = {"step": self.world["step"], "source": "environment_event_notification",
                   "event": announced,
                   "provenance": "submitted event after env.step returned; not a worker observation or a live fire-front map"}
        logged = self.emit("TASK_ENVIRONMENT_NOTICE", payload)
        self.environment_notices.append({"event_id": logged["event_id"], **payload})

    def observe(self, world):
        self.world = deepcopy(world)
        if self.initial_mission is None:
            self.initial_mission = world["mission"]

    def live_agents(self):
        return {a for a, node in self.world["nodes"].items() if node.get("online")}

    def event_keys(self):
        return {json.dumps(e, sort_keys=True) for e in
                self.world.get("event_commands_and_announcements", [])}

    def needs_plan(self):
        live = self.live_agents()
        if not live:
            return bool(self.edges or self.active)
        return (not self.edges or set(self.active) != live or
                (self.direct_environment_events and len(self.environment_notices) > self.planned_notice_count) or
                (len(self.reports) > self.planned_report_count if self.report_driven else
                 bool(self.event_keys() - self.planned_events)) or
                self.world["step"] - self.last_planned_step >= 5)

    def decision_state(self):
        world = self.world
        if self.report_driven:
            ability_keys, ability_catalog = catalog_for_nodes(world["nodes"])
            state = {"version": self.version, "evidence_id": world["evidence_id"],
                    "step": world["step"], "mission": self.initial_mission,
                    "agents": {a: {"capabilities": n.get("capabilities"),
                                   "ability_atoms": ability_keys[a],
                                   "online": n.get("online")}
                               for a, n in world["nodes"].items()},
                    "ability_catalog": ability_catalog,
                    "ability_sharing": SHARING_SEMANTICS,
                    "edges": deepcopy(list(self.edges.values())), "active": dict(self.active),
                    "leader_reports": deepcopy(self.reports[-20:]),
                    "input_provenance": "initial mission, capability/availability roster, leader reports; no live world snapshot"}
            if self.direct_environment_events:
                state["environment_notices"] = deepcopy(self.environment_notices)
                state["input_provenance"] = "initial mission, capability/availability roster, official environment event notices, leader reports; no live world snapshot"
            return state
        return {"version": self.version, "evidence_id": world["evidence_id"],
                "step": world["step"], "mission": world["mission"],
                "rewards": world["rewards"], "fire_active": world.get("fire_active"),
                "reward_schema": world.get("reward_schema", []),
                "events": world.get("event_commands_and_announcements", []),
                "agents": {a: {"position": n.get("position"),
                               "resources": n.get("resources"),
                               "capabilities": n.get("capabilities"),
                               "online": n.get("online")}
                           for a, n in world["nodes"].items()},
                "edges": list(self.edges.values()), "active": self.active}

    def report(self, sender, edge_id, content):
        edge = self.edges.get(edge_id)
        if not edge or edge["leader"] != sender or sender not in self.live_agents():
            raise PlanError("only a current group leader reports to the organizer")
        event = self.emit("TASK_LEADER_REPORT", {"sender": sender, "source": edge_id,
                          "content": content, "step": self.world["step"],
                          "graph_version": self.version})
        self.reports.append({"event_id": event["event_id"], "sender": sender,
                             "source": edge_id, "content": content,
                             "step": self.world["step"], "graph_version": self.version})

    def _topology(self, edges, active):
        return {"members": {eid: frozenset(edge["members"]) for eid, edge in edges.items()},
                "leaders": {eid: edge["leader"] for eid, edge in edges.items()},
                "active": dict(active)}

    def apply(self, proposal, manual_regroup=False, attrition=False):
        if (proposal.get("based_on_version") != self.version or
                proposal.get("evidence_id") != self.world["evidence_id"]):
            raise PlanError("stale plan")
        candidates = proposal.get("edges")
        active = proposal.get("active")
        live = self.live_agents()
        if not isinstance(candidates, list) or not isinstance(active, dict):
            raise PlanError("edges and active assignments are required")
        edges = {}
        for raw in candidates:
            if not isinstance(raw, dict):
                raise PlanError("invalid edge")
            eid, members, leader = raw.get("id"), raw.get("members"), raw.get("leader")
            if (not isinstance(eid, str) or not eid or eid in edges or
                    not isinstance(members, list) or not members or
                    len(set(members)) != len(members) or not set(members) <= live or
                    leader not in members or not isinstance(raw.get("goal"), str) or
                    not raw["goal"].strip()):
                raise PlanError("invalid edge membership or goal")
            tasks = raw.get("tasks", {})
            if not isinstance(tasks, dict) or not set(tasks) <= set(members) or any(
                    not isinstance(v, str) for v in tasks.values()):
                raise PlanError("invalid member suggestions")
            edge = {"id": eid, "goal": raw["goal"], "members": members,
                    "leader": leader, "tasks": tasks,
                    "advice": raw.get("advice", "")}
            if not isinstance(edge["advice"], str):
                raise PlanError("advice must be text")
            previous = self.edges.get(eid)
            edge["revision"] = (previous["revision"] + (any(
                edge[k] != previous[k] for k in ("goal", "members", "leader", "tasks", "advice")))
                if previous else 1)
            edges[eid] = edge
        if set(active) != live or any(eid not in edges or a not in edges[eid]["members"]
                                      for a, eid in active.items()):
            raise PlanError("each live agent needs one active edge")
        topology = self._topology(edges, active)
        if self.fixed_groups and self.group_lock is not None and not attrition:
            if manual_regroup:
                if (set(edges) != set(self.edges) or
                        {eid: len(edge["members"]) for eid, edge in edges.items()} !=
                        {eid: len(edge["members"]) for eid, edge in self.edges.items()} or
                        topology["leaders"] != self.group_lock["leaders"]):
                    raise PlanError("regroup must preserve group IDs, sizes and leaders")
            elif topology != self.group_lock:
                raise PlanError("fixed group membership, leader or active assignment changed")
        retired = [deepcopy(edge) for eid, edge in self.edges.items() if eid not in edges]
        self.archive.extend(retired)
        self.edges, self.active = edges, deepcopy(active)
        self.version += 1
        self.last_planned_step = self.world["step"]
        self.planned_events = self.event_keys()
        self.planned_report_count = len(self.reports)
        self.planned_notice_count = len(self.environment_notices)
        if self.fixed_groups:
            self.group_lock = topology
        self.emit("TASK_GRAPH_COMMITTED", {"version": self.version,
                  "proposal": deepcopy(proposal), "edges": list(edges.values()),
                  "retired": [e["id"] for e in retired],
                  "manual_regroup": manual_regroup, "attrition": attrition})

    def regroup(self, specification):
        """Change memberships once, with no new goals, instructions or messages."""
        if not self.fixed_groups or self.group_lock is None:
            raise PlanError("regroup requires an established fixed graph")
        members = specification.get("members")
        active = specification.get("active")
        if not isinstance(members, dict) or not isinstance(active, dict):
            raise PlanError("regroup needs members and active maps")
        edges = deepcopy(list(self.edges.values()))
        if set(members) != {edge["id"] for edge in edges}:
            raise PlanError("regroup must retain all group IDs")
        for edge in edges:
            edge["members"] = members[edge["id"]]
            edge["tasks"] = {a: task for a, task in edge["tasks"].items()
                             if a in edge["members"]}
            edge.pop("revision", None)
        proposal = {"based_on_version": self.version,
                    "evidence_id": self.world["evidence_id"],
                    "reason": "registered manual diagnostic membership change",
                    "edges": edges, "active": active}
        self.apply(proposal, manual_regroup=True)

    def ensure_fallback(self):
        live = sorted(self.live_agents())
        if not live:
            if self.edges or self.active:
                self.apply({"based_on_version": self.version,
                            "evidence_id": self.world["evidence_id"],
                            "reason": "no online workers remain",
                            "edges": [], "active": {}}, attrition=True)
                self.emit("TASK_GROUP_ATTRITION", {"live_agents": []})
            return
        # A rejected suggestion during attrition must not erase surviving groups.
        if self.edges and set(live) < set(self.active):
            edges = []
            for old in self.edges.values():
                edge = deepcopy(old)
                edge["members"] = [a for a in edge["members"] if a in live]
                if not edge["members"]:
                    continue
                edge["leader"] = edge["leader"] if edge["leader"] in edge["members"] else edge["members"][0]
                edge["tasks"] = {a: task for a, task in edge["tasks"].items() if a in live}
                edge.pop("revision", None)
                edges.append(edge)
            active = {a: eid for a, eid in self.active.items() if a in live}
            self.apply({"based_on_version": self.version,
                        "evidence_id": self.world["evidence_id"],
                        "reason": "remove offline members only", "edges": edges,
                        "active": active}, attrition=True)
            self.emit("TASK_GROUP_ATTRITION", {"live_agents": live})
            return
        if self.edges and set(self.active) == set(live) and all(
                eid in self.edges and a in self.edges[eid]["members"]
                for a, eid in self.active.items()):
            self.emit("TASK_PLAN_RETAINED", {"reason": "invalid new suggestion"})
            return
        proposal = {"based_on_version": self.version,
                    "evidence_id": self.world["evidence_id"],
                    "reason": "continue mission while organization is unavailable",
                    "edges": [{"id": "mission", "goal": self.world["mission"],
                               "members": live, "leader": live[0], "tasks": {},
                               "advice": "Coordinate using observed facts; revise when new evidence arrives."}],
                    "active": {a: "mission" for a in live}}
        self.apply(proposal)
        self.emit("TASK_PLAN_FALLBACK", {"reason": "no usable current suggestion"})

    def ready(self, agent):
        return agent in self.live_agents()

    def route(self, sender, recipient, edge_id, target_edge=None):
        if sender == recipient or sender not in self.live_agents() or recipient not in self.live_agents():
            return False, "invalid endpoint"
        source = self.edges.get(edge_id)
        target = self.edges.get(target_edge or edge_id)
        if not source or not target or sender not in source["members"] or recipient not in target["members"]:
            return False, "outside stated groups"
        if source is target:
            return True, "within group"
        if sender in set(source["members"]) & set(target["members"]):
            return True, "shared member"
        if sender == source["leader"] and recipient == target["leader"]:
            return True, "group coordinators"
        return False, "use a shared member or group coordinators"

    def record_message(self, sender, recipient, edge_id, target_edge, content, message_type=None):
        payload = {"sender": sender, "recipient": recipient,
                          "source": edge_id, "target": target_edge or edge_id,
                          "content": content, "graph_version": self.version,
                          "step": self.world["step"]}
        if message_type is not None:
            payload["message_type"] = message_type
        event = self.emit("TASK_MESSAGE_DELIVERED", payload)
        self.messages.append({"event_id": event["event_id"], "sender": sender,
                              "recipient": recipient, "content": content,
                              "source": edge_id, "target": target_edge or edge_id,
                              "message_type": message_type,
                              "step": self.world["step"], "graph_version": self.version})

    def context(self, agent):
        edge_id = self.active.get(agent)
        edge = self.edges.get(edge_id)
        if not edge:
            return {"goal": self.world["mission"], "suggestion": "Continue the mission."}
        # Render existing routing rules as concrete examples, not generic IDs
        # that the model has to guess or carry forward from old chat.
        memberships = [e for e in self.edges.values() if agent in e["members"]]
        examples = []
        for own in memberships:
            examples.append(f'<GROUP edge="{own["id"]}">group update</GROUP>')
            for member in own["members"]:
                if member != agent:
                    examples.append(f'<GROUP edge="{own["id"]}" to="{member}">message for member {member}</GROUP>')
            if own["leader"] != agent:
                examples.append(f'<REPORT edge="{own["id"]}">observation or help needed</REPORT>')
            else:
                examples.append(f'<ORGANIZER edge="{own["id"]}">analysis and organizational help needed</ORGANIZER>')
                for other in self.edges.values():
                    if other["id"] != own["id"] and other["leader"] != agent:
                        examples.append(f'<LEADER edge="{own["id"]}" to="{other["id"]}">request for leader {other["leader"]}</LEADER>')
        node = self.world["nodes"].get(agent, {})
        return {"step": self.world["step"], "graph_version": self.version,
                "group": edge_id, "goal": edge["goal"], "leader": edge["leader"],
                "members": edge["members"], "suggestion": edge["tasks"].get(agent, ""),
                "advice": edge["advice"],
                "memberships": [{"id": e["id"], "goal": e["goal"], "leader": e["leader"],
                                  "members": e["members"], "suggestion": e["tasks"].get(agent, "")}
                                 for e in self.edges.values() if agent in e["members"]],
                "group_directory": [{"id": e["id"], "goal": e["goal"], "leader": e["leader"],
                                     "members": e["members"]}
                                    for e in self.edges.values()],
                "current_route_examples": examples,
                "own_observation": {"position": node.get("position"),
                                    "resources": node.get("resources"),
                                    "current_cell": node.get("facts", {}).get("current_cell"),
                                    "cell_provenance": "shared map cache; check current perception"},
                "message_history": [m for m in self.messages if m["recipient"] == agent][-5:]}
