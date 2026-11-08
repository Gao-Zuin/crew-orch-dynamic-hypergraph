# 固定分组阶段失配实验：准备状态

2026-10-24 已在轻量超图上另做 3 条诊断轨迹，结果见 [RESULTS_2026_10_24.md](RESULTS_2026_10_24.md)。下文保留此前实验准备及门禁的历史状态。

正式的 6 次完整运行和 12 次短续跑尚未启动。[PROTOCOL.md](PROTOCOL.md) 现标为暂停：本目录的门禁和代码改动针对轻量 `SoftTaskGraph`，不能当成原有完整 `TaskHypergraph` 的对照实验。改用原完整图和组合场景的方向见 [REVISED_DESIGN.md](REVISED_DESIGN.md)。

## 已完成的门禁

- `benchmark_runs/fixed_group_gate_v1`：无效。Nakama 服务未运行，Unity 连接拒绝并反复抛 `DivideByZeroException`；0 个图提交、0 个动作，已终止。不能当任务失败。
- `benchmark_runs/fixed_group_gate_v2`：同一 7 人运输任务 2 步，固定组模式真实执行完成；1 个图提交，14 条动作边界，39 次接收者级送达，原审计通过。模型只生成一组，因此该案例不能用于跨组重组效果检验。
- `benchmark_runs/fixed_group_regroup_gate_v1`：诊断性两组起始方案在第 1 步交换非 leader 成员；2 个图提交、14 条动作边界、17 次送达。运行时原审计误把人工提交当作非法模型提交，故 `status.json` 留有历史 `mechanism_audit_passed=false`。修订审计器后，`audit_updated.json` 重放通过。此短门禁只验证代码路径，不计入正式实验。

门禁用的起始组和重组文件分别是 `gate_initial_plan.json` 和 `gate_regroup.json`，都保留在本目录。单独的动作表、消息表和 PNG 时间线在各有效门禁的 `analysis/` 目录。

## 当前实现接口

`run_task_hypergraph_smoke.py` 接受 `--fixed-groups`，可选 `--initial-plan-path`、`--regroup-path`、`--regroup-step`。起始方案重放时，运行器只替换当前图版本和世界证据 ID；文件内容及哈希进入运行 manifest。换成员文件只能修改已有边的成员与执行归属，且保持各组规模与 leader。此接口一次运行只会执行一次换成员。

当前 Unity 没有完整世界快照恢复。正式分支只能按预登记从同种子重跑，检查卡点前缀是否相近；不能将其说成严格的同状态反事实试验。真实任务可能由模型在起点只建一个组，或没有满足证据要求的卡点；这种情况应按原样报告，不能事后拆组或降低筛选阈值。
