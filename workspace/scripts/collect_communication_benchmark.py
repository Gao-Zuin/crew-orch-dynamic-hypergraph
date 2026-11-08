"""Index existing benchmark artifacts without modifying original experiment logs."""
import argparse
import csv
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("level")
parser.add_argument("seed")
parser.add_argument("--algorithms", nargs="+", default=["Embodied", "CAMON", "ORCH"])
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
logs = root / "ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs"
out = root / "benchmark_runs" / f"communication_{args.level}_seed{args.seed}"
rows = []
for algorithm in args.algorithms:
    console = out / f"{algorithm}.log"
    if not console.exists():
        continue
    text = console.read_text(errors="replace")
    # Bind indexing to the timestamp recorded by this run, not an unrelated rerun.
    import re
    start = re.search(r"\[(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)[^\]]*\] starting", text)
    if not start:
        # Legacy runner logs omit the shell start line. Restrict to the first
        # Unity-connection minute; fail on ambiguity instead of selecting latest.
        start = re.search(r"\[(\d{4}-\d\d-\d\d) (\d\d):(\d\d):", text)
        if not start:
            raise ValueError(f"Missing run timestamp: {console}")
        earliest = "-".join((*start.groups(), "00"))
    else:
        earliest = "-".join(start.groups())
    candidates = sorted(p.parent for p in (logs / algorithm).glob(
        f"**/{args.level}/{args.seed}/*/data.csv") if p.parent.name >= earliest)
    if len(candidates) != 1:
        raise ValueError(f"Expected one result for {console}: {candidates}")
    result = candidates[0]
    with (result / "data.csv").open() as f:
        records = list(csv.DictReader(f))
    if not records:
        raise ValueError(f"No metrics: {result}")
    unity_candidates = list((logs / algorithm).glob(
        f"{args.level}/{args.seed}/*/{result.name}"))
    for category, target in [("results", result)] + [
        ("trajectories", p) for p in unity_candidates
    ]:
        link = out / category / algorithm
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            if link.resolve() != target.resolve():
                raise ValueError(f"Refusing to replace link: {link}")
        elif link.exists():
            raise ValueError(f"Refusing to replace existing file: {link}")
        else:
            link.symlink_to(os.path.relpath(target, link.parent))
    row = {"algorithm": algorithm, "run_complete": "TEST COMPLETE" in text,
           "logged_timesteps": len(records), **records[-1]}
    row["http_200_responses"] = text.count('"HTTP/1.1 200 OK"')
    row["error_lines"] = sum("error" in line.lower() for line in text.splitlines())
    row["png_count"] = sum(len(list(p.rglob("*.png"))) for p in unity_candidates)
    rows.append(row)
if rows:
    with (out / "summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(out / "summary.csv")
    for row in rows:
        print(row)
