"""Descriptive task and collaboration metrics for one soft HT trajectory."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

from fixed_group_timeline import extract, write_csv, draw

REWARD_NAMES = ["exploration", "trees_burned", "trees_cut", "fire_extinguished",
                "correct_trees_cut", "civilians_rescued", "firefighters_transported",
                "civilians_scouted", "fire_scouted_concurrent", "water_scouted",
                "agents_destroyed", "civilians_destroyed", "buildings_destroyed"]


def summarize(events_path, status_path):
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    rows, messages, regroup_steps = extract(events_path)
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    counts = Counter(event["event_type"] for event in events)
    silent_generated = []
    for index, event in enumerate(events):
        if event["event_type"] != "COMMUNICATION_GENERATED":
            continue
        following = []
        next_index = index + 1
        while next_index < len(events) and events[next_index]["event_type"] in (
                "TASK_MESSAGE_DELIVERED", "TASK_MESSAGE_SUPPRESSED"):
            following.append(events[next_index])
            next_index += 1
        if not following:
            silent_generated.append({"event_id": event["event_id"],
                                     "agent": event.get("agent_id"),
                                     "step": event["payload"].get("timestep")})
    commits = []
    snapshots = []
    step_usage = []
    current_step = None
    for event in events:
        kind, payload = event["event_type"], event["payload"]
        if kind == "TASK_WORLD_SNAPSHOT":
            current_step = payload["step"]
            if payload["phase"] in ("before_action", "after_action"):
                snapshots.append({"step": current_step, "phase": payload["phase"],
                                  "event_id": event["event_id"],
                                  "rewards": payload["rewards"],
                                  "fire_active": payload.get("fire_active"),
                                  "announcements": payload.get("event_commands_and_announcements", [])})
        elif kind == "TASK_GRAPH_COMMITTED":
            edges = payload["edges"]
            commits.append({"event_id": event["event_id"], "step": current_step,
                            "version": payload["version"], "group_count": len(edges),
                            "members": {edge["id"]: sorted(edge["members"]) for edge in edges},
                            "leaders": {edge["id"]: edge["leader"] for edge in edges},
                            "goals": {edge["id"]: edge["goal"] for edge in edges},
                            "active": payload["proposal"]["active"],
                            "manual_regroup": payload.get("manual_regroup", False),
                            "attrition": payload.get("attrition", False)})
        elif kind == "LLM_USAGE":
            step_usage.append({"step": payload.get("timestep"),
                               "input_tokens": event.get("input_tokens", 0),
                               "output_tokens": event.get("output_tokens", 0),
                               "cumulative_api_calls": payload.get("cumulative_api_calls")})
    changes = []
    for old, new in zip(commits, commits[1:]):
        membership_changed = sorted(eid for eid in set(old["members"]) | set(new["members"])
                                    if old["members"].get(eid) != new["members"].get(eid))
        active_switched = sorted(a for a in set(old["active"]) | set(new["active"])
                                if old["active"].get(a) != new["active"].get(a))
        leader_changed = sorted(eid for eid in set(old["leaders"]) | set(new["leaders"])
                                if old["leaders"].get(eid) != new["leaders"].get(eid))
        goal_changed = sorted(eid for eid in set(old["goals"]) | set(new["goals"])
                              if old["goals"].get(eid) != new["goals"].get(eid))
        changes.append({"from_version": old["version"], "to_version": new["version"],
                        "step": new["step"], "event_id": new["event_id"],
                        "membership_changed_groups": membership_changed,
                        "active_switched_agents": active_switched,
                        "leader_changed_groups": leader_changed,
                        "goal_changed_groups": goal_changed})
    after = [s for s in snapshots if s["phase"] == "after_action"]
    initial = next((s for s in snapshots if s["phase"] == "before_action"), None)
    final = after[-1] if after else None
    reward_delta = ({name: final["rewards"][i] - initial["rewards"][i]
                     for i, name in enumerate(REWARD_NAMES)} if initial and final else {})
    per_step = []
    prior = initial
    for snapshot in after:
        step_rows = [r for r in rows if r["step"] == snapshot["step"]]
        step_messages = [m for m in messages if m["step"] == snapshot["step"]]
        delta = ({name: snapshot["rewards"][i] - prior["rewards"][i]
                  for i, name in enumerate(REWARD_NAMES)} if prior else {})
        per_step.append({"step": snapshot["step"], "world_event_id": snapshot["event_id"],
                         "fire_active": snapshot["fire_active"],
                         "world_delta": delta,
                         "actions": len(step_rows),
                         "local_change_actions": sum(r["result"] == "local_change" for r in step_rows),
                         "no_local_change_actions": sum(r["result"] == "no_local_change" for r in step_rows),
                         "held_actions": sum(bool(r["held"]) for r in step_rows),
                         "recipient_deliveries": len(step_messages),
                         "cross_group_deliveries": sum(m["source"] != m["target"] for m in step_messages)})
        prior = snapshot
    per_agent = defaultdict(lambda: Counter())
    for row in rows:
        agent = row["agent"]
        per_agent[agent]["actions"] += 1
        per_agent[agent][row["result"]] += 1
        per_agent[agent]["held"] += int(bool(row["held"]))
    for message in messages:
        per_agent[message["sender"]]["messages_sent_to_recipients"] += 1
        per_agent[message["recipient"]]["messages_received"] += 1
    return {"status": status, "event_counts": dict(counts),
            "initial_world": initial, "final_world": final,
            "reward_delta": reward_delta,
            "collaboration": {"graph_commits": len(commits),
                              "membership_change_commits": sum(bool(c["membership_changed_groups"]) for c in changes),
                              "active_assignment_switches": sum(len(c["active_switched_agents"]) for c in changes),
                              "leader_change_commits": sum(bool(c["leader_changed_groups"]) for c in changes),
                              "recipient_deliveries": len(messages),
                              "cross_group_deliveries": sum(m["source"] != m["target"] for m in messages),
                              "messages_suppressed": counts["TASK_MESSAGE_SUPPRESSED"],
                              "messages_generated": counts["COMMUNICATION_GENERATED"],
                              "generated_without_delivery_or_suppression": len(silent_generated),
                              "actions": len(rows),
                              "held_actions": sum(bool(r["held"]) for r in rows),
                              "no_local_change_actions": sum(r["result"] == "no_local_change" for r in rows)},
            "per_agent": {a: dict(c) for a, c in sorted(per_agent.items(), key=lambda x: int(x[0]))},
            "commits": commits, "changes": changes, "silent_generated": silent_generated,
            "per_step": per_step,
            "step_usage": step_usage, "regroup_steps": regroup_steps}, rows, messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    out = args.case / "analysis"
    out.mkdir(exist_ok=True)
    summary, rows, messages = summarize(args.case / "run/events.jsonl", args.case / "status.json")
    (out / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (out / "messages.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2))
    write_csv(out / "actions.csv", rows)
    draw(out / "timeline.png", rows, summary["regroup_steps"])
    with (out / "step_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["step", "world_event_id", "fire_active",
                  "world_delta", "actions", "local_change_actions", "no_local_change_actions",
                  "held_actions", "recipient_deliveries", "cross_group_deliveries"])
        writer.writeheader()
        for item in summary["per_step"]:
            writer.writerow({**item, "world_delta": json.dumps(item["world_delta"])})
    print(json.dumps({"case": str(args.case), "steps": len(summary["per_step"]),
                      "reward_delta": summary["reward_delta"],
                      "collaboration": summary["collaboration"],
                      "usage": summary["status"].get("usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
