"""Freeze and supervise one real task-hypergraph pilot; never overwrite/retry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]


def write_new(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--level", default="Transport_Firefighters_small")
    parser.add_argument("--seed", type=int, default=283)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--scheduled-events-json", help="diagnostic event schedule override; saved in manifest")
    parser.add_argument("--fixed-groups", action="store_true")
    parser.add_argument("--initial-plan-path", type=Path)
    parser.add_argument("--regroup-path", type=Path)
    parser.add_argument("--regroup-step", type=int)
    args = parser.parse_args()
    if (args.regroup_path or args.regroup_step is not None) and not args.fixed_groups:
        parser.error("manual regroup requires --fixed-groups")
    if bool(args.regroup_path) != (args.regroup_step is not None):
        parser.error("--regroup-path and --regroup-step must be supplied together")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    case = output / "run"
    package = ROOT / "ORCH/crew-algorithms/crew_algorithms/wildfire_alg"
    paths = [p for p in package.rglob("*") if p.is_file() and p.suffix in {".py", ".txt", ".json", ".yaml"} and "results" not in p.parts]
    paths += [Path(__file__).resolve(), ROOT / "scripts/run_task_hypergraph.sh", ROOT / "scripts/run_small_communication_benchmark.sh",
              ROOT / "scripts/audit_task_hypergraph.py",
              ROOT / "tests/test_soft_task_graph.py", ROOT / "tests/test_task_runtime.py"]
    manifest = {"level": args.level, "seed": args.seed, "max_steps": args.steps,
                "timeout_seconds": args.timeout, "arm": "HT",
                "model": os.environ.get("MODEL") or "deepseek-chat", "temperature": 0,
                "fixed_groups": args.fixed_groups,
                "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    for key, path in (("initial_plan", args.initial_plan_path), ("regroup", args.regroup_path)):
        if path:
            manifest[key] = {"path": str(path.resolve()),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "content": json.loads(path.read_text())}
    if args.scheduled_events_json:
        scheduled_events = json.loads(args.scheduled_events_json)
        if not isinstance(scheduled_events, list) or not all(isinstance(event, dict) for event in scheduled_events):
            raise ValueError("scheduled events must be a JSON list of objects")
        manifest["diagnostic_scheduled_events_override"] = scheduled_events
    build = ROOT / "ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server"
    manifest["environment_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in build.rglob("*") if p.is_file() and p.suffix != ".log" and
        p.relative_to(build).parts[:3] != ("Unity_Data", "ML-Agents", "Timers")}
    write_new(output / "manifest.json", manifest)
    with tarfile.open(output / "frozen_sources.tar.gz", "w:gz") as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    env = os.environ.copy()
    env.update(LEVEL=args.level, SEED=str(args.seed), MAX_STEPS=str(args.steps), RUN_LOG_ROOT=str(case))
    if args.fixed_groups:
        env["CREW_HT_FIXED_GROUPS"] = "1"
    if args.initial_plan_path:
        env["CREW_HT_INITIAL_PLAN_PATH"] = str(args.initial_plan_path.resolve())
    if args.regroup_path:
        env["CREW_HT_REGROUP_PATH"] = str(args.regroup_path.resolve())
        env["CREW_HT_REGROUP_STEP"] = str(args.regroup_step)
    if args.scheduled_events_json:
        env["CREW_HYPERGRAPH_SCHEDULED_EVENTS_JSON"] = args.scheduled_events_json
    started = time.monotonic()
    with (output / "supervisor.log").open("x") as log:
        process = subprocess.Popen(["bash", str(ROOT / "scripts/run_task_hypergraph.sh")], env=env,
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write_new(output / "process.json", {"supervisor_pid": os.getpid(), "pid": process.pid})
        interrupted = []
        def terminate(signum, frame):
            if signum is not None:
                interrupted.append(signum)
            # Stop only this pilot's validated process group and descendants.
            from architecture_comparison import cleanup
            cleanup(process.pid)
        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)
        error = None
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            terminate(None, None)
            error = "timeout"
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    events = []
    event_path = case / "events.jsonl"
    if event_path.exists():
        for line in event_path.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                break
    finished = next((e for e in reversed(events) if e["event_type"] == "RUN_FINISHED"), None)
    commits = [e for e in events if e["event_type"] == "TASK_GRAPH_COMMITTED"]
    handoffs = [e for e in events if e["event_type"] == "TASK_EDGE_HANDOFF"]
    status = {"exit_code": code, "error": error, "elapsed_seconds": time.monotonic() - started,
              "run_finished": finished is not None, "graph_commits": len(commits), "handoffs": len(handoffs),
              "authorized_actions": sum(e["event_type"] == "TASK_ACTION_AUTHORIZED" for e in events),
              "held_actions": sum(e["event_type"] == "TASK_ACTION_HELD" for e in events),
              "proposal_rejections": sum(e["event_type"] == "TASK_PROPOSAL_REJECTED" for e in events)}
    if interrupted:
        status["error"] = "interrupted"
    mismatches = [str(p.relative_to(ROOT)) for p in paths if hashlib.sha256(p.read_bytes()).hexdigest() != manifest["source_sha256"][str(p.relative_to(ROOT))]]
    status["frozen_sources_unchanged"] = not mismatches
    if mismatches:
        status["source_mismatches"] = mismatches
    if finished:
        status["usage"] = finished["payload"]
    if event_path.exists():
        from audit_task_hypergraph import audit
        result = audit(event_path)
        write_new(output / "audit.json", result)
        status["mechanism_audit_passed"] = result["passed"]
        from hypergraph_campaign import index_artifacts
        index_artifacts(case)
    write_new(output / "status.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    main()
