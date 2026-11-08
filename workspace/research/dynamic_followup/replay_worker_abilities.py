"""Paired control-only input ablation; never send actions or edit a live run."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ORCH/crew-algorithms"))
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph
from crew_algorithms.wildfire_alg.coordination.soft_task_policy import SoftTaskPolicy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("events", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    prefix = []
    for line in args.events.open():
        event = json.loads(line)
        prefix.append(event)
        if event["event_type"] == "TASK_ORGANIZER_REQUEST":
            break
    request = prefix[-1]
    if request["event_type"] != "TASK_ORGANIZER_REQUEST":
        raise ValueError("no recorded organizer request")
    snapshot = next(e for e in reversed(prefix) if e["event_type"] == "TASK_WORLD_SNAPSHOT")
    recorded = json.loads(request["payload"]["messages"][-1]["content"])
    world = {**snapshot["payload"], "evidence_id": snapshot["event_id"]}
    key = json.loads(Path("/data/gzy/MAS/mindcraft/keys.json").read_text())["DEEPSEEK_API_KEY"]
    manifest = {"source_events": str(args.events.resolve()), "snapshot_event": snapshot["event_id"],
                "request_event": request["event_id"], "repeats": args.repeats,
                "source_request_sha256": hashlib.sha256(json.dumps(recorded, sort_keys=True).encode()).hexdigest(),
                "qualification": "same recorded input, new model samples; control-only replay; no physical outcome",
                "only_input_difference": "candidate adds worker_abilities from recorded world"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    summary = []
    for repeat in range(args.repeats):
        for variant in ("baseline", "with_worker_abilities"):
            emitted = []

            def emit(kind, payload):
                event = {"event_id": len(emitted) + 1, "event_type": kind, "payload": payload}
                emitted.append(event)
                return event

            graph = SoftTaskGraph(emit)
            graph.observe(deepcopy(world))
            state = deepcopy(recorded)
            if variant == "with_worker_abilities":
                state["worker_abilities"] = deepcopy(world["worker_abilities"])
                assert {k: v for k, v in state.items() if k != "worker_abilities"} == recorded
            # Preserve the exact old request rather than rebuilding with newer code.
            graph.decision_state = lambda: deepcopy(state)
            policy = SoftTaskPolicy("deepseek-chat", "https://api.deepseek.com", key, emit)
            usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
            error = None
            try:
                accepted = policy.decide(graph, usage)
            except Exception as exc:
                accepted = False
                error = type(exc).__name__
            finally:
                policy.close()
            row = {"repeat": repeat, "variant": variant, "accepted": accepted,
                   "error": error, "usage": usage, "edges": list(graph.edges.values()),
                   "events": emitted}
            (args.output / f"{repeat}_{variant}.json").write_text(json.dumps(row, indent=2, ensure_ascii=False))
            summary.append({k: v for k, v in row.items() if k != "events"})
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
            print(json.dumps({k: v for k, v in row.items() if k not in ("events", "edges")}), flush=True)


if __name__ == "__main__":
    main()
