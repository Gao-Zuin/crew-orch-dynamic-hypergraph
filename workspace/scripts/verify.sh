#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.conda/crew-orch/bin/python"
UNITY="$ROOT/ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server/Unity.x86_64"

for repo in CREW-base CREW-Wildfire ORCH WILDFIRE-ORCH; do
  git -C "$ROOT/$repo" rev-parse --verify HEAD >/dev/null
done
test -x "$PYTHON"
test -x "$UNITY"
DATA_FILE="$ROOT/artifacts/benchmark/ORCH-dataset/result.tar.gz"
DATA_SIZE="$(stat -c %s "$DATA_FILE" 2>/dev/null || echo 0)"
if [[ "${REQUIRE_DATASET:-0}" == "1" ]]; then
  test "$DATA_SIZE" -eq 30569754407
fi

PYTHONPATH="$ROOT/ORCH/crew-algorithms" "$PYTHON" - <<'PY'
import hydra, numpy, openai, torch, torchrl
from crew_algorithms.wildfire_alg.config.build_config import create_level_presets
from crew_algorithms.wildfire_alg.algorithms.ORCH.agent import Agent

presets = create_level_presets()
paper = {
    "Cut_Trees_Sparse_small", "Scale_Level_Complex",
    "Suppress_Fire_Extinguish_Rapid_Growth",
}
assert paper <= presets.keys()
print(f"Python imports OK; {len(presets)} environment presets found")
PY

echo "Unity build: $UNITY"
echo "ORCH dataset: $DATA_FILE ($DATA_SIZE / 30569754407 bytes)"
echo "Verification passed"
