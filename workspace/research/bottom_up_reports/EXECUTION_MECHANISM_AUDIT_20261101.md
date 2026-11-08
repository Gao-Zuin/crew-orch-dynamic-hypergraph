# 当前HT执行路径中的隐性干预清单

2026-11-01。只读审计；本次不修改代码。范围：HT-R3 + Embodied实际调用路径，追溯Flash/Pro的HT-R2行为；不把未启用的空间策略或HG实验机制混入结论。这是本路径清单，不宣称整个Unity/仓库已穷尽审计。

## 已确认的bug

|项目|来源与触发|实际影响|状态/证据|
|---|---|---|---|
|360秒墙钟过期hold|本地Coordinator.fresh被旧HT guard使用|当前同步模拟步即使未推进，长LLM调用仍让动作被替换为原地|R3移除HT检查；FlashRapid step17四次、ProSparse step12十次真实触发；HG另有fresh检查不属于当前HT|
|提议提前进入过去动作|Embodied.action_round在guard/env.step之前append|被替换/未执行的Cut也能变成“我已经做过”|R3 HT改成返回后记实际命令；非HT原记录方式仍保留|
|动作库异常返回原点向量|Embodied.utils.action_round except/未知职业分支返回[0,0,0]，except还append IDLE|环境动作0是朝(x,y)移动，不保证待机；例如越界目标在动作库raise后可能变成往原点走|仍存在，未在本批证明实际触发；不是cut/水规则，也不是超图特有。翻译解析失败返回Action(type0)则通常由动作库转为[0,current]，应区别两条路径|
|无烧树则不判灭火成功|共享core.alg_utils.check_game_done，game_type3/5先查rewards[1]==0|实际起火并完全熄灭、没有烧树也持续判失败|未改原判据；ProRapid第5–99步fire_active=false、灭火格1却全程失败。它是共享判定问题，不是超图要求|
|版本标签不一致|RuntimeBridge.RUN_STARTED仍硬编码HT profile v2；TaskRuntimeBridge.TASK_HYPERGRAPH_STARTED已v3|不改变物理行为，但可误导版本追踪|当前仍存在；审计器依据后者，不能只看RUN_STARTED标签判定版本|

## 仍在运行的本地规则/调度，不应全部叫bug

- **物理动作替换**：HT guard对消防员0水喷水及无action选择当前点hold，反馈原因。Refill的非水源拒绝分支仅在current_cell_source=direct_runtime触发；当前编码是shared_map_memory，所以不能声称本地按缓存地图禁止补水。直升机低层code3兼卸人/投水，校验函数主动不做此类拒绝。源码docstring还写HG-only，但HT确实调用了它；注释不等于调用边界。
- **乘机/离线**：requires_hold对乘机或not graph.ready停步；graph.ready实际只看live_agents，不检查active是否唯一、不是组织建议许可。allows_inference同样只跳过不在线成员。事件原因字符串还含blocked/unassigned/stale，是粗标签，不能据此认定R3仍有墙钟检查。
- **消息路由**：GROUP只给当前边成员，LEADER/ORGANIZER只允许当前leader。非法消息被丢弃，R3有发送者本地格式反馈；无重试、回执、等待回复或解决状态机。这是本地通信限制，不是环境/超图数学上的必然限制。给自己REPORT或只剩自己的GROUP不会向其他人送达。
- **中心更新时机**：初次、在线成员变化、新leader报告或距上次计划5步才调用中心；并非每个新发现都自动传中心。中心只收初始任务/能力在线名单/图/leader报告，没有实时位置或水量快照。
- **方案验收/保留**：version/evidence ID、成员合法性和唯一active等不合法会拒绝整份新方案；保留可用旧图，减员只清理离线成员、leader死亡则选已有首位幸存成员；没有可用图才fallback为mission。它可能造成图未按模型文字意图更新，但不直接hold在线agent动作。fixed_groups只有显式启用才锁组，本批没有启用。
- **消息窗口与顺序**：普通历史clean_messages(t,1)，仅保留当前与上一步；图上下文只带最近5条收件消息；中心最近20条报告。每步只有一轮通信，worker先、leader后；已发言者不能同轮再回复后来消息，但动作阶段可读更新。这些会影响反馈和跨组对齐，而非动作权限。

## 更底层/共享层的自动行为

- **动作解析**：缺action标签返回None，当前HT将其转为当前点hold；ProSparse第22步10号确有1次。翻译解析失败转idle，以及动作库异常返原点，不能统称为模型主动待机。
- **上下文截断**：token_guard默认自动截断，DeepSeek本地按256000预算减4096输出预留；过长时保留最长消息头尾、裁中间。PRINT_TOKEN_COUNTS=False，没看到auto-truncated日志不能证明未触发。本批没有足够证据归因某次失败于截断。
- **API重试**：worker guarded_chat_completion对暂态错误外层最多4次，SDK内层也可能重试；客户端可等待很久，中心timeout90/max_retries1，输出最多4096token。会增加耗时/费用，旧HT曾把时延再变成hold；R3不再这样耦合。
- **原生动作条件**：FF仅0水补到5；直升机0水才能载消防员、没有乘员才能补水；这些是Unity执行语义，R3仅提示清楚，没有新加动作限制。FF单次Cut只砍一棵；当前Embodied未调用ORCH cut-all完成循环。
- **结束/事件顺序**：成功检查在当步物理动作/事件提交前，若原判据提前成立会退出；时域是配置max_steps。预设事件在该步动作槽0提交，返回后通知agents，不直接给中心。若同一步配置多事件当前只提交第一条；本批原预设均单事件，未据此发生丢事件。

## 不在当前HT路径上的旧机制

SpatialPolicy按距离/每组约3人、HR/HG的协议路由/恢复重试、实体交接事务等旧基础设施不能因文件存在就说在HT运行。TaskRuntimeBridge覆盖observe/prompt/dispatch/guard，使用SoftTaskGraph/SoftTaskPolicy。当前active归属是建议，不是强迫只能做该边动作的执行锁。

## 优先级

首先应单独处理异常fallback原点与误导性IDLE、灭火判定假阴性、版本标签/事件原因等追踪不一致；再根据实际轨迹评估路由限制和短历史是否合适。不要继续把这类实现自动行为都归为“LLM能力不足”。此清单不构成新增限制或修复已上线的声明。
