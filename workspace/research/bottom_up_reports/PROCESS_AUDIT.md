# HT-R2：逐级汇报实验与信息协作过程审计

2026-10-30。实现仍是 SoftTaskGraph + SoftTaskPolicy + Embodied，代号 HT-R2，profile `task_hypergraph_reports_v2`。本轮完成实现、小/中型功能门禁和5条较大原生任务；不再继续开跑。主产物目录：`/data1/gzy/crew_bottom_up_20261029_cell_guard/`。

## 1. 结论及证据边界

逐级通信和报告驱动组织调整已经真实走通，但消息送达、leader给出分析、多人达成一致、实际完成任务是四个不同层次。当前最突出的失败并非统一表现为“没有通信”：有的更新选错路由而未传到；有的已被充分讨论，却因错误的职责判断或环境能力假设形成错误共识；还有转述把计划、尝试、他人建议变成了“已经确认”。超图增加联系不能自行修正这些判断。

这里的“思考”专指日志中的可见 justification，结合实际请求重建其依据；不声称读取模型内部思维。机器核查覆盖全部5条的图、重叠动作、实际消息、中心输入边界及用量一致性；语义分析重点核对下列代表链路，不声称逐字人工审阅全部对话。所有事件号均局限于对应轨迹。

## 2. 实现范围与验证

- GROUP广播/点对点、REPORT给本边leader、LEADER给另一边leader、ORGANIZER给中心，四种标签表达五种用途。旧GLOBAL不再被默默当组内广播。没有回执、重试、等待回复或已解决状态机。
- worker先通信、leader后通信。leader利用原通信调用分析，并选择本地处理、组内安排、leader协商或中心上报；worker报告不自动进入中心。新leader报告可在本轮物理动作前触发中心检查。
- 中心实际请求只包含初始任务、能力/在线名单、图和leader报告，没有实时位置、水量、奖励、火点/事件快照。在线名单仍由运行时提供。公开事件通知进入agent历史，中心不直接收到；完整世界快照另存用于离线审计。
- 保留唯一active边；全部成员关系可见，各边消息可接收，动作仍为原Embodied逐步决策。active没有成为禁止做其他边工作的硬约束。
- 本轮最终90项测试通过；真实3步回归的21份动作请求/回复格式正确。小型6步运输验证重叠消息；中型14步原新增平民窗口验证完整报告链。
- 中型链路：REPORT E523/529 → leader分析 E531/536 → LEADER E534/538 → ORGANIZER E539 → 中心请求 E540 → 新边 E542。首次组织仍复用忙碌成员；leader E641指出缺人，中心 E700改派独立成员3，动作 E708确实向(70,70)移动。它证明信息能转成责任调整和行动，不能算新目标已经完成。
- 修复过typed消息历史初始化、公告显著性/REPORT含义、动作请求混入通信输出格式，以及减员后的兜底误折叠分组。没有追加复杂协作机制。历史缺陷、失败门禁和费用全部保留。

## 3. 完整任务与成本

| 原生任务 | agent数 | 返回步数/原时域 | 原任务判定 | 最终主要状态 |
|---|---:|---:|---|---|
| Transport_Helicopter_Down |12|17/35|成功早停|送达10人；11人在线|
| Cut_Trees_Sparse_large |10|50/50|失败|正确砍树68/75；10人在线|
| Suppress_Fire_Extinguish_Rapid_Growth |7|100/100|失败|火仍活跃；4人在线|
| Rescue_Civilians_Search_Rescue_Transport |14|60/60|失败|发现10、送达9/10；14人在线|
| Suppress_Fire_Extinguish_Second_Fire |8|100/100|失败|火仍活跃；1人在线|

所有预设事件均已提交，没有提前注入第二火点或缩短正式窗口。模型实际为deepseek-flash，temperature=0、非思考模式；以逐请求ledger为准。

5条主轨迹共9067次API调用，输入20,537,605、输出1,816,798 token，按保存费率估算USD3.71–7.42。包括失败门禁、中断运行和诊断调用的全部记录：11705次调用，输入25,438,293、输出2,324,391 token，估算USD4.65–9.30。区间为已保存的离峰/高峰价格边界，不是账单；最初9-token连通性探针未计入。详细缓存命中和每条费用见主目录RESULTS.json，不能使用旧CSV的固定GPT费用列。

## 4. 正向样例：观测纠正旧说法，局部协商即可

运输轨迹step16，leader1 E2021结合自己的着陆区观测及4/5号反馈，判断先前“火势密集”的报告与现场不符，请直升机12核查。12号 E2029/2030明确纠正：先前说的密集区其实是三棵树一格的高燃料密度，不是已确认的活跃火焰；其实际感知请求/输出支持这次区分。

12号通过LEADER给另一组leader、GROUP给本组，修正跨组认识；不需要中心重组。任务step17成功。但不能据此说所有成员同一时刻都看到了12号原话：实际收件人仅另一leader和本组，其他成员可能依据自己的leader与现场信息行动。正向结论限于火/燃料类别得到纠正，不扩展为所有乘员名单和状态都已一致。

证据：`semantic_request_samples.json`运输12号step16；对应轨迹的leader_choices.json、communication_timeline.jsonl和原始events.jsonl。

## 5. 失败样例：转述丢失资源数值，再循环成“多方证实”

Sparse任务的世界快照中所有成员水量始终为0。源码Firefighter.CutTree没有水量前提，砍树不需要水。

1. 3号step19 E1873的通信分析知道自己“补水后仍0水”，但GROUP E1874–76缩成“已补水，正在出发”，遗漏0；动作解释又称“水已加满”。同轮4号也声称加满，实际仍0。真实通信和动作请求存在新增消息，因此不能将一切措辞变化归为无输入变化的自相矛盾；关键是环境没有补水成功证据。
2. leader1 step35 E3455把这些话解释为“水源对3号有效、对1/2/4失效”，向中心报告疑似按agent发生的补水故障；中心 E3466把找水写入组目标。
3. leader9 step38 E3769引用组目录中的“NW成员受阻”及自身0水，称团队缺水；中心 E3772把两位leader报告视作相互确认，新增water-scout边，成员1/4/5/9。
4. leader1 E3873要求4号水满前停砍。4号step40 E3997在active仍为NW时转去找水，实际动作目标(10,42)。其输入包含NW和water-scout两边消息，但两边leader都是1号。

核心是证据回流：原报告→中心组目标→另一leader引用目标→中心当成新的确认。多人重复同一来源不等于独立验证。也出现把不需水的砍树工作与补水绑定的优先级漂移。最终68/75，但没有配对对照，不能量化因绕路少砍了多少，或推断动态结构一定更差。

证据：`semantic_request_samples.json`中3号step19、4号step40；Sparse的report_to_plan_evidence.json和原始事件。

## 6. 失败样例：协商意图合理，但最新坐标选错通信范围

Rapid_Growth step20，2号是contain-se-cluster-flank的leader，希望直升机7到新的(26,42)支援，却使用本边GROUP to=7。7号不在这条边，E1220判无效；实际该步没有2→7直接送达。

7号同期的可见判断仍围绕旧请求(26,46)，并认为已带5水在该点待命。这里不能只用“双方都发消息了”判断已对齐：意图、收件人、最新坐标均需对照实际接收输入。全轨迹212条此类组外定向GROUP，221条无效消息。已有LEADER接口能表达需求，模型仍选错范围。

该例不证明双方从未通过旧消息或其他人接触信息。另核查2号两次真正Refill动作，均在合法水源附近，0→5；不能凭“接收补给”等语言就捏造消防员实际尝试从直升机水滴补水。

同一轨迹也有正确保留不确定性的中心判断：直升机7 E1503报告未核实平民，中心 E1506仍安排核查后再承诺救援，不能说所有上报都丢失不确定性。

证据：`rapid_route_mismatch_sample.json`及Rapid轨迹refill_action_evidence.json、report_to_plan_evidence.json。

## 7. 失败样例：“做过补水动作”被认定为“水源已验证”

Rescue的直升机13号step59 E8417/8418：实际感知为位于(49,100)建筑格、0水、未见水源，却把多次执行Refill称为已验证的有效水源，建议14号转来。

其实际输入包括14号自己的0水和询问、11号的水源推荐、leader1关于“是否仍已验证”的问题；输出却归纳为“11/14都确认成功”。自己的动作解释继续选择Refill。尝试、推荐、问题被升级为成功事实，重复并未形成独立确认；全程两架直升机水量最大值均0。

但9/10救援完成不能被忽略。最后7号仍载1名平民，按正确方向从(39,77)向安全点(30,77)移动，返回(33,77)尚未卸载，预算结束。因此最后一人未送达不能单凭水源讨论就断言全部由旁支任务造成。

证据：`semantic_request_samples.json`中13号及7号step59、Rescue原始events.jsonl。E1301→1304、E3520→3523记录水源担忧如何进入侦察目标；这并不自动证明救援实际因缺水受阻。

## 8. 最后第二火点轨迹：信息传到了，却共同决定不处理

原事件step18出现(70,70)新火点，公开通知E1474。step19，4号E1483 REPORT明确把新地点交给leader1；6/8号也向leader5报告。不是通知没有进入LLM，也不是没有向上层leader发消息。

leader1 E1495判断“本边之外、没有本地观测，不分散资源”，通过LEADER告诉5号；leader5 E1499综合成员与另一leader的同一意见，赞同两边都不处理，建议“除非中心重派”。全轨迹ORGANIZER报告为0；中心只收到旧初始任务、图和人员变化，无法从未发出的报告得知新火点。周期检查因此继续维护旧两组。

信息路径为：通知→成员报告→leader综合→跨leader相互认同→无人向中心提出覆盖问题。它暴露“维持本组目标”与“全队新目标需要有人接手”的判断断点；没有请求中心支援不能解释为中心收报后拒绝。也不能用这条轨迹证明每个新事件都必须强制上报或重组。

证据：`second_fire_notice_alignment_samples.json`保存4/1/5号step19和1/5号step20的实际感知、通信、动作请求及回复。

## 9. 重叠成员：接收两位leader确实发生，但对齐在不可执行计划上

第二火点step24–42，7号同时属于灭火与供水两边，active为供水。独立核查19个动作均实际收到两个不同leader的近期消息：先为1/5号，5离线后为1/8号。此前Sparse和Rescue虽有多边消息，但不能称为收到两个不同leader，那里常是同一个leader负责两边。

7号理解两边要求为“到前线交水→回水源→再送水”。step24 E1786通信还说准备送，动作解释已说送完而向水源移动；step25 E1839发现自己仍5水，改向交接点。step28 E1991承认没有交接证据，却把输入中清楚的5水弱化成“水量不确定”，继续执行leader的返程计划。step35 E2278再次载满向前线走；step42 E2564则回应灭火leader的火沿核查要求。

这不是接收不到第二条边，也不是active阻止它响应灭火组。真正问题是双方共同依赖不存在的消防员交水操作：实际完整动作菜单只有移动、砍树、拾/放平民、喷水、补水、待机，没有把水交给另一消防员。7号19步动作全为移动，返回状态水量一直5，没有交水效果。中心图本身也写入“hand off”，错误前提来自组织计划并被leader/worker共同延续。

由此能证明信息接收和跨边响应存在，不能证明有效物资接力；口头形成一致甚至会稳定错误流程。当前证据尚不足以量化双leader造成的认知负担，或证明attention/density机制必要。本轮没有为此加入新规则。

证据：`second_fire_overlap_request_samples.json`，对应轨迹water_handoff_evidence.json、overlap_summary.csv和原始chats。

## 10. 可靠性、范围与后续可检验问题

5条均通过独立记录审计，逐请求用量/cache对齐，冻结源码未变；主工作树180个wildfire_alg源码文件与最终冻结清单一致，见final_main_source_comparison.json。

前两条保留较早健康引擎SHA，后三条使用Cell.UpdateCell粒子空值保护后的私有build；不能宣称5条完全相同引擎。该补丁只改可选粒子对象访问，1864个其他方法体不变；旧/新各100步无LLM回放分别1/0异常，但回放不是保存状态恢复，不用来论证策略效果。原异常SecondFire完整轨迹单独保留，不混入主结果。

Rescue原review仍healthy=false：193次Nakama刷新token异常，全部在ReportMatchStateInNakama的目录状态RPC。其840动作/通信边界、ML-Agents观测及Python本地消息完整，已单独native_exception_review.json接受用于策略分析；不声称Nakama目录更新正常，也不把所有主运行描述为零异常。其余4条主轨迹无原生异常。

已有aboard与任务新鲜度hold单独记录，不把所有停滞归于通信。总体任务仅1/5成功；不同任务各一次，flash与旧chat不同，无同设置ORCH重跑、无动态/固定配对对照，不能推出优于ORCH或动态超边有必要。

若继续研究，优先检验“依据是否保留、是否独立确认、提出的动作是否存在、组外问题是否有人承担”这几条可证伪假设。当前完成的是实现验证和失败机制定位；没有把这些观察变成强制上报、自动路由或复杂状态机。

## 产物入口

- 主目录RESULTS.json/md：全部5条、用量、费用与审阅例外。
- 每条runs/<case>/run/events.jsonl、run/results/Agent_*/chats.txt：原事件及实际LLM输入输出（保留路径/软链接）。
- 每条manifest.json、frozen_sources.tar.gz、status.json、review.json、api_usage.jsonl：配置、源码、引擎身份、状态和逐请求账本。
- 每条independent_artifact_audit.json、leader_choices.json、overlap_summary.csv、communication_timeline.jsonl：记录一致性和消息/动作索引。
- 主目录semantic_request_samples.json、rapid_route_mismatch_sample.json、second_fire_notice_alignment_samples.json、second_fire_overlap_request_samples.json：本文重点样例实际输入/输出，非仅摘句。
- 小中型门禁：`/data1/gzy/crew_bottom_up_20261029_r2/runs/gate_small_transport`及`/data1/gzy/crew_bottom_up_20261029_notice_focus/runs/gate_medium_surprise`。目录身份和历史修正见IMPLEMENTATION_LOG.md，STATE.json是本轮单一入口。


补充：全部16个edge ID的职责、leader接替和跨边交接逐任务核查见[超边职责与交接审计](EDGE_HANDOFF_AUDIT.md)。

Rapid补充逐步语义核查见[Rapid详细审计](RAPID_DEEP_AUDIT.md)：包含新边形成、成员范围变化、路由纠正、投水/交水混淆及墙钟guard干预。
