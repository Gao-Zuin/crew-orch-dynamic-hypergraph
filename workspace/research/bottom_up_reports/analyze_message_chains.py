"""Uniform typed-message chain audit for the 15 complete HT mainline runs.

The counters are protocol-flow proxies.  They do not claim that a follow-up
message preserved the meaning of the triggering report or changed an action.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import re


DEFAULT_RUNS = {
    "flash_r2_transport": "/data1/gzy/crew_bottom_up_20261029_attrition_fix/runs/large_transport_down/run/events.jsonl",
    "flash_r2_sparse": "/data1/gzy/crew_bottom_up_20261029_attrition_fix/runs/large_sparse_clearance/run/events.jsonl",
    "flash_r2_rapid": "/data1/gzy/crew_bottom_up_20261029_cell_guard/runs/large_rapid_growth/run/events.jsonl",
    "flash_r2_rescue": "/data1/gzy/crew_bottom_up_20261029_cell_guard/runs/large_rescue/run/events.jsonl",
    "flash_r2_second_fire": "/data1/gzy/crew_bottom_up_20261029_cell_guard/runs/large_second_fire/run/events.jsonl",
    "pro_r2_transport": "/data1/gzy/crew_ht_r2_pro_campaign_20261030/runs/pro_transport_down/run/events.jsonl",
    "pro_r2_sparse": "/data1/gzy/crew_ht_r2_pro_sparse_20261030/runs/pro_sparse_seed42/run/events.jsonl",
    "pro_r2_rapid": "/data1/gzy/crew_ht_r2_pro_campaign_20261030/runs/pro_rapid_growth/run/events.jsonl",
    "pro_r2_rescue": "/data1/gzy/crew_ht_r2_pro_campaign_20261030/runs/pro_rescue/run/events.jsonl",
    "pro_r2_second_fire": "/data1/gzy/crew_ht_r2_pro_campaign_20261030/runs/pro_second_fire/run/events.jsonl",
    "flash_r3_transport": "/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/runs/flash_transport_down/run/events.jsonl",
    "flash_r3_sparse": "/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/runs/flash_sparse_seed42/run/events.jsonl",
    "flash_r3_rapid": "/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/runs/flash_rapid_growth/run/events.jsonl",
    "flash_r3_rescue": "/data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102/runs/flash_rescue/run/events.jsonl",
    "flash_r3_second_fire": "/data1/gzy/crew_ht_r3_orch_knowledge_flash_second_fire_retry_20261103/runs/flash_second_fire_retry_after_recharge/run/events.jsonl",
}

TAG_RE = re.compile(r"<(GROUP|REPORT|LEADER|ORGANIZER)\b", re.I)
TAG_BODY_RE = re.compile(r"<(GROUP|REPORT|LEADER|ORGANIZER)\b([^>]*)>(.*?)</\1>",
                         re.I | re.S)
COORD_RE = re.compile(r"(?<!\d)(\d{1,3})\s*,\s*(\d{1,3})(?!\d)")


def load_events(path):
    events = []
    current_step = None
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            event = json.loads(line)
            payload = event.get("payload", {})
            explicit = payload.get("step", payload.get("timestep"))
            if isinstance(explicit, int):
                current_step = explicit
            event["_audit_step"] = current_step
            events.append(event)
    return events


def tags(raw):
    return [value.upper() for value in TAG_RE.findall(raw or "")]


def typed_messages(raw):
    messages = []
    for kind, raw_attrs, body in TAG_BODY_RE.findall(raw or ""):
        attrs = dict(re.findall(r'(\w+)\s*=\s*["\']([^"\']*)["\']', raw_attrs))
        messages.append({"kind": kind.upper(), "attrs": attrs, "content": body.strip()})
    return messages


def coordinates(text):
    return {f"{x},{y}" for x, y in COORD_RE.findall(text or "")}


def topology_signature(event):
    payload = event.get("payload", {})
    edges = payload.get("edges", [])
    return (
        tuple(sorted((edge.get("id"), tuple(sorted(edge.get("members", []))), edge.get("leader"))
                     for edge in edges)),
        tuple(sorted(payload.get("proposal", {}).get("active", {}).items())),
    )


def followup_tags(generated, recipient, step, window=1):
    found = []
    for candidate in generated.get(str(recipient), []):
        cstep = candidate["step"]
        if step is not None and cstep is not None and step <= cstep <= step + window:
            found.extend(candidate["tags"])
    return sorted(set(found))


def later_messages(generated, recipient, event_id, step, allowed, window=1):
    found = []
    for candidate in generated.get(str(recipient), []):
        cstep = candidate["step"]
        if (candidate["event_id"] > event_id and step is not None and cstep is not None
                and step <= cstep <= step + window):
            found.extend(message for message in candidate["messages"]
                         if message["kind"] in allowed)
    return found


def analyze_run(path):
    events = load_events(path)
    generated = defaultdict(list)
    generated_counts = Counter()
    delivered_counts = Counter()
    invalid_counts = Counter()
    leader_reports = []
    graph_commits = []
    current_leaders = {}
    silent_self_reports = 0
    for event in events:
        kind = event.get("event_type")
        payload = event.get("payload", {})
        step = event.get("_audit_step")
        if kind == "COMMUNICATION_GENERATED":
            raw = payload.get("raw_output", "")
            found = tags(raw)
            generated[str(event.get("agent_id"))].append(
                {"step": step, "event_id": event["event_id"], "tags": found,
                 "messages": typed_messages(raw)})
            generated_counts.update(found)
            for message in typed_messages(raw):
                if (message["kind"] == "REPORT"
                        and current_leaders.get(message["attrs"].get("edge"))
                        == str(event.get("agent_id"))):
                    silent_self_reports += 1
        elif kind == "TASK_MESSAGE_DELIVERED":
            delivered_counts[payload.get("message_type", "UNKNOWN")] += 1
        elif kind == "TASK_MESSAGE_INVALID":
            invalid_counts[payload.get("message_type", "UNKNOWN")] += 1
        elif kind == "TASK_LEADER_REPORT":
            leader_reports.append(event)
        elif kind == "TASK_GRAPH_COMMITTED":
            graph_commits.append(event)
            current_leaders = {edge.get("id"): str(edge.get("leader"))
                               for edge in payload.get("edges", [])}

    report_followups = Counter()
    leader_followups = Counter()
    coordinate_chains = Counter()
    for event in events:
        if event.get("event_type") != "TASK_MESSAGE_DELIVERED":
            continue
        payload = event["payload"]
        followups = followup_tags(generated, payload.get("recipient"),
                                  event.get("_audit_step"))
        bucket = report_followups if payload.get("message_type") == "REPORT" else (
            leader_followups if payload.get("message_type") == "LEADER" else None)
        if bucket is not None:
            if not followups:
                bucket["NO_TYPED_FOLLOWUP"] += 1
            else:
                bucket.update(followups)
        content_coords = coordinates(payload.get("content", ""))
        if payload.get("message_type") == "REPORT" and content_coords:
            coordinate_chains["coordinate_reports_delivered"] += 1
            outward = later_messages(generated, payload.get("recipient"), event["event_id"],
                                     event.get("_audit_step"), {"LEADER", "ORGANIZER"})
            if outward:
                coordinate_chains["coordinate_reports_with_outward_escalation"] += 1
            if any(content_coords & coordinates(message["content"]) for message in outward):
                coordinate_chains["coordinate_reports_preserved_outward"] += 1
        elif payload.get("message_type") == "LEADER" and content_coords:
            coordinate_chains["coordinate_leader_messages_delivered"] += 1
            outward = later_messages(generated, payload.get("recipient"), event["event_id"],
                                     event.get("_audit_step"), {"GROUP", "ORGANIZER"})
            if outward:
                coordinate_chains["coordinate_leader_messages_with_local_or_center_followup"] += 1
            if any(content_coords & coordinates(message["content"]) for message in outward):
                coordinate_chains["coordinate_leader_messages_preserved_followup"] += 1

    previous = None
    structural_commits = []
    for commit in graph_commits:
        signature = topology_signature(commit)
        if previous is not None and signature != previous:
            structural_commits.append(commit)
        previous = signature
    structural_steps = [event.get("_audit_step") for event in structural_commits]
    commit_steps = {event.get("_audit_step") for event in graph_commits}
    leader_report_steps = {event.get("_audit_step") for event in leader_reports}
    reports_with_commit = sum(event.get("_audit_step") in commit_steps for event in leader_reports)
    structural_with_report = sum(step in leader_report_steps for step in structural_steps)
    structural_attrition = sum(bool(event.get("payload", {}).get("attrition"))
                               for event in structural_commits)

    return {
        "path": str(path),
        "task_id": events[0].get("task_id") if events else None,
        "communication_turns": sum(1 for e in events if e.get("event_type") == "COMMUNICATION_GENERATED"),
        "generated_typed_tags": dict(generated_counts),
        "delivered_recipient_events": dict(delivered_counts),
        "invalid_typed_tags": dict(invalid_counts),
        "generated_report_tags_silently_addressed_to_self": silent_self_reports,
        "report_delivery_followup_proxy": dict(report_followups),
        "leader_delivery_followup_proxy": dict(leader_followups),
        "coordinate_chain_proxy": dict(coordinate_chains),
        "organizer_reports": len(leader_reports),
        "organizer_reports_with_any_same_step_commit": reports_with_commit,
        "graph_commits": len(graph_commits),
        "structural_change_commits_after_initial": len(structural_steps),
        "structural_change_commits_same_step_as_organizer_report": structural_with_report,
        "structural_change_commits_marked_attrition": structural_attrition,
        "structural_change_commits_without_same_step_report_or_attrition":
            len(structural_steps) - structural_with_report - sum(
                bool(event.get("payload", {}).get("attrition"))
                and event.get("_audit_step") not in leader_report_steps
                for event in structural_commits),
        "structural_change_steps": structural_steps,
        "limitations": "Follow-up is same-recipient typed output within 0-1 steps; semantic preservation and action effects are not inferred.",
    }


def analyze_all(runs=None):
    runs = runs or DEFAULT_RUNS
    details = {name: analyze_run(path) for name, path in runs.items()}
    totals = Counter()
    nested = defaultdict(Counter)
    for detail in details.values():
        for key in ("communication_turns", "organizer_reports",
                    "organizer_reports_with_any_same_step_commit", "graph_commits",
                    "structural_change_commits_after_initial",
                    "structural_change_commits_same_step_as_organizer_report",
                    "structural_change_commits_marked_attrition",
                    "structural_change_commits_without_same_step_report_or_attrition",
                    "generated_report_tags_silently_addressed_to_self"):
            totals[key] += detail[key]
        for key in ("generated_typed_tags", "delivered_recipient_events", "invalid_typed_tags",
                    "report_delivery_followup_proxy", "leader_delivery_followup_proxy",
                    "coordinate_chain_proxy"):
            nested[key].update(detail[key])
    return {"scope": {"run_count": len(details), "selection": "all 15 complete HT mainline runs; no short gates or interrupted runs"},
            "totals": {**dict(totals), **{key: dict(value) for key, value in nested.items()}},
            "runs": details}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    result = analyze_all()
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
