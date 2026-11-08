#!/usr/bin/env python3
"""Audit explicit ``after refill`` assignments against observed actions/resources.

This is deliberately a narrow audit.  Firefighter refill only works at zero water;
therefore a manager's ``after refill`` instruction can itself be infeasible when the
assignee has 1--4 water.  The audit separates feasible empty-tank prerequisites from
impossible top-up requests instead of treating literal departure as a worker failure.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


COORD_RE = re.compile(r"\(?\s*(\d+(?:\.\d+)?)\s*[,，]\s*(\d+(?:\.\d+)?)\s*\)?")
AFTER_REFILL_RE = re.compile(r"after\s+refill(?:ing|ed)?", re.I)
AGENT_RE = re.compile(r"AGENT[_\s-]?(\d+)", re.I)


def chebyshev(a, b):
    return max(abs(float(a[0]) - float(b[0])), abs(float(a[1]) - float(b[1])))


def load_events(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def event_step(event):
    payload = event.get("payload", {})
    return payload.get("step", payload.get("timestep"))


def build_trace(events):
    snapshots = {}
    actions = {}
    for event in events:
        payload = event.get("payload", {})
        step = event_step(event)
        if step is None:
            continue
        step = int(step)
        if (event.get("event_type") == "TASK_WORLD_SNAPSHOT"
                and payload.get("phase") == "before_action"):
            snapshots[step] = payload
        elif event.get("event_type") == "ACTION_STARTED":
            actions[(step, str(event.get("agent_id")))] = payload.get("action")
    return snapshots, actions


def mentioned_assignee(content, recipient):
    """Require the delivered recipient to be the named agent nearest the clause.

    Leader broadcasts often contain assignments for several people.  Counting every
    recipient would manufacture obligations, so an unnamed recipient is excluded.
    """
    return assignment_segment(content, recipient) is not None


def assignment_segment(content, recipient):
    """Return a single-agent clause that explicitly orders work after refill."""
    pattern = re.compile(
        rf"AGENT[_\s-]?{re.escape(str(recipient))}\b[^.;]{{0,120}}"
        rf"after\s+refill(?:ing|ed)?[^.;]{{0,180}}",
        re.I,
    )
    match = pattern.search(content)
    if not match:
        return None
    segment = match.group(0)
    refill = AFTER_REFILL_RE.search(segment)
    # There must be a downstream coordinate after the prerequisite phrase;
    # otherwise "I will cover after refill" has no auditable destination.
    if not refill or not COORD_RE.search(segment[refill.end():]):
        return None
    return segment


def assignment_candidates(events):
    seen = set()
    for event in events:
        if event.get("event_type") != "TASK_MESSAGE_DELIVERED":
            continue
        payload = event.get("payload", {})
        content = payload.get("content", "")
        recipient = str(payload.get("recipient", ""))
        segment = assignment_segment(content, recipient)
        if not segment:
            continue
        step = int(payload["step"])
        key = (step, recipient, content)
        if key in seen:
            continue
        seen.add(key)
        yield {
            "event_id": event.get("event_id"), "step": step,
            "agent": recipient, "content": content,
            "assignment_clause": segment,
            "coordinates": [tuple(map(float, pair)) for pair in COORD_RE.findall(
                segment[AFTER_REFILL_RE.search(segment).end():])],
        }


def audit_run(path, horizon=10, target_radius=5):
    events = load_events(path)
    snapshots, actions = build_trace(events)
    observed_capacity = {}
    for snapshot in snapshots.values():
        for agent, node in snapshot.get("nodes", {}).items():
            water = node.get("resources", {}).get("water")
            if isinstance(water, (int, float)):
                observed_capacity[agent] = max(observed_capacity.get(agent, water), water)
    cases = []
    for item in assignment_candidates(events):
        start = snapshots.get(item["step"])
        node = (start or {}).get("nodes", {}).get(item["agent"])
        if not node:
            continue
        water_coord = tuple((start.get("task_parameters") or {}).get(k)
                            for k in ("water_x", "water_y"))
        if None in water_coord:
            continue
        targets = [c for c in item["coordinates"] if chebyshev(c, water_coord) > 1]
        if not targets:
            continue
        initial_water = node.get("resources", {}).get("water")
        if not isinstance(initial_water, (int, float)):
            continue
        # A full tank at assignment time already satisfies "after refill".  Using
        # each run's observed maximum avoids hard-coding a simulator capacity.
        capacity = observed_capacity.get(item["agent"])
        if initial_water == capacity:
            prerequisite_state = "ALREADY_FULL"
        elif initial_water == 0:
            prerequisite_state = "FEASIBLE_EMPTY_TANK_REFILL"
        else:
            prerequisite_state = "INFEASIBLE_POSITIVE_TANK_TOP_UP"
        refill_step = item["step"] if initial_water == capacity else None
        downstream_before_refill = []
        downstream_after_refill = []
        observations = []
        for step in range(item["step"], item["step"] + horizon + 1):
            snap = snapshots.get(step)
            current = (snap or {}).get("nodes", {}).get(item["agent"], {})
            water = current.get("resources", {}).get("water")
            action = actions.get((step, item["agent"]))
            if isinstance(water, (int, float)) and water > initial_water and refill_step is None:
                refill_step = step
            matched_target = None
            if isinstance(action, list) and len(action) >= 3 and action[0] == 0:
                point = (action[1], action[2])
                matched_target = next((t for t in targets if chebyshev(point, t) <= target_radius), None)
                if matched_target is not None:
                    (downstream_before_refill if refill_step is None
                     else downstream_after_refill).append(step)
            if snap and (action is not None or step == item["step"]):
                observations.append({"step": step, "water": water, "action": action,
                                     "target_match": matched_target})
        cases.append({**item, "initial_water": initial_water,
                      "observed_water_capacity": capacity,
                      "prerequisite_state_at_assignment": prerequisite_state,
                      "water_source": water_coord, "downstream_targets": targets,
                      "refill_evidenced_step": refill_step,
                      "downstream_action_before_refill_evidence_steps": downstream_before_refill,
                      "downstream_action_after_refill_steps": downstream_after_refill,
                      "observations": observations})
    return cases


def summarize(all_cases):
    return {
        "explicit_assignments": len(all_cases),
        "already_full_at_assignment": sum(c["prerequisite_state_at_assignment"] == "ALREADY_FULL"
                                           for c in all_cases),
        "feasible_empty_tank_refill_assignments": sum(
            c["prerequisite_state_at_assignment"] == "FEASIBLE_EMPTY_TANK_REFILL"
            for c in all_cases),
        "infeasible_positive_tank_top_up_assignments": sum(
            c["prerequisite_state_at_assignment"] == "INFEASIBLE_POSITIVE_TANK_TOP_UP"
            for c in all_cases),
        "with_prerequisite_satisfied_or_observed": sum(
            c["refill_evidenced_step"] is not None for c in all_cases),
        "with_downstream_action_before_refill_evidence": sum(
            bool(c["downstream_action_before_refill_evidence_steps"]) for c in all_cases),
        "with_downstream_action_after_refill": sum(bool(c["downstream_action_after_refill_steps"])
                                                     for c in all_cases),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("events", nargs="+")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--target-radius", type=int, default=5)
    parser.add_argument("--output")
    args = parser.parse_args()
    runs = {}
    combined = []
    for raw in args.events:
        cases = audit_run(raw, args.horizon, args.target_radius)
        runs[str(Path(raw))] = {"summary": summarize(cases), "cases": cases}
        combined.extend(cases)
    result = {"method": {"horizon": args.horizon, "target_radius": args.target_radius,
                         "refill_rule": "firefighter refills only from zero to capacity",
                         "refill_evidence": "observed water strictly above assignment-step water"},
              "summary": summarize(combined), "runs": runs}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
