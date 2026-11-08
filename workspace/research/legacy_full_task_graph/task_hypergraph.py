"""Task-stage hypergraph state machine, independent of Unity and model SDKs.

An LLM proposes/reviews the complete live organization. Code enforces the
proposal schema, evidence bindings, routing permissions and atomic lifecycle.
It never creates geographical teams or invents replacement domain tasks.
"""
from copy import deepcopy
import json
import math
import re


class ProposalError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ProposalError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


class TaskHypergraph:
    def __init__(self, emit, require_event_ack=True):
        self.emit = emit
        self.require_event_ack = require_event_ack
        self.enforce_ongoing_fire_owners = True
        self.enforce_distinct_links = True
        self.enforce_exact_description = True
        self.version = 0
        self.world = None
        self.edges, self.active, self.links = {}, {}, []
        self.archive, self.messages, self.handoffs = [], [], []
        self.blocked = set()
        self.world_evidence_ids = set()
        self.acknowledged_commands = set()
        self.event_instructions = []

    def observe(self, world):
        """Facts are a new environment snapshot, never edited by model claims."""
        self.world = deepcopy(world)
        require(isinstance(world.get("nodes"), dict), "world needs nodes")
        require(isinstance(world.get("evidence_id"), int), "world needs evidence id")
        self.world_evidence_ids.add(world["evidence_id"])
        live = {a for a, n in world["nodes"].items() if n.get("online")}
        self.blocked = {eid for eid, e in self.edges.items() if not set(e["members"]) <= live}

    def decision_state(self):
        return deepcopy({"graph_version": self.version, "world": self.world,
                         "edges": list(self.edges.values()), "active": self.active,
                         "links": self.links, "blocked_edges": sorted(self.blocked),
                         "messages": self.messages[-80:], "archive": self.archive[-12:],
                         "unacknowledged_events": self.unacknowledged_events()})

    @staticmethod
    def _event_key(command):
        return json.dumps(command, sort_keys=True, ensure_ascii=False)

    def unacknowledged_events(self):
        return [event for event in self.world.get("event_commands_and_announcements", [])
                if self._event_key(event) not in self.acknowledged_commands]

    def ongoing_fire_events(self):
        """Announced fires still requiring an owner while the global fire is active.

        A shared map cell is not fresh enough to establish local extinguishment.
        Once the validator reports no active fire, this conservative duty ends.
        """
        if (self.world.get("mission_rules", {}).get("game_type") not in {3, 5} or
                self.world.get("fire_active") is not True):
            return []
        return [event for event in self.world.get("event_commands_and_announcements", [])
                if event.get("action") == "start_fire"]

    def _known_evidence(self):
        return self.world_evidence_ids | {m["event_id"] for m in self.messages}

    def _evidence(self, refs):
        require(isinstance(refs, list) and bool(refs), "check requires evidence references")
        require(all(isinstance(x, int) and x in self._known_evidence() for x in refs), "unknown evidence reference")

    def evaluate(self, check):
        """Optional exact predicates selected by the LLM; semantic stays unknown.

        True/False/None are observed fact comparisons, NOT an LLM verdict.
        """
        kind = check["kind"]
        if "subjects" in check:
            subjects = check["subjects"]
            require(isinstance(subjects, list) and subjects and len(set(subjects)) == len(subjects), "invalid quantified subjects")
            require(all(a in self.world["nodes"] for a in subjects), "unknown quantified subject")
            require(kind in {"resource", "position", "fact"}, "quantifier applies to agent predicates")
            quantifier = check.get("quantifier")
            require(quantifier in {"all", "any"}, "invalid quantifier")
            values = [self.evaluate({**{k: v for k, v in check.items() if k not in {"subjects", "quantifier"}}, "subject": a}) for a in subjects]
            if quantifier == "all":
                return False if False in values else None if None in values else True
            return True if True in values else None if None in values else False
        if kind == "semantic":
            return None
        if kind == "world":
            require(check.get("field") in {"fire_active", "fire_has_been_observed"}, "unsupported world predicate")
            value = self.world.get(check["field"])
        elif kind == "reward":
            field = check.get("field")
            require(isinstance(field, int) and 0 <= field < 13, "invalid reward index")
            rewards = self.world.get("rewards", [])
            value = rewards[field] if len(rewards) > field else None
        elif kind == "resource":
            node = self.world["nodes"].get(check.get("subject"), {})
            value = node.get("resources", {}).get(check.get("field")) if node.get("online") else None
        elif kind == "position":
            node = self.world["nodes"].get(check.get("subject"), {})
            value = node.get("position") if node.get("online") else None
        elif kind == "fact":
            require(check.get("field") == "in_helicopter", "unsupported node fact")
            node = self.world["nodes"].get(check.get("subject"), {})
            value = node.get("facts", {}).get("in_helicopter") if node.get("online") else None
        else:
            raise ProposalError("unsupported predicate kind")
        if value is None:
            return None
        op, target = check.get("op"), check.get("value")
        require(op in {"eq", "ge", "le", "near"}, "invalid predicate operator")
        if op == "near":
            require(kind == "position" and isinstance(target, list) and len(target) == 2,
                    "near needs position target")
            radius = check.get("radius")
            require(isinstance(radius, (int, float)) and math.isfinite(radius) and radius >= 0,
                    "invalid near radius")
            require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in target), "invalid position")
            return math.dist(value, target) <= radius
        if op == "eq":
            return value == target
        require(isinstance(value, (int, float)) and isinstance(target, (int, float)), "numeric comparison required")
        return value >= target if op == "ge" else value <= target

    def validate(self, proposal):
        """Same full validation without changing live state or writing commit events."""
        preview = TaskHypergraph(lambda kind, payload: {"event_id": 0}, self.require_event_ack)
        for name in ("version", "world", "world_evidence_ids", "acknowledged_commands",
                     "event_instructions", "edges", "active", "links", "archive",
                     "messages", "blocked", "handoffs", "enforce_ongoing_fire_owners",
                     "enforce_distinct_links", "enforce_exact_description"):
            setattr(preview, name, deepcopy(getattr(self, name)))
        preview.apply(proposal)

    def _review(self, review, edge):
        require(review.get("verdict") in {"continue", "revise", "complete", "abort", "blocked"}, "invalid edge verdict")
        require(nonempty(review.get("reason")), "review needs reason")
        self._evidence(review.get("evidence"))
        checks = review.get("checks")
        require(isinstance(checks, list), "review needs check results")
        indexed = {c.get("id"): c for c in checks}
        require(len(indexed) == len(checks) and set(indexed) == {c["id"] for c in edge["checks"]}, "review must cover every edge check")
        for check in edge["checks"]:
            result = indexed[check["id"]]
            require(result.get("verdict") in {"met", "unmet", "unknown"}, "invalid check verdict")
            self._evidence(result.get("evidence"))
            exact = self.evaluate(check)
            if check["kind"] != "semantic":
                expected = "unknown" if exact is None else "met" if exact else "unmet"
                require(result["verdict"] == expected, "LLM check contradicts observed predicate")
                require(self.world["evidence_id"] in result["evidence"], "predicate needs current world evidence")
            if review["verdict"] == "complete":
                require(result["verdict"] == "met", "cannot complete unmet/unknown check")

    def _edge(self, edge, live):
        require(isinstance(edge, dict), "edge must be an object")
        for key in ("id", "stage", "goal", "reason", "leader"):
            require(nonempty(edge.get(key)), f"edge needs {key}")
        members = edge.get("members")
        require(isinstance(members, list) and bool(members), "edge needs members")
        require(all(isinstance(a, str) for a in members), "member ids must be strings")
        require(len(set(members)) == len(members) and set(members) <= live, "invalid/offline members")
        require(edge["leader"] in members, "leader must be a member")
        require(isinstance(edge.get("tasks"), dict) and set(edge["tasks"]) == set(members), "every member needs a task")
        require(all(nonempty(task) for task in edge["tasks"].values()), "empty member task")
        require(isinstance(edge.get("rules"), list) and bool(edge["rules"]) and all(nonempty(r) for r in edge["rules"]), "edge needs rules")
        require(edge.get("communication") in {"all_to_all", "leader_star"}, "invalid intra-edge policy")
        context = edge.get("context")
        require(isinstance(context, dict) and nonempty(context.get("summary")), "edge needs context summary")
        pending = context.get("pending")
        require(isinstance(pending, list) and all(nonempty(p) for p in pending), "invalid pending obligations")
        checks = edge.get("checks")
        require(isinstance(checks, list) and bool(checks), "edge needs completion checks")
        require(all(isinstance(c, dict) for c in checks), "invalid checks")
        ids = [c.get("id") for c in checks]
        require(all(nonempty(c) for c in ids) and len(set(ids)) == len(ids), "invalid check ids")
        for check in checks:
            require(nonempty(check.get("description")), "check needs description")
            require(check.get("kind") in {"semantic", "reward", "resource", "position", "fact", "world"}, "invalid check kind")
            if self.enforce_exact_description and check["kind"] != "semantic":
                require(not re.search(r"\bor\b|或者|或", check["description"], re.IGNORECASE),
                        "exact check description cannot claim an unmodeled OR alternative")
            self.evaluate(check)
        dependencies = edge.get("depends_on", [])
        require(isinstance(dependencies, list) and all(nonempty(x) for x in dependencies), "invalid dependencies")

    def apply(self, proposal):
        """Validate the whole proposal before any graph/obligation mutation."""
        require(self.world is not None, "observe first")
        json.dumps(proposal, allow_nan=False)
        require(proposal.get("based_on_version") == self.version, "stale graph proposal")
        require(proposal.get("evidence_id") == self.world["evidence_id"], "stale world proposal")
        require(nonempty(proposal.get("reason")), "proposal needs reason")
        new_commands = self.unacknowledged_events()
        acknowledgements = proposal.get("event_acknowledgements", [])
        require(isinstance(acknowledgements, list), "event acknowledgements must be a list")
        require(all(isinstance(a, dict) for a in acknowledgements), "invalid event acknowledgement")
        if self.require_event_ack:
            require(len(acknowledgements) == len(new_commands) and
                    sorted(self._event_key(a.get("command")) for a in acknowledgements) ==
                    sorted(self._event_key(event) for event in new_commands),
                    "proposal must acknowledge each new environment event exactly once")
        live = {a for a, n in self.world["nodes"].items() if n.get("online")}
        candidates = proposal.get("edges")
        require(isinstance(candidates, list), "edges must be a list")
        edges = {}
        for candidate in candidates:
            self._edge(candidate, live)
            require(candidate["id"] not in edges, "duplicate edge")
            edges[candidate["id"]] = deepcopy(candidate)
        for acknowledgement in acknowledgements:
            require(acknowledgement.get("decision") in {"replan", "defer"}, "event needs replan or defer decision")
            require(nonempty(acknowledgement.get("reason")) and nonempty(acknowledgement.get("instruction")),
                    "event response needs reason and worker instruction")
            self._evidence(acknowledgement.get("evidence"))
            require(self.world["evidence_id"] in acknowledgement["evidence"],
                    "event response needs current world evidence")
            affected = acknowledgement.get("affected_edges")
            require(isinstance(affected, list) and bool(affected) and len(affected) == len(set(affected)) and
                    set(affected) <= set(edges), "event response needs affected live edges")
        reviews = proposal.get("reviews")
        require(isinstance(reviews, list), "proposal needs reviews")
        by_review = {r.get("edge_id"): r for r in reviews}
        require(len(by_review) == len(reviews) and set(by_review) == set(self.edges), "review every old edge exactly once")
        resolved = {eid: set() for eid in self.edges}
        for resolution in proposal.get("resolved", []):
            eid, obligation = resolution.get("edge_id"), resolution.get("obligation")
            require(eid in self.edges and obligation in self.edges[eid]["context"]["pending"], "unknown resolved obligation")
            require(nonempty(resolution.get("reason")), "resolution needs reason")
            self._evidence(resolution.get("evidence"))
            resolved[eid].add(obligation)
        retired = {}
        for eid, old in self.edges.items():
            review = by_review[eid]
            self._review(review, old)
            if eid not in edges:
                require(review["verdict"] in {"complete", "revise", "abort"}, "cannot silently drop work")
                retired[eid] = review
            else:
                require(edges[eid]["stage"] == old["stage"], "new stage must use successor edge id and handoff")
                changed = any(edges[eid].get(k) != old.get(k) for k in
                              ("stage", "goal", "members", "leader", "tasks", "rules", "communication", "checks", "depends_on"))
                require(review["verdict"] not in {"complete", "abort"}, "terminal edge must retire; use successor id")
                require(not changed or review["verdict"] == "revise", "changed edge needs revise review")
                require(set(old["context"]["pending"]) - resolved[eid] <= set(edges[eid]["context"]["pending"]), "cannot erase pending obligations on retained edge")
        active = proposal.get("active")
        require(isinstance(active, dict) and set(active) == live, "every live agent needs one execution edge")
        invalid_assignments = [(a, eid) for a, eid in active.items() if eid not in edges or a not in edges[eid]["members"]]
        require(not invalid_assignments, "invalid execution assignment (agent must be member of assigned edge): " + repr(invalid_assignments))
        if self.require_event_ack:
            current_replans = [a["command"] for a in acknowledgements
                               if a["command"].get("action") == "start_fire" and
                               a["decision"] == "replan"]
            for command in current_replans + ([event for event in self.ongoing_fire_events()
                                               if self._event_key(event) in self.acknowledged_commands]
                                              if self.enforce_ongoing_fire_owners else []):
                x, y = command.get("x"), command.get("y")
                require(isinstance(x, (int, float)) and isinstance(y, (int, float)),
                        "fire event needs numeric coordinates")
                pair = re.compile(rf"(?<!\d){x:g}(?:\.0+)?\s*[,;]\s*{y:g}(?:\.0+)?(?!\d)")
                affected_edges = next((a["affected_edges"] for a in acknowledgements
                                       if a["command"] == command), list(edges))
                responders = [a for a, eid in active.items()
                              if eid in affected_edges and
                              pair.search(edges[eid]["tasks"][a])]
                require(responders,
                        "new/ongoing fire needs an active execution owner whose task names its coordinates")
                new_fire_edges = [eid for eid, edge in edges.items() if eid not in self.edges and
                                  (pair.search(edge["goal"]) or
                                   any(pair.search(task) for task in edge["tasks"].values()))]
                require(not new_fire_edges or any(eid in new_fire_edges for eid in active.values()),
                        "new fire cooperation edge must have an active owner now, not only waiting members")
                initial = self.world.get("task_parameters", {})
                old_x, old_y = initial.get("fire_x"), initial.get("fire_y")
                if (self.world.get("mission_rules", {}).get("game_type") in {3, 5} and
                        initial.get("fire_known") and isinstance(old_x, (int, float)) and
                        isinstance(old_y, (int, float)) and (old_x, old_y) != (x, y)):
                    old_pair = re.compile(rf"(?<!\d){old_x:g}(?:\.0+)?\s*[,;]\s*{old_y:g}(?:\.0+)?(?!\d)")
                    require(any(old_pair.search(edges[eid]["tasks"][a]) for a, eid in active.items()),
                            "original known fire also needs an active execution owner")
        require(set().union(*(set(e["members"]) for e in edges.values())) == live if edges else not live, "membership must cover live agents")
        terminal_ids = {e["id"] for e in self.archive if e["verdict"] == "complete"} | {eid for eid, r in retired.items() if r["verdict"] == "complete"}
        archived_ids = {e["id"] for e in self.archive}
        require(not (set(edges) & archived_ids), "retired edge ids cannot be reused")
        for eid, edge in edges.items():
            require(set(edge.get("depends_on", [])) <= terminal_ids | set(edges), "dependency must be completed predecessor or current/waiting edge")
        visiting, visited = set(), set()
        def visit(eid):
            require(eid not in visiting, "cyclic edge dependencies")
            if eid in visited or eid not in edges:
                return
            visiting.add(eid)
            for dependency in edges[eid].get("depends_on", []):
                visit(dependency)
            visiting.remove(eid)
            visited.add(eid)
        for eid in edges:
            visit(eid)
        links = proposal.get("links")
        require(isinstance(links, list), "links must be a list")
        link_keys = set()
        for link in links:
            source, target, mode = link.get("source"), link.get("target"), link.get("mode")
            require(source in edges and target in edges and source != target, "invalid edge link")
            require(mode in {"leaders", "shared"} and nonempty(link.get("rule")), "invalid cross-edge policy")
            require((source, target) not in link_keys, "duplicate directed link")
            link_keys.add((source, target))
            if mode == "shared":
                shared = link.get("shared_agent")
                require(shared in set(edges[source]["members"]) & set(edges[target]["members"]), "bridge must belong to both edges")
                if self.enforce_distinct_links:
                    require(any(member != shared for member in edges[target]["members"]),
                            "cross-edge link has no distinct receiver")
            else:
                if self.enforce_distinct_links:
                    require(edges[source]["leader"] != edges[target]["leader"],
                            "cross-edge link has no distinct receiver")
        handoffs = proposal.get("handoffs")
        require(isinstance(handoffs, list), "handoffs must be a list")
        transferred = {eid: set() for eid in retired}
        for handoff in handoffs:
            source, target = handoff.get("source"), handoff.get("target")
            require(source in retired and target in edges, "handoff must connect retired to live edge")
            require(nonempty(handoff.get("context")), "handoff needs context")
            pending = handoff.get("pending")
            require(isinstance(pending, list) and all(nonempty(p) for p in pending), "invalid handoff obligations")
            require(set(pending) <= set(edges[target]["context"]["pending"]), "receiver must accept handoff obligations")
            transferred[source].update(pending)
        for eid, review in retired.items():
            pending = set(self.edges[eid]["context"]["pending"]) - resolved[eid]
            if pending:
                require(pending <= transferred[eid], "retirement must transfer all pending obligations")
            require(any(h["source"] == eid for h in handoffs) or not edges, "retired stage needs context handoff")
        for eid, edge in edges.items():
            old = self.edges.get(eid)
            comparison = {k: v for k, v in old.items() if k != "revision"} if old else None
            edge.pop("revision", None)
            edge["revision"] = old["revision"] + (comparison != edge) if old else 1
        previous = self.edges
        self.version += 1
        self.edges, self.active, self.links = edges, deepcopy(active), deepcopy(links)
        self.handoffs.extend(deepcopy(handoffs))
        self.acknowledged_commands.update(self._event_key(event) for event in new_commands)
        self.event_instructions.extend(deepcopy(acknowledgements))
        self.blocked = {eid for eid, r in by_review.items() if r["verdict"] == "blocked" and eid in edges}
        for eid, review in retired.items():
            self.archive.append({**deepcopy(previous[eid]), "verdict": review["verdict"],
                                 "review": deepcopy(review), "retired_at": self.world["evidence_id"]})
        self.emit("TASK_GRAPH_COMMITTED", {"version": self.version, "proposal": proposal,
                                          "edges": list(edges.values()), "blocked_edges": sorted(self.blocked)})
        for handoff in handoffs:
            self.emit("TASK_EDGE_HANDOFF", handoff)

    def ready(self, agent):
        eid = self.active.get(agent)
        completed = {e["id"] for e in self.archive if e["verdict"] == "complete"}
        return bool(eid in self.edges and eid not in self.blocked and
                    set(self.edges[eid].get("depends_on", [])) <= completed and
                    all(self.world["nodes"].get(a, {}).get("online") for a in self.edges[eid]["members"]))

    def route(self, sender, recipient, edge_id, target_edge=None):
        edge = self.edges.get(edge_id)
        if not edge or sender not in edge["members"]:
            return False, "sender is not a member of source edge"
        if not self.world["nodes"].get(sender, {}).get("online") or not self.world["nodes"].get(recipient, {}).get("online"):
            return False, "offline endpoint"
        if target_edge is None or target_edge == edge_id:
            if recipient not in edge["members"]:
                return False, "recipient is outside source edge"
            return (True, "intra-edge") if edge["communication"] == "all_to_all" or edge["leader"] in {sender, recipient} else (False, "leader-star policy")
        target = self.edges.get(target_edge)
        if not target or recipient not in target["members"]:
            return False, "unknown target edge/recipient"
        for link in self.links:
            if link["source"] != edge_id or link["target"] != target_edge:
                continue
            if link["mode"] == "leaders" and sender == edge["leader"] and recipient == target["leader"]:
                return True, "cross-edge leaders"
            if link["mode"] == "shared" and sender == link["shared_agent"]:
                return True, "cross-edge shared member"
        return False, "no authorized directed cross-edge link"

    def record_message(self, sender, recipient, edge_id, target_edge, content):
        event = self.emit("TASK_MESSAGE_DELIVERED", {"sender": sender, "recipient": recipient,
                         "source": edge_id, "target": target_edge or edge_id, "content": content,
                         "graph_version": self.version})
        self.messages.append({"event_id": event["event_id"], "sender": sender, "recipient": recipient,
                              "source": edge_id, "target": target_edge or edge_id, "content": content})

    def context(self, agent):
        memberships = [deepcopy(e) for e in self.edges.values() if agent in e["members"]]
        ids = {e["id"] for e in memberships}
        handoffs = [e for e in self.archive if any(a == agent for a in e["members"])][-3:]
        return {"graph_version": self.version, "execution_edge": self.active.get(agent),
                "ready": self.ready(agent), "memberships": memberships,
                "waiting_on": {e["id"]: [d for d in e.get("depends_on", []) if not any(x["id"] == d and x["verdict"] == "complete" for x in self.archive)] for e in memberships},
                "links": [l for l in self.links if l["source"] in ids or l["target"] in ids],
                "recent_messages": [m for m in self.messages if m["recipient"] == agent][-12:],
                "incoming_handoffs": [h for h in self.handoffs if h["target"] in ids],
                "event_responses": [a for a in self.event_instructions if set(a["affected_edges"]) & ids],
                "retired_memberships": handoffs,
                "observed_members": {a: deepcopy(n) for a, n in self.world["nodes"].items()
                                     if any(a in e["members"] for e in memberships)}}
