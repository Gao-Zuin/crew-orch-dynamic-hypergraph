# ORCH 与 WILDFIRE 四种基线的 LLM 输入对照

2026-11-02，只读审计。比较本地 generalroboticslab/ORCH checkout（HEAD 104b488）所含 ORCH、CAMON、COELA、HMAS_2、Embodied。不是对论文历史每次请求的复原，也没有核对另一独立 WILDFIRE 仓库的全部版本。

源码根目录：`CREW/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/`。CAMON/COELA/HMAS_2 的 agent.py、utils.py、prompts 无工作区修改；各 __main__.py 有修改，所以另用 git show HEAD:<path>核对原提交调用链。Embodied agent.py/utils.py 有修改，基线结论使用 git HEAD 版本，并排除本地 hypergraph_bridge 注入。

## 主要结论

ORCH 确实向 manager 增加了其他四种基线没有统一加载的环境知识，同时增加了结构化的感知、阶段、进度与重规划上下文。因此比较不只是替换组织拓扑。不能据此量化知识提示的收益，也不能反推论文所有轨迹必然用了同一版本。

ORCH 并非所有角色拥有更多可见信息：CAMON leader 有全队观测/位置/当前与过去动作，HMAS_2 中心有全队感知/动作菜单/历史。它们没有相同环境知识库，不等于没有集中观测或能力说明。

## 逐项对照

| 内容 | ORCH | CAMON | COELA | HMAS_2 | 原 Embodied |
|---|---|---|---|---|---|
| 加载 general 环境知识库 | manager 是 | 无 | 无 | 无 | 无 |
| 自己职业动作菜单 | planner/translator | descriptions/translator | descriptions/translator | descriptions/translator | descriptions/translator |
| 集中决策者有各职业具体动作菜单 | manager 的 team_overviews（路径读取成功时） | leader 聚合全队职业 descriptions | 无中心，各自自己菜单+队伍职业概述 | 中心逐 agent 接收 available_actions | 无中心，通信有职业概述，行动有自己菜单 |
| 原始局部字符地图、当前位置、资源、附近 agent | worker 感知输入有 | 感知输入有 | 感知输入有 | 感知输入有 | 感知输入有 |
| 程序先解析关键目标坐标再交 LLM | worker KEY FEATURES 有 | 无同款 | 无同款 | 无同款 | 无同款 |
| 全队/下属状态汇总 | manager 接收下属摘要、任务、进度、urgent 等 | leader 接收全队观测/位置/动作 | 主要依靠聊天 | 中心接收全队感知及可用动作 | 主要依靠聊天 |
| 持久任务阶段及完成条件上下文 | vertical manager 有；horizontal manager 不同 | 无同款 | 无同款 | 无同款 | 无同款 |
| worker 当前/未来 option 时间线 | 有 past/current/next options、idle_steps | 有过去动作，leader 还看当前动作 | 有过去动作 | 中心有之前状态—动作对 | 有过去动作 |
| 专门的结构生成 critic | LLM 生成入口有；指定/预生成结构可绕过 | 无同款 | 无同款 | 无同款 | 无同款 |
| 计划反馈 | 存在函数，但五处循环 max_iterations=0，当前常规调用关闭 | worker 提案交 leader 评审/可覆盖动作 | 自己权衡消息与动作 | 每步收一次 worker feedback，但 max_feedback_rounds=0 时不据此重规划 | 无同款中心反馈 |

## 1. 额外静态知识：最明确的信息不对称

`algorithms/ORCH/agent.py:208–241`：只给 manager 加载 `prompts/management/knowledge_base.json`，而且把 current_level 覆盖为 general。知识实际进入状态请求与新任务规划请求（:387、:1852；horizontal_manager_agent.py:68、:803）。

其他四种基线的实际 prompt 构造未读取该文件，也未发现等价完整规则块。它们的 descriptions/translator 主要列动作；不能由“有 refill / pickup 动作”推定已提供具体前置条件与组合能力。

general 中的差异包括：

- 水耗尽再补。
- 直升机不能直接接平民，但可搭载并部署带着平民的消防员。
- 消防员一次携带一名平民、距离 4 格内可拾取；平民会移动。
- 地面人员/推土机易被火摧毁、建议距火至少 5 格、不进入/穿过火区。
- 火向邻格扩散，洒水形成湿地隔离，防火带连续并覆盖角落、四周围合。
- Scout Fire 的共同观测要求、发现后尽快确认、避免同地重复洒水。

其中有任务判定知识、物理规则，也有策略建议；不能把安全距离等建议直接称为引擎硬限制。general 原句适用性仍需按任务/引擎核实。

## 2. 观测处理也不同，不只是文件多

`ORCH/worker_agent.py:320–362` 把原始网格与 `_parse_grid_features()` 的结果一起传入感知请求；:396–492 程序计算火、平民、水源、建筑、已灭火格的坐标/区域。:148 附近提示 KEY FEATURES 是权威来源。

其他四种的 agent.py 感知提示主要让模型从字符地图自己数格、算目标坐标。原始局部网格与资源大致同类，ORCH 多的是程序提取后的表示，并非因此获得原本不可见的全局地图。该辅助可能减少空间读取错误，实际效果未做消融。

## 3. 能力说明并非其他方法都没有

CAMON/utils.py:130–242 的 generate_plan 和 :425 之后的 leader review，把全队 descriptions 聚合给 leader；同时给全队 collective observations/locations/current actions/past actions。HMAS_2/utils.py:144–257 的 propose_actions 将每名 agent 的感知和 available_actions 交给中心，并加入 step_history。

COELA/utils.py 的 communication/action 提示有队伍职业概述、个人感知/过去动作/聊天；action 读取自己的 descriptions。Embodied 原始路径同样有个人动作说明、通信队伍概述与聊天。不能说它们只拿一个职业名称。

## 4. 新发现：动作菜单本身存在不一致

CAMON/prompts/descriptions/firefighter_description.txt 与 COELA 对应文件，列了 pickup，却漏列 drop civilian；它们的 firefighter_translator.txt 又支持 Drop off。ORCH firefighter planner、HMAS_2 与 Embodied descriptions 列出 drop。

所以原始提示存在“翻译器能执行，但决策菜单没列”的不一致。这可能阻碍模型主动选出放下平民，不能只凭静态代码断言某条官方任务因此失败。此次未修改这些文件。

## 5. 历史与反馈的实际状态

- ORCH：worker 状态提示明确列任务/团队阶段/团队任务、过去/当前/未来 option 和 idle_steps，生成 summary/percent_complete/urgent。manager 汇总下属任务、进度、urgent、执行状态，vertical manager 以 phase completion_condition 等上下文选重规划动作。
- CAMON：leader 的全队状态可见性很强；worker 提案会被 leader 接收、拒绝或改写。其 past_options 是过去 option，不应一概当作原始物理动作。
- COELA：聊天列表意图限制 5 条，但 add_message 在 append 后调用 pop() 删除尾部，所以满 5 条后丢的是新消息；不能描述成“最近 5 条”。静态发现，未追溯是否命中某个历史失败。
- HMAS_2：主循环每步会收 feedback；max_feedback_rounds=0 只阻止反馈后的再次规划，不阻止首轮 feedback API 调用。step_history 意图保留 5 步，但按 state_time[-1] 解析时间，十位步数后不能可靠理解为最近 5 步。两处在 HEAD 已存在。
- Embodied：HEAD 主循环 clean_messages(t,1)，普通聊天保留当前/上一时间步；过去动作另列。

## 6. 文件存在不等于已进入请求

沿用前一审计的边界：ORCH 的 management/{critic_context,status_phase_context,action_phase_context,vertical_manager_prompts,horizontal_manager_prompts}.txt、worker_status_prompts.txt、oldplanner/* 未发现当前主路径按文件加载；很多是内联提示的摘录或旧实现。

child_feedback/* 的请求函数可给 worker 附上知识库，但五处调用循环 max_iterations=0，不能把它算成当前已经启用的额外输入。实际生效的结构 critic 提示在 ORCH/utils.py 内联。

## 对结果解释的影响

同一地图、seed、任务时域仍不足以隔离“组织架构”的贡献。这里至少还混合了环境先验、观测表示、动作菜单完整性、执行抽象、历史保留与反馈流程差异。

若比较整体系统，可以保留这些差异并明确报告。若要归因于超图/层级等组织方式，需要先统一静态环境事实和基本动作语义，再分别说明哪些观测和上下文属于被比较架构。不能据本审计直接宣称论文无效或某种方法必然更好。
