#!/usr/bin/env python3
"""Frozen-prompt A/B for versioned target responsibility reminders.

Two negative cases contain a real tree in the current cell but no current
authority to cut it.  One positive case is a legitimate, explicitly assigned
cross-edge takeover.  This is a prompt counterfactual, not an environment replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "orch_paper"))
from run_commitment_prompt_ab import ACTION_BLOCK, call_model, parse_action


R3_ROOT = Path(
    "/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/workspace/ORCH/"
    "crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/"
    "deepseek-flash/Cut_Trees_Sparse_large/42/2026-11-02-21-02-12"
)
R2_ROOT = Path(
    "/data1/gzy/crew_bottom_up_20261029_attrition_fix/workspace/ORCH/"
    "crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/"
    "deepseek-flash/Cut_Trees_Sparse_large/42/2026-10-29-16-18-09"
)


CASE_SPECS = [
    {
        "id": "r3_stale_message_overridden_by_graph",
        "root": R3_ROOT, "agent": "2", "step": 7, "target": (19, 37),
        "expected": "AVOID_CUT",
        "status": "STALE_CONFLICT",
        "ledger": (
            "Graph version 2 is newer than the step-4 message that assigned (19,37) to you. "
            "The current owner of (19,37) is Agent 6 in cut-team-b. Your current targets are "
            "(14,42), (17,43), (16,34), and (21,43). Do not cut the current cell at (19,37); "
            "choose feasible work on a current target."
        ),
    },
    {
        "id": "r3_explicit_provisional_takeover",
        "root": R3_ROOT, "agent": "8", "step": 2, "target": (28, 24),
        "expected": "CUT",
        "status": "PROVISIONAL_ALLOWED",
        "ledger": (
            "Your current leader Agent 6 explicitly assigned (28,24) to you at step 1 and "
            "reaffirmed it at step 2. The older graph owner in another edge has not yet issued "
            "a structured release, so ratification remains pending, but this is an active "
            "provisional takeover, not a prohibition. You may continue cutting the current cell "
            "and should report verified completion."
        ),
    },
    {
        "id": "r2_unassigned_actor_against_owner",
        "root": R2_ROOT, "agent": "8", "step": 15, "target": (26, 44),
        "expected": "AVOID_CUT",
        "status": "UNAUTHORIZED_CONFLICT",
        "ledger": (
            "The current graph owner of (26,44) is Agent 10. A separate provisional claim names "
            "Agent 6. No current graph or leader event assigns or releases this target to you, "
            "Agent 8. Do not cut the current cell at (26,44); choose feasible non-conflicting work."
        ),
    },
]


def prompt_for_step(chat_path, step):
    """Select an action block by its current advisory/world step."""
    matches = []
    for index, (user, assistant) in enumerate(
            ACTION_BLOCK.findall(Path(chat_path).read_text(encoding="utf-8"))):
        steps = [int(value) for value in re.findall(r'"step"\s*:\s*(\d+)', user)]
        if steps and steps[-1] == int(step):
            matches.append((index, user, assistant))
    # Repeated historical message steps can occur, but the last JSON step in the
    # prompt is the current advisory step.  There should be one such action block.
    if len(matches) != 1:
        raise ValueError(f"expected one prompt for step {step}, found {len(matches)}")
    return matches[0]


def classify(response):
    action = parse_action(response)
    if action is None:
        return "UNPARSEABLE"
    if re.search(r"\bcut\b", action, re.I):
        return "CUT"
    return "AVOID_CUT"


def reminder(case):
    return f"""

[VERSIONED RESPONSIBILITY LEDGER — SHADOW CONSISTENCY CHECK]
Target: {tuple(case['target'])}
Status: {case['status']}
{case['ledger']}
Precedence: verified environment completion > newer graph/leader event > older assignment.
This ledger does not forbid helping another group: a current explicit provisional takeover may
proceed. If responsibility is stale or conflicting and you are not the assignee, avoid modifying
that target until a release or ratification is observed.
[/VERSIONED RESPONSIBILITY LEDGER]
"""


def frozen_cases():
    result = []
    for spec in CASE_SPECS:
        index, user, logged = prompt_for_step(
            spec["root"] / f"Agent_{spec['agent']}" / "chats.txt", spec["step"])
        result.append({
            **{key: value for key, value in spec.items() if key != "root"},
            "chat_root": str(spec["root"]),
            "block_index": index,
            "prompt_sha256": hashlib.sha256(user.encode()).hexdigest(),
            "logged_action": parse_action(logged),
            "logged_class": classify(logged),
            "prompt": user,
        })
    return result


def run(model, base_url, api_key, repeats):
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180, max_retries=1)
    cases = frozen_cases()
    for case in cases:
        system = (
            f"You are Agent {case['agent']}, an embodied agent in a cooperative multi-agent "
            "robotic task. Choose exactly one next action using the required output format."
        )
        baseline = [call_model(client, model, system, case["prompt"])
                    for _ in range(repeats)]
        ledger = [call_model(client, model, system, case["prompt"] + reminder(case))
                  for _ in range(repeats)]
        for item in baseline + ledger:
            item["action"] = parse_action(item["text"])
            item["class"] = classify(item["text"])
            item["matches_expected"] = item["class"] == case["expected"]
        del case["prompt"]
        case["ledger_reminder"] = reminder(case).strip()
        case["baseline_replays"] = baseline
        case["ledger_replays"] = ledger
    client.close()
    return {
        "scope": {
            "model": model, "temperature": 0, "case_count": len(cases),
            "repeats_per_condition": repeats, "environment_replay": False,
            "purpose": "distinguish stale/conflicting ownership from valid provisional takeover",
        },
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--run-api", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.run_api:
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise SystemExit("DEEPSEEK_API_KEY is not set")
        result = run(args.model, args.base_url, key, args.repeats)
    else:
        cases = frozen_cases()
        for case in cases:
            del case["prompt"]
            case["ledger_reminder"] = reminder(case).strip()
        result = {"scope": {"dry_run": True, "case_count": len(cases)}, "cases": cases}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
