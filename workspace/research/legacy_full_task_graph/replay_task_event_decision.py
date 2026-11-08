"""Re-run one HT organization decision on a recorded real Unity world snapshot.

This is a control-plane diagnostic, not an environment episode or benchmark.
No physical actions are submitted. The original event stream is never edited.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
from legacy_full_task_graph.task_hypergraph import TaskHypergraph
from legacy_full_task_graph.task_policy import LLMTaskPolicy


def write_new(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_events", type=Path)
    parser.add_argument("world_event_id", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--key-file", type=Path, default=Path("/data/gzy/MAS/mindcraft/keys.json"))
    args = parser.parse_args()
    source = args.source_events.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    events = [json.loads(line) for line in source.read_text().splitlines()]
    target = next(e for e in events if e["event_id"] == args.world_event_id)
    if target["event_type"] != "TASK_WORLD_SNAPSHOT":
        raise ValueError("target must be a TASK_WORLD_SNAPSHOT")
    generated = []
    next_id = max(e["event_id"] for e in events) + 1
    def emit(kind, payload):
        nonlocal next_id
        record = {"event_id": next_id, "event_type": kind, "payload": deepcopy(payload)}
        next_id += 1
        generated.append(record)
        return record
    graph = TaskHypergraph(lambda kind, payload: {"event_id": 0}, require_event_ack=False)
    for event in events:
        if event["event_id"] > args.world_event_id:
            break
        kind, payload = event["event_type"], event["payload"]
        if kind == "TASK_HYPERGRAPH_STARTED":
            profile = payload.get("context_profile")
            graph.enforce_ongoing_fire_owners = profile in {"task_hypergraph_v3", "task_hypergraph_v4"}
            graph.enforce_distinct_links = profile in {"task_hypergraph_v3", "task_hypergraph_v4"}
            graph.enforce_exact_description = profile == "task_hypergraph_v4"
        elif kind == "TASK_WORLD_SNAPSHOT":
            graph.observe({**deepcopy(payload), "evidence_id": event["event_id"]})
        elif kind == "TASK_GRAPH_COMMITTED":
            graph.apply(deepcopy(payload["proposal"]))
        elif kind == "TASK_ORGANIZATION_HOLD":
            graph.blocked.update(graph.edges)
        elif kind == "TASK_MESSAGE_DELIVERED":
            graph.messages.append({"event_id": event["event_id"],
                                   **{key: payload[key] for key in
                                      ("sender", "recipient", "source", "target", "content")}})
    graph.require_event_ack = True
    graph.enforce_ongoing_fire_owners = True
    graph.enforce_distinct_links = True
    graph.enforce_exact_description = True
    # The recorded v1 world omitted this existing validator rule. Enrich the
    # replay input from CREW's unchanged check_game_done semantics.
    game_type = graph.world.get("mission_rules", {}).get("game_type")
    if game_type in (3, 5):
        graph.world.setdefault("mission_rules", {})["validator_success_rule"] = (
            "after a fire has begun (reward[1] > 0), fire_active=false globally: all active fires are gone")
    graph.emit = emit
    manifest = {"kind": "recorded_world_control_plane_replay", "source": str(source),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "world_event_id": args.world_event_id,
                "unacknowledged_events": graph.unacknowledged_events(),
                "source_graph_version": graph.version, "model": "deepseek-chat", "temperature": 0,
                "physical_actions_submitted": False}
    write_new(output / "manifest.json", manifest)
    key = json.loads(args.key_file.read_text())["DEEPSEEK_API_KEY"]
    usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
    policy = LLMTaskPolicy("deepseek-chat", "https://api.deepseek.com", key, emit)
    try:
        accepted = policy.decide(graph, usage)
    finally:
        policy.close()
    with (output / "decision_events.jsonl").open("x") as stream:
        for event in generated:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    status = {"accepted": accepted, "usage": usage, "graph_version": graph.version,
              "edges": list(graph.edges.values()), "event_responses": graph.event_instructions,
              "proposal_rejections": [e["payload"]["reason"] for e in generated
                                      if e["event_type"] == "TASK_PROPOSAL_REJECTED"]}
    write_new(output / "status.json", status)
    print(json.dumps({"accepted": accepted, "graph_version": graph.version,
                      "api_calls": usage["api_calls"], "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
