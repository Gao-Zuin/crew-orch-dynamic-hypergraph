#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="$ROOT/.conda/crew-orch"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
GAME_ZIP="$ROOT/artifacts/game-build/Wildfire-StandaloneLinux64-Server.zip"
BUILD_DIR="$ROOT/ORCH/crew-dojo/Builds"
DATA_DIR="$ROOT/artifacts/benchmark/ORCH-dataset"
DATA_FILE="$DATA_DIR/result.tar.gz"
DATA_SIZE=30569754407

command -v conda >/dev/null
command -v git >/dev/null

if [[ ! -x "$ENV_PREFIX/bin/python" ]]; then
  conda create -p "$ENV_PREFIX" python=3.10.11 pip -y
fi

grep -v -E '^-e git\+https://github.com/generalroboticslab/CREW-Wildfire|^PyAudio==|^mlagents_envs @ git\+|^openai-whisper @ git\+' \
  "$ROOT/ORCH/crew-algorithms/requirements-full.txt" | "$ENV_PREFIX/bin/pip" install -i "$PIP_INDEX_URL" -r /dev/stdin
MLAGENTS_SRC="$ROOT/artifacts/ml-agents-src"
if [[ ! -d "$MLAGENTS_SRC/ml-agents-envs" ]]; then
  mkdir -p "$MLAGENTS_SRC"
  git -C "$MLAGENTS_SRC" init
  git -C "$MLAGENTS_SRC" config core.sparseCheckout true
  git -C "$MLAGENTS_SRC" config http.version HTTP/1.1
  git -C "$MLAGENTS_SRC" remote add origin https://github.com/lingyu98/ml-agents.git
  git -C "$MLAGENTS_SRC" sparse-checkout set ml-agents-envs
  git -C "$MLAGENTS_SRC" fetch --depth 1 --filter=blob:none origin 3c6692700e28332548ddf31b176d83e2953f6c01
  git -C "$MLAGENTS_SRC" checkout FETCH_HEAD
fi
"$ENV_PREFIX/bin/pip" install "$MLAGENTS_SRC/ml-agents-envs" --no-deps
"$ENV_PREFIX/bin/pip" install -i "$PIP_INDEX_URL" socksio
"$ENV_PREFIX/bin/pip" install -e "$ROOT/ORCH/crew-algorithms" --no-deps

mkdir -p "$(dirname "$GAME_ZIP")" "$BUILD_DIR" "$DATA_DIR"
if [[ ! -s "$GAME_ZIP" ]]; then
  "$ENV_PREFIX/bin/pip" install gdown
  "$ENV_PREFIX/bin/gdown" 1TPkYg6dqn1-BVt_Jr2bpITzqNsL_gxGO -O "$GAME_ZIP"
fi
if [[ ! -x "$BUILD_DIR/Wildfire-StandaloneLinux64-Server/Unity.x86_64" ]]; then
  unzip -q -o "$GAME_ZIP" -d "$BUILD_DIR"
  chmod +x "$BUILD_DIR/Wildfire-StandaloneLinux64-Server/Unity.x86_64"
fi

if [[ ! -f "$DATA_FILE" ]] || [[ "$(stat -c %s "$DATA_FILE")" -ne "$DATA_SIZE" ]]; then
  touch "$DATA_FILE"
  curl -fL --retry 10 --retry-all-errors -C - \
    https://huggingface.co/datasets/GeneralRoboticsLab/ORCH-dataset/resolve/20d097c0ceb75d5f59f60fba391eaaf0281315a7/result.tar.gz \
    -o "$DATA_FILE"
fi

"$ROOT/scripts/verify.sh"
