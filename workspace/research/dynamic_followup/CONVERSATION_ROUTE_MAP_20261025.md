# 跨对话实验路线核对（2026-10-25）

这是已存在文件/冻结源码的身份核对，不修改实现，不恢复暂停实验。文件不记录聊天会话ID，故第二条路线的对话归属是候选判断。

## 本对话已确认

标签dynamic_followup，代码SoftTaskGraph/SoftTaskPolicy/TaskRuntimeBridge/Embodied，arm HT，profile task_hypergraph_soft_v1。
开发源码/data/gzy/selfevolve/CREW/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/coordination/。
进度与分析/data/gzy/selfevolve/CREW/research/dynamic_followup/。
冻结完整批次/data1/gzy/crew_dynamic_followup_20261025_cycle003/（137/256各100步）、/data1/gzy/crew_dynamic_followup_20261025_cycle010/（137完整100步，排队256取消）；另cycle001运输。当前已暂停。

## 最可能对应另一对话的路线

标签fixed_group_stall / soft_stage_probe，同样SoftTaskGraph/SoftTaskPolicy/Embodied，非原完整TaskHypergraph。
规格与结果/data/gzy/selfevolve/CREW/research/fixed_group_stall/PROBE_2026_10_24.md和RESULTS_2026_10_24.md。
分析工具/data/gzy/selfevolve/CREW/scripts/summarize_soft_stage_run.py，脚本及RESULTS最近修改时间2026-10-25 23:15，并有对应analysis文件更新。修改时间只是活动线索，不独立证明聊天会话归属。
结果根目录/data/gzy/selfevolve/CREW/benchmark_runs/：
- soft_stage_probe_fire_fixed_seed42_v1：第二火点seed42，固定组12步，事件提前到4步。
- soft_stage_probe_fire_dynamic_seed42_v1：同seed/12步/事件4步，重放第一条起始组，允许自主改组。
- soft_stage_probe_rescue_dynamic_seed42_v1：惊喜救援seed42，动态14步，原9步事件。
各目录有manifest.json、status.json、frozen_sources.tar.gz、run/events.jsonl、analysis/。冻结task_runtime.py均实际实例化SoftTaskGraph。

## 共享与干扰证据

两路线开发代码位于同一个ORCH main工作树，不是分开的工作树；实验目录分开不等于源码分开。旧原完整task_hypergraph.py/task_policy.py也在同一个coordination目录，HT名称不唯一标识历史架构。
救援探针status明确frozen_sources_unchanged=false，修改项soft_task_graph.py和tests/test_soft_task_graph.py；RESULTS说明运行中补reward_schema。本对话Cycle001记录同项修改。对救援冻结图与本对话cycle001首次冻结图做差分，恰好多一行reward_schema传递。因此已经有工作目录层面的干扰，不只是理论风险。
救援事件里的组织器请求仍不含reward_schema，与启动时导入旧模块一致；不能推断已被动态换成新运行逻辑。但这条运行不能算源码完整性通过。
目前工作树对本对话cycle010冻结清单覆盖的185份文件全一致，未发现近期核心代码继续偏离。另一路近期新增的是分析脚本/结果，不在该旧清单范围；不能由185份一致推断整个文件系统无新增。

## 分清历史与当前

research/task_hypergraph/README.md和benchmark_runs/task_hypergraph_second_fire_early_v5等属于历史完整任务图；不能直接认作另一对话当前路线。
/data1/gzy/ORCH是官方数据下载目录，不是实现工作区。
CREW/WILDFIRE-ORCH主要为Unity源码，不能仅凭另一个仓库名认定对话隔离。

确认另一聊天归属还需它提供自己的输出目录或上述运行名称；运行配置、实际代码路线、共享关系与完整性问题则已有直接文件证据。
