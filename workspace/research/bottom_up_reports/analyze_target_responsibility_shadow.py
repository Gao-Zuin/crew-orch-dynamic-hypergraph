#!/usr/bin/env python3
"""Shadow a versioned target-owner index over sparse tree-cutting trajectories.

Only task strings beginning with an explicit cut verb create ownership.  Task text
with fallback/ownership caveats is kept as conditional rather than silently promoted
to a primary assignment.  The index is then joined to real move/cut effects.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from analyze_cut_tree_false_prerequisites import DEFAULT_RUNS, cell_delta


COORD = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")
CUT_PREFIX = re.compile(r"^(?:cut\b|continue cutting\b)", re.I)
CONDITIONAL = re.compile(
    r"\b(?:if|only if|otherwise|fallback|assist|coordinate|team [ab] owns|"
    r"team [ab]'s|not already|after \d+)\b", re.I)
ASSIGNMENT_LANGUAGE = re.compile(
    r"\b(?:take|cut|proceed|move|head|heading|assigned|assignment|own|verify|"
    r"help|assist|redirect|handling|backup|finish)\w*\b|(?:→|->)", re.I)


def event_step(event, current=None):
    payload = event.get("payload", {})
    value = payload.get("step", payload.get("timestep"))
    return int(value) if isinstance(value, int) else current


def task_assignment(text, targets):
    """Return conservative primary/conditional target references for one task."""
    if not CUT_PREFIX.search((text or "").strip()):
        return {"primary": [], "conditional": []}
    coords = [tuple(map(int, match)) for match in COORD.findall(text)]
    coords = [coord for coord in coords if coord in targets]
    bucket = "conditional" if CONDITIONAL.search(text) else "primary"
    return {"primary": coords if bucket == "primary" else [],
            "conditional": coords if bucket == "conditional" else []}


def index_graph(edges, targets):
    primary = defaultdict(set)
    conditional = defaultdict(set)
    evidence = defaultdict(list)
    for edge in edges or []:
        for agent, text in (edge.get("tasks") or {}).items():
            parsed = task_assignment(text, targets)
            for kind in ("primary", "conditional"):
                for coord in parsed[kind]:
                    record = (str(agent), str(edge.get("id")))
                    (primary if kind == "primary" else conditional)[coord].add(record)
                    evidence[coord].append({"kind": kind, "agent": str(agent),
                                            "edge": str(edge.get("id")), "task": text})
    return {"primary": primary, "conditional": conditional, "evidence": evidence}


def ownership_class(index, coord, agent):
    primary_agents = {record[0] for record in index["primary"].get(coord, set())}
    conditional_agents = {record[0] for record in index["conditional"].get(coord, set())}
    if agent in primary_agents:
        return "OWN_PRIMARY"
    if agent in conditional_agents:
        return "OWN_CONDITIONAL"
    if primary_agents:
        return "OTHER_PRIMARY_OWNER"
    if conditional_agents:
        return "OTHER_CONDITIONAL_OWNER"
    return "NO_INDEXED_OWNER"


def recent_message_evidence(messages, agent, coord, step, horizon=5):
    token = re.compile(rf"\(\s*{coord[0]}\s*,\s*{coord[1]}\s*\)")
    found = []
    for message in messages.get(str(agent), []):
        if not (step - horizon <= message["step"] <= step):
            continue
        if token.search(message["content"]) and ASSIGNMENT_LANGUAGE.search(message["content"]):
            found.append(message)
    return found


def snapshot_index(index):
    coords = sorted(set(index["primary"]) | set(index["conditional"]))
    return {
        "primary": {f"{x},{y}": sorted(records) for (x, y), records in index["primary"].items()},
        "conditional": {f"{x},{y}": sorted(records)
                        for (x, y), records in index["conditional"].items()},
        "primary_collisions": {
            f"{coord[0]},{coord[1]}": index["evidence"][coord]
            for coord in coords if len({record[0] for record in index["primary"].get(coord, set())}) > 1},
        "primary_conditional_overlaps": {
            f"{coord[0]},{coord[1]}": index["evidence"][coord]
            for coord in coords if index["primary"].get(coord) and index["conditional"].get(coord)},
    }


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
    completed = {event.get("action_id"): event for event in events
                 if event.get("event_type") == "ACTION_COMPLETED"}
    no_effect = {event.get("action_id") for event in events
                 if event.get("event_type") == "ACTION_NO_EFFECT"}

    graph = index_graph([], targets)
    graph_version = 0
    commits = []
    actions = []
    messages = defaultdict(list)
    referenced_messages = {}
    for event in events:
        kind = event.get("event_type")
        if kind == "TASK_MESSAGE_DELIVERED":
            payload = event.get("payload", {})
            step = payload.get("step")
            if isinstance(step, int):
                messages[str(payload.get("recipient"))].append(
                    {"event_id": event.get("event_id"), "step": step,
                     "sender": str(payload.get("sender")), "content": payload.get("content", "")})
        elif kind == "TASK_GRAPH_COMMITTED":
            graph_version += 1
            graph = index_graph(event.get("payload", {}).get("edges", []), targets)
            snap = snapshot_index(graph)
            commits.append({"event_id": event.get("event_id"), "step": event.get("_step"),
                            "graph_version": graph_version,
                            "primary_collision_count": len(snap["primary_collisions"]),
                            "primary_conditional_overlap_count": len(
                                snap["primary_conditional_overlaps"]), **snap})
        elif kind == "ACTION_STARTED":
            raw = event.get("payload", {}).get("action", [])
            if not raw:
                continue
            step = int(event.get("payload", {}).get("timestep", event.get("_step")))
            agent = str(event.get("agent_id"))
            coord = None
            action_kind = None
            successful_effect = False
            completed_target = False
            if raw[0] == 0 and len(raw) >= 3:
                point = (int(raw[1]), int(raw[2]))
                if point in targets:
                    coord, action_kind = point, "MOVE_TO_TARGET"
            elif raw[0] == 1:
                position = (snapshots.get(step, {}).get("nodes", {}).get(agent, {})
                            .get("position"))
                if position:
                    point = tuple(map(int, position))
                    if point in targets:
                        coord, action_kind = point, "CUT_AT_TARGET"
                        delta = cell_delta(completed.get(event.get("action_id"), {}))
                        successful_effect = bool(delta and delta > 0)
                        facts = (completed.get(event.get("action_id"), {}).get("payload", {})
                                 .get("verified_local_delta", {}).get("facts", {}))
                        try:
                            completed_target = successful_effect and int(
                                facts["after"]["current_cell"]) == 0
                        except (KeyError, TypeError, ValueError):
                            completed_target = False
            if coord is not None:
                message_evidence = recent_message_evidence(messages, agent, coord, step)
                for message in message_evidence:
                    referenced_messages[message["event_id"]] = message
                actions.append({"event_id": event.get("event_id"), "action_id": event.get("action_id"),
                                "step": step, "agent": agent, "action_kind": action_kind,
                                "target": list(coord), "graph_version": graph_version,
                                "ownership": ownership_class(graph, coord, agent),
                                "successful_cut_effect": successful_effect,
                                "completed_target": completed_target,
                                "logged_no_effect": event.get("action_id") in no_effect,
                                "recent_assignment_message_evidence": bool(message_evidence),
                                "recent_assignment_message_event_ids": [
                                    message["event_id"] for message in message_evidence[-5:]],
                                "indexed_primary_agents": sorted({
                                    record[0] for record in graph["primary"].get(coord, set())}),
                                "indexed_conditional_agents": sorted({
                                    record[0] for record in graph["conditional"].get(coord, set())})})

    action_counts = Counter(item["ownership"] for item in actions)
    successful = [item for item in actions if item["successful_cut_effect"]]
    completion = [item for item in actions if item["completed_target"]]
    nonowner = [item for item in actions if item["ownership"] == "OTHER_PRIMARY_OWNER"]
    nonowner_completion = [item for item in completion
                           if item["ownership"] == "OTHER_PRIMARY_OWNER"]
    return {
        "events_path": str(events_path), "target_count": len(targets),
        "graph_commit_count": len(commits),
        "commits_with_primary_collision": sum(bool(c["primary_collision_count"]) for c in commits),
        "commits_with_primary_conditional_overlap": sum(
            bool(c["primary_conditional_overlap_count"]) for c in commits),
        "max_primary_collision_targets": max((c["primary_collision_count"] for c in commits), default=0),
        "final_indexed_primary_coverage": len(commits[-1]["primary"]) if commits else 0,
        "commit_indexes": commits,
        "assignment_message_evidence": [referenced_messages[key]
                                        for key in sorted(referenced_messages)],
        "target_directed_action_count": len(actions),
        "target_directed_action_ownership": dict(action_counts),
        "successful_cut_effect_count": len(successful),
        "successful_cut_effect_ownership": dict(Counter(item["ownership"] for item in successful)),
        "target_completion_effect_count": len(completion),
        "target_completion_effect_ownership": dict(Counter(item["ownership"] for item in completion)),
        "other_primary_owner_actions_with_recent_message_evidence": sum(
            item["recent_assignment_message_evidence"] for item in nonowner),
        "other_primary_owner_completion_effects_with_recent_message_evidence": sum(
            item["recent_assignment_message_evidence"] for item in nonowner_completion),
        "cut_no_effect_at_target": sum(item["action_kind"] == "CUT_AT_TARGET"
                                       and item["logged_no_effect"] for item in actions),
        "actions": actions,
    }


def analyze_all(runs=None):
    runs = runs or DEFAULT_RUNS
    return {
        "method": {
            "primary_assignment": "task begins with Cut/Continue cutting and lacks conditional markers",
            "conditional_assignment": "cut task contains if/only-if/otherwise/fallback/assist/ownership caveat",
            "action_join": "exact target coordinate for moves; before-action position for cuts",
            "environment_completion": "verified current_cell tree count reaches zero",
            "limitations": "free-text parser is conservative; ownership is not task necessity; multi-tree cells may support useful joint cutting",
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
