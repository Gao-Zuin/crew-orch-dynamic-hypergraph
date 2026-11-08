# v2 artifact/source audit（不改变冻结行为或指标）

本记录用于解释实验，不修改 `spec.json`、原 validator、arm、seed、行为代码或冻结指标定义。动态状态以各 case 的原始事件和 status 为准。

## 与已有 Minecraft 实现的对应关系

| MAS/hypergraph 实现 | CREW 适配 | 边界 |
|---|---|---|
| `hypergraph_coordinator.js`: updateNode / stateVersion / session / commit | `coordination/hypergraph.py`: observe / fresh / commit_topology | Python 同步宏步接入；不是异步 Minecraft 网络时序的复刻 |
| `resource_heuristic.js`: task workstreams、resource affinity | `crew_adapter.py`: 无任务阶段先验的近邻分组、局部 leader、共享 bridge | CREW 没有可靠 recipe/workstream 元数据，不把 LLM 分解自动变成 contract |
| `hypergraph_adapter.js`: bot inventory / task snapshot | CREW agent position、extra_variables、局部 structured map | 位置/水量/携带状态与地图缓存的 provenance 不同，见下文 |
| 临时 context、active/passive membership | 每次通信和行动 prompt 临时附加最新版组内 context | 不追加成一个持久公共事实历史；旧 agent 聊天仍存在，不能假定会被 evidence 自动纠正 |
| leader/member 路由和 guard escalation | HR 限定投递，保留 sent/delivered/failed/suppressed；runtime hard notices 真正写入 leader 历史 | 不自动减少每个 agent 的 LLM 调用频率；少投递不等于少 token 或有效协作 |
| requirements / completion / progress credit | 中立 reducer 的合成协议测试 | 正式 P/HA/HR 不启用手工 CREW workflow contract |
| receiver-side evidence | 中立 transaction API 要求发送后的 receiver 增量 | 通用物理 collector ID 未暴露，不声称真实 CREW HF 已实现 |
| Date.now 事件时间 | time.monotonic 事件时间 | 时间差只在单次进程内比较，不跨 episode 直接相减 |

## 发现 1：列表顺序不等于拓扑重组

v2 首个 P/Scout 的 `TOPOLOGY_COMMITTED` 原始结构变化序列是：

```text
members [1,2,3], leader 1
members [1,3,2], leader 1
members [1,2,3], leader 1
```

成员集合与 leader 未变，当前 `structural_change` 因 list 顺序发生变化而置 true。冻结汇总仍保留原 `topology_churn=2`，但不能解释成两次真实的成员/leader 重配置，也不能据此宣称图更不稳定或响应更快。

后续工程修复应对 members 集合做规范化 fingerprint，同时保留显示顺序；须另建源码版本及回归测试。当前实验中不修改计数定义或行为，不删除不利的 case。

## 发现 2：最新 observation envelope 不代表每个地图格都是当前直接可见

对照 Unity 源码副本：

- `WILDFIRE-ORCH/crew-dojo/Unity/Assets/Examples/Wildfire/Scripts/AIAgent.cs` 的 `CollectObservations` 取 `map.AccDataMap[i,j]`，是共享累积地图的局部裁剪。
- `MapManager.cs` 中 `miniMapRanges = {10,10,25,30,...}`，但用于实时更新与 fire-scout 计数的 `viewRanges = {5,5,15,20,...}`。
- `UpdateAccumulativeView` 汇总各类 agent；`UpdateSingleAgentView` 在真实 viewRange 内更新 AccDataMap，并按世界 `CellState` 计算 `current_fire_scouts`。

因此，crop 内一个 `f/i/e` cell 可以来自共享记忆，而不是该 agent 当前的直接视野。原始环境没有为每个缓存格提供最后观测者和 last-seen 时间；单纯给外层 snapshot 加 monotonic timestamp 无法恢复这些信息。

v2 `facts.observed_cells` 的正确解读是“最新环境 observation 中报告的地图格”，不能解读成“当前本 agent 直接看见的已验证世界火情”。`current_fire_scouts` 和原 validator 才是本任务同时确认条件的权威证据。这里对照的是源码副本，不把它当作对闭源运行构建逐字节一致的证明。

后续适配应显式区分：

1. 当前 runtime position / water / carried state；
2. 环境返回的 shared map-memory 值（cell-level freshness 不明）；
3. 原 validator 或直接 visibility mask 确认的条件。

不能把第 2 类在 projector 中无条件提升为第 3 类。当前 v2 保留原始字段与版本以便复查，分析不把地图格数量当作同时确认数。

## 第一组已结束 case 的解释限制

Scout seed4651 的 P 在 5 次动作后达标；HA 在 13 次动作后达标。两者都是原 validator 成功，不是“测试进程结束”代替成功。

HA 后半段连续 hold/idle，后续火场扩展使同时确认数达到 2。根据该轨迹，不能将其晚到的成功全部归因于更有效的 agent 协作；也不能仅凭单种子对比断言超图机制总体有害。配对表需保留时域、usage、完整动作与环境计数，等待其他预先确定的 case。

## 可复现源码快照

`benchmark_runs/hypergraph_campaign_v2/frozen_sources.tar.gz` 保存 manifest 中的静态文件，不包含 API key 文件或运行时 profiler Timers。即使以后修复工程问题，也可还原本版本进行复查。

归档 SHA256：`a203b7afd116582eb3d5fa31d3382da415dd560106c8330edfd35fddbeebcfef`。文件是否与 manifest 完全匹配，以归档逐文件 SHA256 审计为准。

2026-10-10 21:34 左右执行流式 tar 逐文件 SHA256 校验：manifest 493 个文件、归档 493 个普通文件，缺失/额外/哈希不符均为 0，`passed=true`。本次同时重跑 29 项离线测试，全部通过；`git -C CREW/ORCH diff --check` 通过。

## 首个种子的阶段性配对结果（非全实验结论）

| arm | 原 validator 成功 | 动作步数 | 返回的全程 token | recipient-level 投递 / 抑制 |
|---|---|---:|---:|---:|
| P | 是 | 5 | 123953 | 38 / 0 |
| HA | 是 | 13 | 402951 | 77 / 0 |
| HR | 是 | 5 | 135913 | 27 / 7 |

数据来自 case 00–02 的完整日志；三个 case 的基础审计均通过。HR 相对 P 少投递 11 条消息，但 token 多 11960（约 9.65%）；少投递不等于少生成消息，也不等于少模型调用。不能把不同独立 LLM rollout 的消息数差异全归因于 7 次 suppression。

HR 的 7 条被抑制消息均是 member 2 与 member 3 之间的直接交流，包括搜索区域确认、位置更新，以及 agent 3 向 agent 2 报告火场确认和等待第二名观察者。它们仍可经 leader 路径交换；本次任务成功只能说明这次轨迹没有因抑制而未达标，不能证明每条抑制都是无害冗余。当前没有逐消息因果标签，不报告 false-suppression rate 或 useful-message rate。

Scout 的三个 agent 都在一条边内，当前结果不验证重叠超边、bridge 的任务收益，也不验证资源交付能力。case 03（projector-off）仍运行时其 outcome 必须保持 unknown；完整 16-case 结果才能进行预定配对分析。后续 7-agent Transport 才能检查真实重叠拓扑下的运行与任务推进。

## 更新：首个 task-seed 的四组均结束

case 03 于 21:36:23 正常结束，exit 0、audit passed。原 validator 在动作 `t=19` 后成功，20 次动作；全程 534318 token（输入 481828、输出 52490），投递 89、抑制 37，耗时 494.21 秒。任务判定来自最后动作后的环境计数，不来自聊天中的“fire contact”。

同一 seed 的四组均成功：P 5 步、HA 13 步、HR 5 步、HR_projector_off 20 步。HR 与 projector-off 相差 15 步、398405 token；这是一次闭环配对观察，不是稳定的因果效应估计。模型采样和动作反馈可导致不同探索路线；需要其他冻结 seed/task，而不能只选择这一组展示。

projector-off 的轨迹显示长期在东/北区域搜索，agent 3 在 `t=17` 的通信中报告西南火场，随后其他 agent 改向 `(20,20)` 附近，在最后一轮形成两名 agent 同时确认。`t=16` 动作后的原 fire-scout 计数已为 1；日志中的口头报告比这一动作后状态晚一轮是正常 observe/reason/act 顺序，不自动构成漏报。地图裁剪和实际视野的限制仍适用。

运输 case 04 已启动，初始三个超边是 `{1,2,3}`、`{4,5,6,3}`、`{7,6}`，leader 为 1、4、7；3 和 6 是重叠成员，active 分别为前两条边。这证明真实环境中能形成重叠结构，但不证明 bridge 被有效利用。leader 路由只是允许投递关系，不是可靠的逐跳自动转发；尤其直升机 7 与其他消防员的跨边协作仍需 agent 主动交换依赖状态。

## 运输 HA 中的证据误读与纠正（进行中的过程审计）

case 04 的 `t=2` 通信轮，已经出现可以由结构化状态核验的误读，而非仅凭措辞猜测：

- events 237–240（state version 32–35）分别记录：4、5 在 `(38,51)` 且 `in_helicopter=true`；6 在 `(54,77)` 且 `in_helicopter=false`；7 在 `(38,51)`、载员数 5。
- event 301，agent 4 却声称 evidence 将“4,5,6”都放在 `(38,51)` 的直升机内，并询问 6 是否已经登机。
- event 316，agent 5 正确指出自己在机内，但又将“likely 4,6”一起推断为在机内；对 6 的推断没有环境依据。
- event 333，agent 6 用自己的实际状态纠正：仍在 `(54,77)` 等待，不属于这 5 名乘客。
- event 350，直升机确认载着 1–5，计划先送达，再返回接 6。此时这仍是行动计划；原 transported 计数尚为 0，不能宣布交付完成。

因此，结构化 context 并不能保证 LLM 逐字段正确读取，甚至会让错误消息带上“verified evidence”的权威措辞。这里的纠正发生在 HA（通信不受限）；之后 HR 是否允许关键纠正抵达相关 agent，需要检查其独立轨迹，不能直接移用 HA 的成功路径。当前仅保留人工核验的案例，不把五句话当作全局 contradiction/恢复率的无偏样本，也不据此改冻结提示。

## 运输 HA：到达不等于卸载（已核验的中间失败）

同一 case 的直升机动作/状态链：

```text
t0 pickup -> carried=5 at (54,77)
t1 move (13,12) -> (38,51), carried=5
t2 move (13,12) -> (22,26), carried=5
t3 move (13,12) -> (13,12), carried=5
t4 claim: “Batch 1 drop-off ... complete”
t4 action: move (54,77) -> (29,37), carried=5, transported=0
```

event 468 为 t3 移动，475/494 为到达后/下一轮前状态；event 599 为 t4 返回移动，606/625 为仍载着 5 人的状态。原始低层动作在此期间没有 code 3 卸载。Embodied 的 `prompts/translator/helicopter_translator.txt` 明确把卸载定义为独立动作；Unity 源码副本 `ControllerScripts/Helicopter.cs` 的 `DropOff()` 清空载员，`GameManager.cs` 仅在目标附近且消防员 `active`（地面）时计入 transported。运行数据本身已经足以否定“这一步已卸载”，无需依赖源码副本与构建逐字节一致的假设。

所以这不是动作慢或统计仅差最后一帧：到达时载员 5、下一次移动后仍载员 5、送达 0，与口头已完成冲突。HA 只是给 context，不强制执行 completion contract；本案例表明证据可用但未被 agent 正确用于确认阶段后置条件。后续是否自发恢复，以后续轨迹和原 validator 为准，不把中间错误直接当作最终失败，也不现场加入卸载规则替它修复。

### 后续：已验证的自发恢复

继续同一次运行，未改 prompt、未注入人工卸载指令：

- `t=5`，event 717：直升机明确承认 earlier drop-complete claim inaccurate，引用当前位置 `(29,37)`、carried=5；event 724 重新移动到目标。
- `t=6`，event 854：到达目标后仍载员 5，明确说 drop NOT complete；event 861 真正执行低层 `[3,0,0]` 卸载。
- `t=6` 动作后原 transported 计数从 0 增加到 5；`t=7` 直升机通信确认 carried=0，随后返回 `(54,77)` 接第 6 人。

这是一次有动作后条件支撑的恢复，不只是在消息里道歉。不能由这次恢复推出 HA 总体改善恢复率：缺少该错误机会的配对 counterfactual，且自然语言 claim 没有完整自动标注 denominator。case 尚未结束，最终成功仍以是否送达第 6 人为准。

### HA 运输终态：6/6 送达，恰好用满预算

case 04 于 21:47 左右正常结束，exit 0、audit passed，1851 条事件；最终 validator 为 `episode_end`，来源 `after_action`，transported=6、success=true。

最后一人的链路有直接证据：t10 pickup（event 1324），t11–13 返程移动，t14 unload（event 1826），动作后 event 1836 的 transported 从 5 升到 6。因此总计 15 次动作，恰好达到原定 horizon，而不是超预算或靠下一轮 CSV 才确认。

全程输入 703862、输出 68017，共 771879 token、420 次 API 调用，耗时 667.24 秒；投递 575、抑制 0（HA 不限制通信）。真实 overlap 存在，active-edge switch 4 次。结果/轨迹所有索引链接均存在。日志中的 local-no-delta 50 次包含等待/在机内保持等情况，不能当作 50 次浪费或使用原算法的 idle 计数定义解释。

当前仅 HA 运输完成，HR/P/干预对应结果尚未齐全；不能把一次成功和纠错案例解释为优于原系统，也不能把实际送达当作中立 handoff API 的物理 collector 安全已验证。HR case 05 已由同一 supervisor 启动，继续原冻结顺序。

## HR 运输终态与 HA 配对：少投递，但相同步数

case 05 于 21:59:12 正常结束，exit 0、audit passed；最终原 validator 成功，6/6 送达，15 次动作。全程 660803 输入 + 70518 输出 = 731321 token；耗时 699.99 秒。recipient-level 投递 219、抑制 287、失败 0，active switch 4 次、存在 overlap。

相对同 seed HA：投递少 356（约 61.9%），总 token 少 40558（约 5.25%），耗时多 32.75 秒（约 4.91%），最终步数均为 15。投递下降远大于 token 下降，符合路由不取消 agent 原始逐轮 LLM 调用的实现边界。独立 LLM rollout 的请求内容不同，不能把投递差全部等同于被抑制的 287 条消息。

HR 首批在 t4 正确卸载 5 人，比 HA 的 t6 早两步；但第二批重现了“到达=交付”的问题：

- t11 移动后已到目标，载员仍为 1；t12 event 1198 却宣称 scope complete、AGENT_6 delivered、all firefighters at target。
- t12 event 1205 选择移动到 `(11,14)`，没有卸载；原送达计数保持 5。
- t13 agent 4 发送纠正：6 仍在机内，运输未完成。普通 leader-to-leader 消息 `msg-1282` 和 `msg-1284` 均有对应 delivered（events 1283、1285），不是仅仅生成了警报文字，也不是硬事件绕过路由。
- t13 直升机承认 6 仍在机内并移回目标；t14 event 1409 执行真正卸载，动作后送达数升为 6。

所以不能将第一批更快直接外推为 HR 完整任务更快。正面证据是这次必要的纠正通过了局部 leader 路由，并最终恢复；负面证据是路由与 context 依然没有阻止错误 completion claim。两者都保留，且不据此修改冻结 policy。更完整的配对还需 P、projector-off 和第二个 seed。

逐动作证据表分别在 `TRANSPORT_HA_TIMELINE_WITH_PROVENANCE.md` 与 `TRANSPORT_HR_TIMELINE_WITH_PROVENANCE.md`；它们是只读辅助产物，不替代冻结 summary 或指标定义。case 06（projector-off）已启动，整体目前 6/16 terminal。

## 运输 projector-off：正常结束但仅 5/6，不删除失败样本

case 06 于 22:10:17 正常结束，exit 0、audit passed，但最终原 validator `success=false`，送达 5/6；15 步预算已用完。全程输入 482680、输出 64543，共 547223 token，耗时 664.61 秒；投递 194、抑制 397，active switch 10 次。其较低 token 不能单独称为效率收益，因为完成情况较差。

关键轨迹与消息可核验：

- t3 已到目标但仍载着 5 人；t4 的通信宣称首批交付 complete/confirmed，实际 event 469 却移动回接载点，送达数仍为 0。
- t6–10 连续出现去目标/去接载点的方向交替，始终没有卸载：t6→目标、t7–8→接载点、t9→目标、t10→接载点。
- t11–13 终于连续返回目标；t14 event 1434 首次执行卸载，送达才升到 5。没有预算完成第 6 人的运输。

与同 seed HR 相比，projector-off 最终任务失败，目标比例差 1/6，token 少 184098（约 25.17%）；不能只截取 token 下降宣传收益。其 observed goal AUC 约 0.02778，HR 约 0.58889；这个 AUC 只覆盖实际动作边界，不是带 contract 的 VMCR。

关闭 projector 仍保留 agent 自身原 observation/perception 和路由反馈，并非完全无观察。该轨迹提示共享结构化状态可能帮助纠错，但单 seed 的不同 rollout 不足以证明这一机制必然有效，且实际闭环拓扑不同。保留预定 P 和其他 seed/task 对照，不能在看到此失败后改 seed 或延长预算。

时间线：`TRANSPORT_PROJECTOR_OFF_TIMELINE.md`。同一 supervisor 已启动 case 07 P；目前 7/16 terminal，所有已结束 case 的基础设施审计通过，其中 1 次任务失败。两种终态明确分开。

## 首个运输种子四组完整：P 未卸载且错误宣布全完成

case 07 P 于 22:20:21 正常结束，exit 0、audit passed，最终 success=false、送达 0/6。15 步预算，全程 523839 token（输入 473254、输出 50585）、603.02 秒、投递 563，无抑制。

直升机 t0 载入 5 人，t1–3 到目标，却没有在任何一轮执行 code 3 卸载。t4 event 612 同时说“drop-off complete”和“5 firefighters aboard”，随后返回接载点；t7–9 再回目标。t10 event 1342 宣称“All 6 ... confirmed delivered”，t10–14 实际均在目标保持。最终机内仍 5 人、地面第 6 人未送达，原计数始终为 0。时间线见 `TRANSPORT_P_TIMELINE.md`。

| seed283 arm | 最终送达 | 原任务成功 | 步数 | 全程 token | 投递 / 抑制 |
|---|---:|---|---:|---:|---:|
| P | 0/6 | 否 | 15 | 523839 | 563 / 0 |
| HA | 6/6 | 是 | 15 | 771879 | 575 / 0 |
| HR | 6/6 | 是 | 15 | 731321 | 219 / 287 |
| HR_projector_off | 5/6 | 否 | 15 | 547223 | 194 / 397 |

同一个任务 seed 下，context 组的恢复和最终进展更好，但比 P 用更多 token；HR 比 HA 少投递、token 略降，却未减少动作步数或 wall-time。任务成功与成本必须并列解释，不能只挑有利维度。原 observation 在 P 中也存在，不能把失败说成没有任何状态输入；实际问题是自然语言已完成的叙事未被 runtime 后置条件纠正。

这提供了本探索实验的过程假设：显式局部 runtime context 可为队友纠正提供更直接依据，leader 路由在这次 HR 中保留了相关纠正路径。但没有 NLP 标注全样本、单个 task-seed 且 provider 非确定性，不能宣称普遍改善 alignment 或因果恢复率。第二种子按原顺序继续，不因首组结果改变候选源码或提示。

目前 8/16 terminal，全部基础设施审计通过，任务成功 6 次、失败 2 次；这不是全实验最终胜率。case 08 为 Scout seed6841 HR，Python/Unity 已确认运行。

## 第二个 Scout 种子：HR 已完成，其余待配对

case 08（seed6841 HR）正常结束、exit 0、audit passed；8 次动作后原同时观察计数达到 2，最终 success=true。全程 222348 token（输入 202909、输出 19439），耗时 189.79 秒；投递 38、抑制 11，active switch 0。仍为三个 agent 单条边，不能声称验证 overlap 的收益；冻结 raw churn=4 仍可能包含列表排序噪声，不改原统计。

目前 9/16 terminal；case 09 的 projector-off 已确认 Python/Unity 正常运行。另三组尚未完整，不能据此判断第二种子的 context 或路由效果，也不与第一种子的步数直接当作同布局重复比较。

### 第二种子的反向结果：关闭 projector 更快

case 09 正常结束、audit passed、原 validator 成功；6 步、139956 token（输入 126354、输出 13602）、146.53 秒，投递 28、抑制 7。相较同 seed HR：少 2 步、少 82392 token、少 43.27 秒。这与 seed4651 的 HR 5 步、projector-off 20 步方向相反。

这条反例必须和前面的有利案例并列报告：context 收益具有任务布局/探索路径/LLM rollout 依赖，当前两次配对不能给出稳定因果收益或统计显著性。关闭 projector 并非必然更差。case 10 P 已启动；目前 10/16 terminal。

## 两个 Scout 种子的完整结果

case 10 P：15 步成功、404087 token、357.10 秒；case 11 HA：7 步成功、192506 token、168.78 秒。两者 exit 0、audit passed，最终原 validator 确认达标。Scout 的所有 8 个 case 均成功。

| Scout seed | P 步数 / token | HA 步数 / token | HR 步数 / token | projector-off 步数 / token |
|---|---:|---:|---:|---:|
| 4651 | 5 / 123953 | 13 / 402951 | 5 / 135913 | 20 / 534318 |
| 6841 | 15 / 404087 | 7 / 192506 | 8 / 222348 | 6 / 139956 |

HA−P 在两种子分别为 +8 步和 −8 步，方向相反；两种子总动作数均为 20，不能说只加 context 稳定加速。HR−HA 分别为 −8 步和 +1 步，仍有异质性。HR−projector-off 分别为 −15 步和 +2 步；一个大幅有利样本不能掩盖反例。

两个 Scout 种子的总 token：P 528040、HA 595457、HR 358261、projector-off 674274。这只是预定两 seed 的描述性合计，不是大样本平均效应，也不跨任务合成单一效率排名。每次调用的随机性、轨迹长度与历史长度共同决定成本；没有额外重复可分离这些因素。

目前 12/16 terminal，全部 infrastructure passed；case 12 为 Transport seed2461 projector-off，Python/Unity 已确认运行。该任务的第二种子四组尚未完成，冻结 campaign 和整体目标继续进行。

## 第二个运输种子的 projector-off：最后一人未卸载

case 12 于 22:45:38 正常结束，exit 0、audit passed，但任务失败、最终送达 5/6。15 步、613770 token（输入 547983、输出 65787）、652.28 秒，投递 200、抑制 405。

与前一个种子的持续往返不同，这次首批已实际卸载，直升机也成功接载最后一人并返回目标 `(84,40)`。但从 t11 起它宣布所有人已交付（event 1198），随后 t11–14 都执行在原地保持的 `[0,84,40]`，最终 event 1513 仍显示 `firefighters_carried=1`。因此不是未到达或缺一帧统计，而是最后卸载后置条件没有成立。

时间线保存为 `TRANSPORT_SEED2461_PROJECTOR_OFF_TIMELINE.md`。两个运输 seed 的该干预均失败，但本 seed 的 P/HA/HR 尚未完成，不能跳过配对就下机制结论。目前 13/16 terminal；case 13 P 的 Python/Unity 已确认正常启动。

### 第二个运输种子的 P：首批送达，最后一人未卸载

case 13 P 正常结束、exit 0、audit passed；15 步后 success=false、送达 5/6。全程 600324 token（输入 540982、输出 59342），646.28 秒，投递 574、无抑制。

该基线实际卸下了首批 5 人；最后一名消防员与直升机主动移动会合，随后登机返程。但到达目标附近后直升机仍载员 1，最终未卸载。因此，不能把 seed283 P 的“从未卸载首批”直接套用到此 seed，也不能因最后一人已到附近就把 5/6 改成成功。

`TRANSPORT_SEED2461_P_TIMELINE.md` 保留逐动作状态。当前 14/16 terminal，全部基础设施审计通过；case 14 HA 已确认 Python/Unity 正常启动，之后仍需 case 15 HR。完整配对与候选新版真实环境门禁尚未完成，整体目标不标记完成。

### 第二个运输种子的 HA：12 步成功

case 14 正常结束、exit 0、audit passed；12 次动作后 6/6 送达、原 validator 成功。全程 610020 token（输入 555400、输出 54620），605.41 秒、投递 440，无抑制。

最后一人的返程是 t9–10 移动到 `(84,40)`，t11 event 1418 真正执行 `[3,0,0]`，event 1428 的动作后送达数升到 6。与该 seed P 的 5/6 相比，HA 多完成了真正卸载，而不是仅修改口头声明；token 多 9696（约 1.62%），wall-time 少约 40.87 秒，但 P 是预算内未完成样本，不能把二者都当作完整 completion latency 直接排名。

时间线：`TRANSPORT_SEED2461_HA_TIMELINE.md`。目前 15/16 terminal，最后一个 HR 已确认 Python/Unity 正常运行。完整分析仍等待该终态；后续候选修正需要独立门禁，不混用旧版效果数据。

## 最后一个 HR 的中间活性问题：等待超出容量的条件

case 15 进行中：t0 已载入 5 人；t1–2 持续原地保持，t3 重复 pickup，直到 t6 前仍在出生点 `(42,82)`、载员 5、送达 0。

events 151、250、348 的通信明确要求第 6 人登机才出发，含“holding ... until ... all 6 aboard”。这不是缺少载员状态：它正确知道当前 5 人在机内、6 仍在外。原始 Embodied `helicopter_description.txt` 明确“up to 5 total”，Unity 源码副本也设 `max_capacity=5`；后者不是对运行 binary 的逐字节证明，但原 agent 已获得的容量描述本身足以说明计划约束冲突。

这个例子与“口头已卸载但实际未卸载”不同：状态对齐可以正确，计划仍因不可满足的同步条件而失去活性。当前空间 heuristic 不推导分批 workflow，HR 也没有 capacity/stall planner；不能把它说成保证可执行协调。保持冻结行为观察后续能否恢复，不依据中间失败修改本 case。

### 建议到达中间 leader，但未被采用/转达

event 400 的普通消息从 leader 1 发往 leader 4，明确建议短暂等待后先送当前载员，再返回接 6，并请转告 7。event 401 证实该消息已 delivered。随后同轮 event 423，leader 4 发给 7 的却是“Continue holding ... Do not depart until ... 6 ... aboard”；下一轮 event 528 再次坚持同一条件。

这不是声称路由完全没有可达路径：1→4 已投递，4→7 也允许。真正缺口是局部 leader 没有采用并转发可行的分批建议，反而强化了不可满足的前提。系统不做自动可靠逐跳转发；也不能只凭这条轨迹证明若允许 1→7 直接通信就一定成功。第 11 轮前仍送达 0，继续等待终态。
# 最终交付索引（2026-10-10）

v2 全部 16 次实验已完成且基础设施审计通过：11 次任务成功、5 次任务失败；返回 token 总计 7,198,377。全量审计 15,668 条事件、9,664 张 PNG，合入新版前 493 个冻结 hash 匹配。以下正文保留逐阶段审计历史，其中“尚在运行”等叙述仅代表当时状态。

最终配对结果、负面案例与版本边界见 [HYPERGRAPH_RESULTS.md](../../HYPERGRAPH_RESULTS.md)。provenance / 成员顺序修正仅在 v2 完成归档后合入，当前 34 项测试及新版 v6 三 case Unity 门禁通过，旧版结果不用于声称新版效果。完整完成检查见 [REQUIREMENTS_AUDIT.md](REQUIREMENTS_AUDIT.md)。

