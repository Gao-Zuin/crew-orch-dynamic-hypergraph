# CREW → CREW-Wildfire → ORCH 复现工作区

本目录同时保留上游的三个阶段和一个部署集成仓库：

- `CREW-base/`：CREW 基础平台（Dojo + Algorithms）。
- `CREW-Wildfire/`：从 CREW fork 的 Wildfire benchmark 环境。
- `ORCH/`：ORCH 论文实验代码，包含 25 个论文任务、ORCH 与 CAMON/COELA/HMAS-2/Embodied baseline。
- `WILDFIRE-ORCH/`：官方网页、Docker/AWS 部署整合。
- `artifacts/game-build/`：官方 Linux Unity 可执行环境。
- `artifacts/benchmark/ORCH-dataset/`：论文完整实验结果集的下载目录（约 30.6 GB，`setup.sh` 支持断点续传）。

## 已配置环境

Conda 环境是工作区内的独立 prefix，不会覆盖机器上同名环境：

```bash
conda activate /data/gzy/selfevolve/CREW/.conda/crew-orch
cd /data/gzy/selfevolve/CREW/ORCH/crew-algorithms
```

重建/补齐资源：

```bash
bash /data/gzy/selfevolve/CREW/scripts/setup.sh
```

健康检查：

```bash
bash /data/gzy/selfevolve/CREW/scripts/verify.sh
```

## 运行 benchmark

`ORCH/crew-algorithms/run_ORCH.sh` 固化了论文 25 个 mission 及各自 5 个 seed；
`run_algorithm_baseline.sh` 运行 CAMON、COELA、HMAS-2 和 Embodied。先在脚本中设置 OpenAI-compatible 的 `MODEL`/`URL`/`API_KEY`，再运行：

```bash
cd /data/gzy/selfevolve/CREW/ORCH/crew-algorithms
bash run_ORCH.sh
bash run_algorithm_baseline.sh
```

无 LLM 的最小环境烟雾测试可用 `run_no-op.sh`。默认 runner 启用 `no_graphics=true`，因此不需要桌面，但 Unity build 仍需要系统的 X11/OpenGL 运行库。

## 无 sudo 的 rootless Docker

当前机器已经为 `gzy` 启用了 rootless Docker，不需要执行 `sudo usermod -aG docker gzy`。启动 Nakama/PostgreSQL：

```bash
bash /data/gzy/selfevolve/CREW/scripts/start_nakama_rootless.sh
```

官方 Unity build 内嵌了 rootful Docker 的 Nakama 地址 `172.23.0.50`。rootless 环境通过一个仅作用于 Unity 进程的 socket 兼容层转发到 `127.0.0.1`；原始 Unity 资源没有被修改。运行完整 NOOP smoke test：

```bash
bash /data/gzy/selfevolve/CREW/scripts/run_noop_rootless.sh
```

全局 HTTP/SOCKS 代理会拦截 Unity 的局域网请求，因此脚本只在实验子进程中取消代理变量。DeepSeek 端点在本机可以直连。

## 数据与版本

上游 commit 和数据集 revision 写在 `VERSIONS.txt`。官方数据集是论文历史运行结果，不是启动新实验的必需输入；新实验会写入 `ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/`。若只需运行 benchmark，可不等待这个历史结果包；重新执行 `setup.sh` 会从已下载字节继续。

Docker 部署配置在 `WILDFIRE-ORCH/deploy/`；Nakama 的 rootless compose 服务当前使用 `/run/user/1021/docker.sock`。

## 本地任务超图扩展

当前路线为 `SoftTaskGraph + SoftTaskPolicy + TaskRuntimeBridge`，复用 Embodied 决策循环。模块关系、现有边界、实验和审计入口见 [当前任务超图](research/task_hypergraph/README.md)。旧完整任务阶段超图已[归档](research/legacy_full_task_graph/README.md)，不参与当前运行或默认测试。清理记录见 [2026-10-28 清理报告](research/legacy_full_task_graph/CLEANUP_REPORT.md)。
