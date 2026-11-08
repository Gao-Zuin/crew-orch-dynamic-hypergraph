# ORCH 与当前 HT 的 LLM 输入差异审计

日期：2026-11-01。只读代码审计；没有修改运行逻辑、补充提示或启动实验。

## 范围与证据边界

比较本地 ORCH 主路径与当前 HT-R3（SoftTaskGraph + SoftTaskPolicy + Embodied）。已完成的 Flash/Pro 五任务是冻结的 HT-R2，不能视为已收到 R3 新提示。

ORCH 目录此次 git status 仅 __main__.py 有修改，下面所引 agent.py、worker_agent.py、horizontal_manager_agent.py、utils.py 和 prompts 没有工作区修改。这不证明下载的官方历史轨迹使用完全相同提交或分支；本审计回答本地官方实现的输入链。

路径基准：`../../ORCH/crew-algorithms/crew_algorithms/wildfire_alg/`（从本文件目录）。下文路径以 wildfire_alg 为根。

## 已确认实际进入请求的差异

| ORCH 来源 | 官方接收方与内容 | 当前 HT 对应情况 | 性质 |
|---|---|---|---|
| algorithms/ORCH/prompts/management/knowledge_base.json | agent.py:208–241 对 manager 载入 general；:387、:1852 等写入状态/规划请求。代码覆盖任务名为 general，不是动态选择任务专属知识。 | task_runtime.py:39–40 只读任务条目并写审计快照；soft_task_graph.py:53 decision_state 不输出 domain_knowledge；worker prompt 也未追加该字段。R3 的 WORLD_RULES 是另写的部分补充。 | 真正的静态知识传递缺口。 |
| algorithms/ORCH/prompts/team_overviews/{firefighter,bulldozer,drone,helicopter}.txt | agent.py:1434 _build_team_summary 构造名单、位置/状态（依 detailed）及按职业去重的详细动作说明，进入管理者分阶段与分工提示。该处相对路径读取失败会忽略描述，不能假设任意 cwd 都成功。 | 中心只收到 crew_adapter.CAPABILITIES 的 navigate/cut 等标签和在线信息；task_runtime.worker_abilities 虽读了 Embodied 详细说明，但未进入 decision_state。R3 WORLD_RULES 部分补充。worker 自身仍会收到自己职业的 Embodied 动作列表。 | 中心能力描述较粗；静态说明遗漏与不传实时位置是不同问题。 |
| worker_agent.py:124–242 内联提示 | worker 收到 mission/team phase/team mission；感知后生成 summary、percent_complete、urgent；显式列出已完成 option、当前 option、未来最多两个 option、idle_steps。 | worker 有任务建议、观测摘要、消息及过去动作；没有相同的 option 当前/未来状态与逐步进度字段。R3 历史记录返回命令、位置/资源，不能等同 option 完成状态。 | 执行框架差异，并非漏加载某一 txt。 |
| agent.py:550–650、horizontal_manager_agent.py:状态汇总 | manager 状态请求逐成员列任务、进度、status、urgent、执行/闲置，部分分支带近期动作；提示选择继续、转阶段、改写任务、补阶段等。 | leader 收消息和本边上下文；中心只收到最近 leader 报告，不自动接收所有成员状态表。 | 原 ORCH 管理过程信息更结构化；HT 自下而上汇报策略也刻意减少自动信息。 |
| agent.py 的 _async_handle_new_mission / _async_handle_phase_transition 等内联提示 | 任务分成阶段，列过去/当前/未来阶段，给出 completion_condition，状态评估据此判断。水平 manager 没有同样的阶段结构。 | 图有 goal/tasks/advice，但无同款阶段队列和独立 completion_condition。R3 建议以观测核实结果，没有实现该状态结构。 | 架构不同；不能只复制提示而声称获得相同闭环。 |
| algorithms/ORCH/prompts/planner/*_planner.txt | utils.py:625 读取并填入位置、当前格、感知、任务及水量/载客；生成最多 20 个高层动作 option。 | Embodied/utils.py 读取 Embodied/prompts/descriptions/*，每次选一个动作。职业动作没有整体丢失；缺少高层 option 分解与持续执行上下文。 | 不能直接搬入“一个 Move 到达任意位置”等 option 语义。 |
| algorithms/ORCH/prompts/translator/*_translator.txt | utils.py:780 读取，翻译动作序列，包含 Cut x / Cut all 等 option 类型。 | Embodied 有自己的单动作 translator；类型编号与 ORCH 不同。 | 有对应组件，非遗漏的环境知识文件。 |
| ORCH/utils.py:1035 critique_team_structure、生成结构内联提示 | 结构 critic 接收任务、职业数量、结构、能力与简化层级原则，拒绝后作为下一次结构生成输入（是否执行取决于生成入口）。 | SoftTaskPolicy 有自身组织建议与 JSON 输出约束，没有该 critic。R3 包含部分小组简化建议。 | 明确的组织算法差异，非需照搬的静态规则。 |

## general 知识中尚未统一明确传给 HT-R3 的内容

以下指未在当前共享 WORLD_RULES 中完整表达；不意味着模型不可能从任务、动作列表、观测或聊天中偶然得知。

- Scout Fire 要至少两个 agent 同时看到火（知识库用“两架无人机直接位于火上”的说法）；R3 没有统一给出这条任务要求。其准确适用范围应以引擎/任务判定核对，不能把 general 原句当作所有任务约束。
- 发现火应尽快确认。
- 消防员一次携带一名平民、拾取距离 4 格。worker 观测能显示是否携带，动作写附近；这不等同中心有明确容量和距离规则。
- 平民会自行移动，要适应并重新搜索。
- 直升机能搭载携带平民的消防员。R3 只写运消防员、不是平民，缺少间接运输的组合能力说明。
- 不要对同一位置重复洒水。官方写得绝对；能否复用应对照环境状态，不宜无条件复制。
- 地面消防员/推土机会被火摧毁，general 建议距 ignited/on-fire/extinguishing 格至少 5 格，避免驶入/穿过；不要损失人员。R3 尚无同等完整安全描述。5 格是官方知识库建议，不应声称引擎硬阈值。
- 火每隔若干步向相邻格扩散。
- 洒水灭火并形成湿地隔离。
- 完整隔离带需要无树格连续，包含角落；围控需四周都封闭。
- 官方 general 的“水耗尽再补”同时指消防员和直升机；R3 空箱限制的详细解释只明确写在消防员段落，不能声称两职业已完整等价覆盖。

R3 已补充官方 general 没有这样明确表达的内容：单次 Cut 一棵、砍树不耗水、消防员正水量不能补满、投水不能给其他 agent 补水、无人机能力边界、命令不等于完成、复述不等于独立证实。因此不是简单的官方提示子集。

## 不应算作“官方已启用、我们遗漏”的文件/路径

1. child_feedback/*_child_feedback.txt：agent.py:1304 的反馈请求确实把 manager 的 knowledge_base 放入 worker 的反馈输入；但 agent.py 的阶段转换、任务重写、新任务三处，以及 horizontal_manager_agent.py 的重写/新任务两处，全部 max_iterations=0。当前常规调用不会执行反馈收集。此前即时更新说“worker 会收到”过于宽泛：应为“代码支持传给 worker，但当前主路径关闭”。
2. prompts/management/{critic_context,status_phase_context,action_phase_context,vertical_manager_prompts,horizontal_manager_prompts}.txt：当前 Python 主路径没有检索到按这些文件名加载。主要实际提示在 agent.py、horizontal_manager_agent.py、utils.py 中内联，不能按文件存在推定生效。
3. prompts/worker_status_prompts.txt：是代码提示摘录，未找到加载路径；worker_agent.py 内联版本才是实际来源。
4. prompts/oldplanner/*：未找到当前主路径加载；实际加载 planner/*。
5. overviews/*：构造时读取并更新 overview，但未找到其在当前主路径直接进入 LLM 请求的使用；实际 manager 能力摘要主要来自 _build_team_summary。
6. Agent.__init__ 尝试读取 WILDFIRE_MULTI_ALG/*/manager_prompt.txt 到 self.planner；当前 ORCH option 生成实际使用 utils.py 的 ORCH/planner/*，不能算两个 planner 都在用。

## 结论与解释边界

最明确的输入接线问题是：已有的静态 domain_knowledge 和 worker_abilities 进入了审计对象，却未进入组织器请求；leader 没有继承 ORCH manager 的知识输入。R3 是人工补充的一部分规则，尚不完整。

状态汇总、阶段完成条件和 options 的差异会影响执行，但属于不同架构的实际机制，不能混入“补齐知识”的修改；本次未改动。

只凭静态审计不能量化这些缺口导致了多少任务失败，也不能确认官方历史轨迹的每个请求内容。后者需要对所选官方轨迹对应代码版本及完整输入另行核对。
