"""Benchmark-neutral, deterministic evidence/topology runtime.

Snapshots are complete observations of the supplied fields, NOT complete world
states. An omitted resource is unknown. Claims never modify runtime evidence.
The policy owns membership only; contracts must come from trusted task metadata.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import time


class Coordinator:
    def __init__(self, episode_id, task_id, seed, arm="HA", event_path=None,
                 clock=time.monotonic, stale_seconds=360):
        if arm not in {"P", "SHADOW", "HA", "HR", "HG", "HF", "HT"}:
            raise ValueError("Unknown protocol arm")
        self.episode_id, self.task_id, self.seed, self.arm = episode_id, task_id, seed, arm
        self.clock, self.stale_seconds = clock, stale_seconds
        self.state_version = self.topology_version = 0
        self.nodes, self.claims, self.transactions = {}, [], {}
        self.edges, self.active, self.events = {}, {}, []
        self.committed_scopes = set()
        self.retired_sessions = set()
        self.path = Path(event_path) if event_path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                raise FileExistsError(self.path)

    def emit(self, event_type, payload=None, agent_id=None, **ids):
        event = dict(episode_id=self.episode_id, task_id=self.task_id,
                     task_seed=self.seed, arm=self.arm, agent_id=agent_id,
                     session_epoch=self.nodes.get(agent_id, {}).get("session_epoch"),
                     event_id=len(self.events) + 1, state_version=self.state_version,
                     timestamp_monotonic=self.clock(), event_type=event_type,
                     topology_version=self.topology_version, edge_id=None,
                     action_id=None, message_id=None, transaction_id=None,
                     payload=deepcopy(payload or {}), input_tokens=0, output_tokens=0)
        event.update(ids)
        # Reject NaN, non-serializable payloads, etc. before modifying the ledger.
        encoded = json.dumps(event, ensure_ascii=False, allow_nan=False)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(encoded + "\n")
        self.events.append(event)
        return event

    def observe(self, snapshot):
        node = deepcopy(snapshot)
        json.dumps(node, allow_nan=False)
        required = {"agent_id", "session_epoch", "observed_at", "resources",
                    "capabilities", "position", "task_id"}
        if not required <= node.keys() or node["task_id"] != self.task_id:
            raise ValueError("Invalid snapshot/task")
        if not math.isfinite(node["observed_at"]) or node["observed_at"] > self.clock():
            raise ValueError("Invalid observation time")
        for value in node["resources"].values():
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("Invalid resource observation")
        agent = node["agent_id"]
        if (agent, node["session_epoch"]) in self.retired_sessions:
            raise ValueError("Snapshot from retired session")
        previous = self.nodes.get(agent)
        if previous and previous["session_epoch"] == node["session_epoch"]:
            if node["observed_at"] < previous["observed_at"]:
                raise ValueError("Out-of-order snapshot")
        if previous and previous["session_epoch"] != node["session_epoch"]:
            self.retired_sessions.add((agent, previous["session_epoch"]))
            for tx in self.transactions.values():
                if agent in (tx["sender"], tx["receiver"]) and tx["status"] not in {
                    "RECEIVER_COMMITTED", "CONSUMED_DOWNSTREAM", "ABORTED"
                }:
                    tx["status"] = "UNKNOWN"
            self.emit("NODE_SESSION_INVALIDATED", {"previous_session": previous["session_epoch"]}, agent)
        self.state_version += 1
        node.update(state_version=self.state_version, online=True)
        self.nodes[agent] = node
        if not previous or not previous.get("online", False) or previous["session_epoch"] != node["session_epoch"]:
            self.emit("NODE_JOINED" if not previous else "NODE_REJOINED", agent_id=agent)
        self.emit("STATE_OBSERVED", node, agent)
        for claim in self.claims:
            if claim["subject"] == agent and claim["session"] == node["session_epoch"]:
                value = node["resources"].get(claim["resource"])
                if value is not None and value != claim["value"] and not claim.get("superseded"):
                    # A historically correct statement is not a contradiction
                    # merely because a later action legitimately changes state.
                    claim["superseded"] = True
                    self.emit("CLAIM_SUPERSEDED", {"claim": claim, "new_runtime_value": value}, claim["speaker"])
        return deepcopy(node)

    def fresh(self, agent):
        node = self.nodes.get(agent)
        return bool(node and node["online"] and
                    self.clock() - node["observed_at"] <= self.stale_seconds)

    def offline(self, agent, reason="OFFLINE"):
        if agent in self.nodes:
            self.state_version += 1
            self.nodes[agent]["online"] = False
            self.emit("NODE_OFFLINE", {"reason": reason}, agent)

    def claim(self, speaker, subject, resource, value):
        node = self.nodes.get(subject)
        claim = dict(speaker=speaker, subject=subject, resource=resource, value=value,
                     session=node["session_epoch"] if node else None, contradicted=False,
                     based_on_state_version=self.state_version, claimed_at=self.clock(), superseded=False)
        self.claims.append(claim)
        self.emit("FACT_CLAIMED", claim, speaker)
        if self.fresh(subject) and resource in node["resources"] and node["resources"][resource] != value:
            claim["contradicted"] = True
            self.emit("FACT_CONTRADICTED", {"claim": claim, "runtime_value": node["resources"][resource]}, speaker)

    def commit_topology(self, proposal):
        self.emit("TOPOLOGY_PROPOSED", proposal)
        if proposal["based_on_state_version"] != self.state_version:
            raise ValueError("Stale topology proposal")
        candidate = deepcopy(proposal["edges"])
        active = deepcopy(proposal["active"])
        # A transient empty proposal is not authority to discard incomplete work.
        if not candidate and any(e["scope"] not in self.committed_scopes for e in self.edges.values()):
            self.emit("TOPOLOGY_RETAINED", {"reason": "sticky_incomplete_membership"})
            return False
        edges = {}
        for edge in candidate:
            if edge["id"] in edges or len(set(edge["members"])) != len(edge["members"]):
                raise ValueError("Duplicate edge/member")
            if edge["leader"] not in edge["members"] or not edge["members"]:
                raise ValueError("Leader must belong to nonempty edge")
            if any(not self.fresh(a) for a in edge["members"]):
                raise ValueError("Unknown/offline/stale member")
            edge.setdefault("phase", "ACTIVE")
            edge.setdefault("contract", None)
            contract = edge["contract"]
            if contract is not None:
                if not isinstance(contract, dict):
                    raise ValueError("Invalid contract")
                quantities = [contract.get(key, {}) for key in ("requirements", "completion", "handoff_completion")]
                progress = contract.get("progress", {})
                if not isinstance(progress, dict):
                    raise ValueError("Invalid progress contract")
                quantities.append(progress.get("inputs_per_output", {}))
                for quantity_map in quantities:
                    if not isinstance(quantity_map, dict) or any(
                        not isinstance(n, (float, int)) or not math.isfinite(n) or n < 0
                        for n in quantity_map.values()
                    ):
                        raise ValueError("Invalid contract quantity")
            edges[edge["id"]] = edge
        members = {a for e in candidate for a in e["members"]}
        if set(active) != members:
            raise ValueError("Each member needs exactly one active edge")
        if any(e not in edges or a not in edges[e]["members"] for a, e in active.items()):
            raise ValueError("Invalid active membership")
        old_active = self.active
        # Membership order is presentation, not a change in the relation.
        def canonical_membership(mapping):
            return {key: {**value, "members": sorted(value["members"])}
                    for key, value in mapping.items()}
        structural_change = (canonical_membership(edges) != canonical_membership(self.edges)
                             or active != self.active)
        if structural_change:
            self.topology_version += 1
        self.edges, self.active = edges, active
        self.reduce()
        self.emit("TOPOLOGY_COMMITTED", {"edges": list(self.edges.values()), "active": active,
                                        "based_on_state_version": self.state_version,
                                        "structural_change": structural_change})
        for agent, edge in active.items():
            if old_active.get(agent) != edge:
                self.emit("ACTIVE_EDGE_SWITCHED" if agent in old_active else "EDGE_ACTIVATED",
                          {"previous_edge": old_active.get(agent)}, agent, edge_id=edge)
        return structural_change

    def _amounts(self, members):
        # Unknown fields are omitted. Do not manufacture zero observations.
        resources = {}
        for agent in members:
            if self.fresh(agent):
                for resource, value in self.nodes[agent]["resources"].items():
                    resources[resource] = resources.get(resource, 0) + value
        return resources

    @staticmethod
    def _met(requirements, amounts):
        return all(k in amounts and amounts[k] >= n for k, n in requirements.items())

    def reduce(self):
        for edge in self.edges.values():
            contract = edge.get("contract")
            if not contract:
                edge["phase"] = "ACTIVE"
                continue
            if edge["scope"] in self.committed_scopes:
                edge["phase"] = "COMPLETED"
                continue
            active = [a for a in edge["members"] if self.active.get(a) == edge["id"]]
            totals = self._amounts(active)
            leader = self._amounts([edge["leader"]]) if edge["leader"] in active else {}
            completion = contract.get("completion", {})
            requirements = contract.get("requirements", {})
            for amounts in (totals, leader):
                progress = contract.get("progress", {})
                produced = amounts.get(progress.get("output"), 0)
                for resource, units in progress.get("inputs_per_output", {}).items():
                    if produced:
                        amounts[resource] = amounts.get(resource, 0) + produced * units
            receipt_totals = {}
            for tx in self.transactions.values():
                if tx["edge_id"] == edge["id"] and tx["status"] in {"RECEIVER_COMMITTED", "CONSUMED_DOWNSTREAM"}:
                    receipt_totals[tx["resource"]] = receipt_totals.get(tx["resource"], 0) + tx["amount"]
            handoff_completion = contract.get("handoff_completion", completion)
            committed = bool(handoff_completion and contract.get("handoff_to") and
                             self._met(handoff_completion, receipt_totals))
            if committed or (completion and not contract.get("handoff_to") and self._met(completion, totals)):
                phase = "COMPLETED"
                self.committed_scopes.add(edge["scope"])
                self.emit("MILESTONE_VERIFIED", {"scope": edge["scope"]}, edge_id=edge["id"])
            elif completion and self._met(completion, leader):
                phase = "READY_FOR_HANDOFF"
            elif completion and self._met(completion, totals):
                phase = "CONSOLIDATING"
            elif not self._met(requirements, totals):
                phase = "COLLECTING"
            elif not self._met(requirements, leader):
                phase = "CONSOLIDATING"
            else:
                phase = "READY_TO_EXECUTE"
            previous = edge["phase"]
            edge["phase"] = phase
            if phase != previous:
                self.emit("PHASE_TRANSITION", {"previous": previous, "phase": phase,
                                              "evidence_version": self.state_version}, edge_id=edge["id"])

    def allowed(self, sender, recipient, hard_event=False):
        if sender == recipient or not self.fresh(recipient):
            return False
        if hard_event:
            return sender in self.nodes  # Trusted runtime notices can report an offline sender.
        if not self.fresh(sender):
            return False
        own = self.edges.get(self.active.get(sender))
        if not own:
            return False
        if recipient == own["leader"] or (sender == own["leader"] and recipient in own["members"]):
            return True
        return any(a["leader"] == sender and b["leader"] == recipient and
                   (bool(set(a["members"]) & set(b["members"])) or
                    (a.get("contract") or {}).get("handoff_to") == b["scope"] or
                    (b.get("contract") or {}).get("handoff_to") == a["scope"])
                   for a in self.edges.values() for b in self.edges.values())

    def send(self, sender, recipient, content, deliver, enforce=True, hard_event=False, propagate_failure=False):
        mid = f"msg-{len(self.events) + 1}"
        ids = dict(agent_id=sender, message_id=mid, edge_id=self.active.get(sender))
        if enforce and not self.allowed(sender, recipient, hard_event):
            self.emit("MESSAGE_SUPPRESSED", {"recipient": recipient, "content": content}, **ids)
            return False, "not permitted by active-edge routing"
        self.emit("MESSAGE_SENT", {"recipient": recipient, "content": content,
                                   "hard_event": hard_event}, **ids)
        try:
            if enforce and not self.fresh(recipient):
                raise RuntimeError("receiver unavailable")
            deliver()
        except Exception as exc:
            self.emit("MESSAGE_FAILED", {"recipient": recipient, "reason": str(exc)}, **ids)
            if propagate_failure:
                raise
            return False, str(exc)
        self.emit("MESSAGE_DELIVERED", {"recipient": recipient}, **ids)
        return True, None

    def compact_context(self, agent, routing=False):
        """Runtime-only local facts; full snapshots stay in the event ledger."""
        edge = self.edges.get(self.active.get(agent))
        if not edge:
            return "[HYPERGRAPH latest runtime evidence] No active group."
        peers = {}
        for member in edge["members"]:
            if not self.fresh(member):
                continue
            node = self.nodes[member]
            peers[member] = {"position": node["position"], "resources": node["resources"],
                             "age_seconds": round(self.clock() - node["observed_at"], 1)}
            facts = node.get("facts", {})
            for key in ("agent_type", "in_helicopter"):
                if key in facts:
                    peers[member][key] = facts[key]
        data = {"state_version": self.state_version, "active_group": edge["id"], "peers": peers}
        if routing:
            data["leader"] = edge["leader"]
            data["allowed_recipients"] = sorted(a for a in self.nodes
                if a != agent and self.fresh(a) and self.allowed(agent, a))
            data["routing"] = "Address only allowed_recipients; GLOBAL reaches only permitted recipients."
        data["source"] = "Runtime position/resources; map cache excluded. Missing/stale peers omitted."
        data["note"] = "Messages and plans are not completed world actions."
        return "[HYPERGRAPH latest runtime evidence]\n" + json.dumps(data, ensure_ascii=False, sort_keys=True)

    def context(self, agent):
        edge = self.edges.get(self.active.get(agent))
        if not edge:
            return "[HYPERGRAPH] No active scope; no verified peer evidence."
        verified = {a: {"session_epoch": self.nodes[a]["session_epoch"],
                        "state_version": self.nodes[a]["state_version"],
                        "age_seconds": round(self.clock() - self.nodes[a]["observed_at"], 3),
                        "resources": self.nodes[a]["resources"], "position": self.nodes[a]["position"],
                        "facts": self.nodes[a].get("facts", {}),
                        "provenance": self.nodes[a].get("provenance", {})}
                    for a in edge["members"] if self.fresh(a)}
        passive = [{"scope": e["scope"], "phase": e["phase"], "leader": e["leader"]}
                   for e in self.edges.values() if agent in e["members"] and e["id"] != edge["id"]]
        adjacent = sorted({e["leader"] for e in self.edges.values()
                           if e["id"] != edge["id"] and (
                               set(e["members"]) & set(edge["members"]) or
                               (edge.get("contract") or {}).get("handoff_to") == e["scope"] or
                               (e.get("contract") or {}).get("handoff_to") == edge["scope"])})
        return "[HYPERGRAPH latest runtime evidence; claims are NOT facts]\n" + json.dumps({
            "state_version": self.state_version, "topology_version": self.topology_version,
            "active_scope": edge["scope"], "phase": edge["phase"], "leader": edge["leader"],
            "role": "LEADER" if edge["leader"] == agent else "MEMBER",
            "members": edge["members"], "runtime_observations": verified,
            "contract": edge.get("contract"),
            "passive_scopes": passive, "adjacent_leaders": adjacent if edge["leader"] == agent else [],
            "routing": "Report deltas/blockers to leader; leaders contact members and adjacent leaders.",
            "warning": "A plan, message or completed command is not a verified world postcondition. "
                       "Shared map-memory cells are not proof of current direct visibility; "
                       "snapshot age does not establish cell-level freshness."
        }, ensure_ascii=False, sort_keys=True)

    def plan_handoff(self, edge_id, sender, receiver, resource, amount):
        edge = self.edges.get(edge_id)
        if not edge or sender not in edge["members"]:
            raise ValueError("Sender outside handoff scope")
        contract = edge.get("contract") or {}
        downstream = next((e for e in self.edges.values() if e["scope"] == contract.get("handoff_to")), None)
        expected_receiver = downstream["leader"] if downstream else contract.get("receiver")
        if contract.get("handoff_to") and receiver != expected_receiver:
            raise ValueError("Wrong/unknown contract receiver")
        if (sender == receiver or not isinstance(amount, (int, float)) or
                not math.isfinite(amount) or amount <= 0 or
                not self.fresh(sender) or not self.fresh(receiver)):
            raise ValueError("Invalid handoff participants/amount")
        source, destination = self.nodes[sender], self.nodes[receiver]
        if resource not in destination["resources"] or source["resources"].get(resource, -1) < amount:
            raise ValueError("Missing verified sender or receiver inventory")
        tid = f"tx-{len(self.transactions) + 1}"
        tx = dict(transaction_id=tid, edge_id=edge_id, sender=sender, receiver=receiver,
                  sender_session=source["session_epoch"], receiver_session=destination["session_epoch"],
                  resource=resource, amount=amount, receiver_before=destination["resources"][resource],
                  receiver_before_version=destination["state_version"],
                  planned_version=self.state_version, status="PLANNED")
        self.transactions[tid] = tx
        self.emit("HANDOFF_PLANNED", tx, sender, transaction_id=tid, edge_id=edge_id)
        return tid

    def handoff_sent(self, tid):
        tx = self.transactions[tid]
        if tx["status"] != "PLANNED":
            raise ValueError("Invalid transaction transition")
        tx.update(status="SENT", sent_version=self.state_version)
        self.emit("HANDOFF_SENT", tx, tx["sender"], transaction_id=tid, edge_id=tx["edge_id"])

    def receiver_commit(self, tid, observed_collector):
        tx = self.transactions[tid]
        if tx["status"] not in {"SENT", "COLLECTOR_OBSERVED"}:
            raise ValueError("No pending sent transaction")
        if observed_collector != tx["receiver"]:
            tx["status"] = "WRONG_COLLECTOR"
            self.emit("COLLECTOR_OBSERVED", {"collector": observed_collector, "status": tx["status"]},
                      transaction_id=tid, edge_id=tx["edge_id"])
            return False
        node = self.nodes.get(observed_collector, {})
        resource = tx["resource"]
        if (not self.fresh(observed_collector) or node["session_epoch"] != tx["receiver_session"] or
                node["state_version"] <= tx["sent_version"] or resource not in node["resources"]):
            return False
        already = sum(previous["amount"] for previous in self.transactions.values()
                      if previous["status"] in {"RECEIVER_COMMITTED", "CONSUMED_DOWNSTREAM"}
                      and previous["receiver"] == observed_collector
                      and previous["receiver_session"] == node["session_epoch"]
                      and previous["resource"] == resource
                      and previous["receiver_committed_version"] > tx["receiver_before_version"])
        if node["resources"][resource] - tx["receiver_before"] - already < tx["amount"]:
            return False
        tx["status"] = "COLLECTOR_OBSERVED"
        self.emit("COLLECTOR_OBSERVED", {"collector": observed_collector}, transaction_id=tid)
        tx.update(status="RECEIVER_COMMITTED", receiver_committed_version=node["state_version"])
        self.emit("RECEIVER_COMMITTED", tx, observed_collector, transaction_id=tid, edge_id=tx["edge_id"])
        self.reduce()
        return True
