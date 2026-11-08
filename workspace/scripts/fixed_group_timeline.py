"""Build an evidence-linked action table and timeline from one HT event stream."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def extract(path):
    events = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    snapshots = {}
    rows = {}
    messages = []
    graph = {}
    active = {}
    held = {}
    current_step = None
    regroup_steps = []
    for event in events:
        kind, payload = event["event_type"], event["payload"]
        agent = event.get("agent_id")
        if kind == "TASK_WORLD_SNAPSHOT":
            current_step = payload["step"]
            snapshots[(current_step, payload["phase"])] = payload
        elif kind == "TASK_GRAPH_COMMITTED":
            graph = {edge["id"]: edge for edge in payload["edges"]}
            active = payload["proposal"]["active"].copy()
        elif kind == "TASK_MANUAL_REGROUP_APPLIED":
            regroup_steps.append(payload["step"])
        elif kind == "TASK_MESSAGE_DELIVERED":
            messages.append({"step": current_step, "event_id": event["event_id"],
                             **{k: payload.get(k) for k in ("sender", "recipient", "source", "target", "content")}})
        elif kind == "ACTION_STARTED":
            step = payload["timestep"]
            eid = active.get(agent)
            edge = graph.get(eid, {})
            rows[(step, agent)] = {"step": step, "agent": agent, "group": eid,
                                   "goal": edge.get("goal"),
                                   "subgoal": edge.get("tasks", {}).get(agent, ""),
                                   "action": payload["action"],
                                   "start_event": event["event_id"], "result_event": None,
                                   "held": (step, agent) in held,
                                   "hold_reason": held.get((step, agent)),
                                   "local_delta": {}, "result": "unknown"}
        elif kind == "TASK_ACTION_HELD":
            held[(current_step, agent)] = payload.get("reason")
            row = rows.get((current_step, agent))
            if row:
                row["held"] = True
                row["hold_reason"] = payload.get("reason")
        elif kind == "ACTION_COMPLETED":
            row = rows.get((current_step, agent))
            if row:
                row["result_event"] = event["event_id"]
                row["local_delta"] = payload.get("verified_local_delta", {})
                row["result"] = "local_change" if row["local_delta"] else "no_local_change"
    for (step, agent), row in rows.items():
        before = snapshots.get((step, "before_action"), {}).get("nodes", {}).get(agent, {})
        after = snapshots.get((step, "after_action"), {}).get("nodes", {}).get(agent, {})
        row["resources_before"] = before.get("resources", {})
        row["resources_after"] = after.get("resources", {})
        row["position_before"] = before.get("position")
        row["position_after"] = after.get("position")
        row["world_rewards_before"] = snapshots.get((step, "before_action"), {}).get("rewards")
        row["world_rewards_after"] = snapshots.get((step, "after_action"), {}).get("rewards")
    return sorted(rows.values(), key=lambda row: (row["step"], int(row["agent"]))), messages, regroup_steps


def write_csv(path, rows):
    fields = ("step", "agent", "group", "goal", "subgoal", "action", "result", "held",
              "hold_reason", "position_before", "position_after", "resources_before",
              "resources_after", "world_rewards_before", "world_rewards_after",
              "start_event", "result_event", "local_delta")
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})


def draw(path, rows, regroup_steps):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    agents = sorted({row["agent"] for row in rows}, key=int)
    assignments = sorted({(row["group"], row["goal"]) for row in rows if row["group"]})
    cmap = plt.get_cmap("tab20")
    color = {assignment: cmap(index % 20) for index, assignment in enumerate(assignments)}
    figure, axis = plt.subplots(figsize=(max(10, max((r["step"] for r in rows), default=0) * .32),
                                         max(3, len(agents) * .42)))
    for row in rows:
        y = agents.index(row["agent"])
        axis.broken_barh([(row["step"], .9)], (y - .35, .7),
                         facecolors=color.get((row["group"], row["goal"]), "#aaaaaa"))
        if row["held"]:
            axis.plot(row["step"] + .45, y, "x", color="black", markersize=7)
        elif row["result"] == "no_local_change":
            axis.plot(row["step"] + .45, y, "o", markerfacecolor="none",
                      markeredgecolor="black", markersize=5)
    for step in regroup_steps:
        axis.axvline(step, color="red", linewidth=1.5, linestyle="--")
    axis.set_yticks(range(len(agents)), [f"agent {a}" for a in agents])
    axis.set_xlabel("Environment decision step")
    axis.set_ylabel("Agent")
    axis.set_title("Subgoal timeline; x = held, circle = no observed local change")
    axis.set_xlim(0, max((r["step"] for r in rows), default=0) + 1)
    axis.invert_yaxis()
    from matplotlib.patches import Patch
    axis.legend(handles=[Patch(color=color[key], label=f"{key[0]}: {(key[1] or '')[:40]}")
                         for key in assignments],
                loc="upper left", bbox_to_anchor=(1, 1))
    figure.tight_layout()
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("events", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, messages, regroup_steps = extract(args.events)
    initial_plan = next((json.loads(line)["payload"]["proposal"]
                         for line in args.events.read_text().splitlines()
                         if json.loads(line)["event_type"] == "TASK_GRAPH_COMMITTED"), None)
    if initial_plan is not None:
        (args.output / "initial_plan.json").write_text(
            json.dumps(initial_plan, ensure_ascii=False, indent=2))
    write_csv(args.output / "actions.csv", rows)
    (args.output / "messages.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2))
    draw(args.output / "timeline.png", rows, regroup_steps)
    print(json.dumps({"action_rows": len(rows), "delivered_messages": len(messages),
                      "regroup_steps": regroup_steps}))


if __name__ == "__main__":
    main()
