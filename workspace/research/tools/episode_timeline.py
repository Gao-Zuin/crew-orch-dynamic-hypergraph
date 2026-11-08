"""Read-only event-to-timeline inspector; not a replacement metric/evaluator.

Only a truncated final JSONL line may be skipped for a live ledger. Output is
stdout by default; --output creates a new file and never overwrites evidence.
"""
import argparse
import json
from pathlib import Path


def read_events(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    events, partial = [], False
    for index, line in enumerate(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise
            partial = True
    return events, partial


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(events, partial=False, agents=None):
    selected = set(agents) if agents else None
    latest, snapshot_ids, actions, rows = {}, {}, {}, []
    for event in events:
        kind, payload = event["event_type"], event["payload"]
        agent = event.get("agent_id")
        if kind == "STATE_OBSERVED":
            latest[agent] = payload
            snapshot_ids[agent] = event.get("event_id", "unknown")
        elif kind == "ACTION_STARTED":
            actions.setdefault(payload["timestep"], {})[agent] = payload.get("action")
        elif kind == "TASK_VALIDATED" and payload["observation_phase"] == "after_action":
            step = payload["timestep"]
            for aid in sorted(latest):
                if selected is not None and aid not in selected:
                    continue
                node = latest[aid]
                rows.append([step, event["event_id"], snapshot_ids[aid], aid,
                             actions.get(step, {}).get(aid, "unknown"),
                             node.get("position", "unknown"),
                             json.dumps(node.get("resources", {}), sort_keys=True),
                             node.get("facts", {}).get("in_helicopter", "unknown"),
                             payload.get("success", "unknown"), payload.get("rewards", [])])
    complete = any(e["event_type"] == "RUN_FINISHED" for e in events)
    header = ["# Action-boundary evidence timeline", "",
              f"Run finished: {complete}; truncated final line: {partial}.", "",
              "Rows show the latest environment-reported snapshot available at each after_action validator; "
              "snapshot event IDs expose older observations rather than asserting freshness. "
              "Missing fields remain unknown. Claims, map-cache cells and semantic "
              "completion are not inferred. Rewards use the original environment order.", "",
              "| step | validator event | snapshot event | agent | issued action | position | resources | aboard | success | rewards |",
              "|---:|---:|---:|---|---|---|---|---|---|---|"]
    return "\n".join(header + ["| " + " | ".join(map(cell, row)) + " |" for row in rows]) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("--agents", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    events, partial = read_events(args.events)
    result = render(events, partial, args.agents)
    if args.output:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(result)
        print(args.output)
    else:
        print(result, end="")
