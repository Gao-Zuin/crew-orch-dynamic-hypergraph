# CREW 超图适配：小样本实验结果

本轮完成 16 次真实 Unity 实验：火情侦察与消防员运输，各 2 个 seed、4 种设置。全部正常结束并通过基础设施审计，任务成功 11/16；失败没有删除或选择性重跑。这是 Embodied 上的适配比较，不是 ORCH 与超图的直接对照，也不是论文级复现。

## 设置与结果

P 保留普通提示和通信、仅记录状态；HA 加入局部协作状态；HR 再限制为成员—leader/相邻重叠组通信；HR-off 保留路由而关闭 context projector。使用 DeepSeek `deepseek-chat`，侦察上限 30 步、运输上限 15 步，顺序配平。seed 是开发过程中见过的 seed，不是独立保留测试集。

| 任务 / seed | P | HA | HR | HR-off |
|---|---|---|---|---|
| 侦察 / 4651 | 成功，5 步 | 成功，13 步 | 成功，5 步 | 成功，20 步 |
| 侦察 / 6841 | 成功，15 步 | 成功，7 步 | 成功，8 步 | 成功，6 步 |
| 运输 / 283 | 0/6，15 步 | 6/6，15 步 | 6/6，15 步 | 5/6，15 步 |
| 运输 / 2461 | 5/6，15 步 | 6/6，12 步 | 0/6，15 步 | 5/6，15 步 |

运输人数采用最后动作后的原环境 validator，不能用 agent 的“已完成”声明替代。达到上限的正常任务失败不是程序故障。

| 设置 | 成功次数 | 返回 token 总数 | 接收者级消息投递数 |
|---|---:|---:|---:|
| P | 2/4 | 1,652,203 | 1,274 |
| HA | 4/4 | 1,977,356 | 1,136 |
| HR | 3/4 | 1,733,551 | 507 |
| HR-off | 2/4 | 1,835,267 | 511 |

总返回 token 为 **7,198,377**，不是完整账单金额，未按缓存命中计价。HR 相对 HA 消息投递减少约 55.4%、token 减少约 12.3%，但成功少一次，不能说无损降本。不同任务和失败截断混合后的步数、耗时不应当作成功完成速度排名。样本不足以支持统计显著性或普遍优势。

## 过程分析

1. **运输暴露“说完成不等于执行完成”。** seed 283 的 P 到达投放点后声称卸载完成，却未执行卸载动作，最终 0/6。HA 同样曾误判，但成员根据仍在机上的状态纠正，直升机返回卸载，最终完成两批运输。HR 也出现末批虚假完成声明，收到提醒后恢复并完成。结构化状态帮助恢复，但不能保证每次被正确使用。
2. **稀疏通信可能形成决策瓶颈。** seed 2461 的 HR 在直升机已载 5 人、容量为 5 时仍等待“6 人全上机”才起飞。成员 1 提议先送现有乘客再返回，该消息确实送达 leader 4；leader 没有采纳，反而继续要求全员上机。最终 0/6。并非所有失败都由消息丢失造成，也不能推断放开直连必然成功。
3. **侦察收益依赖 seed。** HA 相对 P 在两个 seed 分别慢 8 步、快 8 步；HR-off 在 6841 比 HR 快 2 步。context 与路由不是稳定提速器。侦察全部成功，也不说明协作层对更困难任务必然有效。
4. **原始拓扑 churn 有排序噪声。** v2 比较成员列表时将顺序变化算成结构变化。离线回放已证明部分侦察 churn 实为排序变化；保留旧指标，不回填美化结果。

## 版本与证据边界

以上效果数据全部来自冻结 v2。其地图裁剪实际来自共享累积缓存，不能称为 agent 当下直接可见的证据，snapshot 时间也不等于每格最后观察时间。

v2 完成并归档后，当前代码已另行修正地图 provenance、未知格上的 refill guard abstention，以及成员顺序规范化；新增版本的 Unity 门禁位于 `benchmark_runs/hypergraph_gate_v6`，三个 case 全部通过，102 个源码 hash 匹配。34 项主测试和 2 项轨迹工具测试通过。门禁只检查接入正常，不证明修正后仍具有上表效果。没有按失败结果加入容量规划器或人工阶段 workflow。

未支持：真实物理 receiver-side handoff、真实延迟/丢失故障 campaign、learned policy，以及 ORCH 长动作队列上的拓扑切换取消。无可信 contract 的子任务 VMCR、自然语言 alignment、因果 useful-message rate 不提供伪数值。

## 保存位置与复查

- [逐次结果 CSV](benchmark_runs/hypergraph_campaign_v2/summary.csv)、[配对分析 JSON](benchmark_runs/hypergraph_campaign_v2/analysis.json)、[冻结 manifest](benchmark_runs/hypergraph_campaign_v2/manifest.json)。
- 每个 case 保存 `events.jsonl`、控制台、审计、状态及原始结果/图片目录链接。最终全量检查：15,668 条事件、9,664 张 PNG、16 个 case 审计通过、493 个冻结文件 hash 在合入新版前全部匹配。
- [冻结源码归档](benchmark_runs/hypergraph_campaign_v2/frozen_sources.tar.gz)，SHA256：`a203b7afd116582eb3d5fa31d3382da415dd560106c8330edfd35fddbeebcfef`。当前源码已更新，不能要求旧 manifest 匹配当前目录；旧版复现应在单独目录恢复归档。
- [逐事件机制分析](research/hypergraph_v2/ADAPTER_REVIEW.md)、[适配说明](HYPERGRAPH_ADAPTATION.md)、[完成性与支持边界](research/hypergraph_v2/REQUIREMENTS_AUDIT.md)。
- 此前不同任务的原通信架构实验单独保存在 [跨任务分析](benchmark_runs/DIVERSE_TASK_ANALYSIS.md)，不与本轮混算。

只读重算派生分析：

```bash
CREW/.conda/crew-orch/bin/python CREW/scripts/hypergraph_campaign.py analyze \
  --output CREW/benchmark_runs/hypergraph_campaign_v2
```

新源码重新跑实验必须先生成新 gate 与新 manifest，使用新的输出目录；不可续接或覆盖 v2。
