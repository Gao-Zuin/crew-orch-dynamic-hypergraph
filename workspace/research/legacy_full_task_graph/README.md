# 已归档：旧完整任务阶段超图

本目录保存旧 `TaskHypergraph + LLMTaskPolicy`，用于历史轨迹审计与实现参考。它不在当前算法包内，不由 `HT` 入口加载，也不属于当前默认测试集。

当前实现入口见 [任务超图说明](../task_hypergraph/README.md)。归档于 2026-10-28；原源码、脚本和测试的原始路径与字节内容保存在 `original_sources.tar.gz`，校验值见 `manifest.json`。本目录模块的行为未修改，仅调整工具/测试导入路径。

## 内容

- `task_hypergraph.py`、`task_policy.py`：旧结构、生命周期与组织/审查策略。
- `audit.py`：旧完整图的离线审计器，不依赖当前轻量图。
- `test_task_hypergraph.py`：旧实现离线测试，需显式运行。
- `replay_task_event_decision.py`：旧组织器的模型诊断回放；会调用 API，清理验证没有执行该回放。
- `HISTORICAL_NOTES.md`：原研究说明，包含历史行为与原路径。它不是当前运行文档，其中旧运行命令不能用于选择本归档实现。

## 离线使用

从 CREW 根目录执行：

```bash
.conda/crew-orch/bin/python research/legacy_full_task_graph/audit.py \
  benchmark_runs/task_hypergraph_second_fire_early_v5/run/events.jsonl

.conda/crew-orch/bin/python -m unittest discover \
  -s research/legacy_full_task_graph -p 'test_task_hypergraph.py'
```

历史实验目录、事件、指标、冻结源码包保持原样。归档代码不表示恢复了旧方法，也不实现新讨论的报告驱动重组、多重职责协调或自适应注意力。
