"""Infrastructure audit, not an efficacy ranking or task-success assertion."""
import argparse
from collections import Counter
import json
from pathlib import Path


def audit(path):
    events = [json.loads(line) for line in Path(path).read_text().splitlines()]
    failures = []
    def require(condition, message):
        if not condition:
            failures.append(message)
    required = {"episode_id", "task_id", "task_seed", "arm", "agent_id", "session_epoch",
                "event_id", "state_version", "timestamp_monotonic", "event_type", "edge_id",
                "topology_version", "action_id", "message_id", "transaction_id", "payload",
                "input_tokens", "output_tokens"}
    require(bool(events), "empty ledger")
    require(all(required <= e.keys() for e in events), "incomplete event schema")
    require([e["event_id"] for e in events] == list(range(1, len(events) + 1)), "event ID sequence")
    for field in ("state_version", "timestamp_monotonic"):
        require(all(a[field] <= b[field] for a, b in zip(events, events[1:])), f"nonmonotonic {field}")
    counts = Counter(e["event_type"] for e in events)
    require(counts["RUN_STARTED"] == counts["RUN_FINISHED"] == 1, "missing/duplicate run boundaries")
    require(counts["ACTION_STARTED"] == counts["ACTION_COMPLETED"], "unresolved actions")
    started = [e["action_id"] for e in events if e["event_type"] == "ACTION_STARTED"]
    completed = [e["action_id"] for e in events if e["event_type"] == "ACTION_COMPLETED"]
    require(set(started) == set(completed) and len(set(started)) == len(started) == len(completed),
            "unmatched/duplicate action IDs")
    sends = {e["message_id"] for e in events if e["event_type"] == "MESSAGE_SENT"}
    outcomes = [e["message_id"] for e in events if e["event_type"] in {"MESSAGE_DELIVERED", "MESSAGE_FAILED"}]
    require(sends == set(outcomes) and len(outcomes) == len(sends), "unresolved or duplicate message outcome")
    overlap = False
    for event in events:
        if event["event_type"] != "TOPOLOGY_COMMITTED":
            continue
        topo = event["payload"]
        edges = {edge["id"]: edge for edge in topo["edges"]}
        memberships = Counter(a for edge in edges.values() for a in edge["members"])
        overlap |= any(n > 1 for n in memberships.values())
        require(set(topo["active"]) == set(memberships), "missing active assignment")
        require(all(e in edges and a in edges[e]["members"] for a, e in topo["active"].items()), "invalid active assignment")
        require(topo["based_on_state_version"] == event["state_version"], "stale committed topology")
    validated = [e for e in events if e["event_type"] == "TASK_VALIDATED"]
    require(bool(validated) and validated[-1]["payload"]["observation_phase"] in {"after_action", "episode_end"}, "missing final validator")
    usage = [e for e in events if e["event_type"] == "LLM_USAGE"]
    finishes = [e for e in events if e["event_type"] == "RUN_FINISHED"]
    if finishes:
        for token_field in ("input_tokens", "output_tokens"):
            require(sum(e[token_field] for e in usage) == finishes[-1]["payload"][token_field], f"incomplete {token_field} accounting")
    return dict(passed=not failures, failures=failures, events=len(events), counts=dict(counts),
                overlapping_membership_observed=overlap,
                final_validator=validated[-1]["payload"] if validated else None,
                full_usage=finishes[-1]["payload"] if finishes else None,
                unsupported_metrics=["natural_language_contradiction_rate", "causal_useful_message_rate",
                                     "physical_receiver_commit", "subtask_VMCR_without_contracts"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("events")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = audit(args.events)
    if args.output:
        destination = Path(args.output)
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
