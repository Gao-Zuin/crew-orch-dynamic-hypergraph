#!/usr/bin/env python3
"""Audit vertical-manager phase transitions in official ORCH result logs.

The audit uses every indexed DeepSeek method whose name starts with WILDFIRE.
It treats manager-reported progress as a claim, not ground truth, and separately
attaches objective CSV counter deltas when those counters exist.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import glob
import json
from pathlib import Path
import re


PROGRESS_COLUMNS = (
    "fire_extinguished", "correct_trees_cut", "civilians_rescued",
    "firefighters_transported", "civilians_scouted", "fire_scouted", "water_scouted",
)
COMPLEX_TASKS = {
    "Full_Game", "Scale_Level_Complex", "Suppress_Fire_Extinguish_Rapid_Growth",
    "Suppress_Fire_Extinguish_Second_Fire", "Rescue_Civilians_Surprise",
    "Transport_Helicopter_Down",
}
OUT_OF_DOMAIN = re.compile(
    r"\b(infiltrator|hacker|mainframe|electronic lock|motion sensor|"
    r"suppressive fire|security responder|exfil|extraction point|"
    r"flanks and eliminates|escort the asset|dropship|hostile territory)\b", re.I,
)


def indexed_runs(index_path):
    with Path(index_path).open(newline="") as handle:
        return [row for row in csv.DictReader(handle)
                if row.get("model") == "deepseek"
                and row.get("method", "").startswith("WILDFIRE")]


def load_master(run_path):
    candidates = sorted(glob.glob(str(Path(run_path) / "master_logs" / "*.json")))
    if not candidates:
        return None, None
    path = candidates[-1]
    with open(path) as handle:
        return path, json.load(handle).get("events", [])


def load_progress(run_path):
    path = Path(run_path) / "data.csv"
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        try:
            step = int(float(row["timestep"]))
        except (KeyError, TypeError, ValueError):
            continue
        result[step] = {key: float(row.get(key, 0) or 0) for key in PROGRESS_COLUMNS}
    return result


def progress_at(rows, step):
    prior = [candidate for candidate in rows if candidate <= step]
    return rows[max(prior)] if prior else {key: 0.0 for key in PROGRESS_COLUMNS}


def phase_start(statuses, transition_index):
    current = statuses[transition_index].get("phase")
    start = int(statuses[transition_index].get("timestep", 0))
    for item in reversed(statuses[:transition_index]):
        if item.get("phase") != current:
            break
        start = int(item.get("timestep", start))
    return start


def contains_key(value, wanted):
    if isinstance(value, dict):
        return wanted in value or any(contains_key(child, wanted) for child in value.values())
    if isinstance(value, list):
        return any(contains_key(child, wanted) for child in value)
    return False


def simulate_add_phases_queue(current_phase, future_phases, new_phases):
    """Mirror the official ADD_PHASES handler's queue operations exactly."""
    future = list(future_phases)
    future.extend(new_phases)
    history = [current_phase]
    next_current = future.pop(0) if future else current_phase
    return {"current_phase": next_current, "future_phases": future,
            "phase_history": history}


def audit_run(row):
    master_path, events = load_master(row["run"])
    if events is None:
        return {"metadata": row, "master_log": None, "error": "master_log_missing",
                "transitions": []}
    progress = load_progress(row["run"])
    statuses_by_agent = defaultdict(list)
    for event in events:
        if event.get("event_type") == "STATUS_PHASE":
            statuses_by_agent[str(event.get("agent_id"))].append(event)
    for statuses in statuses_by_agent.values():
        statuses.sort(key=lambda item: (int(item.get("timestep", 0)), item.get("timestamp", "")))

    transitions = []
    for event in events:
        if (event.get("event_type") != "ACTION_PHASE"
                or event.get("details", {}).get("decision") != "PHASE_TRANSITION"):
            continue
        agent = str(event.get("agent_id"))
        step = int(event.get("timestep", 0))
        statuses = statuses_by_agent[agent]
        matching = [(index, item) for index, item in enumerate(statuses)
                    if int(item.get("timestep", -1)) == step]
        if not matching:
            transitions.append({"agent": agent, "step": step, "status_missing": True,
                                "to_phase": event.get("phase")})
            continue
        status_index, status = matching[-1]
        details = status.get("details", {})
        from_phase = status.get("phase")
        start = phase_start(statuses, status_index)
        before = progress_at(progress, max(start - 1, 0))
        after = progress_at(progress, step)
        deltas = {key: after[key] - before[key] for key in PROGRESS_COLUMNS}
        later_resumed = any(
            int(item.get("timestep", -1)) > step and item.get("phase") == from_phase
            for item in statuses
        )
        transition = {
            "agent": agent, "step": step, "phase_start_step": start,
            "from_phase": from_phase, "to_phase": event.get("phase"),
            "status_decision": details.get("decision"),
            "reported_phase_percent": details.get("phase_percent"),
            "reported_mission_percent": details.get("mission_percent"),
            "objective_counter_delta_during_phase": deltas,
            "any_objective_counter_increase": any(value > 0 for value in deltas.values()),
            "old_phase_later_resumed_exactly": later_resumed,
            "out_of_domain_to_phase": bool(OUT_OF_DOMAIN.search(event.get("phase") or "")),
        }
        transitions.append(transition)
    return {
        "metadata": {key: row.get(key) for key in
                     ("model", "method", "task", "seed", "configuration", "run")},
        "master_log": master_path,
        "completion_condition_present_anywhere_in_master_log":
            contains_key(events, "completion_condition"),
        "transitions": transitions,
    }


def transition_summary(transitions):
    counter = Counter()
    for item in transitions:
        counter["phase_transitions"] += 1
        if item.get("status_missing"):
            counter["matching_status_missing"] += 1
            continue
        percent = item.get("reported_phase_percent")
        decision = item.get("status_decision")
        if decision == "NEXT_PHASE":
            counter["next_phase_transitions"] += 1
        elif decision == "ADD_PHASES":
            counter["add_phases_transitions"] += 1
        if percent == 100:
            counter["reported_100_percent"] += 1
        elif isinstance(percent, (int, float)):
            counter["reported_below_100_percent"] += 1
            if percent == 0:
                counter["reported_zero_percent"] += 1
        else:
            counter["reported_percent_missing"] += 1
        if decision == "NEXT_PHASE" and isinstance(percent, (int, float)) and percent < 100:
            counter["next_phase_while_reported_below_100"] += 1
            if item.get("any_objective_counter_increase"):
                counter["below_100_next_phase_with_objective_progress"] += 1
        if decision == "ADD_PHASES" and isinstance(percent, (int, float)) and percent < 100:
            counter["add_phases_while_reported_below_100"] += 1
            if item.get("any_objective_counter_increase"):
                counter["below_100_add_phases_with_objective_progress"] += 1
            if not item.get("old_phase_later_resumed_exactly"):
                counter["unfinished_add_phase_never_resumed_exactly"] += 1
        if item.get("any_objective_counter_increase"):
            counter["with_any_objective_counter_increase"] += 1
        if item.get("out_of_domain_to_phase"):
            counter["out_of_domain_phase_transition"] += 1
    return dict(counter)


def analyze(index_path):
    rows = indexed_runs(index_path)
    runs = [audit_run(row) for row in rows]
    transitions = [item for run in runs for item in run["transitions"]]
    by_method = {}
    by_task = {}
    for method in sorted({run["metadata"].get("method") for run in runs}):
        selected = [item for run in runs if run["metadata"].get("method") == method
                    for item in run["transitions"]]
        by_method[method] = transition_summary(selected)
    for task in sorted({run["metadata"].get("task") for run in runs}):
        selected = [item for run in runs if run["metadata"].get("task") == task
                    for item in run["transitions"]]
        by_task[task] = transition_summary(selected)
    return {
        "scope": {"indexed_runs": len(rows),
                  "parsed_runs": sum(run.get("master_log") is not None for run in runs),
                  "missing_master_logs": sum(run.get("master_log") is None for run in runs),
                  "selection": "all indexed deepseek methods starting with WILDFIRE"},
        "summary": transition_summary(transitions),
        "completion_condition_logged_runs":
            sum(bool(run.get("completion_condition_present_anywhere_in_master_log")) for run in runs),
        "add_phases_queue_calibration": {
            "existing_future_phase": simulate_add_phases_queue("A_unfinished", ["B_planned"],
                                                                 ["X_new_immediate"]),
            "no_existing_future_phase": simulate_add_phases_queue("A_unfinished", [],
                                                                    ["X_new_immediate"]),
        },
        "complex_task_summary": transition_summary([
            item for run in runs if run["metadata"].get("task") in COMPLEX_TASKS
            for item in run["transitions"]]),
        "by_method": by_method,
        "by_task": by_task,
        "runs": runs,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="/data1/gzy/ORCH/inspection_20261026/runs_index.csv")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze(args.index)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
