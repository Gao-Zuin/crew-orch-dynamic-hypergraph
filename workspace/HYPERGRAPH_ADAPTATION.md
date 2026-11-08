# CREW 超图协作层适配：实现、证据与未完成项

## 2026-10-12：当前运行路径已精简

当前普通 HA/HR 使用 compact_v5 提示，详细变更见 [精简与大团队实验](research/hypergraph_v5/README.md)。下文的完整 context/schema 描述保留为协议接口说明；正式 prompt 不再重复组内地图、空 contract/阶段及每个成员的整套元数据。HA 不附加 leader 指令，HR 明列可联系对象并合并反馈；普通 local-no-delta 只记录、不自动通知 leader。完整状态仍保存在日志。

## 设计依据与边界

依据 `/data/gzy/MAS/hypergraph/hypergraph_coordination_reference/README.md`，并对照该仓库的：

- `src/coordination/hypergraph/hypergraph_coordinator.js`：事件、snapshot、session、版本化 topology commit；
- `src/coordination/hypergraph/policies/resource_heuristic.js`：局部 leader、active/passive、contract reducer、合法加工 credit；
- `src/agent/hypergraph_adapter.js`：领域 snapshot、临时 context、路由和 guard；
- `tests/hypergraph_coordinator_smoke.js`：上游现有测试，2026-10-10 本机执行通过。

这是 Python 领域适配，不是把 Minecraft 物品名/recipe 改名后直接运行。独立 agent 沿用 Embodied 的 perception、communication、action LLM 和既有动作库。Coordinator 不生成移动目标、补水命令或全局任务计划；也没有新增一个全局 LLM manager。ORCH 原有组织机制不被替换，作为外部对照保留。

## 当前代码

所有 Python 文件位于 `ORCH/crew-algorithms/crew_algorithms/wildfire_alg/coordination/`：

| 文件 | 职责 |
|---|---|
| `hypergraph.py` | 中立的 evidence/event ledger、拓扑校验、局部投影、路由、contract reducer、接收方确认交易 |
| `crew_adapter.py` | 将现有 CREW 局部 observation 编码为 position/resources/capabilities/facts；窄物理前置条件检查；透明分组 heuristic |
| `runtime.py` | opt-in 接入原 Embodied 循环，动作前后 snapshot、原 validator、完整 token 计数、消息投递反馈 |

原代码改动限于 Embodied 主循环与通信/动作提示和投递入口的 hook。`CREW_HYPERGRAPH_ARM` 未设置时不创建 bridge、不写协作日志、不注入 context、不改变原消息与动作路径。P/SHADOW 的正常提示与消息历史格式有直接 parity 测试。

### CREW 字段映射

| CREW observation | 适配后的证据 |
|---|---|
| agent 类型 | 能力列表，例如 navigate/spray/refill/carry_civilian |
| `position` | 当前真实位置，不使用 LLM 描述替代 |
| `extra_variables[1]`（消防员/直升机） | 当前水量 |
| `extra_variables[0]` | 消防员携带平民数，或直升机载消防员数 |
| 消防员 `extra_variables[2]` | 是否在直升机内 |
| 局部 `perception_grid` | 环境返回的共享累积地图局部裁剪；格子的最后观测者/时间未知，不能等同于本 agent 当前直接可见的世界状态 |
| 全局奖励、`fire_active` | 仅用于原 validator 与评估日志，不加入组内 agent context |

缺少字段表示未知，不补成 0。snapshot 带 session、单调时间、state version 和 task ID；旧 session 不能重新覆盖新 session。claim 独立保存，不更新 snapshot。自由自然语言不自动解析成可信结构化事实；真实日志中的语义矛盾仍需结构化声明或人工标注。

源码审计发现 observation 的地图裁剪范围大于实时视野；外层 snapshot 新鲜不代表每个缓存格新鲜。冻结 v2 的 `facts.observed_cells` 仅表示最新 observation 报告的格子，不证明本 agent 当前直接看见火。原 validator 的同时确认数仍是权威条件。详细来源、构建一致性限制及待修复项见 `research/hypergraph_v2/ADAPTER_REVIEW.md`；本次审计不修改冻结行为或指标。

### 拓扑及其动态性

当前可替换 policy 是近邻 heuristic，不使用人工任务阶段：按当前位置组成最多 3 人的主体小组，按质心距离选择 leader，相邻组共享一个 bridge agent。bridge 只在一条边 active，其他 membership 只提供 passive 摘要。小组不等于手工任务分解；三个同构 agent 的小场景可能只有一条边，7-agent 场景可产生真正重叠边。

位置、可用成员变化可能改变分组与 active edge。该 heuristic 还没有学习或调参，也不保证任务最优。原始 Embodied 每个宏步独立重发动作，不保留 ORCH/CAMON 的多步 option 队列；本适配尚未泛化到这些有长队列的执行器，不能声称其 topology 切换已取消所有旧异步动作。

## Arm 与公平性

| Arm | 当前实现 | 实验性质 |
|---|---|---|
| 未设置 | 原算法路径 | baseline 默认 |
| P | 只做 instrumentation；提示/投递/动作不施加协作机制 | benchmark-faithful |
| SHADOW | 计算并记录 topology，但不注入、不限制 | infrastructure/shadow |
| HA | 最新 active-edge evidence，passive 摘要；不限制通信/动作 | benchmark-faithful |
| HR | HA + leader/member/相邻 leader 路由，失败/抑制反馈 | benchmark-faithful |
| HG | HR + spray 水量、可信直接观测的 refill 位置检查；当前共享缓存格上的 refill 检查 abstain；拒绝后一次 LLM 重试，再失败安全保持 | 必须显式 `CREW_HYPERGRAPH_PROTOCOL_STRESS=1` |
| HF | 拒绝启动，不假装支持 | 当前接口没有通用、无歧义的实体 collector/receiver transaction ID |

独立中立 reducer 支持显式 resource contract、partial output credit 和 receiver-side commit，已做合成协议测试；普通 CREW benchmark 不自动创建人工 workflow contract。HG 的物理前置条件属于领域规则 stress，不能冒充普通 HR 的公平增益。

`CREW_HYPERGRAPH_INTERVENTION=projector_off` 保持同一 topology policy、关闭 context；闭环动作不同可导致实际拓扑不同。v2 已完成四次 projector-off 配对实验，结果有正有负；`leader_shuffle` 保持成员/边大小、只更换 leader，尚未开展正式效果实验。不能声称普遍因果价值已验证。

## 测试与复现

离线测试（不需要 Unity/API）：

```bash
CREW/.conda/crew-orch/bin/python -m unittest discover -s CREW/tests -p test_hypergraph.py -v
```

当前机制测试 27 项通过；另有 7 项实验驱动/分析测试，共 34 项。独立轨迹整理工具另有 2 项测试。覆盖 claim 过期、直升机动作编号歧义、hard-event 实际投递、最终 validator、顺序配平、timeout/缺失保留、地图 provenance、未知格 guard abstention 和成员顺序规范化。

真实环境开发门禁：

- `benchmark_runs/hypergraph_gate_v1/HR/`：首次接入发现不存在的 SYSTEM chat 通道；失败日志保留，不纳入效果分析，所属进程已清理。
- `benchmark_runs/hypergraph_gate_v2/HR/`：3-agent Scout、2 步，完整结束，78 条事件，11 次投递、4 次抑制，基础审计通过。
- `benchmark_runs/hypergraph_gate_v2/HR_transport/`：7-agent Transport、2 步，完整结束，178 条事件，26 次投递、22 次抑制、2 次 active-edge 切换，真实重叠 membership，基础审计通过。两个场景均未达到任务目标；门禁不评估胜率。v2 属于开发调试，不是冻结效果实验。
- v3 门禁在实验启动前遇到 Python 3.10 不支持 `hashlib.file_digest`；未产生实验数据，改为兼容的流式 hash。
- `benchmark_runs/hypergraph_gate_v4/manifest.json`：冻结行为代码和提示的 SHA256、任务/seed、模型、顺序、超时；P_scout → HA_scout → HR_transport。总审计结果以该目录 `audit.json` 为准，不能以计划或日志片段替代通过结果。

v4 已于 2026-10-10 21:00 完成，总审计 `passed=true`。P/HA/HR 分别记录 76/74/173 条事件，HR_transport 确认真实重叠 membership；最后一次环境动作后的全程用量分别为 24/24/56 次 API 调用。进程检查未发现本轮 Python/Unity 残留。这是基础设施通过，不是任务成功或效果优势。

后续修正有独立的 v5 门禁，全部通过：P_scout / HA_scout / HR_transport 分别 77 / 83 / 210 条事件，最终 validator 均为 `episode_end`。v5 修正了 HG 对直升机动作编号歧义的误拦截风险（现仅约束语义明确的消防员动作）、提前成功时的最终状态记录、死亡状态 delta、hard-event 实际投递。P/HA/HR 的正式测试以 v5 源码为准，不将不同开发版本混合统计。

## 冻结的配对实验（v1 已终止；v2 已启动，待完成）

配置：`research/hypergraph_v1/spec.json`；冻结 manifest：`benchmark_runs/hypergraph_campaign_v1/manifest.json`。冻结了 660 个源码/配置/构建/测试文件的 SHA256 及 Python、依赖版本；不记录 API key。

v1 首次 P/Scout 运行在 7 次动作后达到原 validator 成功，审计通过。但后续源码校验发现 Unity 写出的 `Unity_Data/ML-Agents/Timers/Wildfire_timers.json` 被错误纳入静态构建 hash，驱动器终止，确认进程无残留。v1 保留 1/16 已完成和 15/16 未执行的完整汇总，不作完整配对结论，也不与 v2 混合。

v2：`research/hypergraph_v2/spec.json` 与 `benchmark_runs/hypergraph_campaign_v2/manifest.json`，冻结 493 个相关静态文件。仅修正 infrastructure 的文件分类，排除 profiler Timers 及历史输出文本；agent、prompt、模型、任务/seed、顺序、timeout 和指标定义不变。增加对应回归测试，仍执行完整相同 16 个 case；不能因 v1 首次成功选择保留它而跳过 v2 对应运行。

| 任务 | 官方种子 | 原始上限 | 对比组 |
|---|---|---:|---|
| Scout_Fire_small | 4651、6841 | 30 步 | P、HA、HR、HR_projector_off |
| Transport_Firefighters_small | 283、2461 | 15 步 | P、HA、HR、HR_projector_off |

共 16 次运行，同一 task-seed 内配对。四组执行顺序在四个 task-seed 上轮换；没有人工 stage contract 或额外领域规划。seed 采用官方列表前两项，含开发时已观察过的 seed，因此这是探索性对比，不是 held-out 或论文级统计复现。

`HR_projector_off` 关闭最新 evidence context，保留相同 topology policy 和通信约束；由于闭环动作影响位置，不能声称不同组的实际拓扑轨迹完全相同。该干预验证 projector 的作用，不直接估计某条特定超边的 ECV。

复现与分析命令：

```bash
# 新建实验目录；要求 gate 通过且冻结源码仍匹配
CREW/.conda/crew-orch/bin/python CREW/scripts/hypergraph_campaign.py plan \
  --spec CREW/research/hypergraph_v2/spec.json \
  --gate CREW/benchmark_runs/hypergraph_gate_v6 \
  --output CREW/benchmark_runs/hypergraph_campaign_fresh

CREW/.conda/crew-orch/bin/python CREW/scripts/hypergraph_campaign.py run \
  --output CREW/benchmark_runs/hypergraph_campaign_fresh

CREW/.conda/crew-orch/bin/python CREW/scripts/hypergraph_campaign.py analyze \
  --output CREW/benchmark_runs/hypergraph_campaign_fresh
```

每次实验保存 `events.jsonl`、控制台、原始结果/图片目录索引、`live_process.json`、`status.json` 和审计。已存在且未完成的 case 不自动覆盖/重跑，须先检查其真实进程；终态失败保留，不从 denominator 删除。`summary.csv` / `analysis.json` 是可重算的派生产物。

指标定义在 manifest 中提前固定：原 validator 成功、最后观察到的原任务目标比例、观察时域内进度 AUC、返回的 token usage、recipient-level 发送/投递/失败/抑制数、active 切换和结构 churn。自然语言 alignment、因果 useful-message rate、无 contract 的子任务 VMCR 和物理交付 fidelity 不编造数值；未完成/timeout 记录不以“未见成功”冒充已验证的最终失败，也不补成成功。token 是运行返回的计数，不是 DeepSeek 完整账单。

新的冻结门禁（输出目录必须不存在）：

```bash
CREW/.conda/crew-orch/bin/python CREW/scripts/run_hypergraph_gate.py \
  --output CREW/benchmark_runs/hypergraph_gate_fresh
```

runner 只终止自己创建的进程组；遇到 timeout/traceback 会保存失败，不覆盖已有实验。门禁在不同 case 之间校验冻结 hash，行为源码改变后必须新建版本，不得接着比较效果。

单次手工测试示例：

```bash
CREW_HYPERGRAPH_ARM=HR \
CREW_HYPERGRAPH_EVENT_PATH=/absolute/new/run/events.jsonl \
RUN_LOG_ROOT=/absolute/new/run \
LEVEL=Scout_Fire_small SEED=4651 MAX_STEPS=2 \
bash CREW/scripts/run_small_communication_benchmark.sh Embodied
```

完整 ledger 含最后一步后的环境状态与全程 usage，避免旧 CSV 的动作前记账遗漏。`audit_hypergraph_run.py` 校验事件顺序、active membership、发送/投递闭环、动作 ID、动作后 validator 和 token 总量；它不是效果评价器。

## 最终实验与支持边界

独立于 gate 的 v2 冻结实验已完成全部 16 次，基础设施审计全部通过，任务成功 11/16。HA 4/4、HR 3/4、P 与 HR-projector-off 各 2/4；这是两类任务、两个 seed 的探索性结果，不能推出普遍优势。详细配对结果、成本和负面案例见 [HYPERGRAPH_RESULTS.md](HYPERGRAPH_RESULTS.md)。v1 中止记录单独保留，不混算。

v2 归档后才合入新版：`map_memory` 明确共享缓存且每格 freshness 未知，context 使用 `runtime_observations` 并携带 provenance；refill guard 对未知来源格 abstain；拓扑比较忽略成员顺序但保留 leader 变化。v6 是当前源码的新门禁，旧版效果不可归因于新版。上面的 plan 示例将为当前源码建立新 manifest，不是复用旧版 hash；重跑须使用不存在的输出目录。

真实 CREW receiver-side handoff、消息延迟/丢失故障注入、拓扑切换对有队列算法的取消、通用 contract 元数据与 learned policy 尚未实现。无可信 contract 的子任务 VMCR、自然语言 alignment、因果 useful-message rate、物理交付 commit 不编造数值。这些研究扩展不等于本次适配测试的既有能力，也不说明“超图优于 ORCH”。
