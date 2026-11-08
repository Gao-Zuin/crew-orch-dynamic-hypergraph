# 实现与门禁记录

## 2026-10-29

- HT-R2继续使用原SoftTaskGraph，不引入另一套图。接入五种通信意图、成员先/leader后通信、leader报告触发中心、本轮组织后更新任务建议。
- 中心组织输入只含初始任务、能力/在线名单、当前图及leader报告；审计保留完整世界快照。在线名单仍来自运行时，不称作下层主动报告。
- active语义保留；上下文列出所有成员关系，增加TASK_OVERLAP_ACTION记录该agent收到的消息与动作。
- 新增逐API provider用量ledger，并显式关闭deepseek-flash思考模式。模型列表实查只有flash/v4-pro，旧deepseek-chat不再列出。价格快照与估计范围方法保存在实验目录。
- 原87项离线测试全部通过（原80项随协议更新，加6项报告链/信息边界测试和1项真实聊天API测试）。日志：第一次实验目录tests_after_real_gate_fix.log。
- 首次真实门禁在第0步因Agent.add_message不接受新EDGE频道而中断；测试替身自动建频道掩盖了这一差异。已修为setdefault，新增实际Agent方法测试；保留失败快照和轨迹，不覆盖。
- 首次目录 `/data1/gzy/crew_bottom_up_20261029/`；修复后冻结目录 `/data1/gzy/crew_bottom_up_20261029_r2/`。后者为当前运行依据。r2仅表示门禁重试快照，算法/通信代号仍HT-R2。
- 当前监督进程3113595、单运行监督进程3113596（必须实时验证PID，不能将本记录当作存活证明）。14:57左右的小型运输已执行3步、21个动作边界、49条成员消息、6次leader分析、3个重叠成员动作记录；原生日志0异常。4条worker误用leader专属标签被记录并忽略，需在门禁结束时分析。
- 门禁尚未结束，尚未启动5个大任务。中型新增平民窗口将使用原第9步事件。后续须审阅真实证据再写gate_review.json放行大任务，不应仅凭单元测试放行。
- 大任务计划：Transport_Helicopter_Down(12agent/35步)、Cut_Trees_Sparse_large(10/50)、Second_Fire(8/100)、Rapid_Growth(7/100)、Rescue_Civilians_Search_Rescue_Transport(14/60)。保留失败，记录任务判定、事件、结构变化、真实消息、重叠成员、tokens/cache/cost范围及原生异常。

待完成：两个门禁的全程检查及必要提示修正；运行5个较大任务；逐轨迹分析leader是否分析处理而非机械转发、是否触发结构变化，以及重叠成员来自两边的消息如何影响行动；整理完整报告后做目标完成审计。

## 小型门禁结束后的核对

- 6步完整门禁healthy=true，5/6送达；42动作，25次hold全部aboard，0原生异常。99成员消息（GROUP82/LEADER11/REPORT6）、12次leader分析，0中心上报（局部运输没有证明必须重组）。
- 119次API、184207/19518输入/输出token，缓存46080/138127命中/未命中，ledger完全对齐；费用估计USD0.03257–0.06514。
- 重叠agent2的6步动作均记录两边消息，active未改变。leader在step3用自身观测纠正了他人集合点误报；step5仍有乘员名单错误，不能将“进行了分析”当作分析正确。
- 细节与事件号：当前实验GATE_SMALL_ANALYSIS.md。中型门禁继续。大型救援在开跑前选定原14人3角色Search_Rescue_Transport；原选择保留plan_before_large_case_refinement.json。

## 中型门禁的事件输入失败与最小修正

- 原14步中型门禁基础设施healthy，但终局3/15，0中心上报。所有五份实际step10请求包含t9公告。event529 agent2看到了70,70，但认为组外且非leader，因而没有报告；其他leader也未将新目标落实为工作。准确说是没有实际消息传递新地点，并非所有推理都没注意到。
- 拒绝放行大任务，r2/gate_review.json明确false。只增加“近期公开通知置于请求前部”的条件分支，并澄清worker REPORT不等于中心升级；不改变路由/active、不自动转发、不强制重组。
- 一次LLM诊断重放已能生成REPORT并保留当前运送，但没有Unity状态变化，不能替代真实门禁。88项离线测试通过。
- 新冻结工作区及真实中型门禁：`/data1/gzy/crew_bottom_up_20261029_notice_focus/`，当前STATE指向此处。小型门禁保留：无公告时42个原请求的prompt行为一致，其他运行方法未改，见small_gate_compatibility.json。算法代号仍HT-R2，不是另一套超图。
- 下一步等待新中型门禁的t9原事件，核查REPORT→leader分析→自主局部处理/LEADER/ORGANIZER。只有证据通过后再启动原5个较大任务；仍未完成长期目标。

## 中型完整链路通过与动作格式接线修复

- 新中型14步healthy=true，70动作/0hold，0原生异常，4/15送达。事件523/529成员REPORT→531/536 leader分析→534/538 leader协商→539中心上报→540报告输入→542新增组，真实走通。
- 641再次报告资源不足后，700把独立核查组改派给3号；708实际向70,70移动，位置16,41→22,44，尚未到达。记录详见notice_focus/GATE_MEDIUM_ANALYSIS.md。
- 新增独立记录核对tools/inspect_run.py，核对每次重叠动作、active及实际入站消息流；小型6步/旧中型14步均收过两个不同leader消息，新中型16次重叠动作的两个edge同leader，不能混称。该工具仅离线审计，不加在线回执状态。
- 又查出prompt()将通信输出指令带入动作请求；旧r2中型agent3 step9真实返回GROUP而没有action。已将通信格式仅留在communication_prompt，89测试通过。70份已保存中型通信请求逐一比较字节一致，其余运行方法未改。
- 新冻结当前目录为 `/data1/gzy/crew_bottom_up_20261029_action_format/`，引擎改为私有字节相同副本，避免其他会话改写共享build。当前短3步物理动作回归已开跑；该项健康且独立审计通过后，沿用已验证小/中型通信路径放行原5大任务。仍是HT-R2同一实现的缺陷修正，不是新图架构。

## 较大任务批次已启动（15:34 +08:00）

- 3步动作格式回归healthy，21个真实动作请求均无通信输出格式，21响应均含action；21授权/0hold、0原生异常，源码/引擎与token/cache账本对齐。
- 当前实验gate_review.json的11项检查均通过，已启动5个原生较大任务顺序批次。实际监督PID3148125/首案例监督3148130已验证存活；第一次核对large_transport_down已1步12动作，0原生异常。后续必须重新验证PID。
- 当前唯一活动运行目录：`/data1/gzy/crew_bottom_up_20261029_action_format/`。其progress.json为批次状态；source_sha256.json/frozen_sources.tar.gz为源码依据；引擎为私有同SHA副本。STATE.json指向这里。
- 已完成代码接入和小/中型功能验证；5条较大完整运行、成本/重叠成员分析及最终逐项完成审计仍待完成，目标继续active。

## 大任务减员兜底缺陷与修复

- 首次large_transport_down在原t4损失leader11后，748模型方案被拒，749动态兜底将两个存活组整体替换为mission。之后旧组名消息失效；最终已记录79次无效消息，10个返回步。此条已主动中断保留，不能算完整运行。记录见action_format/INTERRUPTED_LARGE_REVIEW.json。
- 最小修复：原固定组织已有的减员清理逻辑也用于动态纯减员兜底；只移除离线成员，保持存活组名与执行归属，不增加通信规则或回执。90项测试通过，并用真实748事件前状态及被拒模型方案重放验证，两组保留、11移除、失去leader的组由已有幸存成员接替。
- 原小/中型无agent减员，未走该分支；通信和动作接口未变。当前冻结目录改为 `/data1/gzy/crew_bottom_up_20261029_attrition_fix/`，同HT-R2缺陷修复。引擎哈希不变。全部5个大任务重新按原时域运行，首个完整运输任务同时作为真实减员回归；不是缩短任务替代。
- 新监督PID3163777/3163780真实存活；其manifest模型标签现与实际flash一致。当前完成仍0/5，目标active。前序所有账本（含中断的大任务）会计入成本汇总。

## 减员后重跑观测

- 当前大任务已到step6，原t4直升机损失已发生。当前无效消息0，原生异常0，进程3163777/3163780已重新验证真实存活。
- 本次模型在损失后给出有效方案，尚未触发修复过的兜底分支；不能把此次运行与旧失败轨迹的差异全归于修复。initial observed state相同，但首步动作后已分叉，证据transport_prefix_comparison.json；精确的兜底修复证据仍是attrition_replay.json和回归测试。
- 等待原35步完整运行，不缩短/重启来制造特定分支。5个较大任务仍在批次中，尚无已完成案例。

## 第二火点原生异常检查与继续批次

- 前两条large任务正常结束。第二火点跑完100步、机制/用量审计通过，但Cell.UpdateCell发生一次NullReferenceException，健康检查按预案停批。原完整轨迹保留，不计入干净结果。
- 异常位于SetState(fully_extenguished)后访问可选fire粒子对象/component。采用与既有SprayWater相同的空值保护；补丁只改Cell.UpdateCell，1864个其他标准化方法体不变。旧DLL不覆盖。新SHA bad8db753eede1aaf061090a35dd1164c320941850fef05e6f87ff34939591b1，工具/源码/验证位于 `/data1/gzy/crew_cell_visual_guard_20261029/`。
- 无LLM动作回放100步：旧build复现1次异常（回放第69步）；新build0异常。回放不是状态恢复，探索计数有差异，不当作策略效果对照；因此原异常案例仍单独保留并安排干净重跑。
- 当前续跑目录 `/data1/gzy/crew_bottom_up_20261029_cell_guard/`。actor Python源码与上一冻结目录逐文件一致，90项已通过测试不重复运行。保留原两条健康运行（原引擎SHA），剩余三条用新私有build；每条的引擎差异公开记录。先运行Rapid_Growth和14人Search_Rescue_Transport，最后重跑Second_Fire；5个任务范围不变。
- 新监督3318478已验证真实存活，当前Rapid_Growth。按用户要求恢复低频等待，基本结束后统一分析LLM判断、消息转述、共享与对齐过程。

## 批次结束与统一语义审计（2026-10-30）

- 5条较大原生任务全部结束：运输17步原成功早停；Sparse50、Rapid100、Rescue60、SecondFire100均完整预算失败。5条独立记录审计通过。
- Rescue的193次Nakama异常经源码和实际动作/消息边界核对，均为目录状态RPC刷新token错误；独立审阅接受用于策略分析，保留原healthy=false及原始错误，不将其称为零异常。随后SecondFire健康完成100步、0原生异常。
- 统一审计重点见PROCESS_AUDIT.md：局部观测纠错；转述遗漏与证据循环；组外路由选错；补水尝试被声称为成功；新火点已上报leader却共同判定组外、不向中心提出；双leader消息真正送达但围绕不存在的消防员交水动作形成错误共识。没有因此追加策略规则。
- 更正多leader统计：按不同sender去重；前4条正式任务均未记录收到两个不同当前leader的重叠动作，不能把同leader的两条edge算两位leader。最后SecondFire有19次真正双leader入站动作，原请求/输出已单独抽取保存。
- 主5条API估计USD3.71–7.42；含全部已记录失败准备/诊断USD4.65–9.30。模型flash，不能与旧chat或未重跑的ORCH作因果性能比较。
- 主工作树180个wildfire_alg文件与冻结清单一致。逐项completion_audit.json完成，本轮实现和5任务验证结束；STATE清理过时PID/案例，唯一产物入口为cell_guard目录。

## Pro单任务对照已启动（2026-10-30 15:50 +08:00）

用户提出flash换pro重跑，选择刚详细审计的Sparse原50步、10agent、seed42。冻结目录`/data1/gzy/crew_ht_r2_pro_sparse_20261030/`，基线为attrition_fix/runs/large_sparse_clearance。使用基线原引擎SHA，不能混用后来CellGuard引擎。无提示、规则或结构策略修复；仅将显式关闭thinking的条件扩展到pro（2个API调用位置，diff保存）。逐manifest比较除这两处外全部相同。官方models接口确认deepseek-v4-pro可用；38token的JSON探针通过，独立provider_probe.json记账。

监督PID3916408，实际RUN_STARTED已确认deepseek-v4-pro，10agent加入。只此1条，不自动重试。结束后脚本核对原生异常、源码、usage/cache及重叠记录，保存comparison.json/RESULTS.md和对应实际LLM请求样例。语义审计仍需在运行结束后进行；不把机械审计等同于策略更好。按用户偏好不逐步轮询。

## Pro扩展到全部5任务（2026-10-30）

按用户要求，将原Flash5任务全部换Pro重跑。唯一批次目录`/data1/gzy/crew_ht_r2_pro_campaign_20261030/`；原Sparse在`crew_ht_r2_pro_sparse_20261030`继续，本批等待其终局独立审计通过后保留，再顺序执行运输、Rapid、Rescue、SecondFire四条，不重复Sparse、不自动重试。batch监督PID3923737已验证存活。

五条分别匹配各自Flash基线引擎：运输/Sparse用旧SHA，其他三条用CellGuard SHA。逐manifest比较所有规则/提示/actor源文件一致，仅保留两处Pro关闭thinking的API兼容差异。all_baseline_equivalence.json保存逐条证据。原seed和35/50/100/60/100步、角色预设不变；不重放Flash初始图，初始组织与动作可因模型变化而自然分叉。

tools/run_batch.py只做外部顺序调度，结束后核对每条记录、统计和费用，并抽取实际LLM请求样例；语义分析仍标pending，不能把自动核对写成已完成策略审计。原Flash报告不覆盖；STATE现指Pro主批次，完成后统一审计。

## Pro批次检查、Sparse审计与续跑（2026-10-31）

实际只完成Sparse50步，71/75失败，其他4条因888次Nakama目录RPC错误未启动；不是全部5条已完成。全部888堆栈逐条核对为Refresh token invalid/expired→ReportMatchStateInNakama。500动作/通信、50步、独立记录和用量对齐，另存native_exception_review.json接受策略分析，原healthy=false保留。

续跑只调整外部监督，接受精确已知目录RPC错误的完整独立审阅；其余错误仍停下。没有重跑Sparse、没有改actor/提示/引擎。batch监督PID344840已验证存活，progress当前pro_transport_down，剩余4条顺序执行。

详细结论见PRO_SPARSE_AUDIT.md：Pro无找水支线、零无效路由但也零跨leader/中心上报；初始5组把全部25目标各指派两次。第31步达71后停滞。最后4棵对应(14,42)1、(13,49)2、(49,50)1。两点为只砍一次就宣称清空；(13,49)更涉及实现问题：step12提议Cut被360秒过期guard替换为hold，但action_round已提前将Cut写进past_actions，step13及45据此误以为完成。10次过期hold加1次no-action。该问题已定位，未在正在运行的模型对照中改变规则。

## Pro五任务统一审计与HT-R3完成（2026-11-01）

Pro5条均完成，正式1/5成功；Rapid第5步以后无火却因原burned>0条件仍失败，不与Flash火失控等同。完整分析PRO_CAMPAIGN_AUDIT.md。四条目录RPC异常均有逐条review，原记录保留。

主实现仍同一SoftTaskGraph/SoftTaskPolicy/Embodied，改用profile reports_v3区分新提示及记录行为。共用静态能力事实与少边混合组倾向；当前成员/edge例子覆盖旧角色；本地非法地址反馈，不增加投递生命周期；返回后才记实际动作；移除HT墙钟过期hold。无边数硬上限、无强制合并、无新动作门控。完整改动及反例REVISION_20261101.md。

94测试通过；旧v2完整轨迹仍可重放。6步Flash/6步Pro真实Unity各18动作0hold0拒绝0异常，余树继续Cut各3次；最终源3步Flash9动作检查同样健康，184源码hash与当前主工作树一致。原始replay正例与反例全部保留：初始Sparse倾向1–2边，但旧Rapid3边不可靠合并，Flash重复指派等仍可能出现，未称策略已可靠。验证summary和逐项完成要求位于crew_ht_r3_validation_20261101。未再开5条完整任务。

旧原始结果、提示、引擎、正式计分不改；新代码已接入原HT入口。STATE不再保留旧运行PID或错误地显示Pro运输仍运行。


## 2026-11-02：ORCH知识接入与Flash五任务批次

用户授权补齐缺失输入并用Flash运行。实现共享general/任务知识、四职业实际单步菜单和局部目标坐标辅助；没有引入manager/option/阶段机制。96测试通过；真实3步9动作接线健康，逐worker和中心请求核实知识送达。冻结实验 /data1/gzy/crew_ht_r3_orch_knowledge_flash_20261102，20:42启动五任务完整批次，原seed/上限/事件与每任务引擎hash保留。详细见ORCH_KNOWLEDGE_INTEGRATION_20261102.md；尚无本次完整任务结论。


## 2026-11-03：充值后获授权重跑中断项

仅从头重跑第二火点（flash、seed137、原100步上限），前四项不重跑；原HTTP402中断轨迹保留。使用原冻结工作目录，逐文件源码hash及Unity assembly hash核对一致。新结果 /data1/gzy/crew_ht_r3_orch_knowledge_flash_second_fire_retry_20261103；单次有限执行，结束自动做产物审计，不自动再次重试。


## 2026-11-03：前四任务语义审计完成

报告FLASH_KNOWLEDGE_FOUR_TASK_AUDIT_20261103.md。运输真实两批交付、Sparse三次跨边分区确认、Rapid存在有用火线核对但无依据平民支线；救援识别无火原始观测→虚假火情报告→中心清障/找水边链，以及8号乘机未下机却声称交付、14号重复接人并错地点卸客。保存实际请求样例与资源转换证据；没有改策略/追加运行，第二火点重跑独立继续。


## 2026-11-03：第二火点重跑完整结束

10:52–12:11，100/100步任务失败，fire_active=true、烧树796、实际砍树97、灭火计数3、人员损失4；0原生异常/hold/非法消息，2次方案拒绝；机制/独立产物/用量对账通过。第74步出现东南火线临时边，75步合并，不能未经语义核实当成第二火点责任交接。补齐后五任务完整结果3成功/2失败，见重跑目录FIVE_TASK_OUTCOME_WITH_RETRY.json；原402中断轨迹不计入完整任务结果。第二火点详细语义审计待做。


## 2026-11-03：第二火点完整重跑语义审计

保存SECOND_FIRE_RETRY_AUDIT_20261103.md与实验目录过程/真实请求证据。第19步报告已抵达中心，明确选择暂不派人；全程在线位置最大x54，距新点火最近切比雪夫16。74步短暂SE边并非确认的70,70责任。通过只读IL核对实际DLL，喷水radius3/angle60，5格安全建议被模型当硬约束；50–74步无喷水、烧树301→663。早期危险直线移动和减员另有请求样例。本次只分析，未改运行策略或追加实验。


## 2026-11-04：环境事件直达中心

用户明确要求预设新火点等由环境通知中心再下发。新增实际提交事件通知入口与即时组织触发，下一步中心先决策，运行时将官方通知和任务建议下发；保留现场REPORT/ORGANIZER。仅actual submitted事件，无未来schedule或完整世界快照。profile v5，99离线测试通过，旧v4第二火点审计重放通过。真实3步诊断接线目录/data1/gzy/crew_central_event_validation_20261104，时程不作为任务效果数据。

真实短接线已结束：3步15动作健康；中心收到事件时没有leader上报，先组织后向五名成员转发，实际请求核实。validation_summary.json保存顺序与来源证据。没有启动正式五任务重跑。
