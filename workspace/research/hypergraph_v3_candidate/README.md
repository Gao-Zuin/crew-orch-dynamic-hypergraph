# v3 隔离候选：已于 v2 完成后合入，未作新版效果声明

此目录复制 v2 coordination 模块和机制测试，单独修复源码审计发现的问题，不在 live campaign 的 PYTHONPATH 上。它不是完整 CREW 环境副本，不应直接用作 Unity benchmark 启动目录。

改动仅限：

1. 地图格改标为 `map_memory`，明确 shared accumulated crop、cell last-seen unknown、direct visibility unknown；runtime position/resources 另标来源。projector 不再把全部 snapshot 统一命名为 verified_evidence。
2. refill 的位置 guard 只有可信 `direct_runtime` cell 才能拒绝；当前 CREW 缓存格不满足这一条件，因此 abstain。水量为 0 的喷洒检查保留。
3. 拓扑比较规范化 members 顺序，保留原显示顺序；同一成员集合/leader 不因列表重排而增加版本，真实 leader 变化仍增加版本。

运行：

```bash
CREW/.conda/crew-orch/bin/python -m unittest discover \
  -s CREW/research/hypergraph_v3_candidate/tests -p test_hypergraph.py -v
```

27 项通过（原 22 项按新 schema 调整相关断言 + 3 项新回归 + 默认关闭和不支持/stress arm 入口的 2 项测试）。测试显式检查 coordinator 模块来自本候选目录，防止悄悄导入 editable 安装的原包。

首次运行因候选缺少顶层包 marker，Python 导入了原 editable 包，暴露 schema/churn 测试失败；补齐顶层 marker 后重新执行通过。失败不是 frozen campaign 失败，也不修改原测试记录。

v2 全部 16 次实验结束、493 个冻结文件归档校验通过、原运行进程退出后，以上修正及回归测试已合入主目录。主目录 34 项测试通过；新版真实环境门禁使用 `benchmark_runs/hypergraph_gate_v6`，此目录保留为隔离候选的历史快照。不得用 v2 的效果数据声称上述新提示/schema 有效。不增加人工阶段规划、不替 agent 执行卸载，也不宣称解决自由文本的错误 completion claim。

## 已结束真实轨迹的只读拓扑回放

2026-10-10 22:05 左右，将已结束 6 个 case 的 `STATE_OBSERVED`、`NODE_OFFLINE`、`TOPOLOGY_COMMITTED` 按原 monotonic 时间顺序输入本候选 Coordinator；不回放动作、不调用 LLM、不写入原 ledger。所有 proposal 保留原 based_on_state_version、members、leader、active；仅由候选比较器决定是否发生结构变化。

| case | commit 回放数 | 冻结原 raw churn | 候选顺序规范化 churn |
|---|---:|---:|---:|
| Scout P | 11 | 2 | 0 |
| Scout HA | 27 | 1 | 0 |
| Scout HR | 11 | 1 | 0 |
| Scout projector-off | 41 | 6 | 0 |
| Transport HA | 30 | 2 | 2 |
| Transport HR | 30 | 2 | 2 |

共回放 150 次 commit；6 个 case 的最终 state version 均与原 ledger 一致，proposal 校验未失败。修正去掉三人单边场景的排序噪声，同时保留运输中的真实结构变化。该表是工程回归证据，不替换冻结 summary 的 churn，不是候选闭环效果实验；离线回放不说明修正后的 prompt/schema 会产生相同动作。
