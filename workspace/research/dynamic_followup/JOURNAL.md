# 实验日志

## Cycle 001 — 2026-10-24

### 读取的证据

- 100 步第二火点/seed42：21 次提交，只有一次实际拆组；新火点组拆组后无喷水，leader 长期等待集合。详情见 `../task_hypergraph/dynamic_audit_20261024/REPORT.zh-CN.md`。
- 18:27 检查：前一批固定/动态 12 步探针已结束，均机制审计通过；动态轨迹 88 次授权，无 held。短窗口不当作完整任务效果。
- `TaskRuntimeBridge.observe` 已构造 13 项 reward_schema，但 `SoftTaskGraph.decision_state` 将名称丢弃，只给组织器无名称 rewards 数组。历史长轨迹实际模型请求证实遗漏。

### 唯一修正

在 decision_state 添加一项 `reward_schema: world.get('reward_schema', [])`，保持模拟器指标顺序。没有改变触发频率、分组规则、通信权限、动作限制或成功判据。它是输入语义修复，不承诺解决补水/会合失败。

### 验证

新增回归测试截获 SoftTaskPolicy 实际请求：修改前稳定报 `KeyError: reward_schema`；修改后指标名称与数值逐项对应。8 项轻量图测试、7 项 runtime 测试通过，输出见 `cycle_001_tests.log`。

### 预定真实运行

| case | seed | 完整预算 |
| --- | ---: | ---: |
| Transport_Firefighters_small | 2461 | 15 步 |
| Suppress_Fire_Extinguish_Second_Fire | 137 | 100 步 |
| Suppress_Fire_Extinguish_Second_Fire | 256 | 100 步 |

使用 deepseek-chat、temperature=0，动态成员，不重放起始组、不人工换人、不提前事件。输出与运行副本放 `/data1/gzy/crew_dynamic_followup_20261024_cycle001`。新 seed 与旧 seed42 不能构成修复因果对照；这里只增加覆盖并观察失败是否重现。

### 下一轮重点

先查 batch/progress.json 与实际进程。每条结束后查组织请求指标名称、真正拓扑变化、任务计数、补水成功率、等待往返、跨边投递；区分模型错误、环境机制与代码错误。若提出新修正，先保留对应事件和失败测试，再改变原始工作树；不能修改当前冻结副本。

### 2026-10-25 10:25 启动确认

获得沙箱外执行权限后，隔离批次已启动，supervisor PID=4019868，当前 transport_seed2461。真实 TASK_ORGANIZER_REQUEST 已包含 13 项 reward_schema，证据保存 cycle_001_live_input_check.json；这仅证实接口修复进入实际调用，尚无任务效果结论。批次使用 plan.json 预定三个 case，无自动重试。下一次读取 batch/progress.json，再核对进程，避免重复启动。

### 2026-10-25T10:27:21.996175+08:00 唤醒核查

上轮属于实质进展：接口修复、回归测试、真实启动均有证据。本轮核对存活supervisor PID 4019868 与Unity进程，未重复启动；当前 transport_seed2461，最新快照 {'step': 3, 'phase': 'before_action', 'rewards': [4738, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}。另完成短探针对照审查：第0步已分叉，不能把动态臂后续2人损失归因于调组，见 probe_pair_review_20261025.md。未发现需要立即修改冻结实现的新证据；当前先等待完整轨迹，避免无依据叠加规则。

2026-10-25T10:28:42.389360+08:00 再次确认supervisor存活；运输动作后event 433（step 4）已送达 5/6，held原因仅aboard。记录为运行中进展，不称最终成功。证据 cycle_001_transport_progress.json。

## Cycle 002 — 2026-10-25：补水动作语义核对

上轮属于实质进展/已验证等待：记录短探针第0步前缀分叉，并确认运输5/6进展和存活supervisor。本轮没有重启已有进程。

### 失败证据与可验证假设

旧100步seed42长轨迹共有216次补水，全部在已知水源(15,22)：16次初始水量0均升至5；200次初始水量>0均未增加。动作事件与前后状态保存 `cycle_002_refill_evidence.json`，包括源事件文件SHA-256。示例event521/step4/agent1：0→5；event1307/step11/agent3：3→3。当前Unity C# RefillWater循环条件也为water==0，提供实现侧佐证；不把当前C#无条件当作下载二进制的同版本证明。

可检验假设：执行agent不知道补水不能补满非空水箱，因而反复尝试top-up。它只是一个失败因素假设，不解释全部导航/会合错误。

### 最小修正

仅更新Embodied消防员动作描述：水量0时在水源补至5；非空水箱不会补满。没有增加动作拦截、等待超时、固定路线或强制拆组；也没有修改模拟器。准确性质是动作说明/接口语义补全，不是宣称环境实现已修复。

### 测试

新增测试调用真实action_round提示组装，mock网络与翻译，检查动作请求包含补水条件和容量；同时水量3时仍可返回底层补水动作，证明没有增加veto。旧描述下测试失败，输出 `cycle_002_red_test.log`；修正后1项提示测试、8项图测试、7项runtime测试通过，输出 `cycle_002_tests.log`。离线测试不能证明模型会遵循或任务效果提高。

### 正在运行的批次与下一步

Cycle001仍在隔离副本串行运行，副本保留schema-only版本；此改动未注入当前或后续已排队的case。等完整结果，再确认相同补水失败是否重现，决定是否以同seed、同预算做仅动作说明变化的后续实验。不能用当前运输成功或新seed差异证明本轮修正有效。

## Cycle 003 — 2026-10-25：完成出口用量漏记

### 新的完整运行结果

Cycle001运输seed2461实际完成10个动作步，在第10轮动作前确认运输6/6，原validator success=true，退出码0，52次授权、18次因乘机held，无方案拒绝。全程组成员/leader未改变，3次图提交只是初始及任务更新，不能将成功归功于成员动态变化。

然而原audit唯一失败为usage differs from final usage，supervisor按预定门禁停下，后两个火点case没有启动。已确认旧supervisor PID4019868消失且无Unity遗留进程，不因瞬时观察超时推断终止。

### 实现错误与修正

真实循环在检查任务已完成前调用before_step/组织器，第10轮有最后一次组织调用，但提前break跳过after_step，因此漏记增量LLM_USAGE。记录合计384163/28230，最终385393/28572；差值1230/342恰好等于最后组织器响应event872的用量。

在RuntimeBridge.after_step记录用量后更新checkpoint；finish只补记checkpoint之后的未记用量。没有挪动任务判断、修改组织策略、放宽审计或补造世界进展。

### 测试与历史证据

原实现下新增finish无物理步测试稳定失败；修改后9项runtime（含无after_step结算和完整轮不重复记账）、8项图、1项实际动作提示测试通过，见cycle_003_{red_test,tests}.log。另用真实记录的未记增量经修改后的finish生成补记事件，在单独派生文件中重放通过；见cycle_003_usage_reconciliation.json。它是离线派生修复验证，不是原始日志本身审计通过。旧status、audit和事件文件均保留原样。

### 后续运行决策

不重跑已成功运输任务；剩余第二火点seed137/256各100步迁移到新隔离批次 `/data1/gzy/crew_dynamic_followup_20261025_cycle003`。新版本包括schema、补水语义说明和完成出口记账修复，不与旧schema-only版本混称同版本重复；组规则/动作权限/成功判据不变。新批次继续按审计和完整性门禁，真实任务失败仍保留并继续，无自动重试。

### 2026-10-25T10:37:36.973979+08:00 新批次输入核验

上一轮为实质进展：完成运输、修复记账、测试和启动新批次。本轮确认PID 4027781 存活且Unity在运行；未重复启动。真实organizer请求event 21包含13项指标名，8名执行者chats.txt均包含修正的补水说明。最新快照 {'step': 2, 'phase': 'before_action', 'rewards': [374, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}。这些证据只验证输入接线，不证明行为或任务改善；在新完整结果前不继续修改冻结实现或追加规则。证据cycle_003_live_input_check.json。

### 2026-10-25T10:40:45.616628+08:00 新的规划失败线索

上轮完成真实输入核验，属于证据进展；本轮再次核对supervisor PID 4027781存活。seed137初始图event23要求2号储水relay、8号receive water、两组协调water handoffs，但消防员现有动作没有给队友转水接口。world event19包含worker_abilities四类完整描述，实际organizer请求event21却丢掉该字段，仅含capabilities名称。证据cycle_003_unsupported_water_handoff.json。

候选最小修正是传递已经存在的动作说明，不增加“必须怎样分组”或水交接拦截规则。当前先记录候选，等待完整轨迹观察执行者是否自行纠正；不在冻结运行中改变提示，也不立即再开一版实验。尚不能把计划错误直接判定为后续任务失败原因。

### 2026-10-25T10:43:43.140771+08:00 候选修正先做可证伪重放

上轮为实质证据进展：定位不存在的水交接和输入动作说明遗漏。本轮进行同一记录快照3+3次控制层输入对照：baseline原输入，candidate只补worker_abilities。6次结构均合法、成员结构相同；candidate至少1次仍要求relay water forward，未证明修复。成本6调用、输入6927/输出2789。原始请求/响应和人工分析在 worker_abilities_replay_20261025/，复现工具 replay_worker_abilities.py。

暂不采纳为已有效修正，不追加禁令或分组模板。已再次确认supervisor PID 4027781存活；真实运行最新快照 step 8 before_action，未结束。控制重放不计入物理轨迹数量。

### 2026-10-25T10:46:16.812786+08:00 不同类型的补水失败

上轮控制输入对照属于实质进展：获得候选修正不能保证消除水交接的反例。本轮核对supervisor 4027781存活并重建首8步补水结果：4次在(26,10)、缓存当前cell=0的空箱补水均未增水；5次在真实水源(8,24)或附近的空箱补水均0→5（含(11,23)，说明不能把“必须正好站在水格”硬编码成新限制）。尚无非空top-up命令，早期数据不与旧seed42直接作效果比较。

进一步找到6号首条感知摘要虚构(26,10)水源；初始world中其cached_water_cells为空。消息event48把虚构点发给5号，event120又引用5号的确认作为自身依据，event193称confirmed water source。随后动作event138、212、214、218补水无效。5号感知实际上写没有水源、没有水，但行动仍被同伴消息锚定，甚至称full tank。证据和原文在cycle_003_false_water_chain.json。

这不是已修复的非空补水语义问题，也不是给转水任务加一条禁止规则就能解决。候选方向转向观测/消息来源与实际动作效果的输入绑定，需先用记录提示验证；当前不改变冻结实现、不加坐标黑名单或强制路线。

## Cycle 004 — 混合消息解析遗漏

上一轮为实质证据进展：定位虚构水源的传播与4次无效补水。本轮先用5号step2原动作提示做3+3次输入对照，只增加本人状态/上次动作效果。6次都重复在(26,10)补水；candidate已读懂0→0但仍信任队友确认。详见own_state_replay_20261025/REVIEW.zh-CN.md，不把候选当作有效修复。

### 可复现的独立实现bug

TaskRuntimeBridge.dispatch只要发现任一EDGE标签，就只处理EDGE内部消息，直接忽略段外合法的AGENT/GLOBAL消息。实际step0的5号消息含3个错误数字EDGE ID及一个合法组内GLOBAL；旧实现只记录3次抑制，合法广播也丢了。

### 最小修正与测试

先取EDGE内部包，再从原文删除这些完整区段，将剩余文本按原active组处理。避免重复投递，原group.route权限完全不变。不替模型修正错误EDGE ID，也不扩大广播范围。

两个新增测试在旧实现均失败；修复后11项runtime、8项图、1项动作提示测试通过，见cycle_004_{red_test,tests}.log。真实消息离线重放验证：6/7/8各收到1条合法本组GLOBAL，3个错误EDGE仍被抑制。证据cycle_004_recorded_dispatch_replay.json。这是投递机制修复，不证明任务收益或水源幻觉被解决。

### 运行隔离

当前Cycle003两个完整火点实验仍使用原冻结副本，未注入本轮修复、未重启、未改判据。Cycle编号是工作日志索引，并非增加另一种超图架构。下一步等待完整结果，再决定同seed/同预算的解析器修复后实验。

2026-10-25T10:52:30.211506+08:00 核对supervisor PID 4027781存活，当前 second_fire_seed137，最新快照 step 16 before_action。

## Cycle 005 — 原生喷水异常与证据保留

上轮属于实质进展：修复混合消息解析并通过真实消息重放。本轮没有重复启动实验。

### 真实运行新证据

第二火点事件后step19/event1510立即分为water-logistics(1/2)、suppression-main(3/4/5)、suppression-second(6/8)；7号已不在线。step20/event1578又删除5号并调整主火组leader。它证明本seed及时动态调整，与旧seed42延迟不同，但不可据不同seed归因于此前修正。任务仍未结束。相关前缀在cycle_005_event_response.json。

原生Player-0.log出现MapManager.SprayWater的NullReferenceException，不能把此后的全部行为效果归因于agent。已保存原生日志前缀与事件后前缀；它们不是完整终态日志。

### 精确定位

使用Mono.Cecil只读检查实际Assembly-CSharp.dll。MVID=256a5b92-637c-4cf2-991f-167dd098582a与异常栈一致，IL_00f7后是Cell.fire.GetComponent<ParticleSystem>()和Stop()且没有空检查。Cell状态与fire_extinguished计数更新发生在此前。错误可能中断后续喷水处理/水量消耗，不能假装只是可忽略日志。精确IL、hash和源代码差异见cycle_005_actual_binary_il.txt、cycle_005_engine_error_evidence.json、cycle_005_source_guard.diff。

### 最小源码修正与测试

只在WILDFIRE-ORCH的MapManager.SprayWater给可选fire对象和ParticleSystem组件加空检查，不改火势模型、计分、agent动作或组织规则。测试直接提取真实源码渲染区块，用Mono编译，覆盖缺失对象、缺失组件和正常粒子恰好Stop一次：旧源码出现NullReference，修正后通过。另11项runtime测试通过。

同时为未来批次补上每个case结束后复制原生Unity日志的记录功能，防止下一Unity进程覆盖共享Player-0.log；一项实际文件覆盖回归测试通过。共13项本轮相关测试通过。当前已经启动的旧supervisor不自动获得该功能，仍需每次唤醒保留日志前缀，不能声称完整捕获。

### 严格区分源码与实际构建

**未修改运行中的或官方Unity二进制。源码空检查尚未部署到当前实验，不能声称原生异常已经在真实环境修好。** 常用位置未发现Unity Editor入口；下一步需验证独立构建或可逆的隔离managed-artifact修复，保留官方原始hash/MVID，不在共享build上直接打补丁。不能用此源码单测代替真实引擎验证。

2026-10-25T11:00:25.710221+08:00 核对supervisor 4027781存活，最新快照 step 24 before_action。

## Cycle 006 — 实际Unity构建修复验证

上轮属于实质进展：发现实际二进制空引用、完成源码修正并保存原生日志。本轮按实际hash构建隔离托管修复，不等待或声称Unity Editor源码重建成功。

### 独立修复与校验

GuardSprayVisual.cs使用Mono.Cecil只在SprayWater的GetComponent/Stop前增加Unity Object存在检查；输入hash不匹配、输出已有或原地覆盖均拒绝。实际程序集读回验证其他1864个方法体不变，官方原文件hash仍c27099d25f0413594792fe05f4b6c75f6464a8b78a2ca40b2b259f159ec96591。修复文件hash为3cfe67173b32cef32b34d400720b7751c61f8482f669e88efef2034c6ba317fa，MVID另行区分，未覆盖官方DLL。

三个可执行回归测试通过：原fixture确实空引用；修复后缺对象、缺组件、已销毁对象/组件及正常粒子五种路径都保留世界状态和计数更新，正常粒子恰好停止一次；错误hash和原地覆盖被拒绝。结果cycle_006_tests.log，实际artifact校验cycle_006_artifact_verification.txt。

### 无LLM真实引擎回放

两个独立完整构建副本串行回放seed137已记录的前17步动作，模型调用0次。原版出现1次NullReferenceException，修复版0次；两边17个动作后采样状态（含各实体位置/资源与任务计数）全部一致，最终灭火计数均4、火烧树计数均33。这证明该异常路径得到修复，也表明在这一前缀上没有观察到步边界任务指标收益；不能借此把整条任务失败归咎于引擎错误。

它们是从seed新开世界的动作回放，不是检查点恢复、不是两条新的LLM策略实验，不计入策略成功率。详情cycle_006_engine_validation.json及/data1/gzy/crew_engine_visual_guard_20261025/verification.json。诊断进程均已退出，当前长实验继续原路径。

### 后续使用边界

独立guarded_build已准备好；批次启动器新增显式--build选项，并将路径与程序集hash写入plan，防止悄悄替换环境。当前Cycle003未改构建；等其完整结束后再预登记后续版本，注明Python解析修复与环境修复，不把不同构建混称同版本重复。

2026-10-25T11:10:15.614745+08:00 核对长批次supervisor 4027781存活，最新快照 step 62 before_action。已再次保存原生日志前缀。

补充验证：显式--build选择已通过实际临时目录准备测试，确认构建软链、plan路径、程序集hash和所选case一致；日志跨case覆盖保留测试仍通过。Cycle006共3项托管修复测试＋2项批次产物测试通过。

## Cycle 007 — 历史消息缺少时间标签

上轮属于实质进展：完成真实Unity原版/隔离补丁17步回放，确认异常消除但采样状态无变化。本轮确认原长批次supervisor仍存活，没有重跑case。

### 失败输入链

seed137后段只剩2号、水量1，在水源与火点方向反复往返/补水。检查step76实际Choosing Action提示，TASK GROUP上下文把step28/29/30的event1941/1995/1996/2039重新作为recent_messages注入，没有发送步数或图版本。此时这些消息已46–48轮之久，1/3号已损失；其中仍说3号等待4号转水。2号后期推理仍引用3号等待供水，尽管当前组明确只有自己。证据cycle_007_historical_message_evidence.json。此前chat_history清理不会清掉graph.messages缓存，所以旧消息会再次进入提示。

### 最小信息修正

SoftTaskGraph.record_message保留发送step和graph_version；context带当前step/version，并把recent_messages改为message_history。历史内容仍保留，未增加TTL、清除消息、封禁发送者或动作限制，也没有泄露队友额外私有资源。这里修复的是输入时间语义，不宣称已解决模型相信过时消息的问题。

### 测试

新增图回归覆盖旧发送者离线、成员/leader变更后仍保留原始发送时间；runtime回归验证实际提示同时带当前step99和历史step0。旧实现一项KeyError、一项断言失败；修复后9项图＋12项runtime测试通过，见cycle_007_{red_test,tests}.log。当前冻结批次未注入本轮改动，真实效果需后续另行验证。

2026-10-25T11:16:11.700656+08:00 长批次PID 4027781存活；已保存本轮原生日志前缀，继续等待完整终态。

### 2026-10-25T11:23:25.885126+08:00 第一条新完整火点轨迹结束

seed137完整100步、正常退出、机制审计passed，任务失败，损失7人、灭火17、火烧树944，24次图提交仅6次结构变化，多数来自减员。新火点组6/8形成后无喷水；31步起只有2号，55步后无新增灭火。跨组送达0。完整审查seed137_full_review.md。

对全轨迹固定模型输出离线重放新dispatcher，505→509合法投递，恢复4、丢失0、涉及2条输出；这不是新物理轨迹或任务收益证据，见cycle_007_full_dispatch_replay.json。

检查终态时旧supervisor已启动seed256、覆盖共享原生日志，未获取seed137终态完整native log；已有前缀不能证明完整异常总数。已实现的未来capture功能不能追溯补回，必须明确缺失。当前PID 4027781存活，case second_fire_seed256；已保存256当前native前缀，继续不重跑。

## Cycle 008 — 已修复路径的真实集成门禁

上轮为实质进展：完整seed137失败审查、历史时间语义修复及回归测试。本轮先核对主批次PID存活、seed256继续推进，没有重启原case。

按integration_gate_plan_20261025.md预先指定，在独立目录/构建/日志执行seed137两步门禁、超时900秒，无人工起始组或强制分组。它与主长批次隔离，不注入正在运行的源码。

门禁正常结束，16次授权动作均完成、0 held、0拒绝，机制审计和源码完整性通过。实际使用guarded程序集hash3cfe67173b32cef32b34d400720b7751c61f8482f669e88efef2034c6ba317fa；原生日志已复制到case/unity_logs，异常0。

32份实际通信/行动提示上下文都包含当前step/graph_version和message_history；每条历史消息保留发送step/version，且在当前step1确实看到发送step0的历史，而非删除旧消息。验证cycle_008_gate_verification.json，对应完整目录/data1/gzy/crew_dynamic_followup_20261025_integration_gate/verification.json。用量65次API、输入82453/输出9418，约125.6秒。

这不覆盖第二火点事件或任务成功，不计为新的完整策略样本，不承诺修复水源幻觉或提高成功率。没有引入新组织规则；只完成此前修复的组合接入验证。继续等主seed256完整结果再决定下一批，不自动重复本门禁。

## Cycle 009 — 导航误记为idle

上轮属于实质进展：修复路径真实2步集成门禁通过，非新效果结论。本轮先核对主supervisor与Unity存活，seed256继续。没有重复case或添加组织规则。

### 实现问题

原Embodied runner只要command=0就累加cumulative_idle_steps，而command=0也表示正常导航。seed137全轨迹243个零码命令中208个目标为其他格子，35个目标为当前格子；因此旧idle字段不能支持“243次等待”的结论。该变量仅写CSV，不参与动作、组织器输入或成功判据。

### 最小修正与验证

仅把计数条件改成目标等于当前采样格且非乘机的零码命令。计的是原地保持意图，不是墙钟空闲，也不保证物理上绝对不动；导航仍照常执行。旧CSV不覆盖、不回填，后续版本需注明计数语义修正。

测试执行真实runner的计数代码块而不是另写镜像函数：旧代码把导航计为1，新增测试失败；修正后导航、原地保持、乘机、非移动技能4项测试及12项runtime测试通过，见cycle_009_{red_test,tests}.log。对100步原始事件重放同一真实计数块，280动作中243零码=35保持意图+208导航，见cycle_009_metric_replay.json。

### 运行边界

当前Cycle003冻结运行和已通过门禁的动作行为不受本轮工作树改动影响；它是日志修正，没有增加规划调用、状态限制或路径规则。对比历史idle字段必须从事件重新计算，不能直接混用。完整seed256尚未结束，继续等待其终态再启动后续完整版本验证。

## Cycle 010 — 完整seed256失败与空组空转修复

2026-10-25T11:46:42.161252+08:00

主批次已正常结束，supervisor退出；两例100步均失败、审计通过。完整seed256审查见seed256_full_review.md，最终native日志已保存（2次空引用）。发现36–99步全部agent离线却重复64次空组织API/空图提交，输入67057/输出3326。仅修无人时本地退役一次并跳过API，保留原步数/validator、恢复上线后规划，无新增动作限制。11项图＋12项runtime测试通过，修改前3处失败；64步真实快照离线重放0API/1次退役。详见cycle_010_*。

下一批组合修复完整验证已预登记next_full_plan_20261025.md；同两seed100步、显式guarded构建，非因果归因、不覆盖过去失败。

## Cycle 011 — 活动批次接线核查与经核实等待

2026-10-25T11:48:33.209902+08:00

上一轮属实质进展（空组修复、测试、启动预登记完整批次）。本轮为verified wait：实际PID4084244和Unity4084345存活，seed137完成首轮8个动作，最新快照step1。核对冻结清单185份源码hash均一致，guarded程序集SHA与plan一致；实际通信/动作提示已见当前step/graph_version和带发送时间的message_history。证据cycle_011_live_verification.json。

未到18步事件、无终态，不从开头顺利推断任务收益；没有新增组织/动作规则、没有重启或重复门禁。保持同批继续，后续按STATE读取进度。

## Cycle 012 — 跨组通信缺少可发现的目标地址

2026-10-25T11:49:54.160215+08:00

上一轮为verified wait。本轮主supervisor4084244/Unity4084345均存活，最新step3。不重启、不改运行副本。

失败链调查：完整seed137有505条送达、跨组0、17次outside stated groups；实际worker组上下文只有自己的组ID/leader/members，没有其他组目录，但EDGE接口要求目标边ID与协调人。检查560份实际历史提示上下文，目录存在数0。聊天可能偶然告知其他组，故不能断言任何时候完全无其他组信息，也不把跨组0全部归因于此缺口。证据cycle_012_address_evidence.json。

最小修正：context新增group_directory，仅当前组ID、成员、leader；补一句按目录精确寻址。不传位置/资源、不增加路由规则、不自动代发、不要求必须跨组协作。新增测试从真实bridge.prompt解析地址并发给另一组leader，确认实际dispatch送达；重组后目录更新且不保留退役组。旧代码KeyError失败，新13项runtime＋11项图/策略通过。测试证明接口可发现/可路由，不证明模型会使用或任务收益。

改动仅工作树，当前Cycle010冻结完整运行不含目录，后续需另行真实验证，不能把它的结果算为目录改动效果。

## Cycle 013 — 真实模型重放未支持目录单独部署，撤回候选

2026-10-25T11:52:08.220248+08:00

上一轮为实质进展（寻址缺口与候选实现）。核实主supervisor4084244与Unity4084345仍存活，最新step5，未重启。新轨迹step0已有source-edge占位符原样输出造成丢信。选定该实际leader1首个Sending Messages提示，预定固定3对重放，除目录与精确寻址说明外其余保持一致；无Unity执行、无强制跨组。

结果：baseline3/3有合法路由、0/3有非法路由；with_directory1/3合法、2/3均照抄source-edge而被现有路由拒绝。两版本跨组均0。API6次，输入6900/输出1498。全部原始提示/输出/用量在/data1/gzy/crew_group_address_replay_20261025，分析cycle_013_address_replay_review.json。小样本单提示不能估计总体收益，但不支持把候选标为有效行为修复。

将Cycle012目录候选从运行代码撤回，同时撤回仅测试该候选的测试；完整补丁保留cycle_012_deferred_address_directory.patch，可审查但不得自动部署。当前工作树恢复Cycle010运行路径，12项runtime＋11项graph/policy通过。之前Cycle012测试证明的是地址可用而非模型会正确使用，本轮证据明确收窄结论。没有把更多提示规则层叠上去追逐同一个失败样例。下一步优先等待现有完整轨迹的事件与终态。

## Cycle 014 — 等待同一完整运行，不追加规则

2026-10-25T11:53:44.354774+08:00

上一轮属实质进展：固定6次模型重放否定目录单独部署，撤回候选。本轮为verified wait：supervisor4084244和Unity4084345实际存活，最新step7 before_action，在线8。动作、补水前后资源与当前native前缀已保存cycle_014_live_observation.json及native_prefix_cycle010_seed137_latest.log；本时点native异常0。仍未到第二火点事件，不从早期存活/补水得出修复有效或任务成功结论。未改代码、未重复测试或门禁、未重启。下轮继续同批的事件响应与终态审查。

## Cycle 015 — 观察补水后的执行，保持冻结运行

2026-10-25T11:56:28.469117+08:00

上一轮为verified wait。本轮开始及两次60秒观察后均实际确认supervisor4084244与Unity4084345存活，最新step9 before_action。1–4号曾实际补满，后续正向火点移动；5/6/8号曾空箱靠近火区，7号自行前往水源，需继续检查是否实际喷水与避免损失。行动码计数{"0": 67, "4": 5}，现有native异常0。完整本轮证据cycle_015_live_observation.json。

没有新实现缺陷证据，不把组织建议中的补给角色直接改成动作禁令，也不重复单提示候选调参。原批次继续，尚未完成事件响应与终态验证。

## 用户要求本例跑完后停止

2026-10-25T11:59:53.968624+08:00

仅完成正在运行的second_fire_seed137；取消排队seed256与后续实验。旧supervisor没有运行时停止队列接口，故只SIGSTOP supervisor PID4084244，子runner和Unity不受影响；终态后由本会话保留日志与完成审计汇总，再结束队列进程。不得把supervisor的T状态误判为任务挂死/重启。

## 用户要求停止：当前任务完成与最终归档

2026-10-25T12:27:26.367217+08:00

当前seed137完整100步，正常退出、审计及源码完整性通过，任务失败。263授权动作/0held，16图提交/9结构变化；第50步after_action全员离线，随后0组织API、51步只退役一次。原生Cell.UpdateCell另有1次空引用，未继续修改。保留完整native日志与behavior文件；队列supervisor已结束，取消seed256，核实相关PID均不存在。最终总结STOP_SUMMARY_20261025.md与核查final_current_run_verification.json已保存。遵用户要求暂停长期目标，不再启动后续实验。

## 2026-10-26 用户新授权单次救援完整验证

2026-10-26T16:33:47.834865+08:00

已在启动前说明选择当前主实现而非旧探针冻结版本；两者是同架构。当前无已证实事件后改组并完成整体任务的合格样本。单例Rescue_Civilians_Surprise seed42预算60，原9步事件。发现动态平民目标计分遗漏，仅隔离副本修正；26项测试通过，未修改共享实现。详细SINGLE_RESCUE_VALIDATION_20261026.md；运行目录/data1/gzy/crew_dynamic_success_validation_20261026_rescue42。长期目标仍暂停，不扩展自动队列。

## 2026-10-27 单次救援运行结束核查

2026-10-27T11:54:49.871576+08:00

60步完整结束，正常退出、审计通过、源码一致。目标9步后从10正确增为15，最终送达14/15，发现15，5人均在线，300授权/0held。12图提交但成员/leader/active始终不变，结构变化0；10步起只更新组内目标/成员建议，跨组0。原生MapManager.FixedUpdate有6216次除零异常，影响尚未隔离，不能归因全部模型失败。不满足新目标+结构调整+任务完成。保存validation_review.json和VALIDATION_REVIEW.md；不自动重跑，长期目标仍暂停。


## 2026-10-27：授权的引擎/接口/事实接线修复

已在独立快照 `/data1/gzy/crew_interface_repairs_20261027/workspace` 完成，未覆盖共享核心代码。修复零周期取模异常、统一 HT 通信说明与真实地址、补投递反馈和已有状态/目标/预算输入。建组、路由权限、动作检查及重规划逻辑 AST 不变。36 项测试通过；救援 12 步同动作回放异常 1412→0 且状态完全相同；火场 17 步无异常，3 步仅探索计数差 1；真实 API 定向跨组寻址成功；2 步 Unity+DeepSeek 联调审计及源码检查通过、10 动作全下发、0 原生异常。联调自发跨组仍为 0，不宣称任务收益。详见 [修复报告](/data1/gzy/crew_interface_repairs_20261027/REPAIR_REPORT.md)。正式 ORCH 对照和长期批次未启动。


## 2026-10-27：按用户要求恢复原始提示

官方 GitHub 固定版本与论文核对后，共享消防员补水说明及独立副本新增物理/感知/通信提示、额外 HT 输入已撤回，保留原 HT 接口。Embodied 上游原文即“移动几步”；ORCH 高层移动选项会持续执行，不等于一帧瞬移。36 项针对性检查通过；引擎补丁与投递日志保留，没有新模型调用或 Unity 性能运行。上轮真实联调仅对应撤回前提示。当前记录：[提示恢复与补丁影响报告](/data1/gzy/crew_interface_repairs_20261027/PROMPT_RESTORE_REPORT.md)。


## 2026-10-27：启动有限的运行时结构对照

用户询问能否开始基本同环境配置的超图实验；已启动原版 Rescue_Civilians_Surprise / seed42 的自主与固定组织各 60 步一对，独立快照 `/data1/gzy/crew_runtime_structure_pair_20261027`，supervisor PID1798664。共用构建/模型/恢复提示，固定臂重放自主臂首次自然建组，保留初始开销差异；无事件提前、人工分组或新机制。完整规格见该目录 PROTOCOL.md。与官方历史轨迹作参考，不当作官方 ORCH 方法重跑。有限批次，原长期循环未恢复。


## 2026-10-27：完整动态／固定组织对照完成并汇报

两臂各60步，seed42原版新增平民；动态11/15、固定13/15，均发现15人、全员存活、0引擎异常。动态3次非减员结构变化，固定0次；跨组成功投递两臂均0。动态3号step15独立成组后未收到任何其他agent成功投递消息，动态最后14步送达无增量；两臂末端均有载人未交付。初始可观测状态/拓扑一致、代码/构建相同、审计/冻结通过；step1后状态分叉，一对轨迹不支持普遍因果或官方ORCH优劣结论。完整结果 [RESULTS.md](/data1/gzy/crew_runtime_structure_pair_20261027/RESULTS.md)。有限批次结束，无后续运行。


## 2026-10-28：完成旧完整超图归档清理

用户授权后，将旧TaskHypergraph/LLMTaskPolicy及专用测试/控制回放移至research/legacy_full_task_graph；当前审计仅加载SoftTaskGraph，旧审计显式独立；冻结脚本解除旧测试依赖。当前74项、归档36项测试通过；动态/固定两条完整轨迹与旧完整图一条轨迹的前后审计完全一致。算法包只移出旧2模块，其余运行源码哈希未变，抽查15份历史关键产物未变。更新入口文档及过期运行状态；没有调用模型或启动Unity，原长期实验仍暂停。报告：[CLEANUP_REPORT.md](../legacy_full_task_graph/CLEANUP_REPORT.md)。
