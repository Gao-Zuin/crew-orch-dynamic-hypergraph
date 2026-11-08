"""Plan/run/analyze a frozen paired CREW experiment; failures remain in results."""
import argparse
from collections import Counter
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from audit_hypergraph_run import audit
from run_hypergraph_gate import digest, stop_group

ROOT = Path(__file__).resolve().parents[1]


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def case_plan(spec):
    cases = []
    for i, task in enumerate(spec["task_seed_pairs"]):
        offset = i % len(spec["arms"])
        arms = spec["arms"][offset:] + spec["arms"][:offset]
        for arm in arms:
            cases.append({**task, **arm,
                          "case_id": f"{len(cases):02d}_{task['level']}_seed{task['seed']}_{arm['id']}"})
    return cases


def verify_sources(manifest):
    mismatches = [p for p, sha in manifest["source_sha256"].items() if
                  not (ROOT / p).is_file() or digest(ROOT / p) != sha]
    if mismatches:
        raise RuntimeError(f"Frozen sources changed: {mismatches}; create a new experiment version")


def plan(spec_path, gate_path, output):
    gate = json.loads((gate_path / "audit.json").read_text())
    if not gate["passed"]:
        raise ValueError("Infrastructure gate did not pass")
    gate_manifest = json.loads((gate_path / "manifest.json").read_text())
    verify_sources(gate_manifest)
    spec = json.loads(spec_path.read_text())
    output.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__).resolve(), ROOT / "scripts/run_hypergraph_gate.py",
             ROOT / "scripts/audit_hypergraph_run.py", spec_path,
             ROOT / "tests/test_hypergraph_campaign.py"]
    package = ROOT / "ORCH/crew-algorithms/crew_algorithms"
    paths += [p for p in package.rglob("*") if p.is_file() and p.suffix in {".py", ".yaml", ".txt"}
              and "results" not in p.relative_to(package).parts]
    hashes = {**gate_manifest["source_sha256"],
              **{str(p.relative_to(ROOT)): digest(p) for p in paths}}
    build = ROOT / "ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server"
    # The executable is only a small launcher; hash player code and game assets too.
    environment_hashes = {str(p.relative_to(ROOT)): digest(p) for p in build.rglob("*")
                          if is_static_build_file(p, build)}
    hashes.update(environment_hashes)
    manifest = dict(version=spec["version"], spec=spec, cases=case_plan(spec),
                    build_hash_exclusions=["*.log", "Unity_Data/ML-Agents/Timers/** (runtime profiler output)"],
                    gate=str(gate_path), source_sha256=hashes,
                    python_version=platform.python_version(),
                    python_executable=sys.executable,
                    dependency_versions=sorted({f"{d.metadata['Name']}=={d.version}"
                                                for d in importlib.metadata.distributions()}),
                    metrics={
                        "task_success": "any original-validator success; missing evidence is unknown, not success",
                        "goal_fraction": "last observed target reward / original target, clipped to [0,1]; NOT stage VMCR",
                        "goal_fraction_auc_observed": "trapezoid mean across actual action-boundary observations; no timeout extrapolation",
                        "tokens": "sum structured LLM_USAGE, audited against RUN_FINISHED; partial for censored runs",
                        "message_units": "recipient deliveries, not unique semantic messages or causal usefulness",
                        "churn": "structural topology commits excluding first; event-adjusted causal attribution unsupported",
                        "timeout": "fixed wall clock, retained in intention-to-evaluate denominator",
                        "unsupported": ["subtask_VMCR", "natural_language_alignment", "causal_useful_message_rate",
                                        "physical_handoff_fidelity", "transition_precision_recall_without_contracts"]})
    write_new(output / "manifest.json", manifest)
    print(f"Frozen {len(manifest['cases'])} cases at {output}", flush=True)


def is_static_build_file(path, build):
    relative = path.relative_to(build)
    return path.is_file() and path.suffix != ".log" and relative.parts[:3] != ("Unity_Data", "ML-Agents", "Timers")


def index_artifacts(directory):
    events_path = directory / "events.jsonl"
    if not events_path.exists():
        return
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    start = next((e for e in events if e["event_type"] == "RUN_STARTED"), None)
    if not start or not start["payload"].get("result_path"):
        return
    result = Path(start["payload"]["result_path"])
    if result.is_dir():
        (directory / "results").symlink_to(os.path.relpath(result, directory))
        logs = result.parents[4]
        candidates = list((logs / "Embodied").glob(
            f"{start['task_id']}/{start['task_seed']}/*/{result.name}"))
        if len(candidates) == 1:
            (directory / "trajectories").symlink_to(os.path.relpath(candidates[0], directory))


def run(output):
    manifest = json.loads((output / "manifest.json").read_text())
    verify_sources(manifest)
    for case in manifest["cases"]:
        verify_sources(manifest)
        directory = output / case["case_id"]
        if (directory / "status.json").exists():
            previous = json.loads((directory / "status.json").read_text())
            if previous["terminal"]:
                print(f"Retaining terminal case {case['case_id']}", flush=True)
                continue
        if directory.exists():
            raise RuntimeError(f"Incomplete existing case; inspect its live process before resuming: {directory}")
        directory.mkdir()
        env = os.environ.copy()
        env.update(CREW_HYPERGRAPH_ARM=case["arm"], CREW_HYPERGRAPH_INTERVENTION=case["intervention"],
                   CREW_HYPERGRAPH_PROTOCOL_STRESS="0", CREW_HYPERGRAPH_EVENT_PATH=str(directory / "events.jsonl"),
                   RUN_LOG_ROOT=str(directory), LEVEL=case["level"], SEED=str(case["seed"]),
                   MAX_STEPS=str(case["max_steps"]), MODEL=manifest["spec"]["model"], URL=manifest["spec"]["url"])
        print(f"Starting {case['case_id']}", flush=True)
        error, exit_code = None, None
        started = time.monotonic()
        with (directory / "controller.log").open("x") as log:
            process = subprocess.Popen(["bash", str(ROOT / "scripts/run_small_communication_benchmark.sh"), "Embodied"],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            write_new(directory / "live_process.json", dict(supervisor_pid=os.getpid(), experiment_pid=process.pid,
                pgid=process.pid, command="run_small_communication_benchmark.sh Embodied", started_monotonic=started))
            try:
                while process.poll() is None:
                    if time.monotonic() - started >= manifest["spec"]["timeout_seconds"]:
                        error = "timeout"
                        break
                    console = directory / "Embodied.log"
                    if console.exists() and "Traceback (most recent call last)" in console.read_text(errors="replace"):
                        error = "runtime traceback"
                        break
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
                exit_code = process.poll()
            finally:
                stop_group(process)
        try:
            result = audit(directory / "events.jsonl")
        except (OSError, ValueError, KeyError, IndexError) as exc:
            result = dict(passed=False, failures=[f"artifact audit: {exc}"])
        # Preserve partial data even if environment/controller failed.
        if error or exit_code:
            result["passed"] = False
            result.setdefault("failures", []).append(error or f"exit={exit_code}")
        index_artifacts(directory)
        write_new(directory / "audit.json", result)
        write_new(directory / "status.json", dict(terminal=True, error=error, exit_code=exit_code,
                                                  elapsed_seconds=time.monotonic() - started,
                                                  audit_passed=result["passed"]))
        print(f"Finished {case['case_id']}: audit_passed={result['passed']}", flush=True)
        verify_sources(manifest)
    analyze(output)


def summarize_case(case, directory):
    path = directory / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    status_path = directory / "status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    validations = [e for e in events if e["event_type"] == "TASK_VALIDATED"]
    boundaries = [e for e in validations if e["payload"]["observation_phase"] == "after_action"]
    initial = next((e for e in validations if e["payload"]["observation_phase"] == "before_action"), None)
    def fraction(event):
        if case.get("target_reward_index") is None:
            return None  # Dynamic fire population has no trusted fixed denominator.
        return max(0., min(1., event["payload"]["rewards"][case["target_reward_index"]] / case["target_units"]))
    fractions = ([fraction(initial)] if initial else []) + [fraction(e) for e in boundaries]
    fraction_supported = bool(fractions) and all(f is not None for f in fractions)
    area = sum((a + b) / 2 for a, b in zip(fractions, fractions[1:])) if fraction_supported else None
    usage = [e for e in events if e["event_type"] == "LLM_USAGE"]
    counts = Counter(e["event_type"] for e in events)
    observed_success = any(e["payload"]["success"] for e in validations)
    task_success = True if observed_success else False if counts["RUN_FINISHED"] and validations else None
    topology = [e for e in events if e["event_type"] == "TOPOLOGY_COMMITTED"]
    overlapping = any(any(n > 1 for n in Counter(a for edge in e["payload"]["edges"]
                      for a in edge["members"]).values()) for e in topology)
    row = dict(case_id=case["case_id"], task=case["level"], seed=case["seed"], arm=case["id"],
               terminal=status.get("terminal", False), infrastructure_passed=status.get("audit_passed", False),
               error=status.get("error"), task_success=task_success,
               final_goal_fraction=fraction(validations[-1]) if validations else None,
               observed_action_steps=len(boundaries), planned_max_steps=case["max_steps"],
               goal_fraction_auc_observed=area / (len(fractions) - 1) if fraction_supported and len(fractions) > 1 else None,
               input_tokens=sum(e["input_tokens"] for e in usage), output_tokens=sum(e["output_tokens"] for e in usage),
               usage_complete=bool(counts["RUN_FINISHED"] and status.get("audit_passed")),
               message_sent=counts["MESSAGE_SENT"], message_delivered=counts["MESSAGE_DELIVERED"],
               message_failed=counts["MESSAGE_FAILED"], message_suppressed=counts["MESSAGE_SUPPRESSED"],
               active_edge_switches=counts["ACTIVE_EDGE_SWITCHED"], overlapping_membership=overlapping,
               topology_churn=max(0, sum(e["payload"].get("structural_change", False) for e in topology) - 1),
               local_no_delta_actions=counts["ACTION_NO_EFFECT"], elapsed_seconds=status.get("elapsed_seconds"))
    row["total_tokens"] = row["input_tokens"] + row["output_tokens"]
    return row


def analyze(output):
    manifest = json.loads((output / "manifest.json").read_text())
    rows = [summarize_case(case, output / case["case_id"]) for case in manifest["cases"]]
    # Output is a deterministic derived artifact; inputs and manifest are retained.
    with (output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    paired = []
    for left, right in [("P", "HA"), ("HA", "HR"), ("HR_projector_off", "HR")]:
        for task in manifest["spec"]["task_seed_pairs"]:
            a = next(r for r in rows if r["task"] == task["level"] and r["seed"] == task["seed"] and r["arm"] == left)
            b = next(r for r in rows if r["task"] == task["level"] and r["seed"] == task["seed"] and r["arm"] == right)
            eligible = a["terminal"] and b["terminal"]
            differences = {key: b[key] - a[key] if eligible and a[key] is not None and b[key] is not None else None
                           for key in ("task_success", "final_goal_fraction", "total_tokens", "message_delivered", "active_edge_switches")}
            paired.append(dict(task=task["level"], seed=task["seed"], contrast=f"{right} - {left}",
                               terminal_pair=eligible, both_infrastructure_passed=a["infrastructure_passed"] and b["infrastructure_passed"],
                               differences=differences))
    report = dict(planned_cases=len(rows), terminal_cases=sum(r["terminal"] for r in rows),
                  infrastructure_passed=sum(r["infrastructure_passed"] for r in rows), rows=rows, paired=paired,
                  limitations=["Exploratory: two seeds per task; no statistical significance claim.",
                               "Failures/timeouts are retained; unknown success is not imputed as success.",
                               "Tokens on censored runs are partial observed lower bounds.",
                               "Local no-delta is not proof of no global effect, nor a verified idle metric.",
                               "No workflow metadata: subtask VMCR and phase-transition quality are not estimated.",
                               "Gate is excluded; projector-off is not a matched realized-topology replay."])
    (output / "analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Analysis: {report['terminal_cases']}/{len(rows)} terminal; {output / 'summary.csv'}", flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["plan", "run", "analyze"])
    parser.add_argument("--output", required=True, type=lambda x: Path(x).resolve())
    parser.add_argument("--spec", type=lambda x: Path(x).resolve())
    parser.add_argument("--gate", type=lambda x: Path(x).resolve())
    args = parser.parse_args()
    if args.command == "plan":
        if not args.spec or not args.gate:
            parser.error("plan requires --spec and --gate")
        plan(args.spec, args.gate, args.output)
    elif args.command == "run":
        run(args.output)
    else:
        analyze(args.output)
