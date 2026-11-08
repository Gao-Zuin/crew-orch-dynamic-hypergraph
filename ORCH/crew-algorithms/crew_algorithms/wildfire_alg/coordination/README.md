# 任务超图代码入口

当前任务超图：`SoftTaskGraph + SoftTaskPolicy`，由 `TaskRuntimeBridge` 接入既有 Embodied 循环。

```text
CREW_HYPERGRAPH_ARM=HT
  runtime.py: RuntimeBridge.from_environment
    task_runtime.py: TaskRuntimeBridge
      soft_task_graph.py: 结构、状态与路由
      soft_task_policy.py: LLM组织提案（初始任务/名单/leader报告）
      task_communication.py: 明确的组内消息与逐级报告
```

`hypergraph.py` 的 Coordinator、`crew_adapter.py` 的编码及检查、`runtime.py` 的共享基类仍被当前路线使用，不是可以随旧完整图一起删除的文件。

旧完整 `TaskHypergraph / LLMTaskPolicy` 已从本包移出，归档于 `CREW/research/legacy_full_task_graph/`。当前入口不会加载归档实现。旧空间模式只作历史兼容，不与HT实验混算。

完整说明：`CREW/research/task_hypergraph/README.md`。历史运行以各自manifest、frozen_sources.tar.gz和事件profile为准。

当前通信修订为HT-R2（task_hypergraph_reports_v2），不新增另一套图实现。协议与门禁/大任务进度见 CREW/research/bottom_up_reports/README.md 和 STATE.json。
