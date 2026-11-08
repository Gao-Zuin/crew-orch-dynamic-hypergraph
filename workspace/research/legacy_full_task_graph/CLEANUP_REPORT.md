# 2026-10-28：旧完整超图退出主实现

已完成清理。当前任务超图仍为 SoftTaskGraph + SoftTaskPolicy + TaskRuntimeBridge，复用 Embodied 循环。没有实现新讨论的通信/汇报/多重职责协议，没有修改组织器提示、路由权限、动作控制或物理构建，没有调用模型或启动Unity。

## 迁移与解耦

- 从活动 coordination 包移走 task_hypergraph.py（419行）、task_policy.py（420行），放入本归档目录；两文件字节与迁移前相同。
- 旧512行测试和104行控制层回放移入归档，调整导入路径。旧策略的相对模块依赖保留。
- scripts/audit_task_hypergraph.py 只审计当前 task_hypergraph_soft_v1；本目录audit.py只审计旧完整图。错误profile得到明确失败和正确入口提示。
- 当前audit_soft函数AST未改变；旧轨迹审计结果亦与拆分前一致。
- run_task_hypergraph_smoke.py的冻结文件清单移除旧测试依赖，仍保留当前graph/runtime测试。
- 历史批量读档工具research/task_hypergraph/audit_dynamic_runs.py根据事件profile明确选择当前或归档审计器，归档导入仅发生在历史分支。
- 新增coordination/README.md；重写当前research/task_hypergraph入口说明；更新根说明和dynamic_followup状态说明，移除“旧批次当前运行/长期任务active”的过期描述。
- 原研究说明移至HISTORICAL_NOTES.md；原路径、原字节源码/工具备份见original_sources.tar.gz及manifest.json。

当前仍使用runtime.py、hypergraph.py的Coordinator和crew_adapter.py；这些共享模块及历史空间模式未随旧完整图一起删除。历史profile和目录名也没有重命名。

## 测试夹具同步

默认测试曾遗留两项与先前修复不一致的预期/初始化：补水测试仍要求已撤回的新提示，早停测试通过__new__绕过构造函数而缺tokens_before/step。此次仅对齐测试预期和补齐夹具字段，生产提示与运行代码未变。首轮失败记录和修改前文件均保留在清理证据目录。

## 验证

| 检查 | 结果 |
|---|---|
| 当前默认离线测试 | 74项通过 |
| 显式归档离线测试 | 36项通过 |
| 动态seed42完整60步轨迹离线审计 | 通过，完整审计输出与清理前一致，300动作 |
| 固定seed42完整60步轨迹离线审计 | 通过，完整审计输出与清理前一致，300动作 |
| 旧完整图second_fire_early_v5离线审计 | 通过，完整输出与清理前一致 |
| 错误profile保护 | 两个审计器均拒绝对方profile |
| 运行文件冻结清单 | 182个路径均存在，未包含已迁移模块/旧测试 |
| 当前审计导入隔离 | 新进程导入当前审计不会加载归档命名空间；旧coordination模块不可再导入 |
| 算法包内容校验 | 只有旧2个模块移出；其余迁移前清单中的源码文件哈希全部相同 |
| 历史产物校验 | 两条最新实验与一条旧实验共15份关键事件/状态/审计/manifest/冻结包哈希未变 |
| CLI导入检查 | 当前运行冻结、两种审计、旧回放help和历史批量分析5个入口通过；没有执行模型回放 |

本次只修改主工作区与研究工具；`/data1/gzy/crew_runtime_structure_pair_20261027/workspace` 等已运行快照保持原样。历史运行的效果与局限不因本次清理变化。

完整证据：`/data1/gzy/crew_legacy_cleanup_20261028/verification.json`、`current_tests.log`、`legacy_tests.log`及前后审计JSON。原文件字节备份在同目录及本归档original_sources.tar.gz中。

归档显式用法见[README.md](README.md)，当前代码说明见[任务超图入口](../task_hypergraph/README.md)。
