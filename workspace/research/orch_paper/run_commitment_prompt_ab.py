#!/usr/bin/env python3
"""Replay frozen action prompts with literal and domain-aware obligation hints.

This is a prompt-level counterfactual, not an environment replay.  It extracts the
exact user prompts logged by the Pro second-fire run and stores only hashes plus
model responses, never API credentials or the very large prompts themselves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re


ACTION_BLOCK = re.compile(
    r"Choosing Action\n-+\n\nuser\n-----\n(.*?)\n-----\n\nassistant\n-----\n(.*?)\n-----",
    re.S,
)
ACTION_TAG = re.compile(r"<action>\s*(.*?)\s*</action>", re.S | re.I)
COORD = re.compile(r"\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?")


DEFAULT_CHAT_ROOT = Path(
    "/data1/gzy/crew_ht_r2_pro_campaign_20261030/workspace/ORCH/crew-algorithms/"
    "crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-v4-pro/"
    "Suppress_Fire_Extinguish_Second_Fire/137/2026-10-31-17-00-49"
)
DEFAULT_EVENTS = Path(
    "/data1/gzy/crew_ht_r2_pro_campaign_20261030/runs/pro_second_fire/run/events.jsonl"
)


def extract_prompt(chat_path, step):
    matches = []
    for user, assistant in ACTION_BLOCK.findall(Path(chat_path).read_text()):
        advisory_steps = re.findall(
            r"\[TASK GROUP — ADVISORY\]\s*\{\"step\":\s*(\d+)", user)
        if advisory_steps and int(advisory_steps[-1]) == int(step):
            matches.append((user, assistant))
    if len(matches) != 1:
        raise ValueError(f"expected one action prompt for step {step}, found {len(matches)}")
    return matches[0]


def snapshots(path):
    result = {}
    with Path(path).open() as handle:
        for line in handle:
            event = json.loads(line)
            payload = event.get("payload", {})
            if (event.get("event_type") == "TASK_WORLD_SNAPSHOT"
                    and payload.get("phase") == "before_action"):
                result[int(payload["step"])] = payload
    return result


def reminder(case):
    """Naive literal reminder retained as a negative-control intervention."""
    prerequisite = case["status"]
    if prerequisite == "VERIFIED":
        status_line = (
            f"VERIFIED: observed water is {case['water']}, satisfying the refill prerequisite. "
            "The downstream task may proceed if current observations remain safe.")
    else:
        status_line = (
            f"NOT VERIFIED: observed water is still {case['water']}; no water increase has been "
            "observed since this sequence was assigned. Continue an action that advances the refill "
            "prerequisite before departing for the downstream target.")
    return f"""

[NAIVE LITERAL EXECUTION LEDGER — NEGATIVE CONTROL]
Pending sequence: refill at {tuple(case['water_source'])}, then travel to {tuple(case['target'])}.
Authoritative environment state: position={tuple(case['position'])}, water={case['water']}.
Prerequisite status: {status_line}
This reminder is not an execution-permission gate. Override it only for a newer explicit
cancellation/reassignment or an immediately observed safety threat, and explain the evidence.
[/NAIVE LITERAL EXECUTION LEDGER]
"""


def domain_aware_reminder(case):
    if case["water"] >= 5:
        status = (
            "VERIFIED: the tank is full, so the downstream task may proceed if current "
            "observations remain safe.")
    elif case["water"] > 0:
        status = (
            f"BLOCKED AS WRITTEN: the tank has {case['water']} water. In this environment a "
            "firefighter can refill only when the tank is exactly 0; 1-4 water cannot be "
            "topped up. Do not repeat refill or wait for a top-up. Use the remaining water "
            "productively or choose other feasible work, and do not claim refill occurred. "
            "The manager's literal 'refill first' prerequisite needs correction.")
    else:
        status = (
            "FEASIBLE AND PENDING: the tank is empty. Refill at the real water source and "
            "verify that water increases before starting the downstream task.")
    return f"""

[DOMAIN-AWARE EXECUTION LEDGER — OBSERVATION, NOT PERMISSION]
Requested sequence: refill at {tuple(case['water_source'])}, then travel to {tuple(case['target'])}.
Authoritative environment state: position={tuple(case['position'])}, water={case['water']}.
Status: {status}
Override this reminder for a newer explicit cancellation/reassignment or an immediately
observed safety threat, and explain the evidence.
[/DOMAIN-AWARE EXECUTION LEDGER]
"""


def parse_action(response):
    match = ACTION_TAG.search(response or "")
    return match.group(1).strip() if match else None


def classify_action(response, water_source, target, radius=2):
    action = parse_action(response)
    if action is None:
        return "UNPARSEABLE"
    if "refill" in action.lower():
        return "REFILL"
    found = COORD.search(action)
    if not found:
        return "OTHER"
    point = tuple(float(value) for value in found.groups())
    distance = lambda coord: max(abs(point[0] - coord[0]), abs(point[1] - coord[1]))
    if distance(water_source) <= radius:
        return "MOVE_WATER_SOURCE"
    if distance(target) <= radius:
        return "MOVE_DOWNSTREAM_TARGET"
    return "MOVE_OTHER"


def cases_from_trace(chat_root, events_path):
    world = snapshots(events_path)
    specs = [
        # Four unique historical prerequisite violations.
        {"agent": "2", "step": 68, "assigned_step": 67, "target": (70.0, 70.0),
         "water_source": (8.0, 24.0), "status": "NOT_VERIFIED"},
        {"agent": "3", "step": 71, "assigned_step": 69, "target": (41.0, 59.0),
         "water_source": (8.0, 24.0), "status": "NOT_VERIFIED"},
        {"agent": "3", "step": 75, "assigned_step": 74, "target": (70.0, 70.0),
         "water_source": (8.0, 24.0), "status": "NOT_VERIFIED"},
        {"agent": "3", "step": 92, "assigned_step": 90, "target": (41.0, 59.0),
         "water_source": (8.0, 24.0), "status": "NOT_VERIFIED"},
        # Positive control: environment already shows full water before departure.
        {"agent": "3", "step": 32, "assigned_step": 31, "target": (41.0, 59.0),
         "water_source": (8.0, 24.0), "status": "VERIFIED"},
    ]
    cases = []
    for spec in specs:
        user, logged = extract_prompt(chat_root / f"Agent_{spec['agent']}" / "chats.txt",
                                      spec["step"])
        node = world[spec["step"]]["nodes"][spec["agent"]]
        case = {**spec, "position": tuple(node["position"]),
                "water": node["resources"]["water"],
                "prompt_sha256": hashlib.sha256(user.encode()).hexdigest(),
                "logged_response": logged,
                "logged_action": parse_action(logged),
                "logged_class": classify_action(logged, spec["water_source"], spec["target"]),
                "prompt": user}
        cases.append(case)
    return cases


def call_model(client, model, system, user):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        max_tokens=768,
        extra_body={"thinking": {"type": "disabled"}},
    )
    usage = response.usage
    return {"response_id": response.id, "finish_reason": response.choices[0].finish_reason,
            "text": response.choices[0].message.content or "",
            "usage": {"prompt_tokens": usage.prompt_tokens,
                      "completion_tokens": usage.completion_tokens}}


def run_experiment(chat_root, events_path, model, base_url, api_key, repeats=1):
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=1)
    cases = cases_from_trace(chat_root, events_path)
    for case in cases:
        system = (
            f"You are Agent {case['agent']}, an embodied agent in a cooperative multi-agent "
            "robotic task. You are in a 80 by 80 forest grid world that spans x:[0 to 80] "
            "and y:[0 to 80]. Your job is to choose your next best action given your task, "
            "observations, past actions and chat history."
        )
        baseline = [call_model(client, model, system, case["prompt"])
                    for _ in range(repeats)]
        ledger = [call_model(client, model, system, case["prompt"] + reminder(case))
                  for _ in range(repeats)]
        for result in baseline + ledger:
            result["action"] = parse_action(result["text"])
            result["class"] = classify_action(result["text"], case["water_source"], case["target"])
        del case["prompt"]
        case["ledger_reminder"] = reminder(case).strip()
        case["baseline_replays"] = baseline
        case["ledger_replays"] = ledger
    client.close()
    return {"scope": {"model": model, "temperature": 0, "case_count": len(cases),
                      "repeats_per_condition": repeats,
                      "ledger_condition": "naive literal negative control",
                      "environment_replay": False}, "cases": cases}


def extend_domain_aware(existing_path, chat_root, events_path, model, base_url, api_key):
    from openai import OpenAI
    result = json.loads(Path(existing_path).read_text())
    repeats = int(result["scope"]["repeats_per_condition"])
    frozen = {(case["agent"], case["step"]): case
              for case in cases_from_trace(chat_root, events_path)}
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=1)
    for stored in result["cases"]:
        case = frozen[(stored["agent"], stored["step"])]
        if case["prompt_sha256"] != stored["prompt_sha256"]:
            raise ValueError("frozen prompt hash changed")
        system = (
            f"You are Agent {case['agent']}, an embodied agent in a cooperative multi-agent "
            "robotic task. You are in a 80 by 80 forest grid world that spans x:[0 to 80] "
            "and y:[0 to 80]. Your job is to choose your next best action given your task, "
            "observations, past actions and chat history."
        )
        replays = [call_model(client, model, system,
                              case["prompt"] + domain_aware_reminder(case))
                   for _ in range(repeats)]
        for replay in replays:
            replay["action"] = parse_action(replay["text"])
            replay["class"] = classify_action(replay["text"], case["water_source"],
                                                case["target"])
        stored["naive_literal_reminder"] = stored.pop("ledger_reminder")
        stored["domain_aware_reminder"] = domain_aware_reminder(case).strip()
        stored["naive_literal_replays"] = stored.pop("ledger_replays")
        stored["domain_aware_replays"] = replays
    client.close()
    result["scope"]["conditions"] = ["baseline", "naive_literal_negative_control",
                                      "domain_aware"]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-root", type=Path, default=DEFAULT_CHAT_ROOT)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-api", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--extend-existing", type=Path)
    args = parser.parse_args()
    if args.run_api:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise SystemExit("DEEPSEEK_API_KEY is not set")
        if args.extend_existing:
            result = extend_domain_aware(args.extend_existing, args.chat_root, args.events,
                                         args.model, args.base_url, key)
        else:
            result = run_experiment(args.chat_root, args.events, args.model, args.base_url, key,
                                    repeats=args.repeats)
    else:
        cases = cases_from_trace(args.chat_root, args.events)
        for case in cases:
            del case["prompt"]
        result = {"scope": {"dry_run": True, "case_count": len(cases)}, "cases": cases}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
