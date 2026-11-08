# v3 扩展批次（2026-10-11）

用户要求继续增加实验、记录和分析。本批固定 24 次：侦察/运输各两个新 seed，树线清理/灭火各一个新 seed，每个 task-seed 都比较 P、HA、HR、HR-projector-off。具体参数在 `spec.json`，不按结果换 seed 或修改行为。使用 provenance-aware 新源码，禁止与 v2 旧源码结果混算。

侦察与树线 30 步、运输 15 步均为原时域；灭火固定 15 步观察窗口，原时域为 100 步，不能把窗口失败推断为完整任务不能完成。灭火没有可信固定总火量，goal_fraction 和 AUC 留空，分别报告 fire_active、灭火数和烧毁树木数。树线报告初值与增量，避免把初始空缺树木计为贡献。

记录：原始聊天、感知/行动输出、每个接收者的投递/抑制反馈、动作前后状态、资源/位置变化、原 validator、完整返回 token、PNG。每个终态实验自动生成带 event ID 的 `evidence_timeline.md`；批次自动更新 `LIVE_ANALYSIS.md` 与 `extended_analysis.json`，包含资源变化索引、初末 rewards 和通信矩阵。未结束实验保持 pending，不读半写入日志评分。最后另生成标准 `summary.csv` 与 `analysis.json`。

启动入口：

```bash
CREW/.conda/crew-orch/bin/python CREW/scripts/hypergraph_campaign.py plan \
  --spec CREW/research/hypergraph_v3/spec.json \
  --gate CREW/benchmark_runs/hypergraph_gate_v6 \
  --output CREW/benchmark_runs/hypergraph_campaign_v3
CREW/.conda/crew-orch/bin/python CREW/research/tools/expanded_campaign.py \
  CREW/benchmark_runs/hypergraph_campaign_v3
```

启动只执行一次，不能同时启动多个 supervisor。已有 incomplete case 必须先检查进程，不自动重跑。runner 中每 case 最多 2400 秒，超时与故障留在 denominator。单 Unity slot 串行，预计数小时；返回 token 可能达到千万量级，实际值以后续记录为准。当前磁盘约 156 GB 可用，本批不下载大规模外部轨迹。

人工分析重点：成员报告是否和资源状态一致；运输是否真正卸载；灭火是否先取水再喷洒；长期意图是否转成可执行动作；leader 是否转达关键建议；通信减少是否伴随任务退化。自动指标不冒充语义真伪、因果有用通信率或 agent 内部信念。
