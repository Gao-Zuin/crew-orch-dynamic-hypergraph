#!/usr/bin/env python3
"""Audit unnecessary water prerequisites in complete sparse tree-cutting runs.

The simulator contract says cutting does not consume or require water.  This audit
therefore treats refill actions in a pure Cut_Trees run with no fire as a conservative
lower bound on task-irrelevant work.  It does not infer water-seeking movement, so the
reported waste is intentionally incomplete.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re


DEFAULT_RUNS = {
    "flash_r2_sparse": {
        "events": Path("/data1/gzy/crew_bottom_up_20261029_attrition_fix/runs/large_sparse_clearance/run/events.jsonl"),
        "data": Path("/data1/gzy/crew_bottom_up_20261029_attrition_fix/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-flash/Cut_Trees_Sparse_large/42/2026-10-29-16-18-09/data.csv"),
    },
    "pro_r2_sparse": {
        "events": Path("/data1/gzy/crew_ht_r2_pro_sparse_20261030/runs/pro_sparse_seed42/run/events.jsonl"),
        "data": Path("/data1/gzy/crew_ht_r2_pro_sparse_20261030/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-v4-pro/Cut_Trees_Sparse_large/42/2026-10-30-15-50-29/data.csv"),
    },
    "flash_r3_sparse": {
        "events": Path("/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/runs/flash_sparse_seed42/run/events.jsonl"),
        "data": Path("/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-flash/Cut_Trees_Sparse_large/42/2026-11-02-21-02-12/data.csv"),
    },
}

REFILL_CUT_SEQUENCE = re.compile(
    r"(?:refill.{0,140}(?:then|before|after).{0,140}cut|"
    r"cut.{0,140}(?:after|once).{0,140}refill)", re.I)
FALSE_NECESSITY = re.compile(
    r"(?:"
    r"(?:do not|don't|cannot|can't) cut until (?:you |we |i )?(?:have )?water|"
    r"(?:need|must|will need)(?: to| a)? refill before (?:the |your |my )?(?:first )?cut|"
    r"(?:no|zero|out of) water.{0,50}(?:can't|cannot|unable to) cut|"
    r"(?:can't|cannot|unable to) cut.{0,50}(?:because|without|with no|with zero|out of) water|"
    r"do not claim cuts? until (?:the )?refill"
    r")", re.I)


def load_events(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def action_step(event):
    payload = event.get("payload", {})
    return int(payload.get("timestep", payload.get("step")))


def water_at(snapshots, step, agent):
    return (snapshots.get(step, {}).get("nodes", {}).get(str(agent), {})
            .get("resources", {}).get("water"))


def cell_delta(completed):
    facts = completed.get("payload", {}).get("verified_local_delta", {}).get("facts", {})
    try:
        before = int(facts["before"]["current_cell"])
        after = int(facts["after"]["current_cell"])
    except (KeyError, TypeError, ValueError):
        return None
    return before - after


def unique_coordination_claims(events):
    seen = set()
    claims = []
    for event in events:
        if event.get("event_type") != "TASK_MESSAGE_DELIVERED":
            continue
        payload = event.get("payload", {})
        content = payload.get("content", "")
        key = (payload.get("sender"), payload.get("step"), content)
        if key in seen:
            continue
        seen.add(key)
        if REFILL_CUT_SEQUENCE.search(content) or FALSE_NECESSITY.search(content):
            claims.append({"event_id": event.get("event_id"), "step": payload.get("step"),
                           "sender": payload.get("sender"), "content": content,
                           "refill_cut_sequence": bool(REFILL_CUT_SEQUENCE.search(content)),
                           "explicit_false_necessity": bool(FALSE_NECESSITY.search(content))})
    return claims


def progress_metrics(data_path):
    with Path(data_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    values = [int(float(row["correct_trees_cut"])) for row in rows]
    base = values[0]
    progress = [value - base for value in values]
    return {"logged_steps": len(rows), "initial_correct_trees_cut": base,
            "final_correct_trees_cut": values[-1], "progress": progress[-1],
            "progress_series": progress,
            "trees_fire_max": max(int(float(row["trees_fire"])) for row in rows)}


def analyze_run(events_path, data_path):
    events = load_events(events_path)
    snapshots = {int(event["payload"]["step"]): event["payload"] for event in events
                 if event.get("event_type") == "TASK_WORLD_SNAPSHOT"
                 and event.get("payload", {}).get("phase") == "before_action"}
    completed = {event.get("action_id"): event for event in events
                 if event.get("event_type") == "ACTION_COMPLETED"}
    no_effect = {event.get("action_id") for event in events
                 if event.get("event_type") == "ACTION_NO_EFFECT"}
    actions = [event for event in events if event.get("event_type") == "ACTION_STARTED"]
    cuts = [event for event in actions if event.get("payload", {}).get("action", [None])[0] == 1]
    refills = [event for event in actions if event.get("payload", {}).get("action", [None])[0] == 4]
    successful_cuts = [event for event in cuts
                       if (cell_delta(completed.get(event.get("action_id"), {})) or 0) > 0]
    successful_zero = [event for event in successful_cuts
                       if water_at(snapshots, action_step(event), event.get("agent_id")) == 0]
    refill_evidence = []
    for event in refills:
        step = action_step(event)
        before = water_at(snapshots, step, event.get("agent_id"))
        after = water_at(snapshots, step + 1, event.get("agent_id"))
        refill_evidence.append({"event_id": event.get("event_id"), "action_id": event.get("action_id"),
                                "step": step, "agent": str(event.get("agent_id")),
                                "water_before": before, "water_next_step": after,
                                "water_increased": (isinstance(before, (int, float))
                                                    and isinstance(after, (int, float))
                                                    and after > before),
                                "logged_no_effect": event.get("action_id") in no_effect})
    claims = unique_coordination_claims(events)
    return {
        "events_path": str(events_path), "data_path": str(data_path),
        "actions": len(actions), "move_actions": sum(
            event.get("payload", {}).get("action", [None])[0] == 0 for event in actions),
        "cut_actions": len(cuts), "successful_cut_effects": len(successful_cuts),
        "successful_cut_effects_with_zero_water": len(successful_zero),
        "refill_actions": len(refills),
        "refill_actions_logged_no_effect": sum(item["logged_no_effect"] for item in refill_evidence),
        "refill_actions_with_next_step_water_increase": sum(
            item["water_increased"] for item in refill_evidence),
        "refill_evidence": refill_evidence,
        "unique_refill_cut_claims": len(claims),
        "unique_explicit_false_necessity_claims": sum(
            item["explicit_false_necessity"] for item in claims),
        "claim_examples": claims[:20],
        **progress_metrics(data_path),
    }


def fixed_horizon_auc(series, target_progress, horizon):
    extended = (list(series) + [series[-1]] * horizon)[:horizon]
    return sum(extended) / target_progress / horizon


def analyze_all(runs=None):
    runs = runs or DEFAULT_RUNS
    details = {name: analyze_run(paths["events"], paths["data"])
               for name, paths in runs.items()}
    target_progress = max(detail["progress"] for detail in details.values())
    for detail in details.values():
        detail["normalized_progress_auc_h20"] = fixed_horizon_auc(
            detail["progress_series"], target_progress, 20)
        detail["normalized_progress_auc_h50"] = fixed_horizon_auc(
            detail["progress_series"], target_progress, 50)
    return {
        "method": {
            "authoritative_rule": "cutting one tree does not require or consume water",
            "waste_lower_bound": "refill commands in pure Cut_Trees runs with trees_fire_max=0",
            "cut_success": "ACTION_COMPLETED current_cell integer decreases",
            "fixed_horizon_auc": "mean cumulative correct-tree progress / best observed total progress; terminal progress carried forward",
            "limitations": "water-seeking moves are not inferred; cross-version comparison is observational, not causal",
        },
        "target_progress_for_normalization": target_progress,
        "runs": details,
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
