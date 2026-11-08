"""Wait for the existing large-team check, then freeze/archive/run exactly once."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True, type=lambda s: Path(s).resolve())
    parser.add_argument("--gate-pid", required=True, type=int)
    parser.add_argument("--spec", required=True, type=lambda s: Path(s).resolve())
    parser.add_argument("--output", required=True, type=lambda s: Path(s).resolve())
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    lock = args.spec.parent / "launch_status.json"
    with lock.open("x") as stream:
        json.dump({"phase": "waiting_for_checks", "pid": os.getpid(), "gate_pid": args.gate_pid}, stream)
    deadline = time.monotonic() + 3000
    while not (args.gate / "audit.json").exists():
        command_path = Path(f"/proc/{args.gate_pid}/cmdline")
        if not command_path.exists() or b"run_hypergraph_gate.py" not in command_path.read_bytes():
            raise RuntimeError("Check process exited without final audit; inspect gate artifacts")
        if time.monotonic() >= deadline:
            raise TimeoutError("Waiting for existing checks exceeded 3000 seconds")
        time.sleep(5)
    report = json.loads((args.gate / "audit.json").read_text())
    if not report["passed"]:
        raise RuntimeError("Large-team checks failed; no formal campaign launched")
    subprocess.run([sys.executable, str(ROOT / "scripts/hypergraph_campaign.py"), "plan",
                    "--spec", str(args.spec), "--gate", str(args.gate), "--output", str(args.output)], check=True)
    manifest = json.loads((args.output / "manifest.json").read_text())
    archive = args.output / "frozen_sources.tar.gz"
    subprocess.run(["tar", "-czf", str(archive), "-C", str(ROOT), "--",
                    *sorted(manifest["source_sha256"])], check=True)
    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with (args.output / "archive_record.json").open("x") as stream:
        json.dump({"sha256": archive_digest, "files": len(manifest["source_sha256"])}, stream, indent=2)
    with lock.open("w") as stream:
        json.dump({"phase": "campaign_started", "pid": os.getpid(), "output": str(args.output),
                   "archive_sha256": archive_digest}, stream, indent=2)
    print("Large-team checks passed; formal campaign starting", flush=True)
    os.execv(sys.executable, [sys.executable, str(ROOT / "research/tools/expanded_campaign.py"), str(args.output)])


if __name__ == "__main__":
    main()
