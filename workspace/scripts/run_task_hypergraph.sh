#!/usr/bin/env bash
# Task-stage hypergraph, independent of the archived spatial-policy campaigns.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CREW_HYPERGRAPH_ARM=HT
export CREW_HYPERGRAPH_INTERVENTION=none
export CREW_HYPERGRAPH_PROTOCOL_STRESS=0
export LEVEL="${LEVEL:-Transport_Firefighters_small}"
export SEED="${SEED:-283}"
export MAX_STEPS="${MAX_STEPS:-5}"
export RUN_LOG_ROOT="${RUN_LOG_ROOT:-$ROOT/benchmark_runs/task_hypergraph_${LEVEL}_seed${SEED}}"
export CREW_HYPERGRAPH_EVENT_PATH="$RUN_LOG_ROOT/events.jsonl"
if [[ -e "$RUN_LOG_ROOT" ]]; then
  echo "Existing run directory; refusing overwrite or automatic repeat: $RUN_LOG_ROOT" >&2
  exit 2
fi
# Keep the existing HTTPS proxy for model API traffic. The underlying runner's
# NO_PROXY already bypasses it for Unity/Nakama on localhost/private addresses.
exec bash "$ROOT/scripts/run_small_communication_benchmark.sh" Embodied
