# 给新对话：本地轻量超图与官方ORCH轨迹对比分析交接

## 任务与范围

请基于现有轨迹，分析组织、信息、通信与实际执行的差异，尤其是重复报告、事实矛盾、虚假完成、等待许可、补水/运输/救援交接、事件后责任分配。先追踪具体失败链和可验证的有效协作，不预设ORCH最优，也不把失败直接归咎于超图结构。当前本地实验按用户要求暂停；此交接授权轨迹分析，不自动修改共享实现、重启Unity或调用模型。

本对话标签dynamic_followup，运行arm=HT、profile=task_hypergraph_soft_v1，实现SoftTaskGraph+SoftTaskPolicy+TaskRuntimeBridge+Embodied。Cycle编号是日志轮次，不是新架构。

## 一、本对话实际运行目录（主分析样本）

### transport_schema_only

- case目录：`/data1/gzy/crew_dynamic_followup_20261024_cycle001/runs/transport_seed2461`
- 实际worker对话/指标目录：`/data1/gzy/crew_dynamic_followup_20261024_cycle001/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-chat/Transport_Firefighters_small/2461/2026-10-25-10-25-16`
- 冻结源码副本：`/data1/gzy/crew_dynamic_followup_20261024_cycle001/workspace`

### fire_original_137

- case目录：`/data1/gzy/crew_dynamic_followup_20261025_cycle003/runs/second_fire_seed137`
- 实际worker对话/指标目录：`/data1/gzy/crew_dynamic_followup_20261025_cycle003/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-chat/Suppress_Fire_Extinguish_Second_Fire/137/2026-10-25-10-34-58`
- 冻结源码副本：`/data1/gzy/crew_dynamic_followup_20261025_cycle003/workspace`

### fire_original_256

- case目录：`/data1/gzy/crew_dynamic_followup_20261025_cycle003/runs/second_fire_seed256`
- 实际worker对话/指标目录：`/data1/gzy/crew_dynamic_followup_20261025_cycle003/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-chat/Suppress_Fire_Extinguish_Second_Fire/256/2026-10-25-11-16-34`
- 冻结源码副本：`/data1/gzy/crew_dynamic_followup_20261025_cycle003/workspace`

### fire_repaired_137

- case目录：`/data1/gzy/crew_dynamic_followup_20261025_cycle010/runs/second_fire_seed137`
- 实际worker对话/指标目录：`/data1/gzy/crew_dynamic_followup_20261025_cycle010/workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/results/logs/Embodied/deepseek-chat/Suppress_Fire_Extinguish_Second_Fire/137/2026-10-25-11-46-45`
- 冻结源码副本：`/data1/gzy/crew_dynamic_followup_20261025_cycle010/workspace`

三条灭火运行都为Suppress_Fire_Extinguish_Second_Fire，deepseek-chat、temperature0，8名消防员、允许动态图自主改组；各预算100步，使用原第18步第二火点事件，无人工起始图/换人。不是seed42短探针的物理续跑，不存在100步固定分组对照。

|样本|物理运行结果|审计/完整性|图提交/初始化后结构变化|灭火计数|实际节点损失|
|---|---|---|---|---|---|
|cycle001运输2461|预算15步，完成10个动作步，第10步动作前确认送达6/6|源码一致；原机制审计仅因用量漏记失败|3/0|不适用|0|
|cycle003火137|100步，任务失败，fire_active=true|通过/一致|24/6|17|7|
|cycle003火256|100步，任务失败，fire_active=true|通过/一致|76/8|22|8|
|cycle010火137|100步，任务失败，fire_active=true|通过/一致|16/9|8|8|

运输中18次held均为乘机原因，不能叫组织阻塞。三条灭火运行held均0。cycle010动作263次：238次零码导航/保持、8次补水、17次喷水；590次接收者级送达，跨组0，12次路由拒绝。cycle003火137送达505、跨组0；火256送达813、跨组0。

### 目录文件怎么读

每个case含manifest.json（配置/源码及构建hash）、frozen_sources.tar.gz、status.json、audit.json、behavior_summary.json、behavior_detail.json、run/events.jsonl、run/Embodied.log、supervisor.log。原始模型提示和回答在上述worker目录Agent_*/chats.txt，指标在data.csv；RUN_STARTED.payload.result_path是权威定位入口，勿只在case下找chats。

日志section包括Summarizing Observations、Sending Messages、Choosing Action、Executing Actions。并非所有场景第N段都对应第N步：乘机、离线等会跳过推理。结合事件步号/位置/行动关联，必要时从冻结源码恢复未记录的system模板。

关键事件：TASK_WORLD_SNAPSHOT（step、phase、节点/水量/地图缓存/奖励/事件公告）、TASK_ORGANIZER_REQUEST/RESPONSE、TASK_GRAPH_COMMITTED、COMMUNICATION_GENERATED、TASK_MESSAGE_DELIVERED/SUPPRESSED、ACTION_STARTED/COMPLETED、TASK_VALIDATED、NODE_OFFLINE、LLM_USAGE、RUN_FINISHED。区分before_action与after_action，步号0起始；低层0是导航/原地保持，3是喷水，4是补水，不能按上层翻译器枚举直接解释低层码。

TASK_MESSAGE_DELIVERED按接收者计数，一条广播发3人记3次。LLM_USAGE是结算事件，不等于该步发生一次API调用。图提交不等于成员变化，重命名/减员/退役不等于任务收益。节点地图为共享累积缓存，缺少逐格新鲜度，不能冒充直接可见的实时真值；死亡后缓存位置也不是精确死亡点。

## 二、各版本差异：比较前必须明确

- cycle001：reward_schema补传，仍有提前成功结束漏记最后组织器用量的问题；旧status/audit没有改写。派生重放补记后通过，不等于原始审计通过。
- cycle003：reward_schema、真实补水条件说明、用量finish修复；原始Unity构建。
- cycle010：再加入混合消息解析修复、历史消息step/图版本、导航/保持计数修正、全员离线后跳过组织器；显式guarded Unity构建。仅修MapManager.SprayWater视觉对象空引用，不是改火灾规则。
- cycle010构建：/data1/gzy/crew_engine_visual_guard_20261025/runtime_check/guarded_build；程序集SHA256以batch/plan.json为准（3cfe67173b32cef32b34d400720b7751c61f8482f669e88efef2034c6ba317fa）。
- group_directory候选已撤回，从未进入cycle010运行；不能假设worker知道其他组精确ID/leader。补worker_abilities、本人状态/上次结果的候选小样本重放也未作为有效修复部署。
- cycle003火137完整末尾native日志被后续case覆盖，只有前缀，不能给全程异常总数；火256和cycle010有unity_logs/。cycle010有另一处Cell.UpdateCell空引用1次，未修复，原因贡献未知。

## 三、最新cycle010火137的典型表现（最优先核对）

### A. 没做补水，却报告成功，触发错误交接

6号36/37步朝(8,24)移动；38步仅到(36,48)、水1、无Refill，却发事件2336：已补水，FULL(3 water)，允许5号离岗。实际动作事件2340却转回(44,58)。5号38步据此开始自己的补水行程（动作2338）。两人的交接依据不成立。

5号38–43步连续去水源；44步在(14,30)、水1，通信事件2453仍说去水源、距补满6–8步，行动2457却以“已经满箱”为由转回(46,60)。45步事件2472报告FULL且已从水源返回，实际(21,37)、水1；46步事件2495同句说tank1(full)。这一轮没有抵达水源、没有Refill、水量没增。应检查同一轮通信与行动不一致、计划/过程/完成混淆、报告压过真实状态。

### B. 建议被当许可，满箱反复等待

1号4步补满，12–18步无喷水，17/18步水5且原地保持；推理明确等containment-prep授权。程序不要求这类组织许可，advisory也说不限制安全行动。不能把所有赶路/等待均算浪费，但额外许可依赖确实导致等待。19步4号否认平民后1号才喷；20步动作后全局灭火计数到8，之后直到全灭前没再增长。

### C. 请求另一组，却只发送给本组

26步5号生成事件1844，GLOBAL内容请求water-logistics确认补水；实际1847/1848只送到6/8号，目标组没收到。基本提示称global channel，HT追加说明才说裸GLOBAL只到当前组；worker上下文只有自己组，无其他组目录。还存在source-edge占位符照抄（初始1号事件32），所以零跨组不能解释为零需求或模型不愿协作。

实际格式有两层：<GLOBAL>或<AGENT_n>默认当前活动组；跨组需<EDGE id="真实源组" target="真实目标组"><AGENT_n>内容</AGENT_n></EDGE>，并满足共同成员或leader到leader路由。抽象示例不是可直接用的地址。程序反馈outside stated groups，不能自动补上正确地址。单人组GLOBAL排除发送者后可无收件人，既无送达也无拒绝（另对话救援样例），所以要同时检查生成、投递和实际收件人。

### D. 重复局部汇报和移动，没有完成真实轮换

6号39–46步重复“缺口守住、水1、火没过y58、你FULL后通知”；41–44动作是(46,60)→(46,62)→(46,60)→(46,58)→(46,60)。5号则反复承诺补满返回但未完成。不是所有重复都无用，关键看资源、责任交接和任务计数是否推进。32–36步仍有真实喷水，不能说后期完全不行动。

### E. 重组reason与edges/tasks不一致

19步图事件1426、22步1619的reason均说新增第二火点响应/侦察组；实际仍两组、成员任务围绕原火点，没有第二火点执行者。32步事件2119承认第二火点未安排人。17步事件1293把7号转入补水组是一次真实在线成员转移；其余多为减员、回退、重命名及退役。不要把16次提交或9次结构变化称为16/9次有效优化。

### F. 虚构救援被纠正后又重新出现

3号10/11步原始图无C，任务平民配置为0，但摘要生成火边平民，11步为救援朝(44,61)走。19步4号事件1436否认平民，触发一次有效纠错；22/23步7号又报告其他坐标的平民，25步出现(34,53)，7号据此中断补水去救援。检查“生成错误→队友传播→分配任务→纠正→重新生成”的链。

### G. 死亡机制和50步边界

不是50步统一断线：NODE_OFFLINE均DESTROYED。死亡after_action步：3号11，1号21，2号26，4号32，7号34，8号35，6号46，5号50。8人最后动作都是移动，且仍有水。7/8个最后目标在原始输入缓存标危险，其中6个e、1个f；精确途中死亡格未逐帧记录。

部署DLL与源码均证实i/f/e（Extinguishing）会触发消防员死亡，x（Fully Extinguished）安全。提示只写状态名，没有清楚说明e致死。5号50步原始图53个e、无i/f，摘要称已处理；其移动目标(42,62)是e，随后死亡。不能把“无明火”当通行安全。

50步动作后全员离线；51步本地只退役一次，后续0组织API，环境继续到99步。这是真实验证的空组空转修复，不是后50步agent仍在尝试。旧256从36步起无人却还有64次空组织调用，不能算有效重组。

## 四、较早两条火场轨迹提供的补充证据

cycle003火137：19步真拆为补水、原火点、新火点三组；新火点6/8号此后无喷水。8号19–23步还在原区域，24步才向新区域推进，27步缓存位置(66,69)，28步损失。31步起只剩2号，69个动作中57导航、9喷水、3补水；55步后灭火数不再增加。4次在虚构水源(26,10)空箱补水无增水；旧信息反复作为recent_messages注入。68/78步水1补水无效。

cycle003火256：19步建立重叠的第二火点边，23步退役；36步起无人，后续64次空组织器API。8个节点离线但reward agents_destroyed停在7。

## 五、比较与统计的陷阱

- 全员离线后原生奖励可能冻结；最新末尾烧树366不能直接说优于旧137的944。使用节点online判断人员状态，并保留原reward，不改写。
- 旧idle把所有低层0导航都计入。旧137的243个零码中208导航、35原地保持意图。不能把idle列直接当等待时长。
- 审计通过不等于任务成功。口头自报FULL/任务完成不是资源/环境真值，原始地图也有缓存新鲜度限制。
- 本地3条完整灭火轨迹都失败，不能估计可靠成功率、证明动态超边必要或固定组足够。不同seed、修复组合、构建、采样会分叉。
- “智能参考计划”是待验证假设，REFERENCE_ORGANIZATION_PLAN.md没有实际成功运行。只替换组织器与同时接管感知/行动是不同基线；给参考策略额外物理知识应双方同步或明确标作信息改进。

## 六、不要混入另一对话的3条短探针

身份soft_stage_probe / fixed_group_stall，同样轻量SoftTaskGraph，不是另一套完整架构。
结果根/data/gzy/selfevolve/CREW/benchmark_runs/：soft_stage_probe_fire_fixed_seed42_v1（固定12步）、soft_stage_probe_fire_dynamic_seed42_v1（动态12步、起始组重放）、soft_stage_probe_rescue_dynamic_seed42_v1（动态14步）。火场第二火点提前到4步，不是原18步。
规格/结果/data/gzy/selfevolve/CREW/research/fixed_group_stall/PROBE_2026_10_24.md与RESULTS_2026_10_24.md。救援运行期间共享工作区修改reward_schema，其完整性false；实际请求仍用启动旧版本。结果目录分开不等于开发代码隔离。

## 七、官方ORCH数据与推荐对照

完整解压目录/data1/gzy/ORCH/result/。全量核对路径/普通文件大小及gzip流通过（1192032文件，缺失0、大小差0），非逐文件内容hash。8875份data.csv、109513份chats、3823份master_log*.json、1064172张PNG。官方数据是ORCH论文实验集合，WILDFIRE仅其中一种方法，不等于本地SoftTaskGraph。

入口/data1/gzy/ORCH/inspection_20261026/REPORT.zh-CN.md；机器索引runs_index.csv/json；14条文本候选recommended_runs.json；3条GPT图像参考visual_reference_runs.json。

优先选择同模型家族deepseek、同任务/seed，仍需核对真实模型版本、环境/事件/人数与判断条件：
1. Transport_Helicopter_Down/42：WILDFIRE终态运送10，default6，no_critic0。追查设备损失后的交接闭环与任务分配。
2. Rescue_Civilians_Surprise/42：WILDFIRE/Embodied/default终态送达11/8/13，均60行。追查旧乘客责任和新增目标切换。
3. Suppress_Fire_Extinguish_Second_Fire/42：WILDFIRE灭火16/损失计数4，Embodied11/1，default6/7，均100行；看第二火点、补水和安全/效率权衡。
4. Scout_Fire_Drone_Lost/42：Embodied12行、default13行最终同时见火2；WILDFIRE35行最终0。核对失联后的组织恢复和结束原因，不凭行数判成功。
5. Transport_Firefighters_small/2461：WILDFIRE和Embodied均15行、运送计数5；对照本地6/6，但先核对环境任务是否真的相同。

官方CSV没有显式成功字段。Agent_*含管理者，不当作物理人数；master日志有STATUS_PHASE/ACTION_PHASE/FINAL_ACTION，也有主观进度，需与最终动作和CSV对照。模型生成了消息不证明收到，应在收件人的后续上下文核对。PNG不是所有轨迹都有：抽查DeepSeek候选无图，GPT/WILDFIRE对应轨迹有图；不得把GPT画面当DeepSeek状态，capture号也不默认是决策步。

_old与重复timestamp分开；纯横向/纵向变体先核对team_structure_id_tables/invalid_horizontal_vertical_manager_configs.csv，部分配置标签与实际拓扑不符。结构ID是分类标签，不是分数。

## 八、已有分析入口

全部在/data/gzy/selfevolve/CREW/research/dynamic_followup/：
- STATE.json、JOURNAL.md、STOP_SUMMARY_20261025.md：状态、历史修改、暂停总结。
- POSTSTOP_EXECUTION_STALL_AUDIT.md/.json：执行卡点，含精选事件/真实资源/动作/模型原文。
- POSTSTOP_DEATH_PROMPT_AUDIT.md/.json：死亡机制与实际提示，部署DLL已核对。
- seed137_full_review.md、seed256_full_review.md：cycle003完整审查。
- REFERENCE_ORGANIZATION_PLAN.md：未运行的强参考组织方案。
- CONVERSATION_ROUTE_MAP_20261025.md：两对话/共享源码与短探针边界。
- handoff_runs.json：四条本对话运行的准确目录、worker日志路径和原status。

实现工作区/data/gzy/selfevolve/CREW/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/coordination/；但分析实际运行应先读各批workspace或frozen_sources.tar.gz，不以当前共享工作区代替历史代码。旧完整TaskHypergraph/task_policy.py也在此，HT入口名本身不能标识历史版本。

## 建议输出

先从最新本地137的“虚假补水交接”及官方Helicopter_Down/Surprise中真实交接入手，再比较火场。每个案例输出：当时输入→计划/消息→实际收件者→动作→环境结果→后续是否纠正。分别标注模型事实错误、协议/提示缺口、环境限制、组织决策问题、无法确认。给出有效协作的正例与失败反例，避免只挑支持预设结论的样本；不把相关性或语言解释当因果证明。
