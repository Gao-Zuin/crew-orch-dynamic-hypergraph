# 2026-10-28 项目结构与冗余审计

范围：当前主工作区 `/data/gzy/selfevolve/CREW`、最近完整实验冻结副本 `/data1/gzy/crew_runtime_structure_pair_20261027/workspace`、默认与已验证 Unity 构建、运行/审计工具与文档。只读审计及CPU合成探针，没有修改生产代码、提示、权限或环境；没有模型调用、Unity运行或GPU计算任务。

结论：旧完整图移出主实现解决了一层混淆。现在更重要的是主开发入口、已验证修复、部署构建和实验记录缺乏统一事实来源；其次才是历史模式耦合和文件整理。不能依据文件名直接继续删除共享模块或上游参考仓库。

## P0：主工作区不是最近验证配置

### 1. 动态救援目标修复仍只存在独立快照

主工作区与最近冻结副本的算法包比对，除已按要求归档的旧2模块外，差异仅在3处：

- `algorithms/Embodied/__main__.py`
- `coordination/task_runtime.py`
- `coordination/soft_task_graph.py`

主循环没有 `_record_spawned_civilian_target` 或 `civilian_target` 更新。原始check_game_done允许外部传入更新目标，但默认仍取初始 `5*2=10`。当前主TaskRuntimeBridge的validator_data同样没有新增目标。

执行实际check_game_done函数的CPU探针：救出10人、未传动态目标时success=True；显式目标15时False。冻结副本包含事件提交后的目标增量修复。这说明若直接从主入口启动新增平民任务，可能在10人时按旧目标结束，而最近完整实验是按15人判定。

这次审计没有回填修复，也没有把历史实验改成主工作区版本。上一轮清理保证的是清理前后主代码行为不变，不代表主代码已与最近验证副本汇合。

主分支也没有独立副本中的TASK_MESSAGE_DISPATCHED、空广播回执及最近动作结果日志接线。因此“已经实现/验证”需要绑定工作区，不能只给功能名。

### 2. 主入口默认构建未包含已验证补丁

| 构建 | Assembly-CSharp.dll SHA256 |
|---|---|
| 主入口 `ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server` | c27099d25f0413594792fe05f4b6c75f6464a8b78a2ca40b2b259f159ec96591 |
| 最近独立验证 `crew_interface_repairs_20261027/engine_build` | 0fd6faf54fbac94d481a71b56cc6f02527883ff7dca8816ec5fa8d45ef635196 |

主入口指向原始构建；后者包含喷水视觉对象保护和零周期保护。默认batch允许显式选build，但省略后又回到原构建。测试还会读取WILDFIRE-ORCH仓库中的C#源代码/补丁fixture，不能因此证明默认部署DLL包含同样修复。

建议：先明确唯一开发基线，按差异逐项汇合已验证且未撤回的修复、测试与构建选择；恢复提示的用户要求继续保持。实验快照作为历史证据保留，不能把它们悄悄改成新主分支。

## P1：语义与职责存在结构性耦合

### 3. HT继承了含历史空间模式的RuntimeBridge

RuntimeBridge同时承担事件状态、观测、旧SpatialPolicy分组、提示、路由、协议压力检查和动作/用量生命周期。HT覆盖了observe/prompt/dispatch/guard等方法，又借用父类的初始化、before_step、action_started、after_step、finish。父类初始化创建SpatialPolicy，随即被HT覆盖；名义空间边、恢复反馈等历史字段仍存在。

因此runtime.py、hypergraph.py、crew_adapter.py目前不能直接归档。适合先提取真正共享的观测/事件/动作记录基础，再把旧空间模式放到单独适配器；不需要重写当前组织算法。

### 4. 两套图状态与版本混在同一事件体系

Coordinator维护edges/active/topology_version，SoftTaskGraph也维护edges/active/version。HT实际使用后者，事件封装却默认写前者的topology_version。CPU探针在真实HT类上提交首图后，payload.version=1而外层topology_version=0。已有轨迹也可见这一格式。

当前审计读取payload所以不受此字段影响，但其他分析脚本若按外层版本判断会误判。需定义唯一权威组织版本，区分观察版本与图版本；旧日志保持原样，分析器应按profile解释。

### 5. 墙钟新鲜度与模拟步耦合

Coordinator默认stale_seconds=360，HT guard调用c.fresh。合成探针在同一个模拟步、人员与环境状态未变时，仅将clock推进400秒，原动作从[0,10,10]变为[0,0,0]，被标为stale。

这不是已完成5人实验的失败解释（它们300动作均下发、0hold），却是50人大团队串行LLM循环的潜在问题：推理延迟可能被误作环境观察已经失效。需要明确同步模拟步与真实时间的不同新鲜度语义，不能仅通过扩大超时掩盖。

### 6. 运行配置、健康判据和冻结范围不统一

- 当前入口链：run_task_hypergraph.sh → run_small_communication_benchmark.sh → Embodied；另外还有dynamic_followup_batch、旧hypergraph_campaign、architecture_comparison及独立run_pair.py。
- shell允许MODEL/URL覆盖，run_task_hypergraph_smoke manifest却硬编码deepseek-chat/temperature0；换模型可能产生配置记录偏差。现有DeepSeek运行不据此改判。
- 默认batch会保存native exception数量，但healthy条件不读取它；最近独立run_pair会在原生异常时停队列。两种runner的含义不一致。
- smoke记录启动前构建hash，结束后只校验源码；最近pair另做了程序集检查。构建通过路径链接复用，不等于不可变副本。
- 进程清理工具被放在旧architecture_comparison实验脚本里，当前smoke从其导入cleanup；归档旧对比脚本时会误伤当前运行工具。
- 当前分析器有多套JSONL解析、计数和命名，如图提交/拓扑变化/减员等处理各自维护。应共享事件读取与明确指标定义，保留各实验的特定统计。

建议用一份运行配置生成命令与manifest，统一基础进程/冻结/日志收尾组件；旧脚本保留显式历史入口。共享物理指标不应藏在旧campaign工具里。

### 7. 版本与环境说明不完整

coordination整个新增目录仍显示为ORCH仓库中的未跟踪内容；CREW根目录本身不是git仓库，外部scripts/tests/research也没有统一根版本。冻结包能保护已跑实验，但常规git diff不会展示未跟踪文件内容，单个上游commit不足以定位本地实现。

pyproject声明openai ^0.27.8，requirements-full与wildfire额外依赖声明1.82.0，实际安装为1.82.0；setup通过--no-deps editable安装和额外包维持运行。现有环境可用，但仅按pyproject重建不能得到同一依赖集合。需要明确唯一可复现安装途径及本地扩展的版本管理根。

## P2：可读性与体积冗余

### 8. 文档和状态入口还不唯一

HYPERGRAPH_ADAPTATION.md等根文档仍将历史HA/HR/近邻策略称为“当前”；最新README则指向HT。dynamic_followup/STATE.json顶层batch/change等仍指Cycle010，最新pair/cleanup放在后加子字段。读顶层与读新子字段会得到不同的“当前”。

建议保留原文档历史信息，增加明确历史标签；仅保留一个current指针记录开发源码、验证快照、build、实验状态。历史条目单独列为timeline。不要在多个README和STATE不同位置各维护一套当前状态。

### 9. 日志与运行内存存在重复

运行快照重复带入能力说明、任务知识、规则等静态信息，但decision_state没有把这些字段送给组织器；它们主要用于记录，并非增加了模型知识。不能因字段出现在snapshot就声称LLM看过。

Coordinator把所有完整事件写盘后又保存在events列表；节点观察和world snapshot有重复数据、多次deepcopy，长时域大团队内存随事件数增长。适合区分静态运行元数据、动态状态和有限内存缓存，保留完整磁盘证据；不能直接删除日志字段使历史审计失效。

### 10. 多仓库和多快照不等同可删垃圾

CREW主目录约11GiB：.conda约5.8G，artifacts约1.6G，ORCH约1.1G，benchmark_runs约644M；各上游/部署参照仓库约455–476M。大部分体积是环境和运行资产，删除839行旧图并不会显著释放磁盘。

CREW-base、CREW-Wildfire、ORCH、WILDFIRE-ORCH是不同上游/部署用途，不能只按相近名字合并删除。/data1下workspace/frozen_sources作为运行溯源，不应随活动代码整理一起删除；可建立清晰索引、将新运行产物统一放到/data1，历史保持原路径。

## 建议执行顺序

1. 汇合已验证且未撤回的修复与回归测试，明确默认引擎构建，先解决“从哪里启动才算当前实现”。
2. 固定运行配置、版本和健康判据的单一来源，建立清楚的current状态入口。
3. 从RuntimeBridge/Coordinator提取共享基础，隔离旧空间逻辑，统一图版本含义与模拟步新鲜度。
4. 再整理runner/analysis/tests目录和历史文档；不扩展组织规则，不重跑历史结果。

详细机器证据与探针：`/data1/gzy/crew_structure_audit_20261028/evidence.json`、`check_structure.py`。本次审计未修复上述问题，也没有以新探针替代原实验效果证据。
