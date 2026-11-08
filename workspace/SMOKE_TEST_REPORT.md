# Smoke test report (2026-10-04)

## Passed

- Python/ORCH imports passed; 30 environment presets loaded.
- Unity executable and shared libraries are present; `ldd` reports no missing dependencies.
- Rootless Docker 27.3.1 is active for user `gzy` at `/run/user/1021/docker.sock`; no `docker` group membership or sudo was used.
- PostgreSQL 12.2 and Nakama 3.15.0 built and started successfully. Nakama loaded `backend.so`, registered all seven RPC functions, reached `healthy`, and returned HTTP 200 on port 7350.
- DeepSeek API passed with `deepseek-chat` via `https://api.deepseek.com`. The key was read at runtime from `/data/gzy/MAS/mindcraft/keys.json`; it was not copied into this workspace or printed.
- ORCH team-structure generation passed for `Scout_Fire_small`, producing a valid horizontal manager over three drone workers.
- Full NOOP Unity/ML-Agents run passed for `Scout_Fire_small`, seed `20261004`: protocol 1.5.0 connected, all 30 timesteps ran, and the process ended with `TEST COMPLETE`.
- Real ORCH + DeepSeek integration passed through timestep 4 for `Scout_Fire_small`, seed `20261006`: manager/worker hierarchy creation, observations, parallel DeepSeek calls (HTTP 200), task assignment, option generation, action translation, Unity stepping, and next-step observations all succeeded. The smoke run was then stopped intentionally to limit API cost.

NOOP artifacts are under `ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/NOOP/Scout_Fire_small/20261004/`. DeepSeek ORCH artifacts are under `ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/ORCH/deepseek-chat/preset/Scout_Fire_small/20261006/`.

## Compatibility fixes applied

- Generated the Go module/vendor tree expected by the upstream Nakama Dockerfile and used a Go directive accepted by its Go 1.19 plugin builder.
- Added `scripts/rootless_nakama_redirect.c`: the released Unity build expects Nakama at the rootful bridge address `172.23.0.50`; the preload shim redirects only that IPv4/IPv4-mapped-IPv6 destination to the rootless published ports on loopback. Original Unity assets remain unchanged.
- Removed the obsolete import-time `QWEN_API_KEY` requirement from `core/gpt.py`; its legacy synchronous client is now initialized lazily from the selected ORCH provider.
- Added repeatable rootless service and NOOP runners in `scripts/start_nakama_rootless.sh` and `scripts/run_noop_rootless.sh`.

## Known upstream issue

`Cut_Trees_Sparse_small` passes `FireSpreadSpeed=0`; the released Unity build then reports `DivideByZeroException` in `Examples.Wildfire.MapManager.FixedUpdate()`. `Scout_Fire_small` is the validated smoke-test preset.

The historical ORCH result archive is still a resumable partial download. It is not required for new benchmark runs.
