"""CREW-only observation encoding and narrow physical precondition checks.

No task decomposition or movement targets are generated here. Local map facts
are cells actually present in an agent's observation, not the global Unity map.
"""
from copy import deepcopy
import math


CAPABILITIES = {
    0: ["navigate", "cut", "spray", "refill", "carry_civilian"],
    1: ["navigate", "cut_path"],
    2: ["navigate", "scout"],
    3: ["navigate", "transport_firefighter", "spray", "refill"],
}

# MapManager.viewRanges in the current Unity source. AIAgent reads a larger
# AccDataMap crop, which can contain another worker's cached observations.
SOURCE_DIRECT_VIEW_RADIUS = {0: 5, 1: 5, 2: 15, 3: 20}


def encode_observation(agent_id, observation, task_id, session_epoch, observed_at):
    agent_type = int(observation["agent_type"])
    position = list(map(float, observation["position"]))
    extras = observation.get("extra_variables", [])
    resources = {}
    if agent_type in (0, 3) and len(extras) >= 2:
        resources["water"] = int(extras[1])
        resources["civilian_carried" if agent_type == 0 else "firefighters_carried"] = int(extras[0])
    # This is shared AccDataMap memory, not a direct visibility mask.
    facts = {"agent_type": agent_type, "current_cell": observation.get("current_cell"),
             "current_cell_source": "shared_map_memory",
             "map_memory": {"source": "environment_shared_accumulated_map_crop",
                            "cell_last_seen_at": None, "direct_visibility": "unknown",
                            "cells": {"fire": [], "water": [], "civilian": []}},
             "own_view_source_candidate": {
                 "radius": SOURCE_DIRECT_VIEW_RADIUS.get(agent_type),
                 "source": "Unity MapManager.viewRanges square; source-derived, deployed build not independently attested",
                 "cells": {"fire": [], "water": [], "civilian": []}}}
    if agent_type == 0 and len(extras) >= 3:
        facts["in_helicopter"] = bool(extras[2])
    rows = observation.get("perception_grid", "").strip().splitlines()
    radius = observation["map_range"] // 2
    for y, row in enumerate(rows):
        for x, raw in enumerate(row.strip().split(",")):
            cell = raw.strip().strip("*'")
            kind = "fire" if cell in {"i", "f", "e"} else "water" if cell == "w" else "civilian" if cell == "C" else None
            if kind:
                coordinate = [position[0] - radius + x, position[1] - radius + y]
                facts["map_memory"]["cells"][kind].append(coordinate)
                own_radius = SOURCE_DIRECT_VIEW_RADIUS.get(agent_type)
                if own_radius is not None and abs(x - radius) <= own_radius and abs(y - radius) <= own_radius:
                    facts["own_view_source_candidate"]["cells"][kind].append(coordinate)
    return dict(agent_id=str(agent_id), task_id=task_id, session_epoch=session_epoch,
                observed_at=observed_at, resources=resources,
                capabilities=CAPABILITIES.get(agent_type, []), position=position, facts=facts,
                provenance={"position": "runtime_agent_state",
                            "resources": "runtime_extra_variables",
                            "map_memory": "shared_cache; per-cell freshness and observer unknown",
                            "own_view_source_candidate": "inside source-defined own update square; deployed-build equivalence unverified"})


def validate_low_level_action(snapshot, action):
    """Return rejection + recovery feedback, never substitute a domain plan.

    HG protocol-stress ONLY: spray needs water; refill requires water-source cell.
    Unknown observations cannot establish violation, so abstain rather than veto.
    """
    # Helicopter low-level code 3 aliases unload passengers AND deploy water.
    # Without the high-level command, vetoing it could block a valid rescue.
    # Abstain for helicopters rather than invent semantics for an ambiguous code.
    if snapshot["facts"]["agent_type"] != 0:
        return True, None
    if action[0] == 3 and snapshot["resources"].get("water") == 0:
        return False, "Spray rejected: latest observed water is 0. Re-observe and choose a feasible recovery action."
    cell = snapshot["facts"].get("current_cell")
    if (action[0] == 4 and snapshot["facts"].get("current_cell_source") == "direct_runtime"
            and cell is not None and cell.strip("*'") != "w"):
        return False, "Refill rejected: latest observed cell is not a water source. Re-observe and replan recovery."
    return True, None


class SpatialPolicy:
    """Task-agnostic local teams with a shared bridge; no workflow prior.

    Nearest-neighbor grouping partitions agents into groups of <=3. Each group elects its member
    closest to the centroid; previous leaders stay while membership is stable.
    A bridge from the preceding group overlaps adjacent groups. The grouping is
    intentionally a transparent first heuristic, not an optimized policy.
    """
    def predict(self, coordinator):
        nodes = sorted((n for a, n in coordinator.nodes.items() if coordinator.fresh(a)),
                       key=lambda n: n["agent_id"])
        groups = []
        remaining = list(nodes)
        while remaining:
            anchor = remaining[0]
            group = sorted(remaining, key=lambda n: (
                math.dist(n["position"], anchor["position"]), n["agent_id"]))[:3]
            groups.append(group)
            selected = {n["agent_id"] for n in group}
            remaining = [n for n in remaining if n["agent_id"] not in selected]
        edges, active = [], {}
        for i, group in enumerate(groups):
            members = [n["agent_id"] for n in group]
            edge_id = f"local:{i}"
            center = [sum(n["position"][d] for n in group) / len(group) for d in (0, 1)]
            old_leader = coordinator.edges.get(edge_id, {}).get("leader")
            leader = old_leader if old_leader in members else min(group, key=lambda n: (
                math.dist(n["position"], center), n["agent_id"]))["agent_id"]
            if i:
                bridge = groups[i - 1][-1]["agent_id"]
                members.append(bridge)
            edges.append(dict(id=edge_id, scope=f"local collaboration {i}", members=members,
                              leader=leader, phase="ACTIVE", contract=None))
            active.update({n["agent_id"]: edge_id for n in group})
        return dict(based_on_state_version=coordinator.state_version,
                    edges=deepcopy(edges), active=active)
