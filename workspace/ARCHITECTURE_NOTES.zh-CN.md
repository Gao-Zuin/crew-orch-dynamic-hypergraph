# CREW / CREW-Wildfire 架构与扩展笔记

核对日期：2026-10-21。依据本地源码；下述运行验证仅为 `scripts/verify.sh` 的依赖、配置导入和构建文件检查，未重新运行 Unity episode。源码与下载的二进制是否完全一致，仍需运行时对照。

## 1. 工作区边界

| 目录 | 用途 |
| --- | --- |
| `CREW-base` | 基础平台：Unity Dojo、Nakama、Python Algorithms；含 Bowling、HideAndSeek、FindTreasure 等环境及 RL/人类反馈工具 |
| `CREW-Wildfire` | 野火仿真与四类异构实体、任务预设、LLM 多智能体基线 |
| `ORCH` | 后续组织协作算法、扩充任务与指标；当前本机主要实验入口 |
| `WILDFIRE-ORCH` | 部署、人类交互与更新的 Unity 源码；不要误以为 ORCH 自带完整 Unity 工程 |
| `research`、`scripts`、`benchmark_runs` | 本地研究扩展、实验工具和运行产物；与上游环境规范区分 |
| `artifacts/game-build` | 下载的 Unity 构建；改 C# 不会改变现成构建 |

版本基线见 `VERSIONS.txt`，但该文件不能代表工作树没有后续修改。

## 2. 两条通信链与执行流程

```text
Hydra 环境/模型配置 + level preset + seed
  → update_config
  → make_env → make_base_env → UnityEnv / UnityWrapper
  → ML-Agents Python ↔ Unity ML-Agents（观测、动作、reward/done、side channels）
  → AIAgent → PlayerController → MapManager / CellGrid
  → GameManager 计算任务元数据和指标
  → Python 解析观测 → 协作算法/LLM → option/action library → 下一轮动作

人类客户端 ↔ Nakama / DojoConnection / Unity Netcode ↔ 仿真服务端
```

Nakama 承载多人连接与消息；Python 的环境 step 通过 ML-Agents，不能把两者视为同一个接口。Dojo 的事件、反馈、接管与记录能力是平台能力，不等于每个 Wildfire 基线都完整使用。

Python 环境入口在 `crew-algorithms/crew_algorithms/envs/{configs,unity}.py`；启动命令参数组装在 `utils/rl_utils.py:make_base_env`。配置经过 Hydra/attrs → 命令行参数 → Unity `ConfigReader`/各 Manager；新增配置必须逐段接通。

`UnityWrapper` 从 behavior specs 构造 TorchRL specs，按 agent ID 放入 TensorDict；step 根据 valid_mask/done 发出 ActionTuple。典型调用：

```python
state = env.reset()
state['agents']['action'] = action_tensor  # 每个槽位三个数
next_state = env.step(state)
observations = next_state['next']['agents']['observation']['obs_0']
env.close()
```

具体 runner 对 state 的更新方式应一并核对，不能照搬普通 Gym 的返回结构。

## 3. 仿真与信息结构

Unity 核心目录为 `crew-dojo/Unity/Assets/Examples/Wildfire/Scripts/`。

- `GameManager`：任务初始化、目标坐标与元数据、评分、帧循环和图像记录。
- `MapManager`：地图、累计可见地图、实体列表、灭火/砍树等世界修改；同文件还定义 Cell、CellGrid 与火势传播。
- `AIAgentManager`：固定槽位池，先分配 Manager，再分配消防员、推土机、无人机、直升机，剩余为 Default。
- `AIAgent`：观测序列化、动作接收、决策请求、人类反馈/回放入口。
- `ControllerScripts`：各实体动作与资源/携带/移动状态。

地图由 seed 和 Perlin noise 等生成高度、湿度、植被、建筑、风场；火势受单元状态、邻接、坡度、风和湿度等影响。移动/资源/火势随 Unity 仿真推进，因此一次 Python 决策不等于一次火势更新。

特别注意：实体观测裁剪自 `AccDataMap`。它由团队所有实体更新并积累，包含团队共同探索的信息，而非严格独立的瞬时传感器。小地图半径为 10/10/25/30，更新真实可见信息的半径为 5/5/15/20。要测试通信价值或私有信息，必须明确是否保留这条隐式共享路径。

## 4. 观测协议

固定单槽位长度 **3728**：

| 索引 | 普通实体含义 |
| --- | --- |
| 0 | 类型：0 消防员、1 推土机、2 无人机、3 直升机、4 环境 Manager、5 Default |
| 1…3721 | 局部栅格，最大 61×61，不足填 -1 |
| 3722 | imitation learning 标记 |
| 3723、3724 | grid x、y |
| 3725…3727 | 三个实体附加状态 |

消防员附加状态为携带平民、水量、非活动标记（乘直升机时相关）；直升机为所载消防员数、水量、保留值。栅格尺寸分别为 21×21、21×21、51×51、61×61，遍历为 y 外层、x 内层。坐标是栅格坐标，非 Unity 世界坐标；合法单元范围为 `[0, map_size-1]`。

第 0 行是环境 Manager 元数据，实际实体 ID 从 1 开始。`num_agents` 包括 Manager 和 Default 槽位，不能直接当作活跃实体数。ORCH 的逻辑组织管理者也不能与环境的 Manager 元数据槽位混淆。

Unity 实际地图编码：0 未揭示，1…4 湿润单元及树量，5…8 干燥单元及树量，9 ignited，10 on_fire，11 extenguishing，12 fully_extenguished，13 水源，14 建筑，15 平民。Python `translate_cell` 映射字符正确与否需结合这些语义；Wildfire docstring 把 10/14/15 描述为消防员/推土机/砍树，与这里的 C# 不符。

## 5. 动作与长期技能

底层是三个连续数值 `[command, x, y]`，其语义依实体类型解释；上层 option 编号不等于 command 编号。

| 实体 | 底层 command |
| --- | --- |
| 消防员 | 0 移动、1 砍树、2 取放平民、3 喷水、4 补水 |
| 推土机 | 0 移动、1 清树 |
| 无人机 | 移动为主要接口，具体以 Drone.HandleActionArray 为准 |
| 直升机 | 0 移动、1 接载、2 补水、3 卸载/投水 |

`libraries/*_option_library.py` 将长期目标展开到 action_queue；`generate_action_from_option` 和 `check_if_option_done` 依据位置与附加状态推进。LLM 生成的结构化计划不是直接环境动作。

`AIAgent.ExecuteAction` 将三个值之和为零的动作改写首项为 -1。因此 `[0,0,0]` 在此实现中不是普通“移动到原点”。现有 Python 边界判断部分允许 `map_size`，与实际栅格上界不一致；扩展时不能继承为协议规范。

## 6. 任务、成功与评分

Wildfire `config/build_config.py` 定义 17 个预设，基于六种 game_type：

| game_type | 任务 | Wildfire 完成判定 |
| --- | --- | --- |
| 0 | 稀疏/线状砍树 | score ≥ tree_count × trees_per_line × 3 |
| 1 | 侦察火情 | score ≥ 2 |
| 2 | 运输消防员 | score ≥ 起始消防员数 |
| 3 | 控火/灭火及其组合 | Python check_game_done 始终 False，受运行步数等限制 |
| 4 | 已知位置救援/搜索救援/运输组合 | score ≥ civilian_count × civilian_clusters |
| 5 | 综合任务 | Python check_game_done 始终 False |

Wildfire 的 Manager 行为 `[type, game_type, map_size, score, task_payload…]`。控火/综合 score 在 Unity 中是树木、建筑、平民与地面实体损失的加权负值，不能与砍树分数直接比较。

**ORCH 是另一版协议**：索引 3…15 为 13 维指标，任务 payload 从 16 开始；最后一格 3727 为 fire_active。指标依次为探索、火烧树、主动砍树、灭火、正确砍树、救援、运输、平民侦察、同时侦察火情、水源侦察、实体损失、平民损失、建筑损失。返回值 `score = rewards[4]` 只代表正确砍树，不是统一任务总分。

ORCH 控火/综合终止要求已经有树被火烧毁且 fire_active=False；救援支持动态 civilian_target。灭火终止和综合任务成功应在新任务里分别定义，不能仅从现有函数名推断。

本机 ORCH 导入检查发现 **30 个预设**；runner 有 25 组 benchmark seed 定义，但当前 `run_ORCH.sh` 仅启用一个 PRESETS 项。README 的“25 个任务”不等于默认执行 25 个任务，也不等于配置中只有 25 个预设。额外场景包括实体损失、突发平民、第二火点、水源发现、火势加速和规模任务；事件的实际注入位置须沿 runner/算法侧及 Unity 构建继续核对。

## 7. 新环境与任务集的改动边界

1. **现有机制的新场景**：增加 preset、seed 划分、实体组合、known 设置、预算与任务说明；接入 runner、日志和适用的团队配置。
2. **新的目标/成功规则**：同步改 GameManager 初始化与指标、Manager payload、Python parse_game_data/check_game_done、数据导出和分析。任务说明、可观察信息与成功判定必须一致。
3. **新的世界机制/实体能力**：修改 CellGrid/MapManager/Controller、Prefab、枚举和 ML-Agents specs，再同步 Python config/CLI、观测和动作解析、option 库与提示词；重新构建 Unity。
4. **全新领域环境**：复用 Dojo/Nakama/ML-Agents/TorchRL 桥接，另建场景、控制器、状态/动作协议、任务生成器和评估器；无需继承野火的固定编码。

每个新任务至少明确：任务 ID/版本、生成参数与 seed、实体能力和数量、信息公开边界、动作与时间预算、成功/失败/超时、过程指标、扰动触发条件、日志 schema、可复现启动配置。设计通信实验时，额外明确共享地图、位置列表和组织管理者能够访问的信息。

## 8. 本机运行证据与剩余验证

`scripts/verify.sh` 已通过：工作区 conda 的 Python 与主要依赖可导入、ORCH Agent 可导入、30 个 preset 可读取、Unity 可执行文件存在。历史结果压缩包仅下载约 1.48 GB / 30.57 GB，并非新实验必需输入。

本机通过 rootless Docker 启动 Nakama；官方构建的固定内网地址由 `scripts/rootless_nakama_redirect.c` 兼容，入口见 `start_nakama_rootless.sh`、`run_noop_rootless.sh`。后续运行应沿用这些约定。

本轮未启动服务、未调用 LLM、未执行 Unity episode、未修改仿真或算法代码。新增任务落地前需以实际构建验证：观测长度/顺序、动作效果、时间推进、终止、指标与 seed 可复现性；不能以静态读码代替。
