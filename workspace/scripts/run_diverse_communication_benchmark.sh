#!/usr/bin/env bash
# Two distinct additional task families, paired across communication methods.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for task in Cut_Trees_Lines_small:9259 Suppress_Fire_Extinguish:1975; do
  export LEVEL="${task%:*}" SEED="${task#*:}" MAX_STEPS=5
  for method in Embodied CAMON ORCH; do
    # Resume only runs that have a successful process-completion marker.
    logfile="$ROOT/benchmark_runs/communication_${LEVEL}_seed${SEED}/${method}.log"
    if [[ -f "$logfile" ]] && rg -q '^TEST COMPLETE$' "$logfile"; then
      continue
    fi
    if [[ -f "$logfile" ]]; then
      echo "Existing incomplete log, inspect before rerunning: $logfile" >&2
      exit 1
    fi
    bash "$ROOT/scripts/run_small_communication_benchmark.sh" "$method"
  done
  "$ROOT/.conda/crew-orch/bin/python" "$ROOT/scripts/collect_communication_benchmark.py" "$LEVEL" "$SEED"
done
