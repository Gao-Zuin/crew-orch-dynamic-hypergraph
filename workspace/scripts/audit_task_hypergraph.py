"""Replay the active SoftTaskGraph profile; no archived full-graph dependency.

This verifies recorded mechanics, not independent physical task success.
Historical full-stage profiles use research/legacy_full_task_graph/audit.py.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ORCH/crew-algorithms"))
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph


def audit_soft(events, failures):
    """Replay the advisory profile without imposing legacy stage permissions."""
    graph = SoftTaskGraph(lambda kind, payload: {"event_id": 0})
    counters = Counter()
    last_id = 0
    last_proposal = None
    started, completed = {}, set()
    decisions = {}
    transitions, overlap, cross = [], [], []
    usage = [0, 0]
    finished = None
    validations = []
    replay_initial = False
    for event in events:
        try:
            eid, kind, payload = event["event_id"], event["event_type"], event["payload"]
            if eid <= last_id:
                raise ValueError("non-monotonic event ids")
            last_id = eid
            counters[kind] += 1
            if kind == "TASK_HYPERGRAPH_STARTED":
                graph.fixed_groups = bool(payload.get("fixed_groups"))
                graph.report_driven = payload.get("context_profile") in {"task_hypergraph_reports_v2", "task_hypergraph_reports_v3", "task_hypergraph_reports_v4", "task_hypergraph_reports_v5"}
                graph.direct_environment_events = payload.get("context_profile") == "task_hypergraph_reports_v5"
                replay_initial = bool(payload.get("initial_plan_replay"))
            elif kind == "TASK_WORLD_SNAPSHOT":
                graph.observe({**deepcopy(payload), "evidence_id": eid})
            elif kind == "TASK_LEADER_REPORT":
                edge = graph.edges.get(payload["source"])
                if not edge or edge["leader"] != payload["sender"] or payload["graph_version"] != graph.version:
                    raise ValueError("invalid leader report")
                graph.reports.append({"event_id": eid, **deepcopy(payload)})
            elif kind == "TASK_ENVIRONMENT_NOTICE":
                if not graph.direct_environment_events or payload.get("source") != "environment_event_notification":
                    raise ValueError("unexpected official environment notice")
                graph.environment_notices.append({"event_id": eid, **deepcopy(payload)})
            elif kind == "TASK_CENTRAL_NOTICE_DELIVERED":
                notice = next((n for n in graph.environment_notices
                               if n["event_id"] == payload["source_notice_event_id"]), None)
                if (notice is None or payload["recipient"] not in graph.live_agents() or
                        payload["graph_version"] != graph.version):
                    raise ValueError("central downlink differs from notice or current graph")
                announced = notice["event"]
                if payload["content"] != announced.get("announcement", f"Game event: {announced['action']}"):
                    raise ValueError("central downlink changed the official announcement")
            elif kind == "TASK_ORGANIZER_REQUEST" and graph.report_driven:
                state = json.loads(payload["messages"][-1]["content"])
                if state != graph.decision_state():
                    raise ValueError("organizer input differs from declared source state")
            elif kind == "TASK_ORGANIZER_RESPONSE":
                try:
                    last_proposal = json.loads(payload["content"].strip().removeprefix("```json").removesuffix("```").strip())
                except ValueError:
                    last_proposal = None
            elif kind == "TASK_GRAPH_COMMITTED":
                proposal = payload["proposal"]
                old = set(graph.edges)
                if payload.get("manual_regroup"):
                    graph.regroup({"members": {edge["id"]: edge["members"] for edge in proposal["edges"]},
                                   "active": proposal["active"]})
                    if (list(graph.edges.values()) != payload["edges"] or
                            graph.active != proposal["active"]):
                        raise ValueError("manual regroup changed more than membership")
                else:
                    initial_replay_commit = replay_initial and graph.version == 0
                    if not (initial_replay_commit or payload.get("attrition") or
                            last_proposal == proposal or proposal.get("reason") ==
                            "continue mission while organization is unavailable"):
                        raise ValueError("commit differs from model suggestion or mission fallback")
                    graph.apply(proposal, attrition=bool(payload.get("attrition")))
                if graph.version != payload["version"] or list(graph.edges.values()) != payload["edges"]:
                    raise ValueError("commit differs from replay")
                if old - set(graph.edges):
                    transitions.append({"event_id": eid, "retired": sorted(old - set(graph.edges)),
                                        "created": sorted(set(graph.edges) - old)})
                if any(sum(a in e["members"] for e in graph.edges.values()) > 1 for a in graph.active):
                    overlap.append(eid)
            elif kind == "TASK_MESSAGE_DELIVERED":
                allowed, reason = graph.route(payload["sender"], payload["recipient"],
                                              payload["source"], payload["target"])
                if not allowed or payload["graph_version"] != graph.version:
                    raise ValueError("invalid message route: " + reason)
                message_type = payload.get("message_type")
                if graph.report_driven:
                    source = graph.edges[payload["source"]]
                    target = graph.edges[payload["target"]]
                    if message_type not in {"GROUP", "REPORT", "LEADER"}:
                        raise ValueError("unknown typed message")
                    if message_type == "REPORT" and payload["recipient"] != source["leader"]:
                        raise ValueError("report bypasses leader")
                    if message_type == "LEADER" and (payload["sender"] != source["leader"] or payload["recipient"] != target["leader"]):
                        raise ValueError("leader message has worker endpoint")
                    if message_type in {"GROUP", "REPORT"} and payload["source"] != payload["target"]:
                        raise ValueError("within-edge intent crossed an edge")
                if payload["source"] != payload["target"]:
                    cross.append(eid)
            elif kind in {"TASK_ACTION_AUTHORIZED", "TASK_ACTION_HELD"}:
                agent = event["agent_id"]
                if kind == "TASK_ACTION_AUTHORIZED" and (not graph.ready(agent) or
                        payload["edge"] != graph.active.get(agent)):
                    raise ValueError("invalid action binding")
                decisions[agent] = (kind, payload)
            elif kind == "ACTION_STARTED":
                agent, action_id = event["agent_id"], event["action_id"]
                decision, detail = decisions.pop(agent)
                expected = detail["action"] if decision == "TASK_ACTION_AUTHORIZED" else [0, *graph.world["nodes"][agent]["position"]]
                if payload["action"] != expected or action_id in started:
                    raise ValueError("action differs from decision")
                started[action_id] = payload["action"]
            elif kind == "ACTION_COMPLETED":
                if event["action_id"] not in started or event["action_id"] in completed:
                    raise ValueError("invalid action completion")
                completed.add(event["action_id"])
            elif kind == "TASK_VALIDATED":
                validations.append(payload)
            elif kind == "LLM_USAGE":
                usage[0] += event["input_tokens"]
                usage[1] += event["output_tokens"]
            elif kind == "RUN_FINISHED":
                finished = payload
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            failures.append(f"event {event.get('event_id')}: {exc}")
    if finished is None:
        failures.append("run has no RUN_FINISHED")
    elif usage != [finished["input_tokens"], finished["output_tokens"]]:
        failures.append("usage differs from final usage")
    if set(started) != completed:
        failures.append("unfinished action boundaries")
    return {"passed": not failures, "failures": failures, "event_counts": dict(counters),
            "graph_version": graph.version, "stage_changes": transitions,
            "overlap_commit_events": overlap, "cross_edge_message_events": cross,
            "action_count": len(started), "retired_edges": graph.archive,
            "last_validation": validations[-1] if validations else None, "usage": finished,
            "qualification": "advisory graph replay; task success uses original validator"}


def audit(path):
    events, failures = [], []
    for index, line in enumerate(path.read_text().splitlines(), 1):
        try:
            events.append(json.loads(line))
        except ValueError:
            failures.append(f"invalid JSON at line {index}")
    if not any(e.get("event_type") == "TASK_HYPERGRAPH_STARTED" and
               e.get("payload", {}).get("context_profile") in {"task_hypergraph_soft_v1", "task_hypergraph_reports_v2", "task_hypergraph_reports_v3", "task_hypergraph_reports_v4", "task_hypergraph_reports_v5"}
               for e in events):
        failures.append("Expected current profile task_hypergraph_soft_v1. "
                        "For archived full-graph traces use "
                        "research/legacy_full_task_graph/audit.py.")
        return {"passed": False, "failures": failures,
                "event_counts": dict(Counter(e.get("event_type") for e in events)),
                "qualification": "unsupported profile; no legacy fallback in current audit"}
    return audit_soft(events, failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.events)
    if args.output:
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)



if __name__ == "__main__":
    main()
