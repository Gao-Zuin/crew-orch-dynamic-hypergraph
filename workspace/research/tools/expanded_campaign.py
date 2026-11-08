"""Durable runner with terminal-only incremental reports. Never changes actions.

Raw evidence is immutable. Derived report files are atomically regenerated;
timelines are created once per terminal case. In-progress cases remain unknown.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from hypergraph_campaign import summarize_case
from episode_timeline import read_events, render


def detail(events):
    validations = [e for e in events if e["event_type"] == "TASK_VALIDATED"]
    completed = [e for e in events if e["event_type"] == "ACTION_COMPLETED"]
    messages = Counter()
    for e in events:
        if e["event_type"] in {"MESSAGE_DELIVERED", "MESSAGE_SUPPRESSED", "MESSAGE_FAILED"}:
            messages[(str(e.get("agent_id")), str(e["payload"].get("recipient")), e["event_type"])] += 1
    transitions = []
    for e in completed:
        delta = e["payload"].get("verified_local_delta", {})
        if "resources" in delta or "online" in delta:
            transitions.append({"event_id": e["event_id"], "agent_id": e["agent_id"],
                                "action_id": e.get("action_id"), "action": e["payload"].get("action"),
                                "resources": delta.get("resources"), "online": delta.get("online")})
    initial = validations[0]["payload"] if validations else {}
    final = validations[-1]["payload"] if validations else {}
    a, b = initial.get("rewards"), final.get("rewards")
    boundaries = [e for e in validations if e["payload"].get("observation_phase") == "after_action"]
    first_active = next((e for e in boundaries if e["payload"].get("fire_active") is True), None)
    first_clear = next((e for e in boundaries if first_active and e["event_id"] > first_active["event_id"]
                        and e["payload"].get("fire_active") is False), None)
    return {"event_count": len(events), "initial_rewards": a, "final_rewards": b,
            "reward_delta": [y-x for x,y in zip(a,b)] if a is not None and b is not None else None,
            "initial_fire_active": initial.get("fire_active"), "final_fire_active": final.get("fire_active"),
            "first_observed_ignition_event": first_active.get("event_id") if first_active else None,
            "first_observed_clear_after_ignition_event": first_clear.get("event_id") if first_clear else None,
            "final_observed_clear_after_ignition": bool(first_active and final.get("fire_active") is False),
            "resource_transitions": transitions,
            "position_change_actions": sum("position" in e["payload"].get("verified_local_delta", {}) for e in completed),
            "message_matrix": [{"sender": s, "recipient": r, "event_type": k, "count": n}
                               for (s,r,k),n in sorted(messages.items())],
            "notes": ["Resource transitions are runtime observations, not proof a particular action caused the change.",
                      "Position changes and local-no-delta are not causal productivity/idle metrics.",
                      "No automatic semantic contradiction score; inspect raw messages against snapshot event IDs."]}


def atomic_text(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(value)
    temporary.replace(path)


def update(output, exit_code=None):
    manifest = json.loads((output / "manifest.json").read_text())
    rows, details = [], {}
    for case in manifest["cases"]:
        directory = output / case["case_id"]
        if not (directory / "status.json").exists():
            rows.append({"case_id": case["case_id"], "task": case["level"], "seed": case["seed"],
                         "arm": case["id"], "terminal": False, "task_success": None})
            continue
        rows.append(summarize_case(case, directory))
        events, partial = read_events(directory / "events.jsonl") if (directory / "events.jsonl").exists() else ([], False)
        details[case["case_id"]] = detail(events)
        timeline = directory / "evidence_timeline.md"
        if not timeline.exists():
            with timeline.open("x", encoding="utf-8") as stream:
                stream.write(render(events, partial))
    report = {"planned_cases": len(rows), "terminal_cases": sum(r["terminal"] for r in rows),
              "runner_exit_code": exit_code, "rows": rows, "details": details,
              "analysis_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    atomic_text(output / "extended_analysis.json", json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    lines = ["# Expanded campaign: live results", "",
             f"Terminal: {report['terminal_cases']}/{len(rows)}; runner exit: {exit_code}.", "",
             f"Frozen campaign version {manifest['version']}; do not pool different source versions. "
             "Suppression windows are specified per case in manifest; they may be shorter than the original 100 steps. "
             "Unknown/pending outcomes remain unknown. Token values on failed infrastructure are observed lower bounds.", "",
             "| Case | Task success | Goal fraction | Steps | Tokens | Delivered / suppressed | Reward delta |",
             "|---|---|---|---:|---:|---|---|"]
    for r in rows:
        if not r["terminal"]:
            lines.append(f"| {r['case_id']} | pending | — | — | — | — | — |")
            continue
        d = details[r["case_id"]]
        lines.append(f"| [{r['case_id']}]({r['case_id']}/evidence_timeline.md) | {r['task_success']} | "
                     f"{r['final_goal_fraction']} | {r['observed_action_steps']} | {r['total_tokens']} | "
                     f"{r['message_delivered']} / {r['message_suppressed']} | {d['reward_delta']} |")
    lines += ["", "## Interpretation boundaries", "",
              "Tree reward delta subtracts initially clear cells; final fraction alone is not new clearing. "
              "For suppression use final_fire_active, reward[3] extinguished and reward[1] burned separately; "
              "there is no fabricated fixed fire denominator. Transport success requires the environment's delivered count, "
              "not a message saying unload/complete. Scout uses the original concurrent-scout counter, not cached map cells.", "",
              "extended_analysis.json includes initial/final rewards, resource transition event IDs, "
              "position-change counts and recipient-level message matrices. Raw agent chats and PNG links remain in each case. "
              "Full task-seed contrasts are generated by the frozen campaign analyzer at the end; "
              "semantic contradictions and causal useful messages require manual evidence review."]
    lines += ["", "For fire tasks, extended_analysis.json separately reports observed ignition and subsequent clear event IDs. "
              "This is a post-hoc descriptive signal, not a replacement success score. The unchanged original containment "
              "validator also requires burned-tree count > 0; no-burn episodes can remain validator-false despite fire_active=false."]
    atomic_text(output / "LIVE_ANALYSIS.md", "\n".join(lines)+"\n")
    return report["terminal_cases"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=lambda s: Path(s).resolve())
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.report_only:
        print("Terminal:", update(args.output))
        return
    # One supervisor only; the campaign itself rejects existing incomplete cases.
    with (args.output / "expanded_supervisor.json").open("x") as stream:
        import os
        json.dump({"pid": os.getpid(), "output": str(args.output)}, stream)
    with (args.output / "campaign_controller.log").open("x") as log:
        process = subprocess.Popen([sys.executable, str(ROOT / "scripts/hypergraph_campaign.py"),
                                    "run", "--output", str(args.output)], stdout=log, stderr=subprocess.STDOUT)
        previous = -1
        while process.poll() is None:
            try:
                count = update(args.output)
                if count != previous:
                    print(f"Terminal {count}; reports updated", flush=True)
                    previous = count
            except Exception as error:
                # Analysis must never terminate or modify a live experiment.
                print(f"Report error: {type(error).__name__}: {error}", flush=True)
            time.sleep(20)
    update(args.output, process.returncode)
    print(f"Campaign exited {process.returncode}", flush=True)
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
