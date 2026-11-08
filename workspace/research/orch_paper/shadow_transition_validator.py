#!/usr/bin/env python3
"""Classify historical transitions without changing or replaying actions.

The shadow validator is intentionally non-blocking.  It asks what evidence or
state preservation would have been required, and exposes overlap between rules.
It does not claim that a flagged historical decision would have produced a
better score if changed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def official_labels(transition):
    labels = []
    if transition.get("out_of_domain_new_phases"):
        labels.append("FILTER_UNSUPPORTED_GENERATED_PHASES")
    if transition.get("out_of_domain_to_phase"):
        labels.append("REJECT_UNSUPPORTED_ACTIVE_PHASE")
    percent = transition.get("reported_phase_percent")
    decision = transition.get("status_decision")
    if decision == "ADD_PHASES" and isinstance(percent, (int, float)) and percent < 100:
        labels.append("PRESERVE_CURRENT_AND_INSERT_INTERRUPT")
    elif decision == "NEXT_PHASE" and isinstance(percent, (int, float)) and percent < 100:
        labels.append("REQUEST_COMPLETION_EVIDENCE")
    if not labels:
        labels.append("PASS_WITH_EXISTING_EVIDENCE")
    return labels


def local_labels(case):
    premature = bool(case.get("premature_downstream_action_steps"))
    verified = bool(case.get("downstream_action_after_refill_steps"))
    if premature and verified:
        return ["PREREQUISITE_VIOLATION_THEN_RECOVERED"]
    if premature:
        return ["PREREQUISITE_VIOLATION"]
    if verified:
        return ["VERIFIED_PREREQUISITE_SEQUENCE"]
    return ["PENDING_OR_UNOBSERVED_SEQUENCE"]


def interrupt(state, new_task):
    """Pause the active task and run an explicit interrupt immediately."""
    updated = {key: list(value) if isinstance(value, list) else value
               for key, value in state.items()}
    if updated.get("active") is not None:
        updated.setdefault("suspended", []).append(updated["active"])
    updated["active"] = new_task
    return updated


def complete_active(state):
    """Resume the most recently suspended task before planned future work."""
    updated = {key: list(value) if isinstance(value, list) else value
               for key, value in state.items()}
    if updated.get("suspended"):
        updated["active"] = updated["suspended"].pop()
    elif updated.get("future"):
        updated["active"] = updated["future"].pop(0)
    else:
        updated["active"] = None
    return updated


def analyze(official_path, local_path):
    official = json.loads(Path(official_path).read_text())
    local = json.loads(Path(local_path).read_text())
    official_cases = []
    official_counts = Counter()
    official_combinations = Counter()
    evidence_counts = Counter()
    for run in official["runs"]:
        for transition in run["transitions"]:
            labels = official_labels(transition)
            for label in labels:
                official_counts[label] += 1
            official_combinations[" + ".join(labels)] += 1
            if "REQUEST_COMPLETION_EVIDENCE" in labels:
                evidence_counts["with_objective_counter_progress" if
                                transition.get("any_objective_counter_increase") else
                                "without_objective_counter_progress"] += 1
            official_cases.append({
                "run": run["metadata"].get("run"), "task": run["metadata"].get("task"),
                "agent": transition.get("agent"), "step": transition.get("step"),
                "from_phase": transition.get("from_phase"),
                "to_phase": transition.get("to_phase"), "labels": labels,
            })

    local_cases = []
    local_counts = Counter()
    local_combinations = Counter()
    for run_path, run in local["runs"].items():
        for case in run["cases"]:
            labels = local_labels(case)
            for label in labels:
                local_counts[label] += 1
            local_combinations[" + ".join(labels)] += 1
            local_cases.append({"run": run_path, "event_id": case.get("event_id"),
                                "step": case.get("step"), "agent": case.get("agent"),
                                "labels": labels})

    initial = {"active": "A_unfinished", "future": ["B_planned"], "suspended": []}
    interrupted = interrupt(initial, "X_new_interrupt")
    resumed = complete_active(interrupted)
    return {
        "scope": {"official_transition_count": len(official_cases),
                  "local_explicit_sequence_count": len(local_cases)},
        "official_shadow_summary": dict(official_counts),
        "official_label_combinations": dict(official_combinations),
        "completion_evidence_request_context": dict(evidence_counts),
        "local_shadow_summary": dict(local_counts),
        "local_label_combinations": dict(local_combinations),
        "recoverable_interrupt_calibration": {
            "initial": initial, "after_interrupt": interrupted,
            "after_interrupt_completion": resumed,
        },
        "interpretation_boundary": (
            "Labels are retrospective review requirements, not proof that blocking "
            "the historical decision would improve task score."),
        "official_cases": official_cases,
        "local_cases": local_cases,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--official", required=True)
    parser.add_argument("--local", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze(args.official, args.local)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
