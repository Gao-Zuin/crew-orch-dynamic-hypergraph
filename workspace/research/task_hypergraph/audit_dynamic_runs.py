"""Read existing events only; never start Unity or call a model."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_task_hypergraph import audit


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def signature(edges, active):
    return (sorted((e["id"], sorted(e["members"]), e["leader"]) for e in edges), active)


def inspect(run):
    path = run / "run/events.jsonl"
    events = [json.loads(line) for line in path.open()]
    counts = Counter(e["event_type"] for e in events)
    start = next(e["payload"] for e in events if e["event_type"] == "TASK_HYPERGRAPH_STARTED")
    world, previous, previous_active = None, {}, {}
    commits, states, actions, communication = [], [], [], []
    for event in events:
        kind, payload = event["event_type"], event["payload"]
        if kind == "TASK_WORLD_SNAPSHOT":
            world = payload
            if world["phase"] == "after_action":
                for agent, node in world["nodes"].items():
                    states.append({"step": world["step"], "event_id": event["event_id"],
                                   "agent": agent, "position": node.get("position"),
                                   "water": node.get("resources", {}).get("water"),
                                   "rewards": world["rewards"]})
        elif kind == "TASK_GRAPH_COMMITTED":
            edges = {e["id"]: e for e in payload["edges"]}
            active = payload["proposal"]["active"]
            fields = []
            for eid in sorted(previous.keys() | edges.keys()):
                if eid not in previous:
                    fields.append(eid + ":created")
                elif eid not in edges:
                    fields.append(eid + ":removed")
                else:
                    fields.extend(eid + ":" + field for field in
                                  ("members", "leader", "goal", "tasks", "advice", "stage", "checks", "rules", "depends_on", "context", "communication")
                                  if previous[eid].get(field) != edges[eid].get(field))
            if previous_active != active:
                fields.append("active")
            commits.append({"step": world["step"], "phase": world["phase"],
                            "event_id": event["event_id"], "version": payload["version"],
                            "initial": not bool(previous),
                            "topology_changed": bool(previous) and signature(list(previous.values()), previous_active) != signature(list(edges.values()), active),
                            "fields_changed": fields, "edges": list(edges.values()),
                            "active": active, "reason": payload["proposal"].get("reason"),
                            "manual": bool(payload.get("manual_regroup"))})
            previous, previous_active = edges, active
        elif kind == "ACTION_STARTED":
            actions.append({"step": world["step"], "event_id": event["event_id"],
                            "agent": event["agent_id"], "action": payload["action"]})
        elif kind == "COMMUNICATION_GENERATED":
            communication.append({"step": world["step"], "event_id": event["event_id"],
                                  "agent": event["agent_id"], "text": payload["raw_output"]})
    last = next((e["payload"] for e in reversed(events) if e["event_type"] == "TASK_VALIDATED"), {})
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    summary = {"run": run.name, "profile": start.get("context_profile", "legacy"),
               "fixed": start.get("fixed_groups", False),
               "level": events[0]["task_id"], "seed": events[0]["task_seed"],
               "requested_steps": manifest.get("max_steps"),
               "completed_steps": sum(e["event_type"] == "TASK_WORLD_SNAPSHOT" and e["payload"]["phase"] == "after_action" for e in events),
               "finished": bool(counts["RUN_FINISHED"]), "commits": len(commits),
               "topology_changes_after_initial": sum(c["topology_changed"] for c in commits),
               "identical_field_commits_after_initial": sum(not c["initial"] and not c["fields_changed"] for c in commits),
               "action_boundaries": counts["ACTION_STARTED"], "authorized": counts["TASK_ACTION_AUTHORIZED"],
               "held": counts["TASK_ACTION_HELD"], "rejections": counts["TASK_PROPOSAL_REJECTED"],
               "last_success": last.get("success"), "last_rewards": last.get("rewards"),
               "last_fire_active": last.get("fire_active"),
               "events_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return summary, {"commits": commits, "states": states, "actions": actions,
                     "communication": communication, "event_counts": dict(counts)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory, attempts_without_events = [], []
    replay_dirs = []
    for run in sorted((ROOT / "benchmark_runs").iterdir()):
        if not run.is_dir() or not run.name.startswith(("task_hypergraph_", "fixed_group_")):
            continue
        if "replay" in run.name:
            replay_dirs.append(run.name)
        path = run / "run/events.jsonl"
        if not path.exists():
            if (run / "manifest.json").exists():
                attempts_without_events.append(run.name)
            continue
        summary, detail = inspect(run)
        inventory.append(summary)
        if summary["finished"]:
            if summary["profile"] in {"task_hypergraph_soft_v1", "task_hypergraph_reports_v2"}:
                result = audit(path)
            else:
                sys.path.insert(0, str(ROOT / "research"))
                from legacy_full_task_graph.audit import audit as audit_legacy
                result = audit_legacy(path)
            summary["current_audit_passed"] = result["passed"]
            (args.output / (run.name + ".audit.json")).write_text(json.dumps(result, indent=2))
        else:
            summary["current_audit_passed"] = None
        if run.name == "task_hypergraph_second_fire_soft_full_seed42_v1":
            (args.output / "long_run_detail.json").write_text(json.dumps(detail, indent=2, ensure_ascii=False))
            write_csv(args.output / "long_run_commits.csv", detail["commits"])
            write_csv(args.output / "long_run_actions.csv", detail["actions"])
            write_csv(args.output / "long_run_states.csv", detail["states"])
            worker_summary = []
            for agent in map(str, range(1, 9)):
                actions = [a for a in detail["actions"] if a["agent"] == agent and a["step"] >= 29]
                states = [s for s in detail["states"] if s["agent"] == agent and s["step"] >= 29]
                nearest = min(states, key=lambda s: math.dist(s["position"], [70, 70]))
                worker_summary.append({"agent": agent, "post_split_action_counts": dict(Counter(a["action"][0] for a in actions)),
                                       "closest_second_fire": nearest,
                                       "closest_distance": math.dist(nearest["position"], [70, 70])})
            (args.output / "long_run_workers.json").write_text(json.dumps(worker_summary, indent=2))
    write_csv(args.output / "inventory.csv", inventory)
    (args.output / "inventory.json").write_text(json.dumps({"runs": inventory,
        "attempts_without_events": attempts_without_events, "control_replay_directories": replay_dirs}, indent=2))
    print(json.dumps({"event_runs": len(inventory), "finished_runs": sum(r["finished"] for r in inventory),
                      "current_audit_failures": [r["run"] for r in inventory if r["current_audit_passed"] is False],
                      "control_replay_directories": len(replay_dirs),
                      "attempts_without_events": attempts_without_events}, ensure_ascii=False))


if __name__ == "__main__":
    main()
