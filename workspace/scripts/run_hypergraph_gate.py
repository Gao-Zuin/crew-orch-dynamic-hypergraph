"""Frozen infrastructure gate. Does not contribute to efficacy estimates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from audit_hypergraph_run import audit


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def stop_group(process):
    # Only the new process group created for THIS invocation is targeted.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--large-teams", action="store_true", help="Check actual 10/14/15-agent environments")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    algorithms = root / "ORCH/crew-algorithms/crew_algorithms/wildfire_alg"
    files = list(algorithms.rglob("*.py"))
    files += list((algorithms / "algorithms/Embodied/prompts").rglob("*.txt"))
    files += list((algorithms.parent / "conf").rglob("*.yaml"))
    files += [root / "scripts/run_small_communication_benchmark.sh", Path(__file__).resolve(),
              root / "scripts/audit_hypergraph_run.py", root / "tests/test_hypergraph.py",
              root / "build/rootless_nakama_redirect.so"]
    hashes = {str(p.relative_to(root)): digest(p) for p in sorted(files)}
    cases = [dict(id="P_scout", arm="P", level="Scout_Fire_small", seed=4651),
             dict(id="HA_scout", arm="HA", level="Scout_Fire_small", seed=4651),
             dict(id="HR_transport", arm="HR", level="Transport_Firefighters_small", seed=283)]
    if args.large_teams:
        cases = [dict(id="P_cut10", arm="P", level="Cut_Trees_Sparse_large", seed=212, agent_count=10),
                 dict(id="HA_transport14", arm="HA", level="Transport_Firefighters_large", seed=741, agent_count=14),
                 dict(id="HR_full15", arm="HR", level="Full_Game", seed=6434, agent_count=15)]
    manifest = dict(version=6, suite="infrastructure_gate_only", max_steps=2,
                    model="deepseek-chat", url="https://api.deepseek.com", timeout=args.timeout,
                    cases=cases, source_sha256=hashes,
                    rationale="launch, baseline parity, post-action truth, overlap/routing, cleanup; not efficacy")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    results = []
    for case in cases:
        if any(digest(root / p) != sha for p, sha in hashes.items()):
            raise RuntimeError("Behavior source changed after freeze; create a new gate version")
        directory = output / case["id"]
        directory.mkdir()
        env = os.environ.copy()
        env.update(CREW_HYPERGRAPH_ARM=case["arm"],
                   CREW_HYPERGRAPH_EVENT_PATH=str(directory / "events.jsonl"),
                   CREW_HYPERGRAPH_INTERVENTION="none", CREW_HYPERGRAPH_PROTOCOL_STRESS="0",
                   RUN_LOG_ROOT=str(directory), LEVEL=case["level"], SEED=str(case["seed"]),
                   MAX_STEPS="2", MODEL=manifest["model"], URL=manifest["url"])
        print(f"Starting {case['id']}", flush=True)
        with (directory / "controller.log").open("w") as log:
            process = subprocess.Popen(["bash", str(root / "scripts/run_small_communication_benchmark.sh"), "Embodied"],
                                       env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + args.timeout
            error = None
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline:
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
            finally:
                stop_group(process)
        if error or process.returncode:
            result = dict(passed=False, failures=[error or f"exit={process.returncode}"])
        else:
            result = audit(directory / "events.jsonl")
        if case["arm"] == "HR" and not result.get("overlapping_membership_observed"):
            result["passed"] = False
            result.setdefault("failures", []).append("no overlapping membership observed")
        if case.get("agent_count") and result.get("passed"):
            events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
            observed_count = len({e["agent_id"] for e in events if e["event_type"] == "NODE_JOINED"})
            result["observed_agent_count"] = observed_count
            if observed_count != case["agent_count"]:
                result["passed"] = False
                result.setdefault("failures", []).append(f"agent count {observed_count} != {case['agent_count']}")
        (directory / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
        results.append(dict(case=case, audit=result))
        print(f"Finished {case['id']}: passed={result['passed']}", flush=True)
    (output / "audit.json").write_text(json.dumps(dict(passed=all(r["audit"]["passed"] for r in results),
                                                      results=results), indent=2) + "\n")
    return 0 if all(r["audit"]["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
