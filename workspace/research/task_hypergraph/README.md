# 当前任务超图：SoftTaskGraph

唯一的当前任务超图运行路线是：

```text
Embodied.__main__
  → RuntimeBridge.from_environment（CREW_HYPERGRAPH_ARM=HT）
  → TaskRuntimeBridge
  → SoftTaskGraph + SoftTaskPolicy
```

这里的 `TaskRuntimeBridge` 是当前轻量图的接线代码，文件名 `task_runtime.py` 不代表旧完整图。`HT` 保留为兼容的入口名，当前逐级汇报修订代号为 HT-R2，事件 profile 为 `task_hypergraph_reports_v2`；旧轻量运行使用 `task_hypergraph_soft_v1`；历史 profile 和实验目录不重命名。

## 活动代码与职责

目录：`ORCH/crew-algorithms/crew_algorithms/wildfire_alg/coordination/`。

| 文件 | 职责 |
|---|---|
| `soft_task_graph.py` | 超边、成员/leader/active、组目标与任务建议、方案校验、消息路由、固定组织选项 |
| `soft_task_policy.py` | 当前中心组织器 LLM 提案、用量、失败处理 |
| `task_runtime.py` | 审计观测、任务建议、worker先/leader后通信、报告触发组织与动作接线 |
| `task_communication.py` | GROUP广播/定向、REPORT、LEADER、ORGANIZER五种通信用途 |
| `runtime.py` | 共享运行桥接基类、动作与用量记录、入口选择 |
| `hypergraph.py` | 当前仍使用的 Coordinator 状态/事件基础设施，以及历史空间模式支持 |
| `crew_adapter.py` | 观测编码、基础物理检查，以及历史空间策略 |

同目录旧 `task_hypergraph.py`、`task_policy.py` 已迁至 [旧完整图归档](../legacy_full_task_graph/README.md)。旧空间 P/HA/HR 等模式仍存在，属于历史兼容路径，不是新的任务超图版本；本次未删改共享基础设施。

## 当前语义与边界

允许一个 agent 具有多重成员关系，仍保留唯一 active 超边。所有成员关系及消息按显式edge标注，worker先通信，leader后通信；leader用原通信LLM调用分析报告，选择组内处理、leader协商或上报中心。没有回执、待回复或已解决状态机。GLOBAL不再被偷偷解释为组内广播。

中心输入改为初始任务、能力/在线名单与leader报告；完整环境快照仅保留审计。在线名单仍是运行时可用性元数据。每5步的原检查保留，新的leader报告也触发本轮组织检查。多重职责协商、完成退出、自适应注意力尚未实现。[本轮协议与进度](../bottom_up_reports/README.md)。

## 实验与工具

当前运行/冻结入口仍为 `scripts/run_task_hypergraph.sh`、`scripts/run_task_hypergraph_smoke.py`。当前离线审计 `scripts/audit_task_hypergraph.py` 接受 `task_hypergraph_reports_v2` 和历史 `task_hypergraph_soft_v1`，旧完整图应显式使用归档审计器；不会自动把旧图按轻量规则审计。

默认相关测试：`tests/test_soft_task_graph.py`、`tests/test_task_runtime.py`。旧完整图测试位于归档，不在默认 tests 中。

当前逐级汇报门禁及后续5个较大任务以 `research/bottom_up_reports/STATE.json` 为入口；不得把旧实验状态当作当前队列状态。之前动态/固定各60步的结果和对应冻结源码位于 `/data1/gzy/crew_runtime_structure_pair_20261027/`，结果为11/15与13/15，不能推出普遍优劣。开发工作区不能替代历史运行的冻结源码；本次没有修改该实验快照。

历史批量分析器 `research/task_hypergraph/audit_dynamic_runs.py` 会按记录中的 profile 明确选择当前或归档审计器，仅用于读取既有记录，不是运行入口。
