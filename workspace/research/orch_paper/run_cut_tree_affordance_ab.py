#!/usr/bin/env python3
"""Replay frozen Cut_Trees action prompts with one authoritative affordance fact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_commitment_prompt_ab import call_model, extract_prompt, parse_action, snapshots


CHAT_ROOT = Path(
    "/data1/gzy/crew_bottom_up_20261029_attrition_fix/workspace/ORCH/crew-algorithms/"
    "crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-flash/"
    "Cut_Trees_Sparse_large/42/2026-10-29-16-18-09"
)
EVENTS = Path(
    "/data1/gzy/crew_bottom_up_20261029_attrition_fix/runs/large_sparse_clearance/"
    "run/events.jsonl"
)

AFFORDANCE_HINT = """

[AUTHORITATIVE ACTION AFFORDANCE]
Cutting one tree in the firefighter's current cell does not require or consume water.
Water is needed for spraying fire, not for cutting. Do not refill or travel to water solely
as a prerequisite to cutting. Re-evaluate the current cell and latest assignments, avoid
duplicate work, and choose the best feasible action.
[/AUTHORITATIVE ACTION AFFORDANCE]
"""

CONTRACT_HINT = """

[AUTHORITATIVE ACTION AND RESPONSIBILITY CONTRACT]
Cutting one tree in the firefighter's current cell does not require or consume water.
Water is needed for spraying fire, not for cutting. Do not refill or travel to water solely
as a prerequisite to cutting. Also preserve the latest explicit responsibility partition:
do not choose a coordinate currently assigned or claimed by another agent unless newer
evidence says that responsibility was released or its fallback condition was activated.
If your current cell contains your assigned target tree, cut it. Otherwise continue an
uncontested assigned target or choose non-duplicative feasible work.
[/AUTHORITATIVE ACTION AND RESPONSIBILITY CONTRACT]
"""


def classify(response, water_sources):
    action = (parse_action(response) or "").lower()
    if "cut" in action:
        return "CUT"
    if "refill" in action:
        return "REFILL"
    if "move" in action and any(
            f"{int(x)},{int(y)}" in action.replace(" ", "")
            for x, y in water_sources):
        return "MOVE_WATER_SOURCE"
    if "move" in action:
        return "MOVE_OTHER"
    if action:
        return "OTHER"
    return "UNPARSEABLE"


def frozen_cases(chat_root=CHAT_ROOT, events_path=EVENTS):
    world = snapshots(events_path)
    specs = [
        {"agent": "3", "step": 9, "role": "historical_water_detour",
         "water_sources": [(11, 26), (16, 34)]},
        {"agent": "4", "step": 6, "role": "historical_water_detour",
         "water_sources": [(16, 34)]},
        {"agent": "1", "step": 7, "role": "historical_refill_attempt",
         "water_sources": [(16, 34)]},
        {"agent": "2", "step": 9, "role": "historical_correct_cut_control",
         "water_sources": [(11, 26)]},
    ]
    result = []
    for spec in specs:
        prompt, logged = extract_prompt(chat_root / f"Agent_{spec['agent']}" / "chats.txt",
                                        spec["step"])
        node = world[spec["step"]]["nodes"][spec["agent"]]
        result.append({**spec, "position": node["position"],
                       "water": node["resources"]["water"],
                       "current_cell": node.get("facts", {}).get("current_cell"),
                       "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                       "logged_action": parse_action(logged),
                       "logged_class": classify(logged, spec["water_sources"]),
                       "prompt": prompt})
    return result


def run(model, base_url, api_key, repeats, chat_root=CHAT_ROOT, events_path=EVENTS):
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=1)
    cases = frozen_cases(chat_root, events_path)
    for case in cases:
        system = (
            f"You are Agent {case['agent']}, an embodied agent in a cooperative multi-agent "
            "robotic task. Choose your next best action from the available action types."
        )
        for condition, suffix in (("baseline", ""), ("affordance_aware", AFFORDANCE_HINT)):
            replays = [call_model(client, model, system, case["prompt"] + suffix)
                       for _ in range(repeats)]
            for replay in replays:
                replay["action"] = parse_action(replay["text"])
                replay["class"] = classify(replay["text"], case["water_sources"])
            case[f"{condition}_replays"] = replays
        del case["prompt"]
    client.close()
    return {"scope": {"model": model, "temperature": 0, "case_count": len(cases),
                      "repeats_per_condition": repeats, "environment_replay": False,
                      "conditions": ["baseline", "affordance_aware"]},
            "affordance_hint": AFFORDANCE_HINT.strip(), "cases": cases}


def extend_contract(existing_path, model, base_url, api_key,
                    chat_root=CHAT_ROOT, events_path=EVENTS):
    from openai import OpenAI
    result = json.loads(Path(existing_path).read_text())
    repeats = int(result["scope"]["repeats_per_condition"])
    frozen = {(case["agent"], case["step"]): case
              for case in frozen_cases(chat_root, events_path)}
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=1)
    for stored in result["cases"]:
        case = frozen[(stored["agent"], stored["step"])]
        if case["prompt_sha256"] != stored["prompt_sha256"]:
            raise ValueError("frozen prompt hash changed")
        system = (
            f"You are Agent {case['agent']}, an embodied agent in a cooperative multi-agent "
            "robotic task. Choose your next best action from the available action types."
        )
        replays = [call_model(client, model, system, case["prompt"] + CONTRACT_HINT)
                   for _ in range(repeats)]
        for replay in replays:
            replay["action"] = parse_action(replay["text"])
            replay["class"] = classify(replay["text"], case["water_sources"])
        stored["contract_aware_replays"] = replays
    client.close()
    result["scope"]["conditions"] = ["baseline", "affordance_aware", "contract_aware"]
    result["contract_hint"] = CONTRACT_HINT.strip()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--run-api", action="store_true")
    parser.add_argument("--extend-existing", type=Path)
    args = parser.parse_args()
    if args.run_api:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise SystemExit("DEEPSEEK_API_KEY is not set")
        if args.extend_existing:
            result = extend_contract(args.extend_existing, args.model, args.base_url, key)
        else:
            result = run(args.model, args.base_url, key, args.repeats)
    else:
        cases = frozen_cases()
        for case in cases:
            del case["prompt"]
        result = {"scope": {"dry_run": True, "case_count": len(cases)}, "cases": cases}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
