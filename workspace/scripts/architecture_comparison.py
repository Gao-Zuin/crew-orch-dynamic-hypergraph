"""Frozen, serial four-architecture comparison with independent smoke checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "ORCH/crew-algorithms"
CASES = [("Embodied", "P"), ("CAMON", None), ("ORCH", None), ("Hypergraph", "HR")]


def hydra_value(value):
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {hydra_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(hydra_value(v) for v in value) + "]"
    return json.dumps(value)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def summarize(directory):
    events = [json.loads(line) for line in (directory / "observer.jsonl").read_text().splitlines()]
    states = [e["payload"] for e in events if e["event_type"] == "STATE"]
    usage = [e["payload"].get("usage") for e in events if e["event_type"] == "LLM_RESPONSE"]
    return {"steps": max((s["step"] for s in states), default=0),
            "initial_rewards": states[0]["rewards"] if states else None,
            "final_rewards": states[-1]["rewards"] if states else None,
            "agent_count": len(states[0]["agents"]) if states else None,
            "task_success": any(s["task_success"] for s in states) if states else None,
            "returned_calls": len(usage), "missing_usage_calls": sum(u is None for u in usage),
            "tokens": sum(u.get("total_tokens", 0) for u in usage if u)}


def run_case(output, name, arm, steps, timeout, team):
    directory = output / name
    directory.mkdir()
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("CREW_HYPERGRAPH_") or key.lower() in ("http_proxy", "https_proxy", "all_proxy"):
            env.pop(key)
    key = json.loads(Path("/data/gzy/MAS/mindcraft/keys.json").read_text())["DEEPSEEK_API_KEY"]
    env.update(BASELINE_API_KEY=key, ORCH_API_KEY=key, CREW_BENCHMARK_MAX_STEPS=str(steps),
               ARCH_OBSERVER_PATH=str(directory / "observer.jsonl"), SDL_VIDEODRIVER="dummy",
               CUDA_VISIBLE_DEVICES="0", LD_PRELOAD=str(ROOT / "build/rootless_nakama_redirect.so"),
               PYTHONPATH=str(PACKAGE), NO_PROXY="localhost,127.0.0.1,172.23.0.50",
               no_proxy="localhost,127.0.0.1,172.23.0.50")
    if arm:
        env.update(CREW_HYPERGRAPH_ARM=arm, CREW_HYPERGRAPH_INTERVENTION="none", CREW_HYPERGRAPH_PROTOCOL_STRESS="0",
                   CREW_HYPERGRAPH_EVENT_PATH=str(directory / "hypergraph_events.jsonl"))
    algorithm = "Embodied" if arm else name
    command = [sys.executable, str(ROOT / "scripts/observe_architecture.py"), algorithm,
               "envs.level=Cut_Trees_Sparse_large", "envs.seed=212", "envs.collaboration_mode=ai_control",
               "envs.llm_model=custom", "envs.model_name=deepseek-chat", "envs.llm_url=https://api.deepseek.com",
               "envs.no_graphics=true"]
    if name == "ORCH":
        command.append("++envs.team_config=" + hydra_value(team))
    start = time.monotonic()
    print(f"Starting {name}, {steps} steps", flush=True)
    with (directory / "console.log").open("x") as log:
        process = subprocess.Popen(command, cwd=PACKAGE, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write(directory / "process.json", {"pid": process.pid, "supervisor_pid": os.getpid(), "command": command})
        error = None
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            error, code = "timeout", None
        finally:
            # Unity starts its own session. Terminate descendants as well as the process group.
            subprocess.run([sys.executable, str(ROOT / "scripts/architecture_comparison.py"), "cleanup", str(process.pid)], check=True)
    try:
        result = summarize(directory)
    except (OSError, ValueError, KeyError) as exc:
        result = {"observation_error": str(exc)}
    result.update(exit_code=code, error=error, elapsed_seconds=time.monotonic() - start)
    result["audit_passed"] = code == 0 and "TEST COMPLETE" in (directory / "console.log").read_text() and result.get("agent_count") == 10 and result.get("steps", 0) > 0 and result.get("missing_usage_calls") == 0
    write(directory / "status.json", result)
    print(f"Finished {name}: {result}", flush=True)
    return result["audit_passed"]


def cleanup(pid):
    parents = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
            parents[int(path.parent.name)] = int(fields[1])
        except (OSError, ValueError):
            pass
    owned = {pid}
    while True:
        extra = {p for p, parent in parents.items() if parent in owned} - owned
        if not extra:
            break
        owned.update(extra)
    for target in reversed(sorted(owned)):
        try:
            os.kill(target, signal.SIGTERM)
        except ProcessLookupError:
            pass


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "cleanup":
        cleanup(int(sys.argv[2]))
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=False, parents=True)
    presets = json.loads((PACKAGE / "crew_algorithms/wildfire_alg/experiment_presets_backup.json").read_text())
    hierarchy = presets["Cut_Trees_Sparse_large"]["hierarchy"]["config"]
    team = {"humans": [], "managers": {int(k.split("_")[1]): {**v, "children": [int(c.split("_")[1]) for c in v["children"]]} for k, v in hierarchy.items()}}
    paths = [p for p in (PACKAGE / "crew_algorithms").rglob("*") if p.is_file() and p.suffix in (".py", ".txt", ".yaml", ".json") and "results" not in p.parts]
    paths += [Path(__file__).resolve(), ROOT / "scripts/observe_architecture.py", ROOT / "build/rootless_nakama_redirect.so"]
    build = ROOT / "ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server"
    build_paths = [p for p in build.rglob("*") if p.is_file() and p.suffix != ".log" and p.relative_to(build).parts[:3] != ("Unity_Data", "ML-Agents", "Timers")]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    environment_hashes = {str(p.relative_to(ROOT)): digest(p) for p in build_paths}
    write(output / "manifest.json", {"cases": CASES, "level": "Cut_Trees_Sparse_large", "seed": 212,
          "steps": 20, "timeout_seconds": 6000, "model": "deepseek-chat", "temperature": 0,
          "team_config": team, "source_sha256": hashes, "environment_sha256": environment_hashes,
          "comparison": "equal 20 environment steps; common 6000s safety timeout; wall time and all manager tokens measured, not equal token budgets"})
    with tarfile.open(output / "frozen_sources.tar.gz", "w:gz") as archive:
        for path in paths:
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    for phase, steps, timeout in (("checks", 2, 900), ("experiments", 20, 6000)):
        directory = output / phase
        directory.mkdir()
        for name, arm in CASES:
            if any(digest(ROOT / p) != sha for p, sha in hashes.items()):
                raise RuntimeError("Frozen source changed")
            passed = run_case(directory, name, arm, steps, timeout, team)
            if phase == "checks" and not passed:
                write(output / "stopped.json", {"reason": "runtime check failed", "case": name})
                return
    write(output / "completed.json", {"completed": True})


if __name__ == "__main__":
    main()
