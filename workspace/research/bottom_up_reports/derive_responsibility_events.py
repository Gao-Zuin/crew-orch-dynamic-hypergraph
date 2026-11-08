#!/usr/bin/env python3
"""Derive conservative ASSIGN/PROVISIONAL_CLAIM/COMPLETE events from frozen logs.

The ledger is intentionally shadow-only.  Graph tasks create baseline ownership;
only messages from the current source-edge leader can change it.  A leader may
replace ownership inside its own edge.  A claim across an existing edge boundary
is retained as provisional rather than silently stealing the target.  Verified
environment completion dominates later stale graph text.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from analyze_cut_tree_false_prerequisites import DEFAULT_RUNS, cell_delta
from analyze_target_responsibility_shadow import (
    COORD, event_step, index_graph, task_assignment,
)


ARROW_ASSIGN = re.compile(r"(?:AGENT[_ ]?)?(\d+)\s*(?:→|->)\s*(\(\s*\d+\s*,\s*\d+\s*\))", re.I)
COORD_TOKEN = r"\(\s*\d+\s*,\s*\d+\s*\)"
DIRECT_ASSIGN = re.compile(
    rf"(?:\byou\s+(?:take|own|handle)|\bproceed\s+to|\bplease\s+(?:take|proceed\s+to)|"
    rf"\bfinish\s+cutting|\bkeep\s+cutting|\bmove\s+to|\bhead\s+to|\bthen\s+take)"
    rf"\s*((?:{COORD_TOKEN})(?:\s*(?:,|/|and|then)\s*{COORD_TOKEN})*)",
    re.I,
)
CONTINUATION_ASSIGN = re.compile(
    rf"\bafter\s+you\s+verify\s*({COORD_TOKEN})", re.I)
NEGATIVE = re.compile(r"\b(?:avoid|do not|don't|skip|leave|not take|not go)\b", re.I)


def coords(text, targets):
    return [tuple(map(int, match)) for match in COORD.findall(text or "")
            if tuple(map(int, match)) in targets]


def leader_assignments(content, recipient, sender, targets, allow_direct=True):
    """Parse high-precision target assignments from one leader delivery."""
    found = defaultdict(set)
    for agent, raw_coord in ARROW_ASSIGN.findall(content or ""):
        coord = tuple(map(int, COORD.search(raw_coord).groups()))
        if coord in targets:
            found[str(agent)].add(coord)
    # Point-to-point leader messages use 'you' without repeating the recipient.
    if allow_direct:
        for match in DIRECT_ASSIGN.finditer(content or ""):
            prefix = content[max(0, match.start() - 20):match.start()]
            if NEGATIVE.search(prefix):
                continue
            for coord in coords(match.group(1), targets):
                found[str(recipient)].add(coord)
        for match in CONTINUATION_ASSIGN.finditer(content or ""):
            for coord in coords(match.group(1), targets):
                found[str(recipient)].add(coord)
    # Explicit named imperative, e.g. 'AGENT_3: ... move to (12,31)'.
    for match in re.finditer(r"AGENT[_ ]?(\d+)\b([^.;]*?)(?=AGENT[_ ]?\d+\b|[.;]|$)",
                             content or "", re.I):
        agent, segment = match.group(1), match.group(2)
        if NEGATIVE.search(segment):
            continue
        for direct in DIRECT_ASSIGN.finditer(segment):
            if re.search(r"\bI\s*$", segment[:direct.start()], re.I):
                continue
            for coord in coords(direct.group(1), targets):
                found[str(agent)].add(coord)
    # A leader can explicitly assign itself with 'I take ...' or 'I (6) take ...'.
    for self_match in re.finditer(
            r"\bI(?:\s*\(\s*(\d+)\s*\))?\s*(?:take|own|handle)([^.;]*)",
            content or "", re.I):
        stated = self_match.group(1)
        if stated is None or stated == str(sender):
            for coord in coords(self_match.group(2), targets):
                found[str(sender)].add(coord)
    return {agent: sorted(values) for agent, values in found.items()}


def graph_state(edges, targets):
    index = index_graph(edges, targets)
    agent_edges = {}
    leaders = {}
    members = defaultdict(set)
    for edge in edges or []:
        edge_id = str(edge.get("id"))
        leaders[edge_id] = str(edge.get("leader"))
        for agent in edge.get("members", []):
            members[edge_id].add(str(agent))
        for agent in (edge.get("tasks") or {}):
            agent_edges[str(agent)] = edge_id
    return index, agent_edges, leaders, members


def analyze_run(events_path):
    events = []
    current_step = None
    with Path(events_path).open(encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            current_step = event_step(event, current_step)
            event["_step"] = current_step
            events.append(event)
    first_snapshot = next(event for event in events
                          if event.get("event_type") == "TASK_WORLD_SNAPSHOT")
    targets = {tuple(map(int, coord)) for coord in
               first_snapshot["payload"].get("task_parameters", {}).get("target_trees", [])}
    snapshots = {int(event["payload"]["step"]): event["payload"] for event in events
                 if event.get("event_type") == "TASK_WORLD_SNAPSHOT"
                 and event.get("payload", {}).get("phase") == "before_action"}
    completed_actions = {event.get("action_id"): event for event in events
                         if event.get("event_type") == "ACTION_COMPLETED"}
    delivery_fanout = defaultdict(set)
    for event in events:
        if event.get("event_type") != "TASK_MESSAGE_DELIVERED":
            continue
        payload = event.get("payload", {})
        key = (str(payload.get("sender")), payload.get("step"), str(payload.get("source")),
               payload.get("content", ""))
        delivery_fanout[key].add(str(payload.get("recipient")))

    owners = defaultdict(set)       # coord -> {(agent, edge)}
    provisional = defaultdict(set)  # coord -> {(agent, edge)}
    completed_targets = set()
    agent_edges = {}
    leaders = {}
    members = defaultdict(set)
    derived = []
    completion_checks = []
    stale_graph_assignments = []
    seen_deliveries = set()

    for event in events:
        kind = event.get("event_type")
        step = event.get("_step")
        if kind == "TASK_GRAPH_COMMITTED":
            edges = event.get("payload", {}).get("edges", [])
            index, agent_edges, leaders, members = graph_state(edges, targets)
            next_owners = defaultdict(set)
            for coord, records in index["primary"].items():
                if coord in completed_targets:
                    stale_graph_assignments.append(
                        {"event_id": event.get("event_id"), "step": step,
                         "target": list(coord), "records": sorted(records)})
                else:
                    next_owners[coord].update(records)
            owners = next_owners
            provisional = defaultdict(set)
            derived.append({"type": "GRAPH_ASSIGN", "event_id": event.get("event_id"),
                            "step": step, "owned_target_count": len(owners),
                            "collision_target_count": sum(len({a for a, _ in records}) > 1
                                                          for records in owners.values())})
        elif kind == "TASK_MESSAGE_DELIVERED":
            payload = event.get("payload", {})
            source = str(payload.get("source"))
            sender = str(payload.get("sender"))
            recipient = str(payload.get("recipient"))
            content = payload.get("content", "")
            fanout_key = (sender, payload.get("step"), source, content)
            is_direct = len(delivery_fanout[fanout_key]) == 1
            key = ((sender, recipient, payload.get("step"), source, content)
                   if is_direct else (sender, "BROADCAST", payload.get("step"), source, content))
            if key in seen_deliveries or leaders.get(source) != sender:
                continue
            seen_deliveries.add(key)
            assignments = leader_assignments(
                content, recipient, sender, targets,
                allow_direct=is_direct)
            for assignee, assigned_coords in assignments.items():
                if assignee not in members.get(source, set()):
                    continue
                for coord in assigned_coords:
                    if coord in completed_targets:
                        continue
                    existing_edges = {edge for _, edge in owners.get(coord, set())}
                    record = (assignee, source)
                    if not existing_edges or existing_edges == {source}:
                        before = sorted(owners.get(coord, set()))
                        if owners.get(coord, set()) == {record}:
                            event_type = "LEADER_REAFFIRM"
                        else:
                            owners[coord] = {record}
                            provisional[coord].clear()
                            event_type = "LEADER_ASSIGN"
                    else:
                        before = sorted(owners.get(coord, set()))
                        if record in provisional.get(coord, set()):
                            event_type = "PROVISIONAL_REAFFIRM"
                        else:
                            provisional[coord].add(record)
                            event_type = "PROVISIONAL_CROSS_EDGE_CLAIM"
                    derived.append({"type": event_type, "event_id": event.get("event_id"),
                                    "step": payload.get("step"), "source_edge": source,
                                    "leader": sender, "assignee": assignee,
                                    "target": list(coord), "previous_owners": before,
                                    "content": content})
        elif kind == "ACTION_STARTED" and event.get("payload", {}).get("action", [None])[0] == 1:
            action_id = event.get("action_id")
            action_step = int(event.get("payload", {}).get("timestep", step))
            agent = str(event.get("agent_id"))
            position = (snapshots.get(action_step, {}).get("nodes", {}).get(agent, {})
                        .get("position"))
            if not position:
                continue
            coord = tuple(map(int, position))
            if coord not in targets:
                continue
            completed = completed_actions.get(action_id, {})
            delta = cell_delta(completed)
            facts = (completed.get("payload", {}).get("verified_local_delta", {})
                     .get("facts", {}))
            try:
                reaches_zero = bool(delta and delta > 0
                                    and int(facts["after"]["current_cell"]) == 0)
            except (KeyError, TypeError, ValueError):
                reaches_zero = False
            owner_agents = {a for a, _ in owners.get(coord, set())}
            provisional_agents = {a for a, _ in provisional.get(coord, set())}
            if coord in completed_targets:
                authority = "ALREADY_COMPLETE"
            elif agent in owner_agents:
                authority = "CURRENT_OWNER"
            elif agent in provisional_agents:
                authority = "PROVISIONAL_CROSS_EDGE"
            elif owner_agents:
                authority = "UNAUTHORIZED_AGAINST_OWNER"
            else:
                authority = "UNOWNED"
            check = {"event_id": event.get("event_id"), "action_id": action_id,
                     "step": action_step, "agent": agent, "target": list(coord),
                     "authority": authority, "owners": sorted(owners.get(coord, set())),
                     "provisional_claims": sorted(provisional.get(coord, set())),
                     "successful_effect": bool(delta and delta > 0),
                     "completed_target": reaches_zero}
            completion_checks.append(check)
            if reaches_zero:
                completed_targets.add(coord)
                owners.pop(coord, None)
                provisional.pop(coord, None)
                derived.append({"type": "ENV_COMPLETE", "event_id": event.get("event_id"),
                                "step": action_step, "agent": agent, "target": list(coord),
                                "authority_at_completion": authority})

    completions = [item for item in completion_checks if item["completed_target"]]
    return {
        "events_path": str(events_path), "target_count": len(targets),
        "derived_event_counts": dict(Counter(item["type"] for item in derived)),
        "completion_authority": dict(Counter(item["authority"] for item in completions)),
        "successful_cut_authority": dict(Counter(item["authority"] for item in completion_checks
                                                  if item["successful_effect"])),
        "completed_target_count": len(completed_targets),
        "stale_graph_assignment_count": len(stale_graph_assignments),
        "stale_graph_assignment_target_count": len({tuple(item["target"])
                                                     for item in stale_graph_assignments}),
        "stale_graph_assignments": stale_graph_assignments,
        "derived_events": derived,
        "cut_checks": completion_checks,
    }


def analyze_all(runs=None):
    runs = runs or DEFAULT_RUNS
    return {
        "method": {
            "leader_authority": "sender must equal current source-edge leader",
            "within_edge_assignment": "replaces current owner only when target is unowned or all owners are in the same source edge",
            "cross_edge_assignment": "retained as provisional; does not silently remove existing owner",
            "completion": "verified current_cell reaches zero and dominates later graph text",
            "boundary": "shadow reconstruction, not runtime permission gate",
        },
        "runs": {name: analyze_run(paths["events"]) for name, paths in runs.items()},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze_all()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
