"""Run a finite, serial batch from an isolated source snapshot; never retry cases."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("transport_seed2461", "Transport_Firefighters_small", 2461, 15),
    ("second_fire_seed137", "Suppress_Fire_Extinguish_Second_Fire", 137, 100),
    ("second_fire_seed256", "Suppress_Fire_Extinguish_Second_Fire", 256, 100),
]


def now():
    return datetime.now().astimezone().isoformat()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    temporary.replace(path)


def capture_unity_logs(workspace, output):
    """Preserve native logs before the next Unity instance overwrites them."""
    source = workspace / "ORCH/UnityLogs"
    destination = output / "unity_logs"
    files = sorted(source.glob("*.log"))
    if not files:
        return {"logs_available": False, "exception_count": None}
    destination.mkdir(parents=True, exist_ok=False)
    for file in files:
        shutil.copy2(file, destination / file.name)
    player = destination / "Player-0.log"
    lines = player.read_text(errors="replace").splitlines() if player.exists() else []
    exceptions = [line for line in lines if "Exception:" in line]
    return {"logs_available": player.exists(), "exception_count": len(exceptions),
            "exception_headings": exceptions, "directory": str(destination)}


def prepare(batch, cases, build=None):
    selected_build = (build or ROOT / "ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server").resolve()
    assembly = selected_build / "Unity_Data/Managed/Assembly-CSharp.dll"
    if not (selected_build / "Unity.x86_64").is_file() or not assembly.is_file():
        raise ValueError("selected build must contain the executable and managed assembly")
    batch.mkdir(parents=True, exist_ok=False)
    workspace = batch / "workspace"
    workspace.mkdir()
    for name in ("scripts", "tests"):
        shutil.copytree(ROOT / name, workspace / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "ORCH/crew-algorithms", workspace / "ORCH/crew-algorithms",
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "outputs",
                                                  "experiment_logs", "UnityLogs", "*.pyc"))
    (workspace / ".conda").mkdir()
    (workspace / ".conda/crew-orch").symlink_to(ROOT / ".conda/crew-orch")
    (workspace / "ORCH/crew-dojo").mkdir()
    (workspace / "ORCH/crew-dojo/Builds").mkdir()
    (workspace / "ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server").symlink_to(selected_build)
    (workspace / "build").mkdir()
    shutil.copy2(ROOT / "build/rootless_nakama_redirect.so", workspace / "build")
    write(batch / "plan.json", {
        "created": now(), "implementation": "SoftTaskGraph isolated snapshot; per-run source hashes are authoritative",
        "build": str(selected_build),
        "assembly_sha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
        "model": "deepseek-chat", "fixed_groups": False,
        "event_schedule": "original preset; no overrides or artificial initial graph",
        "cases": [dict(id=i, level=l, seed=s, steps=n) for i, l, s, n in cases],
        "comparison": "exploratory new trajectories; not a causal pre/post comparison",
        "source_snapshot": str(workspace),
        "stop": "stop after infrastructure/audit/source-integrity failure; retain task failures; no retry",
    })


def run(batch):
    workspace = batch / "workspace"
    progress = {"started": now(), "pid": os.getpid(), "state": "running", "completed": []}
    write(batch / "progress.json", progress)
    env = os.environ.copy()
    for key in ("CREW_HT_FIXED_GROUPS", "CREW_HT_INITIAL_PLAN_PATH", "CREW_HT_REGROUP_PATH",
                "CREW_HT_REGROUP_STEP", "CREW_HYPERGRAPH_SCHEDULED_EVENTS_JSON"):
        env.pop(key, None)
    try:
        plan = json.loads((batch / "plan.json").read_text())
        for entry in plan["cases"]:
            case, level, seed, steps = (entry[k] for k in ("id", "level", "seed", "steps"))
            output = batch / "runs" / case
            progress.update(current=case, updated=now())
            write(batch / "progress.json", progress)
            command = [sys.executable, str(workspace / "scripts/run_task_hypergraph_smoke.py"),
                       str(output), "--level", level, "--seed", str(seed),
                       "--steps", str(steps), "--timeout", "18000"]
            print(now(), "START", case, flush=True)
            result = subprocess.run(command, env=env, cwd=workspace)
            status = json.loads((output / "status.json").read_text()) if (output / "status.json").exists() else {}
            summary = {"id": case, "returncode": result.returncode, "status": status}
            summary["native_engine"] = capture_unity_logs(workspace, output)
            if (output / "audit.json").exists():
                audit = json.loads((output / "audit.json").read_text())
                summary["last_validation"] = audit.get("last_validation")
            # Save detailed graph/worker traces only after the run is complete.
            if (output / "run/events.jsonl").exists():
                from importlib.util import module_from_spec, spec_from_file_location
                script = ROOT / "research/task_hypergraph/audit_dynamic_runs.py"
                spec = spec_from_file_location("dynamic_run_audit", script)
                module = module_from_spec(spec)
                spec.loader.exec_module(module)
                inventory, detail = module.inspect(output)
                write(output / "behavior_summary.json", inventory)
                write(output / "behavior_detail.json", detail)
                summary["behavior"] = inventory
            progress["completed"].append(summary)
            progress["updated"] = now()
            write(batch / "progress.json", progress)
            healthy = (result.returncode == 0 and status.get("run_finished") and
                       status.get("mechanism_audit_passed") and status.get("frozen_sources_unchanged"))
            if not healthy:
                progress["state"] = "stopped_for_review"
                break
        else:
            progress["state"] = "completed_pending_analysis"
    except Exception as error:
        progress.update(state="supervisor_error", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        progress["updated"] = now()
        write(batch / "progress.json", progress)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("start", "run"))
    parser.add_argument("batch", type=Path)
    parser.add_argument("--cases", nargs="+", choices=[case[0] for case in CASES])
    parser.add_argument("--build", type=Path, help="explicit independent Unity build; recorded in plan and run manifests")
    args = parser.parse_args()
    batch = args.batch.resolve()
    if args.mode == "run":
        run(batch)
        return
    cases = [case for case in CASES if args.cases is None or case[0] in args.cases]
    prepare(batch, cases, args.build)
    write(batch / "progress.json", {"state": "launching", "created": now(), "completed": []})
    with (batch / "batch.log").open("x") as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "run", str(batch)],
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    write(batch / "supervisor.json", {"pid": child.pid, "started": now()})
    print(json.dumps({"batch": str(batch), "pid": child.pid}), flush=True)


if __name__ == "__main__":
    main()
