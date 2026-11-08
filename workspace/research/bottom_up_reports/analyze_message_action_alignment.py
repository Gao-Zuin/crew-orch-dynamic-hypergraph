"""Spatial response proxy for cross-group LEADER messages.

For every coordinate-bearing LEADER delivery, compare the target edge's action
targets one step before versus the delivery step and next step.  A within-run
circular permutation of message coordinates is the negative control.

Alignment is not causal adoption: local observations and shared task context can
produce the same action.  The permutation only tests whether the logged pairing
is more specific than the run's coordinate/action marginals.
"""
from collections import defaultdict
from pathlib import Path
import argparse
import json
import math
import random
import sys
import re


sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_message_chains import DEFAULT_RUNS, coordinates, load_events  # noqa: E402


def parse_coord(value):
    x, y = value.split(",")
    return float(x), float(y)


def close(target, coord, radius):
    return max(abs(target[0] - coord[0]), abs(target[1] - coord[1])) <= radius


def action_targets(events):
    targets = defaultdict(dict)
    for event in events:
        if event.get("event_type") != "ACTION_STARTED":
            continue
        action = event.get("payload", {}).get("action")
        step = event.get("payload", {}).get("timestep")
        if (isinstance(step, int) and isinstance(action, list) and len(action) >= 3
                and all(isinstance(v, (int, float)) and math.isfinite(v) for v in action[1:3])):
            targets[step][str(event.get("agent_id"))] = (float(action[1]), float(action[2]))
    return targets


def completed_actions(events):
    completed = defaultdict(dict)
    for event in events:
        if event.get("event_type") != "ACTION_COMPLETED":
            continue
        match = re.match(r"t(\d+)-agent", str(event.get("action_id", "")))
        if match:
            completed[int(match.group(1))][str(event.get("agent_id"))] = event
    return completed


def after_action_rewards(events):
    rewards = {}
    for event in events:
        payload = event.get("payload", {})
        if (event.get("event_type") == "TASK_WORLD_SNAPSHOT"
                and payload.get("phase") == "after_action"
                and isinstance(payload.get("step"), int)):
            rewards[payload["step"]] = payload.get("rewards", [])
    return rewards


def task_reward_index(task_id):
    if "Rescue_Civilians" in (task_id or ""):
        return 5
    if "Transport" in (task_id or ""):
        return 6
    if "Cut_Trees" in (task_id or ""):
        return 4
    if "Fire" in (task_id or "") or "Rapid_Growth" in (task_id or ""):
        return 3
    return None


def distance_to_coords(position, coords):
    return min(max(abs(position[0] - coord[0]), abs(position[1] - coord[1]))
               for coord in coords)


def annotate_physical_outcomes(actual, messages, events, radius, horizon=5):
    message_by_id = {message["event_id"]: message for message in messages}
    completed = completed_actions(events)
    rewards = after_action_rewards(events)
    task_id = events[0].get("task_id") if events else None
    reward_index = task_reward_index(task_id)
    summary = defaultdict(int)
    for detail in actual["details"]:
        if not detail["new_alignment"]:
            continue
        summary["new_alignment"] += 1
        message = message_by_id[detail["event_id"]]
        coords = tuple(tuple(value) for value in detail["coords"])
        returned = False
        closer = False
        interaction = False
        resource_change = False
        civilian_pickup = False
        water_spent = False
        for match in detail["post_matches"]:
            event = completed.get(match["step"], {}).get(match["agent"])
            if event is None:
                continue
            returned = True
            position = event.get("payload", {}).get("verified_local_delta", {}).get("position")
            if position and position.get("before") and position.get("after"):
                closer |= (distance_to_coords(position["after"], coords)
                           < distance_to_coords(position["before"], coords))
        for step in range(message["step"], message["step"] + horizon + 1):
            for agent in message["members"]:
                event = completed.get(step, {}).get(agent)
                if event is None:
                    continue
                payload = event.get("payload", {})
                action = payload.get("action", [])
                if (len(action) >= 3 and action[0] != 0
                        and any(close((action[1], action[2]), coord, radius) for coord in coords)):
                    interaction = True
                    resources = payload.get("verified_local_delta", {}).get("resources")
                    if resources and resources.get("before") != resources.get("after"):
                        resource_change = True
                        before, after = resources["before"], resources["after"]
                        civilian_pickup |= (before.get("civilian_carried") == 0
                                            and after.get("civilian_carried") == 1)
                        water_spent |= (isinstance(before.get("water"), (int, float))
                                        and isinstance(after.get("water"), (int, float))
                                        and after["water"] < before["water"])
        coincident_progress = False
        if reward_index is not None:
            baseline_step = max((step for step in rewards if step < message["step"]), default=None)
            baseline = (rewards[baseline_step][reward_index] if baseline_step is not None
                        and len(rewards[baseline_step]) > reward_index else None)
            later = [value[reward_index] for step, value in rewards.items()
                     if message["step"] <= step <= message["step"] + horizon
                     and len(value) > reward_index]
            coincident_progress = baseline is not None and later and max(later) > baseline
        physical = {"aligned_action_returned": returned,
                    "verified_position_moved_closer": closer,
                    "on_target_nonmove_interaction_within_horizon": interaction,
                    "on_target_resource_change_within_horizon": resource_change,
                    "civilian_pickup_within_horizon": civilian_pickup,
                    "water_spent_within_horizon": water_spent,
                    "coincident_global_task_progress_within_horizon": bool(coincident_progress)}
        detail["physical_outcome_proxy"] = physical
        for key, value in physical.items():
            summary[key] += bool(value)
    actual["physical_chain_summary"] = dict(summary)


def leader_deliveries(events):
    current_edges = {}
    messages = []
    for event in events:
        payload = event.get("payload", {})
        if event.get("event_type") == "TASK_GRAPH_COMMITTED":
            current_edges = {edge.get("id"): tuple(str(a) for a in edge.get("members", []))
                             for edge in payload.get("edges", [])}
        elif (event.get("event_type") == "TASK_MESSAGE_DELIVERED"
              and payload.get("message_type") == "LEADER"):
            found = tuple(sorted(parse_coord(value) for value in coordinates(payload.get("content", ""))))
            target = payload.get("target")
            members = current_edges.get(target, ())
            if found and members and isinstance(payload.get("step"), int):
                messages.append({"event_id": event["event_id"], "step": payload["step"],
                                 "source": payload.get("source"), "target": target,
                                 "direct_recipient": str(payload.get("recipient")),
                                 "target_members": members, "members": (), "coords": found,
                                 "content": payload.get("content", "")})
    # Attribute downstream actions only to agents with a logged information path:
    # the direct leader recipient, plus recipients of that leader's near-term
    # GROUP messages that preserve at least one exact coordinate.
    delivered = [event for event in events if event.get("event_type") == "TASK_MESSAGE_DELIVERED"]
    for message in messages:
        informed = {message["direct_recipient"]}
        for event in delivered:
            payload = event.get("payload", {})
            if (event["event_id"] <= message["event_id"]
                    or payload.get("step") not in {message["step"], message["step"] + 1}
                    or str(payload.get("sender")) != message["direct_recipient"]
                    or payload.get("message_type") != "GROUP"
                    or payload.get("target") != message["target"]):
                continue
            if set(message["coords"]) & {parse_coord(value) for value in coordinates(payload.get("content", ""))}:
                informed.add(str(payload.get("recipient")))
        message["members"] = tuple(sorted(informed, key=lambda value: int(value)))
    return messages


def matches(coords, members, targets, steps, radius):
    result = []
    for step in steps:
        for agent in members:
            target = targets.get(step, {}).get(agent)
            if target is None:
                continue
            for coord in coords:
                if close(target, coord, radius):
                    result.append({"step": step, "agent": agent,
                                   "action_target": list(target), "message_coord": list(coord)})
    return result


def max_persistence(coords, members, targets, start_step, radius, horizon=5):
    """Longest consecutive aligned action sequence beginning at step or step+1."""
    best = 0
    for agent in members:
        for first in (start_step, start_step + 1):
            target = targets.get(first, {}).get(agent)
            if target is None or not any(close(target, coord, radius) for coord in coords):
                continue
            length = 0
            for step in range(first, first + horizon):
                target = targets.get(step, {}).get(agent)
                if target is None or not any(close(target, coord, radius) for coord in coords):
                    break
                length += 1
            best = max(best, length)
    return best


def score(messages, coord_sets, targets, radius, include_details=True):
    post = 0
    new = 0
    details = []
    for message, coords in zip(messages, coord_sets):
        step = message["step"]
        before = matches(coords, message["members"], targets, (step - 1,), radius)
        after = matches(coords, message["members"], targets, (step, step + 1), radius)
        post += bool(after)
        new += bool(after) and not bool(before)
        if include_details:
            persistence = (max_persistence(coords, message["members"], targets, step, radius)
                           if bool(after) and not bool(before) else 0)
            details.append({"event_id": message["event_id"], "step": step,
                            "source": message["source"], "target": message["target"],
                            "direct_recipient": message["direct_recipient"],
                            "informed_members": list(message["members"]),
                            "target_edge_member_count": len(message["target_members"]),
                            "coords": [list(value) for value in coords],
                            "pre_matches": before, "post_matches": after,
                            "new_alignment": bool(after) and not bool(before),
                            "max_consecutive_alignment_steps": persistence})
    count = len(messages)
    return {"message_count": count, "post_alignment_count": post,
            "new_alignment_count": new,
            "post_alignment_rate": post / count if count else None,
            "new_alignment_rate": new / count if count else None,
            "details": details}


def analyze_run(path, radius=5.0, outcome_horizon=5):
    events = load_events(path)
    messages = leader_deliveries(events)
    targets = action_targets(events)
    actual_coords = [message["coords"] for message in messages]
    actual = score(messages, actual_coords, targets, radius)
    annotate_physical_outcomes(actual, messages, events, radius, horizon=outcome_horizon)
    control_rates = []
    if len(messages) > 1:
        # All non-identity circular shifts form a deterministic within-run control.
        for shift in range(1, len(messages)):
            shifted = actual_coords[shift:] + actual_coords[:shift]
            candidate = score(messages, shifted, targets, radius, include_details=False)
            control_rates.append(candidate["new_alignment_rate"])
    control_mean = sum(control_rates) / len(control_rates) if control_rates else None
    control_ge_actual = (sum(rate >= actual["new_alignment_rate"] for rate in control_rates)
                         if control_rates else None)
    return {
        "path": str(path), "task_id": events[0].get("task_id") if events else None,
        "radius_chebyshev": radius,
        "actual": actual,
        "control": {
            "method": "all non-identity within-run circular shifts of message coordinate sets",
            "shift_count": len(control_rates),
            "mean_new_alignment_rate": control_mean,
            "shifts_at_least_actual": control_ge_actual,
            "fraction_at_least_actual": (control_ge_actual / len(control_rates)
                                         if control_rates else None),
        },
        "limitations": "Spatial novelty is a response proxy, not semantic or causal adoption.",
    }


def analyze_all(runs=None, radius=5.0, permutation_samples=500, seed=20261108,
                outcome_horizon=5):
    runs = runs or DEFAULT_RUNS
    details = {name: analyze_run(path, radius, outcome_horizon) for name, path in runs.items()}
    total_messages = sum(item["actual"]["message_count"] for item in details.values())
    total_new = sum(item["actual"]["new_alignment_count"] for item in details.values())
    persistence = [detail["max_consecutive_alignment_steps"]
                   for item in details.values() for detail in item["actual"]["details"]
                   if detail["new_alignment"]]
    physical_totals = defaultdict(int)
    for item in details.values():
        for key, value in item["actual"].get("physical_chain_summary", {}).items():
            physical_totals[key] += value
    weighted_control = sum(
        (item["control"]["mean_new_alignment_rate"] or 0) * item["actual"]["message_count"]
        for item in details.values() if item["control"]["mean_new_alignment_rate"] is not None)
    controlled_messages = sum(
        item["actual"]["message_count"] for item in details.values()
        if item["control"]["mean_new_alignment_rate"] is not None)
    prepared = []
    for path in runs.values():
        events = load_events(path)
        messages = leader_deliveries(events)
        if messages:
            prepared.append((messages, [message["coords"] for message in messages],
                             action_targets(events)))
    rng = random.Random(seed)
    null_counts = []
    for _ in range(permutation_samples):
        count = 0
        for messages, coord_sets, targets in prepared:
            shuffled = list(coord_sets)
            rng.shuffle(shuffled)
            count += score(messages, shuffled, targets, radius,
                           include_details=False)["new_alignment_count"]
        null_counts.append(count)
    null_counts.sort()
    ge_actual = sum(value >= total_new for value in null_counts)
    return {
        "scope": {"run_count": len(details), "radius_chebyshev": radius,
                  "physical_outcome_horizon_steps": outcome_horizon,
                  "selection": "all coordinate-bearing delivered LEADER messages in 15 complete HT mainline runs"},
        "totals": {"message_count": total_messages, "new_alignment_count": total_new,
                   "actual_new_alignment_rate": total_new / total_messages if total_messages else None,
                   "new_alignments_persistent_at_least_2_steps":
                       sum(value >= 2 for value in persistence),
                   "new_alignments_persistent_at_least_3_steps":
                       sum(value >= 3 for value in persistence),
                   "mean_max_consecutive_alignment_steps":
                       sum(persistence) / len(persistence) if persistence else None,
                   "physical_chain_summary": dict(physical_totals),
                   "message_weighted_control_mean_rate":
                       weighted_control / controlled_messages if controlled_messages else None,
                   "global_within_run_permutation_control": {
                       "samples": permutation_samples, "seed": seed,
                       "mean_new_alignment_count": sum(null_counts) / len(null_counts),
                       "mean_new_alignment_rate": (sum(null_counts) / len(null_counts) / total_messages
                                                   if total_messages else None),
                       "p95_new_alignment_count": null_counts[int(0.95 * (len(null_counts) - 1))],
                       "permutations_at_least_actual": ge_actual,
                       "smoothed_fraction_at_least_actual":
                           (ge_actual + 1) / (len(null_counts) + 1)}},
        "runs": details,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--radius", type=float, default=5.0)
    parser.add_argument("--permutations", type=int, default=500)
    parser.add_argument("--outcome-horizon", type=int, default=5)
    args = parser.parse_args()
    result = analyze_all(radius=args.radius, permutation_samples=args.permutations,
                         outcome_horizon=args.outcome_horizon)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
