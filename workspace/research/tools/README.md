# 只读过程审计工具

`episode_timeline.py` 将结构化 ledger 中每个 `after_action` validator 与最新 snapshot、发出的动作排在同一表中。它不更改原始日志，不覆盖已有输出，不修改冻结指标；snapshot event ID 保留观测来源，不能把旧 snapshot 自动当作新鲜证据。

```bash
CREW/.conda/crew-orch/bin/python CREW/research/tools/episode_timeline.py \
  CREW/benchmark_runs/hypergraph_campaign_v2/04_Transport_Firefighters_small_seed283_HA/events.jsonl \
  --agents 6 7 --output /absolute/new/timeline.md

CREW/.conda/crew-orch/bin/python -m unittest discover \
  -s CREW/research/tools -p test_episode_timeline.py -v
```

默认只打印到 stdout。live 日志末尾未完成的 JSON 行可跳过并显式标记；中间损坏行报错。这个工具不是 infrastructure auditor，也不自动解释自然语言、推断因果、重新定义 success 或判定动作完成。离线专项测试 2 项通过；与冻结的 29 项机制/driver 测试分开计数。

已生成实例：`research/hypergraph_v2/TRANSPORT_HA_TIMELINE_WITH_PROVENANCE.md`。旧的不带 snapshot ID 实例保留，不作为最新推荐入口。新增工具没有改动 campaign 的冻结文件；2026-10-10 21:51 左右重新执行冻结源 hash 校验通过。
