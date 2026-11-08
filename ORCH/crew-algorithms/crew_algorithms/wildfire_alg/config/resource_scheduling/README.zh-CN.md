# 共享资源组合任务集

本任务集面向 ORCH 事件运行器，此目录独立于原始任务表。主实验 focused 有12个任务，扩展实验 combined 有12个任务：Early/Late × drone/helicopter/bulldozer × Sufficient/Contended。每组只改变关注 worker 的数量（2/1），作为资源充足对照与资源竞争条件。建议种子 42、137、256、503、819，共 60 个实验实例。

原始任务由 game_type 0–5 分别表示砍树、侦察、运输、灭火、救援、完整场景。单一 game_type 无法直接叠加，因此这里使用 Full_Game（5）组合火灾、搜救和运输，不将单项砍树任务的特殊地图参数硬塞进完整场景。消防员可步行、砍树或灭火，worker 并非所有动作的唯一实现方式。

Early 在决策步 0/1 报告新火点/新平民，形成开局附近的并行需求；Late 在 8/9 报告，要求重分配已有队伍。事件必须错开：现有 update_config 会移动同一步冲突事件。坐标为 100 地图内的 (80,80)、(20,80)，新增平民使用已有 spawn_civilians_5 指令；没有假设任意人数生成或运行中增加 worker。

无人机承担新火点侦察与新平民区域搜索；直升机承担部署消防员与向新火区部署另一队消防员；推土机承担两个火区的隔离。每项希望分配一个关注 worker，故并行目标需求 2，供给 1 时须排队、抢占或用其他能力替代。Late 的 2-worker 条件在初始只分配一个时有一个余量；初始任务是否已经占用两个取决于策略，配置不强制闲置。

重要边界：这些数量与 [release+1,release+13] 窗口是实验调度目标，不是 Unity 硬约束。没有实现 worker 独占预约、必须同时施工、窗口逾期自动失败或任务级评分。Sufficient 只表示关注资源数量足够，不保证路程、水量、存活及整个任务可完成。初始火区/平民位置由种子生成，新火点能否成功点燃、早期任务是否已经完成、是否真实形成重叠，需要运行时观测确认；不能仅凭配置声称必然发生冲突。

运行目标为 ORCH 的事件运行器，配合支持 pseudo-manager 5/10 指令的 Unity 构建。此目录不自动注册到原任务表。

加载：通过 from crew_algorithms.wildfire_alg.config.resource_scheduling import create_level_presets 加载，调用 create_level_presets()，将选中 preset 交给 ORCH config/build_config.py 的 update_config。其余执行、事件发射和结果采集沿用 ORCH 现有流程。tasks.json 的 design 字段留给实验分析，不传入 Unity。

评估应记录事件实际执行步、有效火格/平民增量、worker 分配及位置、首次响应延迟、换组次数、救援数、火势变化和 worker 损失。只将事件成功落地且两个需求确实重叠的实例纳入资源竞争分析；其余保留为无效操纵实例。应先做多种子 Unity 预跑，再冻结正式评估种子。

难度修订与轨迹证据见 [DIFFICULTY_REVIEW.zh-CN.md](DIFFICULTY_REVIEW.zh-CN.md)。新增 relaxed（24步）/urgent（16步）截止时间公告版本，分别调用 create_level_presets("relaxed") / create_level_presets("urgent")；原目标100步。截止时间尚不由原生runner评分，实际可解性待脚本基线及Unity预跑校准。

职业速度复核后的预算以 [MOVEMENT_AUDIT.zh-CN.md](MOVEMENT_AUDIT.zh-CN.md) 和 tasks.json 为准：无人机16/24步，直升机20/30步，推土机32/48步（紧迫/宽松）。此前统一16/24步已被替换。

当前默认加载 focused 单火点主实验；原双事件版本使用 create_level_presets(family="combined")。任务契约、现有遥测缺口见 [CONTRACT.zh-CN.md](CONTRACT.zh-CN.md)；静态与旧轨迹保守审计见 audit.py 和 audit_seed137.json。

组织效应研究另见 [STRUCTURE_STUDY.zh-CN.md](STRUCTURE_STUDY.zh-CN.md)：四格动态任务×稀缺无人机矩阵，与固定/可变协作边配对。

四种子无模型Unity物理门禁及候选配对种子见 [PHYSICAL_GATE.zh-CN.md](PHYSICAL_GATE.zh-CN.md)。
