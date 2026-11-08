#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.conda/crew-orch/bin/python"
REDIRECT_SRC="$ROOT/scripts/rootless_nakama_redirect.c"
REDIRECT_SO="$ROOT/build/rootless_nakama_redirect.so"
ALGORITHMS="$ROOT/ORCH/crew-algorithms"

mkdir -p "$ROOT/build"
cc -shared -fPIC -O2 -Wall -Wextra -o "$REDIRECT_SO" "$REDIRECT_SRC" -ldl

cd "$ALGORITHMS"
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    -u http_proxy -u https_proxy -u all_proxy \
    CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
    SDL_VIDEODRIVER=dummy \
    LD_PRELOAD="$REDIRECT_SO" \
    PYTHONPATH="$ALGORITHMS" \
    "$PYTHON" -m crew_algorithms.wildfire_alg.algorithms.NOOP \
    envs.level="${LEVEL:-Scout_Fire_small}" \
    envs.seed="${SEED:-20261004}" \
    envs.collaboration_mode=ai_control \
    envs.no_graphics=true
