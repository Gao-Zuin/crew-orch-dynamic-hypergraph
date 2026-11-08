# 任务约束为何在协作链中失效：轨迹审查、论文与 Jev 适配

2026-10-12。本文审查已有轨迹，不修改算法，不调用 Jev，不启动新实验。

## 核心判断

目前最完整的失效链不是“中心收不到信息”，而是：局部事实已经进入管理者输入，却被概括成总体合理的叙事；阶段决策用总体紧迫性替代逐条完成条件；同一模型的确认继续沿用这个叙事；程序把确认直接变成组织状态切换。

需要区分三件事：未提取约束、未满足约束、明知约束却重新解释。本例包含后两者，不能全部归为遗忘或长上下文过载。

## 1. 灭火轨迹：信息在哪里失效

记录：`communication_Suppress_Fire_Extinguish_seed1975/results/ORCH`，8 名执行者＋9 号管理者，t=0–4。master log 有 44 条 STATUS_PHASE；t=3 的 8 名 worker 中，6 名在 urgent 重复提到同一火点 `(48,30)`。

### 1.1 从局部错误到团队级关注

t=3，AGENT_5 的任务是东南侧侦察和保持安全距离，却在 urgent 声称火点旁 `(47,30)` 有 civilian `i`。符号定义中 `i` 是 Ignited，平民由 `C` 表示。管理者随即把“火点旁可能有平民”收入自己的 urgent。

这是异常汇报的错误生成及向上传播。管理者保留了“可能”，但没有回查符号依据。本轮仍选择 CONTINUE_PHASE，没有观察到为该平民增设救援任务，因此应把“关注内容偏移”与“行动任务改派”分开。

worker prompt 的 urgent 要求是重要信息，如意外火情、平民或问题，并给出了“发现平民，建议进入运输阶段”的示例。这说明平民信息是被明确鼓励报告的类别；示例是否造成这次误报需要换示例回放才能确认，不能由一次误读直接归因。

### 1.2 已有明确反例，却把安全约束概括成满足

t=4 的阶段完成条件包含两部分：至少一人确认火的位置/范围，所有人距点燃、燃烧或灭火中的格子至少 5 格。

管理者输入中包括：

| 成员 | 输入中的状态 | 与火点 `(48,30)` 的关系 |
|---|---|---|
| AGENT_5 | `(48,32)`，明确说火在北侧 2 格 | 明确不满足 5 格 |
| AGENT_6 | `(47,34)`，明确说约 4 格 | 明确不满足 5 格 |
| AGENT_4 | 后续 roster 给出 `(51,29)`；状态却说维持 5 格以上 | 坐标与自然语言安全判断冲突 |

仅 AGENT_5 就足以否定“所有人安全”，无需讨论距离度量细节，也无需完整重建火场。

管理者输出的 summary 却称多个 agent 在保持安全距离。推理还复述了完成条件，随后称位置确认基本满足、所有人没水更紧迫，选择 NEXT_PHASE。其 phase_percent_complete 自报 75，而不是 100。

因此最直接的解释是：它没有把“确认火点 AND 所有人安全”逐项求值，而是用“侦察信息足够、该补水了”的整体判断替代了这个合取条件。模型自己生成的阶段百分比也不是可执行完成证明。

选择补水本身可能有利于撤离危险位置；错误在于把阶段当成完成，并在描述中抹去了安全例外。不能将“原阶段完成”与“因风险中止并转入恢复行动”混为一谈。

### 1.3 确认不是独立验证，反而强化了错误

同一轮第二次调用要求 CONFIRM/CANCEL，突出的是覆盖队列以及不能违背人类指令。它没有新取环境状态、没有程序计算距离、没有单独列出 AGENT_5 这个反例。

确认回复进一步声称所有人都保持了 5 格距离，随后 CONFIRM。第一轮是弱化条件，第二轮变成明确的错误事实陈述。

当前源码与该轨迹吻合：状态决策和确认共用 status_messages；确认返回 CONFIRM 后直接保留原 decision；NEXT_PHASE 将 status 设为 2，阶段处理随后弹出下一阶段、把旧阶段加入历史并重置完成条件。这个路径没有检查距离或完成条件的独立程序验证。

这不是“完全没有确认”，而是确认流程检查了模型的回答，却没有核验回答依赖的事实。

## 2. 运输反例：不能把所有条件都机械地冻结

记录：`communication_Transport_Firefighters_small_seed283/results/ORCH`，7 名执行者＋8 号管理者，t=0–2。

t=0，管理者生成“所有 6 人登机”阶段，明知容量 5，还给直升机安排接人、原地卸载、再次接人的队列。自然语言提到了容量，却没有生成可行的分批运输结构。

t=1，直升机 urgent 明确报告 5/5 满载、另一人无法登机，需要先在目的地卸载。管理者正确识别这与原阶段目标冲突，进入飞行阶段，允许第六人在原地等待。t=2，管理者仍在 urgent 中记录该人尚待接送。

这个片段表明中心能够采用局部关键反馈。它修正了初始不合理的阶段安排，但剩余接送责任还需继续完成；短记录没有证明最终送齐。

它还限定了验证器的职责：不能只问“原阶段条件是否满足”，然后永远禁止切换。应该分别处理：

- 环境/安全硬约束：不能用叙事判为满足。
- 可重写的计划条件：例如所有人一批登机，可以显式改为多批。
- 未完成的任务责任：第六个人不能随阶段切换一起被抹掉。

## 3. 原因与因素：按现有证据排序

| 因素 | 当前证据 | 判断 |
|---|---|---|
| 合取/全称条件被总体判断替代 | 一名成员明确距火 2 格，仍宣称所有人安全 | 最直接的行为证据 |
| 任务推进压力覆盖完成条件 | 推理明确以“没水更紧迫”支持切换 | 已观察到的理由；不是内部注意力测量 |
| 事实与自我解释混在摘要中 | 坐标不安全，却声称保持安全距离 | 下游需要消解冲突，当前没有明确证据优先级 |
| 同模型确认沿用先前结论 | 弱化条件后再次声称已满足并确认 | 已观察到；确认没有外部核验 |
| 运行时没有阻止错误阶段提交 | CONFIRM 直接映射到阶段切换 | 当前实现中的可执行缺口 |
| 提示类别/示例诱导汇报 | urgent 明列平民，示例建议转运输 | 提示确有该内容；诱导效应待回放检验 |
| 重复汇报使关键反例不显眼 | t=3 六人重复火点 | 已有冗余；是否导致漏判待检验 |
| 长上下文位置效应 | 关键状态嵌于多人状态和重复任务中 | 文献支持这一风险；本例未做位置消融 |
| 跨轮对话无限累积 | 管理者 async_status_phase 每轮重置 status_messages | 当前路径不支持这一解释 |

所以，目前优先级是“约束求值和提交机制”，其次才是“中心减负”。即使把输入缩到一个 agent，现有提交路径仍允许没有验证的 CONFIRM。

## 4. 相关顶会论文：它们能解释哪一段

以下链接均为论文原始发表页面。PDF 保存到 `papers/`；TACL 一篇是期刊补充，单独标明，不混称会议论文。

### P1. Why Do Multi-Agent LLM Systems Fail? — NeurIPS 2025，Datasets and Benchmarks

[论文](https://papers.nips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html)

MAST 基于多架构轨迹给出 14 类失败。当前案例适合按违反任务规范、未采用其他 agent 输入、错误验证等维度标注；不能把阶段切换直接标成整个任务提前终止。它适合组织失效链，不直接揭示模型内部原因。

### P2. On the self-verification limitations of large language models on reasoning and planning tasks — ICLR 2025

[论文](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f3c5e56274140e0420baa3916c529210-Abstract-Conference.html)

在 Game of 24、图着色和 STRIPS 规划中比较自我验证与可靠外部验证。前者可能使表现恶化，后者明显改善。这最直接对应当前“再确认一次没有纠错”的问题。论文中的可靠外部验证器不能等同于另一个概率判断模型。

### P3. Large Language Models Cannot Self-Correct Reasoning Yet — ICLR 2024

[论文](https://proceedings.iclr.cc/paper_files/paper/2024/hash/8b4add8b0aa8749d80a34ca5d941c355-Abstract-Conference.html)

研究缺少外部反馈的内生自我纠错，发现其困难且可能退化。对应本例的 CONFIRM 在同一上下文中延续原叙事；论文结论不是“所有形式的纠错都无效”。

### P4. CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing — ICLR 2024

[论文](https://proceedings.iclr.cc/paper_files/paper/2024/hash/fef126561bbf9d4467dbb8d27334b8fe-Abstract-Conference.html)

让模型借助工具结果验证并修正输出，说明外部反馈的重要性。对当前案例的迁移点是查询结构化状态、计算违反条件的成员，再反馈具体反例，而不是增加一轮泛化的确认。

### P5. FollowBench: A Multi-level Fine-grained Constraints Following Benchmark for Large Language Models — ACL 2024，主会长文

[论文](https://aclanthology.org/2024.acl-long.257/)

把指令拆成细粒度约束，并逐层增加约束，评价逐条遵守情况。对应当前应把确认火点、安全距离、资源准备、未完成责任分开计分。它是文本指令基准，不能直接提供动态世界中的安全保证。

### P6. PlanBench: An Extensible Benchmark for Evaluating Large Language Models on Planning and Reasoning about Change — NeurIPS 2023，Datasets and Benchmarks

[论文](https://proceedings.nips.cc/paper_files/paper/2023/hash/7a92bcdede88c7afd108072faf5485c8-Abstract-Datasets_and_Benchmarks.html)

使用规划领域系统评估动作与状态变化推理。当前运输初始计划“容量 5 却一批接齐 6 人”很适合按前置条件、资源限制、动作效果拆解；自然语言提及限制不等于计划可行。

### 补充：Lost in the Middle: How Language Models Use Long Contexts — TACL 2024，期刊

[论文](https://aclanthology.org/2024.tacl-1.9/)

显示相关信息的位置会影响检索和利用，长上下文容量不代表鲁棒使用。它支持对当前多人状态做位置/冗余消融，不足以证明本例就是位置效应造成。

## 5. Jev 能否适配

这里的 Jev 是 TypeSafe AI 的 System One 决策模型。官方接口接收 state 与类型化问题，返回 Choice、Score 或 Noul；它适合边界明确的语义判断，不负责生成新计划。[官方介绍](https://docs.typesafe.ai/introduction)

### 5.1 最适合：局部、证据明确的语义审查

可分别问：

- 本条汇报是否指出当前任务的阻塞条件？
- 本条“完成”声明是否有动作后观测支持？
- 本条汇报是在陈述观测，还是把意图写成已发生事实？
- 管理者提案是否遗漏给定的未完成责任？
- 提案是在修复不可行阶段，还是在声称原阶段已经完成？

为每个问题提供相关局部状态和对应声明，分类可设为支持、矛盾、证据不足。不要要求一次判断“整体任务、安全、资源、协作是否全部合理”。这是候选适配方案，目前没有 Jev 在本轨迹上的实测结果。

### 5.2 不应该交给 Jev：能精确计算的条件

距火是否小于 5 格、载客是否超过 5、当前地图格子是不是平民、记录是否过期，优先由环境 API/程序判断。未知状态返回未知，不由模型补成满足。

Jev 官方对 `jev-1.13` 明确列出数值精度、计数、多层间接推理、无关长上下文、冲突指令与选项顺序等局限，并要求数学计算留在代码中。因此把全体轨迹再交给 Jev，让它计算所有距离并批准整体计划，不是适配方向。[官方局限](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

### 5.3 合适的分工

环境记录提供事实 → 代码计算硬约束与反例 → Jev 判断局部汇报/提案的语义关系 → 规划模型产生修正 → 运行时决定是否提交。

对当前灭火 t=4：程序发现 AGENT_5 距已报告火点 2 格即可判定原安全条件未满足；Jev 的附加价值是判断“所有人安全”的声明与证据矛盾，或者区分“侦察完成”与“因风险中止”。它不需要重新算距离。

对运输：程序确认容量 5、待运 6 人；语义判断可识别需要分批并检查第六人的接送责任是否在计划变化后仍保留。新航线和多批规划仍由规划模型负责。

Jev 返回的类型正确和概率不是形式化证明，不能当作论文中 sound verifier 的替代。在线使用前先做只读轨迹回放，不让它改变动作。

## 6. 如何检验解释与 Jev 的增量价值

先从已有轨迹截取决策前的状态，隐藏后续结果，给每条约束标注满足、违反、未知，以及支持它的事件。标签依据世界状态而不是原模型的百分比。

对同一片段比较：原确认；原模型＋逐条约束清单；代码硬约束核验；代码＋Jev 局部语义审查。用未参与问题设计的片段做测试，避免只复述已知案例。

重点测：

- 不安全/未完成状态被批准的比例。
- 已满足状态被错误阻止的比例。
- 关键任务约束从观测到 worker、再到 manager 的保留情况。
- 改计划时未完成责任被丢失的比例。
- Jev 相对代码与原模型清单新增检出的错误，及新增误报、耗时与用量。

原因消融只改一个因素：移动关键反例的位置；去掉重复火点汇报；把“保持安全”的自报改成纯坐标事实；确认时去掉先前模型结论；删改 urgent 的平民示例。这样才能区分位置、冗余、叙事、自确认和示例影响。

## 证据入口

- [灭火 worker→manager 误报链，master log 86 行](../../benchmark_runs/communication_Suppress_Fire_Extinguish_seed1975/results/ORCH/master_logs/master_log_20261010_203811.txt:86)
- [灭火管理者任务/状态输入，235 行](../../benchmark_runs/communication_Suppress_Fire_Extinguish_seed1975/results/ORCH/Agent_9/chats.txt:235)
- [管理者首次决策，356 行](../../benchmark_runs/communication_Suppress_Fire_Extinguish_seed1975/results/ORCH/Agent_9/chats.txt:356)
- [管理者错误确认，412 行](../../benchmark_runs/communication_Suppress_Fire_Extinguish_seed1975/results/ORCH/Agent_9/chats.txt:412)
- [运输容量反馈与阶段调整，48 行](../../benchmark_runs/communication_Transport_Firefighters_small_seed283/results/ORCH/master_logs/master_log_20261010_162426.txt:48)
- [每轮重置管理者状态上下文，agent.py 368 行](../../ORCH/crew-algorithms/crew_algorithms/wildfire_alg/algorithms/ORCH/agent.py:368)
- [确认流程，agent.py 806 行](../../ORCH/crew-algorithms/crew_algorithms/wildfire_alg/algorithms/ORCH/agent.py:806)
- [阶段切换，agent.py 1562 行](../../ORCH/crew-algorithms/crew_algorithms/wildfire_alg/algorithms/ORCH/agent.py:1562)

## 总结

当前问题最准确的表述是：多 agent 的局部事实进入中心后，没有被保留为决定阶段变化的显式约束；确认又用同源叙事代替了事实核验。Jev 可作为局部语义审查器，但硬约束必须由可计算的世界状态决定，计划修复必须保留未完成责任。
