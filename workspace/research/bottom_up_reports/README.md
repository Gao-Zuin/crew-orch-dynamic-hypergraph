2026-11-08完成[15条完整主线消息链审计](MESSAGE_CHAIN_AUDIT_15_RUNS_20261108.md)：不是案例抽样。1165个REPORT中894送达、15无效、256个由当前leader发给自己并被旧运行时静默吞掉；坐标事实跨跳保留和33次结构变化来源已统一统计。根据全量证据，当前运行时已对leader自REPORT返回本地纠错，不自动升级或重发；加入后续空间负对照测试后共133项项目环境测试通过。协议因果校准另见 `../structure_calibration/PROTOCOL_CAUSALITY_AUDIT_20261108.md`，当前候选机制从“必然少一拍”修正为“预先共享可减少连续LLM交接次数”。

同日完成[跨组消息—动作空间负对照](MESSAGE_ACTION_ALIGNMENT_AUDIT_20261108.md)：覆盖659条带坐标LEADER送达，动作只归因给直接收件leader及有精确坐标转发证据的成员。半径5的真实首次对齐17.3%、同轨迹置换15.2%，总体差距很小；半径2/3存在更清楚的精确坐标复制信号，但集中在Pro救援等少数轨迹。114次首次对齐中106次真实靠近，5步内只有13次目标附近非移动操作、6次资源变化。第二火点存在很晚且短暂的转向，说明“动作响应”仍不等于持续责任或任务效果。

进一步完成[顺序任务可行性审计](SEQUENTIAL_COMMITMENT_AUDIT_20261108.md)：严格筛出15条“点名个人、补水后、去明确坐标”的已送达消息。规则复核发现消防员仅在水量为0时才能补到5；旧Pro第二火点的11条指令均要求水量1—4的成员先“补满”，前置条件本身不可执行。6条随后带可用余水出发，不再误判为成员违约；5条窗口内未解决冲突。其余4条为已满或从0真实补水后的有效顺序。该结果把候选机制从“强制维持承诺”修正为“先验证能力与状态转移可行性，再记录承诺”。

同日完成[砍树错误前置条件审计](CUT_TREE_FALSE_PREREQUISITE_AUDIT_20261108.md)：同seed三条完整稀疏砍树轨迹中，旧Flash执行68次无效补水并产生98条“补水→砍树”通信，最终还新增找水桥接组；同一轨迹38次零水砍树真实生效，直接证明该依赖错误。冻结prompt A/B中正确动作规则消除12/12水相关选择，但仅追加责任合同仍不能可靠避开他人目标，说明下一层需要结构化、版本化的目标责任索引，而不是更多自然语言警告。

随后完成[目标责任影子索引](TARGET_RESPONSIBILITY_SHADOW_AUDIT_20261108.md)：覆盖三条砍树轨迹全部26次图提交及980个精确指向任务坐标的动作。Pro R2的25个目标在10次提交中始终全部双主责；R2 Flash图内无碰撞但实际改派大量留在聊天层；R3无双主责、采用条件备用。初步近邻检查发现6个图外完成都有leader消息，后续[版本化责任事件账本](RESPONSIBILITY_EVENT_LEDGER_AUDIT_20261108.md)进一步修正为5个当前有效/暂定接管、1个被新图覆盖后的陈旧执行。结论是图只应提供关系和初始责任，执行真相需合并图版本、结构化改派和环境完成证据。

对应的[冻结提示A/B](RESPONSIBILITY_LEDGER_PROMPT_AB_20261108.md)使用两个冲突负例和一个合法跨组接管正例，各重放3次。账本把R2无授权冲突从3/3继续砍变为3/3离开，同时保留合法接管3/3继续砍；R3陈旧消息的Pro baseline本身已3/3避开，所以不能把该案例归因于账本。总计baseline 6/9、账本9/9，仅说明值得进入短Unity shadow实验，不是任务级因果证明。

2026-11-04已按用户指令接入[环境事件直达中心再下发](CENTRAL_ENVIRONMENT_EVENTS_20261104.md)，输入profile为task_hypergraph_reports_v5，同一超图实现。worker现场发现的上报保留；旧五任务仍是v4。99项离线测试及旧轨迹审计通过，真实短接线状态见STATE.json。

重叠成员的非active边leader反应已核实，见[人力可用性审计](OVERLAP_AVAILABILITY_AUDIT_20261104.md)：Rapid有实际释放协商但未到岗，救援全组能力不足上报，第二火点原边仍获回应。

五任务的初始超边、重组与实际协作作用，见[统一评价](FIVE_TASK_HYPEREDGE_ASSESSMENT_20261103.md)。区分图提交、成员/leader变化、增撤边与组内任务协商，不把动态次数视作效果。

第二火点完整重跑已审计，见[过程分析](SECOND_FIRE_RETRY_AUDIT_20261103.md)：公告和上报送达，但未分配验证职责；5格安全建议与冻结引擎3格喷水射程不匹配，长期转为局部隔离带作业。本轮五任务完整结果3成功/2失败，无新实验启动。

前四任务已完成过程审计，见[知识补充后四任务审计](FLASH_KNOWLEDGE_FOUR_TASK_AUDIT_20261103.md)。三成功、一失败；救援的虚假火情传播和乘客交接失配有原始请求证据。第二火点充值后单独重跑，状态以STATE.json对应目录为准。

# 当前输入修订：HT-R3 + ORCH知识（2026-11-02）

同一实现路径，profile `task_hypergraph_reports_v4`。补齐共享环境知识、所有职业单步动作说明及局部坐标辅助；96项离线测试和3步真实接线通过。已启动原五任务各一条完整Flash运行，结果尚未完成。见[接入说明](ORCH_KNOWLEDGE_INTEGRATION_20261102.md)，进度以STATE.json及实验目录progress.json为准。

# 当前实现 HT-R3（2026-11-01）

仍是 SoftTaskGraph + SoftTaskPolicy + Embodied 的同一路径，当前profile为 `task_hypergraph_reports_v3`，不是恢复旧完整图或并行新架构。Flash/Pro五任务均已完成，详见[统一审计](PRO_CAMPAIGN_AUDIT.md)；共性实现调整及验证见[本次修订](REVISION_20261101.md)。新增静态能力说明、少量混合组倾向、具体通信例子及本地格式反馈；动作历史记录真实返回命令，HT不再因API墙钟耗时hold。无边数上限、强制拆组或回执状态机。以下保留HT-R2历史接入说明，旧冻结轨迹仍是v2。

## 历史HT-R2接入说明（2026-10-29）

本轮继续使用 SoftTaskGraph + SoftTaskPolicy + Embodied，没有恢复旧完整图。代号 HT-R2 表示通信和中心信息来源的修订；运行 profile 为 task_hypergraph_reports_v2。当前入口仍是 scripts/run_task_hypergraph.sh。

五种用途由四种标签表达：GROUP(edge)组内广播、GROUP(edge,to)组内点对点、REPORT(edge)给该边leader、LEADER(edge,to-edge)给另一leader、ORGANIZER(edge)由leader向中心报告。GLOBAL/AGENT_n/旧EDGE不再作为HT通信格式。非HT的原Embodied提示不变。

worker先通信、leader后通信，使leader通常能在同一轮看到成员报告。leader用原有通信LLM调用的justification分析，并自主选择本地行动、组内协调、leader咨询或中心上报；没有强制升级或自动把worker报告转发给中心。已经发言的leader若随后收到另一个leader的信息，可在动作决策或下一轮处理。没有回执、重试、待回复/已解决状态机。

中心的输入是初始任务、能力/在线名单、现有图与最近leader报告；不再传入位置、资源、奖励、fire_active、事件快照。在线名单仍是运行时可用性元数据，由运行时提供，避免给已离线agent分配任务；不将其声称为下层主动汇报。完整world快照仍保存在日志用于独立审计。原每5步组织检查保留，新leader报告也能触发本轮动作前的组织检查。

预设事件执行返回后，其公开announcement进入agent消息历史；中心不直接接收announcement。公告标为公共通知，不充当局部观测或事件物理效果确认。

保留每个agent唯一active边，但多重成员能按显式edge收发各边消息；上下文列出全部成员关系，记录TASK_OVERLAP_ACTION，包括active、各边leader、动作和最近收到的消息。没有新增退出超边/冲突仲裁状态机。

当前目录以 [STATE.json](STATE.json) 为准，活动批次路径只在该文件维护。历史门禁目录只保存缺陷和修复证据，不是并行的图实现。先离线测试，再小型运输和中型新增平民窗口，审核后进入5个较大正式任务。小型运输用明确标注的手工起始重叠图，验证多重成员通信；其余让LLM自然组织。正式大任务使用原始时域和事件时间，不修改游戏参数。任务失败保留；基础设施/源码变化/原生异常需要先审阅，不自动重跑。

本轮API模型列表仅提供deepseek-flash和deepseek-v4-pro，使用flash非思考模式temperature0。逐请求usage ledger保存model、response_id、provider缓存命中/未命中token，不保存key。cost按官方费率给出离峰/高峰估计区间，并保存原始用量；CSV原有固定GPT费率列不作为DeepSeek成本。https://api-docs.deepseek.com/quick_start/pricing/ （2026-10-29核对）

原始判定边界沿用task_verdict_audit/REPORT_20261029.md，尤其事件前早停、烧树前提、fire_active刷新滞后；不得把机制审计通过等同于任务成功。

通信输出格式仅由communication_prompt()注入；物理动作prompt()只附带建议上下文，保留原action格式。代码、门禁与后续运行的详细修正顺序见[IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md)，完成要求见[COMPLETION_REQUIREMENTS.md](COMPLETION_REQUIREMENTS.md)。

本轮已于2026-10-30完成：5条较大任务全部结束并统一审计，原任务成功1/5。完整说明见[信息协作过程审计](PROCESS_AUDIT.md)，含真实输入、leader判断、转述、跨组对齐和实际动作的证据；主产物RESULTS.json及completion_audit.json通过STATE.json定位。没有继续追加运行。
