#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALGORITHMS="$ROOT/ORCH/crew-algorithms"
PYTHON="$ROOT/.conda/crew-orch/bin/python"
REDIRECT_SO="$ROOT/build/rootless_nakama_redirect.so"
KEY_FILE="${KEY_FILE:-/data/gzy/MAS/mindcraft/keys.json}"
LEVEL="${LEVEL:-Scout_Fire_small}"
SEED="${SEED:-4651}"
MODEL="${MODEL:-deepseek-chat}"
URL="${URL:-https://api.deepseek.com}"
MAX_STEPS="${MAX_STEPS:-3}"
RUN_LOG_ROOT="${RUN_LOG_ROOT:-$ROOT/benchmark_runs/communication_${LEVEL}_seed${SEED}}"
ACTIVE_PID=""

cleanup() {
  if [[ -n "$ACTIVE_PID" ]] && kill -0 "$ACTIVE_PID" 2>/dev/null; then
    kill -TERM "$ACTIVE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "$RUN_LOG_ROOT" "$ROOT/build"
if [[ ! -f "$REDIRECT_SO" ]]; then
  cc -shared -fPIC -O2 -Wall -Wextra \
    -o "$REDIRECT_SO" "$ROOT/scripts/rootless_nakama_redirect.c" -ldl
fi

API_KEY="$($PYTHON - "$KEY_FILE" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    print(json.load(f)["DEEPSEEK_API_KEY"])
PY
)"
export BASELINE_API_KEY="$API_KEY"
export ORCH_API_KEY="$API_KEY"
export CREW_BENCHMARK_MAX_STEPS="$MAX_STEPS"

orch_team_config() {
  case "$LEVEL" in
    Scout_Fire_small)
      printf '%s' '++envs.team_config={humans: [], managers: {4: {children: [1, 2, 3], type: "horizontal", team_name: "MAP_WIDE_FIRE_SEARCH_COORDINATION"}}}'
      ;;
    Transport_Firefighters_small)
      printf '%s' '++envs.team_config={humans: [], managers: {8: {children: [1, 2, 3, 4, 5, 6, 7], type: "vertical", team_name: "FIREFIGHTER_DEPLOYMENT_TRANSPORT"}}}'
      ;;
    Rescue_Civilians_Known_Location_small)
      printf '%s' '++envs.team_config={humans: [], managers: {4: {children: [1, 2, 3], type: "vertical", team_name: "CIVILIAN_EXTRACTION_TEAM"}}}'
      ;;
    Cut_Trees_Lines_small)
      printf '%s' '++envs.team_config={humans: [], managers: {4: {children: [3, 1, 2], type: "horizontal", team_name: "LINE_TREE_CLEARANCE_TEAM"}}}'
      ;;
    Suppress_Fire_Extinguish)
      printf '%s' '++envs.team_config={humans: [], managers: {9: {children: [1, 2, 3, 4, 5, 6, 7, 8], type: "vertical", team_name: "FIRE_SUPPRESSION_TEAM"}}}'
      ;;
    *)
      echo "No fixed ORCH team config is registered for level '$LEVEL'" >&2
      return 2
      ;;
  esac
}

run_one() {
  local algorithm="$1"
  shift
  local log_file="$RUN_LOG_ROOT/${algorithm}.log"
  echo "[$(date --iso-8601=seconds)] starting $algorithm ($LEVEL, seed=$SEED, max_steps=$MAX_STEPS)" | tee "$log_file"
  set +e
  (
    cd "$ALGORITHMS"
    env -u HTTP_PROXY -u http_proxy -u ALL_PROXY -u all_proxy \
      NO_PROXY="localhost,127.0.0.1,172.23.0.50" \
      no_proxy="localhost,127.0.0.1,172.23.0.50" \
      CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
      SDL_VIDEODRIVER=dummy \
      LD_PRELOAD="$REDIRECT_SO" \
      PYTHONPATH="$ALGORITHMS" \
      "$PYTHON" -m "crew_algorithms.wildfire_alg.algorithms.${algorithm}" \
        envs.level="$LEVEL" \
        envs.seed="$SEED" \
        envs.collaboration_mode=ai_control \
        envs.llm_model=custom \
        envs.model_name="$MODEL" \
        envs.llm_url="$URL" \
        envs.no_graphics=true \
        "$@"
  ) > >(tee -a "$log_file") 2>&1 &
  ACTIVE_PID=$!
  wait "$ACTIVE_PID"
  local status=$?
  ACTIVE_PID=""
  set -e
  if (( status != 0 )); then
    echo "[$(date --iso-8601=seconds)] failed $algorithm (exit=$status)" | tee -a "$log_file"
    return "$status"
  fi
  echo "[$(date --iso-8601=seconds)] finished $algorithm" | tee -a "$log_file"
}

case "${1:-all}" in
  Embodied|COELA|HMAS_2|CAMON)
    run_one "$1"
    ;;
  ORCH)
    run_one ORCH "$(orch_team_config)"
    ;;
  all)
    for algorithm in Embodied COELA HMAS_2 CAMON; do
      run_one "$algorithm"
    done
    run_one ORCH "$(orch_team_config)"
    ;;
  *)
    echo "usage: $0 [all|Embodied|COELA|HMAS_2|CAMON|ORCH]" >&2
    exit 2
    ;;
esac
