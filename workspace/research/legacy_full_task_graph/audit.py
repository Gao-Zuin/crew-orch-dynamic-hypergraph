"""Offline audit for archived full task-stage profiles only."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research"))
from legacy_full_task_graph.task_hypergraph import TaskHypergraph


def audit(path):
    events = []
    failures = []
    for index, line in enumerate(path.read_text().splitlines(), 1):
        try:
            events.append(json.loads(line))
        except ValueError:
            failures.append(f"invalid JSON at line {index}")
    if any(e.get("event_type") == "TASK_HYPERGRAPH_STARTED" and
           e.get("payload", {}).get("context_profile") == "task_hypergraph_soft_v1"
           for e in events):
        failures.append("SoftTaskGraph trace: use scripts/audit_task_hypergraph.py.")
        return {"passed": False, "failures": failures,
                "qualification": "current profile excluded from archived audit"}
    graph = TaskHypergraph(lambda kind, payload: {"event_id": 0})
    counters = Counter()
    last_proposal = last_verification = None
    normalized_labels = []
    normalized_pending = []
    normalized_checks = []
    normalized_handoffs = []
    advisory_rejection = None
    decisions, started, completed = {}, {}, set()
    transitions, overlap_commits, cross_messages = [], [], []
    last_id = 0
    usage = [0, 0]
    finished = None
    for event in events:
        try:
            eid, kind, payload = event["event_id"], event["event_type"], event["payload"]
            if eid <= last_id:
                raise ValueError("non-monotonic event ids")
            last_id = eid
            counters[kind] += 1
            if kind == "TASK_HYPERGRAPH_STARTED":
                profile = payload.get("context_profile")
                graph.require_event_ack = profile != "task_hypergraph_v1"
                graph.enforce_ongoing_fire_owners = profile in {"task_hypergraph_v3", "task_hypergraph_v4"}
                graph.enforce_distinct_links = profile in {"task_hypergraph_v3", "task_hypergraph_v4"}
                graph.enforce_exact_description = profile == "task_hypergraph_v4"
            elif kind == "TASK_WORLD_SNAPSHOT":
                graph.observe({**deepcopy(payload), "evidence_id": eid})
            elif kind == "TASK_ORGANIZER_RESPONSE":
                try:
                    last_proposal = json.loads(payload["content"].strip().removeprefix("```json").removesuffix("```").strip())
                except ValueError:
                    last_proposal = None
                last_verification = None
                normalized_labels = []
                normalized_pending = []
                normalized_checks = []
                normalized_handoffs = []
                advisory_rejection = None
            elif kind == "TASK_REVIEW_LABEL_NORMALIZED":
                if last_proposal is None:
                    raise ValueError("review normalization has no model proposal")
                normalized_labels.append(payload)
            elif kind == "TASK_PENDING_NORMALIZED":
                if last_proposal is None:
                    raise ValueError("pending normalization has no model proposal")
                normalized_pending.append(payload)
            elif kind == "TASK_EXACT_CHECK_NORMALIZED":
                if last_proposal is None:
                    raise ValueError("check normalization has no model proposal")
                normalized_checks.append(payload)
            elif kind in {"TASK_HANDOFF_PENDING_NORMALIZED", "TASK_HANDOFF_RECEIVER_NORMALIZED"}:
                if last_proposal is None:
                    raise ValueError("handoff normalization has no model proposal")
                normalized_handoffs.append((kind, payload))
            elif kind == "TASK_VERIFIER_RESPONSE":
                try:
                    last_verification = json.loads(payload["content"])
                except ValueError:
                    last_verification = None
            elif kind == "TASK_VERIFIER_ADVISORY_REJECTION":
                advisory_rejection = payload
            elif kind == "TASK_GRAPH_COMMITTED":
                proposal = payload["proposal"]
                expected = deepcopy(last_proposal)
                if expected is None:
                    raise ValueError("commit has no returned LLM proposal")
                resolved = {(r.get("edge_id"), r.get("obligation")) for r in expected.get("resolved", [])}
                for pending_fix in normalized_pending:
                    edge_id = pending_fix["edge_id"]
                    old_edge = graph.edges.get(edge_id)
                    new_edge = next((e for e in expected["edges"] if e["id"] == edge_id), None)
                    if old_edge is None or new_edge is None:
                        raise ValueError("pending normalization requires a retained edge")
                    current = new_edge["context"]["pending"]
                    missing = [obligation for obligation in old_edge["context"]["pending"]
                               if obligation not in current and (edge_id, obligation) not in resolved]
                    if missing != pending_fix["obligations"]:
                        raise ValueError("pending normalization does not match old duties")
                    current.extend(missing)
                for repair_kind, repair in normalized_handoffs:
                    source = repair["source"]
                    receivers = [h for h in expected.get("handoffs", []) if h.get("source") == source]
                    if repair_kind == "TASK_HANDOFF_PENDING_NORMALIZED":
                        old_edge = graph.edges.get(source)
                        if old_edge is None or source in {e["id"] for e in expected["edges"]}:
                            raise ValueError("handoff pending normalization needs a retired edge")
                        chosen = [h for h in receivers if h["target"] in repair["targets"]]
                        if [h["target"] for h in chosen] != repair["targets"]:
                            raise ValueError("handoff normalization targets differ")
                        resolved_old = {d for edge_id, d in resolved if edge_id == source}
                        missing = [d for d in old_edge["context"]["pending"] if d not in resolved_old and
                                   not any(d in h["pending"] for h in chosen)]
                        if missing != repair["obligations"]:
                            raise ValueError("handoff normalized duties differ from old edge")
                        for handoff in chosen:
                            handoff["pending"].extend(missing)
                    else:
                        target = repair["target"]
                        handoff = next((h for h in receivers if h["target"] == target), None)
                        candidate = next((e for e in expected["edges"] if e["id"] == target), None)
                        if handoff is None or candidate is None:
                            raise ValueError("handoff receiver normalization has no selected target")
                        current = candidate["context"]["pending"]
                        absent = [d for d in handoff["pending"] if d not in current]
                        if absent != repair["obligations"]:
                            raise ValueError("handoff receiver normalized duties differ")
                        current.extend(absent)
                tracked = ("stage", "goal", "members", "leader", "tasks", "rules",
                           "communication", "checks", "depends_on")
                for label in normalized_labels:
                    edge_id = label["edge_id"]
                    old_edge = graph.edges.get(edge_id)
                    new_edge = next((e for e in expected["edges"] if e["id"] == edge_id), None)
                    review = next((r for r in expected["reviews"] if r["edge_id"] == edge_id), None)
                    if old_edge is None or new_edge is None or review is None or review["verdict"] != "continue":
                        raise ValueError("normalization is not tied to an unchanged-id edge review")
                    changed = [key for key in tracked if new_edge.get(key) != old_edge.get(key)]
                    if (label.get("from"), label.get("to"), label.get("changed_fields")) != ("continue", "revise", changed) or not changed or "stage" in changed:
                        raise ValueError("review normalization does not match model-changed fields")
                    review["verdict"] = "revise"
                for correction in normalized_checks:
                    edge_id, check_id = correction["edge_id"], correction["check_id"]
                    old_edge = graph.edges.get(edge_id)
                    review = next((r for r in expected["reviews"] if r["edge_id"] == edge_id), None)
                    check = next((c for c in old_edge["checks"] if c["id"] == check_id), None) if old_edge else None
                    result = next((c for c in review["checks"] if c["id"] == check_id), None) if review else None
                    if check is None or check["kind"] == "semantic" or result is None:
                        raise ValueError("normalization is not tied to an exact old check")
                    observed = graph.evaluate(check)
                    verdict = "unknown" if observed is None else "met" if observed else "unmet"
                    prior_refs = result.get("evidence") if isinstance(result.get("evidence"), list) else []
                    new_refs = prior_refs if graph.world["evidence_id"] in prior_refs else prior_refs + [graph.world["evidence_id"]]
                    if (correction["prior_verdict"], correction["verdict"], correction["prior_evidence"], correction["evidence"]) != (result.get("verdict"), verdict, prior_refs, new_refs):
                        raise ValueError("exact check normalization differs from current world")
                    result["verdict"], result["evidence"] = verdict, new_refs
                if proposal != expected:
                    raise ValueError("commit differs from returned LLM proposal plus logged review-label normalization")
                if not last_verification:
                    raise ValueError("commit lacks independent LLM review")
                reviews = last_verification.get("edge_reviews", [])
                candidate_ids = {e["id"] for e in proposal["edges"]}
                review_ids = {r["edge_id"] for r in reviews}
                if len(reviews) != len(review_ids) or not candidate_ids <= review_ids:
                    raise ValueError("independent review does not cover committed edges")
                approved = (last_verification.get("accepted") is True and last_verification.get("issues") == [] and
                            all(r.get("accepted") is True for r in reviews if r["edge_id"] in candidate_ids))
                if not approved:
                    exact_completion_only = all(
                        r.get("verdict") in {"continue", "revise", "blocked"} or
                        (r.get("verdict") == "complete" and
                         all(check["kind"] != "semantic" for check in graph.edges[r["edge_id"]]["checks"]))
                        for r in proposal["reviews"])
                    urgent = (exact_completion_only and
                              ((any(event.get("action") == "start_fire" for event in graph.unacknowledged_events()) and
                                any(a.get("decision") == "replan" for a in proposal.get("event_acknowledgements", []))) or
                               (graph.enforce_ongoing_fire_owners and bool(graph.ongoing_fire_events()))))
                    if not urgent or advisory_rejection is None or advisory_rejection.get("issues") != last_verification.get("issues") or advisory_rejection.get("candidate_edge_ids") != sorted(candidate_ids):
                        raise ValueError("unapproved verifier result lacks bounded urgent-replan advisory record")
                old = deepcopy(graph.edges)
                graph.apply(proposal)
                if payload["version"] != graph.version or payload["edges"] != list(graph.edges.values()):
                    raise ValueError("committed graph differs from deterministic replay")
                if any(sum(a in e["members"] for e in graph.edges.values()) > 1 for a in graph.active):
                    overlap_commits.append(eid)
                if set(old) - set(graph.edges):
                    transitions.append({"event_id": eid, "retired": sorted(set(old) - set(graph.edges)),
                                        "created": sorted(set(graph.edges) - set(old))})
            elif kind == "TASK_ORGANIZATION_HOLD":
                graph.blocked.update(graph.edges)
            elif kind == "TASK_MESSAGE_DELIVERED":
                allowed, reason = graph.route(payload["sender"], payload["recipient"], payload["source"], payload["target"])
                if not allowed:
                    raise ValueError("unauthorized message delivered: " + reason)
                if payload["graph_version"] != graph.version:
                    raise ValueError("message bound to old organization")
                graph.messages.append({"event_id": eid, **{k: payload[k] for k in ("sender", "recipient", "source", "target", "content")}})
                if payload["source"] != payload["target"]:
                    cross_messages.append(eid)
            elif kind in {"TASK_ACTION_AUTHORIZED", "TASK_ACTION_HELD"}:
                agent = event["agent_id"]
                if kind == "TASK_ACTION_AUTHORIZED":
                    if not graph.ready(agent) or payload["edge"] != graph.active.get(agent) or payload["revision"] != graph.edges[payload["edge"]]["revision"]:
                        raise ValueError("action has invalid edge execution ownership")
                decisions[agent] = (kind, payload)
            elif kind == "ACTION_STARTED":
                agent, action_id = event["agent_id"], event["action_id"]
                if agent not in decisions:
                    raise ValueError("action has no hypergraph authorization/hold")
                decision, detail = decisions.pop(agent)
                expected = detail["action"] if decision == "TASK_ACTION_AUTHORIZED" else [0, *graph.world["nodes"][agent]["position"]]
                if payload["action"] != expected:
                    raise ValueError("executed action differs from organization decision")
                if action_id in started:
                    raise ValueError("duplicate action id")
                started[action_id] = payload["action"]
            elif kind == "ACTION_COMPLETED":
                action_id = event["action_id"]
                if action_id not in started or action_id in completed:
                    raise ValueError("action completion without unique start")
                completed.add(action_id)
            elif kind == "LLM_USAGE":
                usage[0] += event["input_tokens"]
                usage[1] += event["output_tokens"]
            elif kind == "RUN_FINISHED":
                finished = payload
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            failures.append(f"event {event.get('event_id')}: {exc}")
    if finished is None:
        failures.append("run has no RUN_FINISHED")
    else:
        if usage != [finished["input_tokens"], finished["output_tokens"]]:
            failures.append("summed action-boundary usage differs from final usage")
        if set(started) != completed:
            failures.append("unfinished action boundaries")
    validations = [e for e in events if e["event_type"] == "TASK_VALIDATED"]
    semantic_completions = [{"edge": e["id"], "semantic_checks": [c["id"] for c in e["checks"] if c["kind"] == "semantic"]}
                            for e in graph.archive if e["verdict"] == "complete"]
    return {"passed": not failures, "failures": failures, "event_counts": dict(counters),
            "graph_version": graph.version, "stage_changes": transitions,
            "overlap_commit_events": overlap_commits, "cross_edge_message_events": cross_messages,
            "action_count": len(started), "retired_edges": [{"id": e["id"], "verdict": e["verdict"]} for e in graph.archive],
            "LLM_semantic_completion_checks": semantic_completions,
            "last_validation": validations[-1]["payload"] if validations else None,
            "usage": finished, "qualification": "mechanism replay, not independent proof of semantic LLM verdicts"}



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
