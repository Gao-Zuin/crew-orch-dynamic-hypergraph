#!/usr/bin/env bash
# One reproducible ORCH HT cell. Set D=0/1, R=0/1, ARM=fixed/adaptive.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
D="${D:?set D=0 or 1}"
R="${R:?set R=0 or 1}"
ARM="${ARM:?set ARM=fixed or adaptive}"
case "$D:$R" in 0:0|0:1|1:0|1:1) ;; *) echo "D and R must be 0 or 1" >&2; exit 2;; esac
case "$ARM" in fixed) export CREW_HT_FIXED_GROUPS=1;; adaptive) export CREW_HT_FIXED_GROUPS=0;; *) echo "ARM must be fixed or adaptive" >&2; exit 2;; esac
FAMILY="${FAMILY:-structure}"
case "$FAMILY" in structure) PREFIX=Structure;; composite) PREFIX=Composite;; *) echo "FAMILY must be structure or composite" >&2; exit 2;; esac
export CREW_RESOURCE_SCHEDULING_FAMILY="$FAMILY"
export CREW_HT_STRUCTURAL_INITIAL_PLAN=1
export CREW_HT_ROUND_DELIVERY="${CREW_HT_ROUND_DELIVERY:-1}"
export CREW_HT_LOCAL_EVENT_INFO="${CREW_HT_LOCAL_EVENT_INFO:-1}"
export LEVEL="${PREFIX}_D${D}_R${R}"
export SEED="${SEED:-42}"
export MAX_STEPS="${MAX_STEPS:-100}"
export RUN_LOG_ROOT="${RUN_LOG_ROOT:-$ROOT/benchmark_runs/${FAMILY}_matrix/${LEVEL}_seed${SEED}_${ARM}_local${CREW_HT_LOCAL_EVENT_INFO}}"
if [[ "$MAX_STEPS" -lt 9 && "$D" == 1 ]]; then
  echo "Dynamic cell needs at least 9 steps to submit the event" >&2
  exit 2
fi
exec bash "$ROOT/scripts/run_task_hypergraph.sh"
