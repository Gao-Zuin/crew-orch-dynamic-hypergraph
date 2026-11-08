"""Exact protocol-path calibration for the structural initial plan.

This is not a task-success simulator.  It uses the production initial-graph
builder and SoftTaskGraph, then computes shortest legal typed-message paths.
"""
from collections import deque
from copy import deepcopy
from pathlib import Path
import json
import sys


PACKAGE = Path(__file__).resolve().parents[2] / "ORCH" / "crew-algorithms"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from crew_algorithms.wildfire_alg.config.resource_scheduling.initial_structure import (  # noqa: E402
    build_initial_structure,
)
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph  # noqa: E402


CENTER = "ORGANIZER"


def structure_nodes(scarce=True):
    """Roster used by the real structure study: 8 FF, dozer, 1/2 drones, helicopter."""
    last_drone = 10 if scarce else 11
    nodes = {
        str(i): {"online": True, "facts": {"agent_type": 0}}
        for i in range(1, 9)
    }
    nodes["9"] = {"online": True, "facts": {"agent_type": 1}}
    for i in range(10, last_drone + 1):
        nodes[str(i)] = {"online": True, "facts": {"agent_type": 2}}
    nodes[str(last_drone + 1)] = {"online": True, "facts": {"agent_type": 3}}
    return nodes


def build_graph(adaptive=False, scarce=True):
    nodes = structure_nodes(scarce=scarce)
    world = {"step": 0, "evidence_id": 1, "mission": "calibration",
             "nodes": nodes, "event_commands_and_announcements": []}
    graph = SoftTaskGraph(lambda kind, payload: {"event_id": 1}, fixed_groups=not adaptive)
    graph.observe(world)
    proposal = build_initial_structure(nodes, 1)
    graph.apply(proposal)
    if adaptive:
        changed = deepcopy(proposal)
        changed["based_on_version"] = graph.version
        support = next(edge for edge in changed["edges"] if edge["id"] == "support")
        scout = next(a for a, node in nodes.items()
                     if node["facts"]["agent_type"] == 2)
        if scout not in support["members"]:
            support["members"].append(scout)
        graph.apply(changed)
    return graph, nodes


def legal_adjacency(graph):
    """Direct deliveries allowed by the current GROUP/REPORT/LEADER/ORGANIZER tags."""
    adjacency = {agent: set() for agent in graph.live_agents()}
    adjacency[CENTER] = set()
    edges = list(graph.edges.values())
    for edge in edges:
        # GROUP/REPORT: any member can reach any other member in the same edge.
        for sender in edge["members"]:
            adjacency[sender].update(a for a in edge["members"] if a != sender)
        # ORGANIZER: only a current edge leader may report to the center.
        adjacency[edge["leader"]].add(CENTER)
    # LEADER: leaders can address leaders of other existing edges.
    for source in edges:
        for target in edges:
            if source["id"] != target["id"] and source["leader"] != target["leader"]:
                allowed, _ = graph.route(source["leader"], target["leader"],
                                         source["id"], target["id"])
                if allowed:
                    adjacency[source["leader"]].add(target["leader"])
    return adjacency


def shortest_path(adjacency, source, target):
    queue = deque([(source, [source])])
    seen = {source}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for neighbor in sorted(adjacency.get(node, ())):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None


def same_round_cascade(path, communication_order):
    """Whether immediate delivery can traverse a path before the action phase.

    Every non-final worker must get its message before its own communication
    turn.  The final recipient may have spoken already because all physical
    actions are chosen only after the communication round finishes.
    """
    turns = {agent: i for i, agent in enumerate(communication_order)}
    senders = [node for node in path[:-1] if node != CENTER]
    return all(turns[first] < turns[second]
               for first, second in zip(senders, senders[1:]))


def analyze():
    results = {}
    for arm, adaptive in (("fixed", False), ("adaptive_pre_shared", True)):
        graph, nodes = build_graph(adaptive=adaptive, scarce=True)
        adjacency = legal_adjacency(graph)
        scout = next(a for a, node in nodes.items()
                     if node["facts"]["agent_type"] == 2)
        support = graph.edges["support"]
        support_leader = support["leader"]
        executor = next(a for a in support["members"]
                        if nodes[a]["facts"]["agent_type"] == 0 and a != support_leader)
        leader_path = shortest_path(adjacency, scout, support_leader)
        worker_path = shortest_path(adjacency, scout, executor)
        center_path = shortest_path(adjacency, scout, CENTER)
        leaders = {edge["leader"] for edge in graph.edges.values()}
        input_order = sorted(nodes, key=int)
        communication_order = sorted(input_order, key=lambda a: a in leaders)
        results[arm] = {
            "scout": scout,
            "support_leader": support_leader,
            "support_executor": executor,
            "leader_path": leader_path,
            "leader_deliveries": len(leader_path) - 1,
            "worker_path": worker_path,
            "worker_deliveries": len(worker_path) - 1,
            "center_path": center_path,
            "center_deliveries": len(center_path) - 1,
            "assumed_runtime_communication_order": communication_order,
            "worker_path_can_cascade_same_immediate_round":
                same_round_cascade(worker_path, communication_order),
            "center_path_can_cascade_same_immediate_round":
                same_round_cascade(center_path, communication_order),
        }

    fixed = results["fixed"]
    pre_shared = results["adaptive_pre_shared"]
    # With next-step delivery, a reactive topology change cannot precede the
    # center learning the scout's evidence.  It commits after the fixed center
    # path, then needs one more delivery to reach a support worker.
    results["causal_timelines"] = {
        "fixed_center_task_binding": fixed["center_deliveries"],
        "fixed_support_leader_delivery": fixed["leader_deliveries"],
        "fixed_peer_delivery": fixed["worker_deliveries"],
        "adaptive_pre_shared_peer_delivery": pre_shared["worker_deliveries"],
        "adaptive_reactive_peer_delivery": fixed["center_deliveries"] + 1,
        "units": "decision-step deliveries after local evidence",
    }
    results["interpretation"] = (
        "Sharing the scout before local evidence shortens worker delivery. "
        "Sharing it only after that evidence reaches the organizer does not beat "
        "the fixed topology's center task-binding path. Under immediate delivery "
        "and the current member-before-leader order, both fixed paths can cascade "
        "within one communication round; topology then reduces the number of "
        "separate message decisions, not a guaranteed number of action steps."
    )
    results["independent_hop_success_sensitivity"] = [
        {"per_message_success": p,
         "fixed_peer_chain": round(p ** fixed["worker_deliveries"], 4),
         "fixed_center_chain_before_planner": round(p ** fixed["center_deliveries"], 4),
         "adaptive_pre_shared_peer_chain": round(p ** pre_shared["worker_deliveries"], 4)}
        for p in (0.5, 0.7, 0.9)
    ]
    return results


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
