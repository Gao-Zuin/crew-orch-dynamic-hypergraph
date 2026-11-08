# CREW 适配完成性审计（2026-10-10，已完成本阶段）

目标是参考 MAS/hypergraph 的设计与实现，在 CREW 中实际适配并测试；不是仅写设计方案，也不要求把参考文档全部后续研究路线一次实现。以下把已验证接入、协议合成测试、真实任务效果和未支持能力分开。不能以某一层测试通过推断其他层已完成。

## 架构与机制

| 要求 | 当前证据 | 判定 / 限制 |
|---|---|---|
| 默认关闭，保留原 agent 执行能力 | Embodied `__main__.py` / `utils.py` 的可选 bridge；`test_runtime_prompt_and_message_parity` | 正常路径测试通过；不声称完整运行分布严格一致 |
| coordinator 与 CREW adapter 分离 | `coordination/hypergraph.py`、`crew_adapter.py`、`runtime.py` | 已实现；policy 不生成领域行动 |
| snapshot 的 task/session/version/monotonic time | `observe`、`emit`；时序、session、JSON schema 测试 | 机制通过；缓存地图的每格 freshness 未知，见 ADAPTER_REVIEW |
| claim 不覆盖 runtime evidence | `claim` 与 `observe` 独立；claim / superseded 测试 | 结构化协议通过；运行中的自由文本只保留，不自动评分为 fact |
| overlapping membership，单 active，多 passive | SpatialPolicy、commit 校验、context；overlap 测试 | v5 HR_transport 真实观测到 overlap 和 2 次 active switch |
| 局部 context，非全局历史拼接 | `context` 与 `prompt`；组内 evidence、passive 摘要、leader 邻接 | 已接入；v2 结束后已显式标注共享缓存 provenance，v6 真实日志验证 |
| leader/member 路由与投递反馈 | `allowed` / `send` / `dispatch` | HR 真机有 delivered/suppressed，failed 有合成测试；没有自动 leader 转发 worker 全部消息 |
| hard event 真正可到达接收者 | `hard_notice`；`test_hard_notice_really_delivered` | 已测真实回调写入 history；不是仅记录 escalation 标签 |
| 原 validator 不被 context 取代 | `observe` 独立调用 `core.alg_utils.check_game_done`；final/early-exit 测试 | 已测；只读原奖励用于评估，不注入全局奖励到 agent context |
| 动作后状态和最终 usage | `after_step` / `finish`；v5 三个 case audit | 真实运行通过；local-no-delta 不是全局无效或真实 idle 的充分证据 |
| reducer 的 partial credit、单调完成 | contract / progress 测试 | 仅中立合成测试；正式 benchmark 无可信 stage metadata，不启用手写 workflow |
| handoff 不相信 sender，receiver 增量确认 | receiver evidence / partial receipt / restart / wrong collector 测试 | 中立 API 已测；CREW 物理 collector ID 不充分，HF 明确拒绝启动 |
| guard 拒绝后恢复、未知时不 veto | HG guard/retry/abstention/heli alias 测试 | 仅协议 stress；普通 P/HA/HR 不启用，不宣称真实全域交付安全 |
| restart 与 sticky incomplete membership | retired session / stale / sticky 测试 | 合成机制通过；未做真实 Unity restart 故障 campaign |

## 实验设计与结果交付

| 要求 | 权威证据 | 当前状态 |
|---|---|---|
| 先过 infrastructure gate | `benchmark_runs/hypergraph_gate_v5/audit.json` | 三 case `passed=true`；不进入效果统计 |
| 配对 task-seed 与固定 arm 顺序 | `spec.json`、campaign `manifest.json`；balanced-order 测试 | 2 任务 × 2 seed × 4 arm；原时域；四种顺序配平 |
| 至少一项干预 | `HR_projector_off` 固定在 spec | 全部四次完成；闭环下不保证实际拓扑轨迹相同，不称单边 ECV |
| frozen code/config/model/threshold | manifest 493 hashes；`frozen_sources.tar.gz` | 逐文件归档 hash 全匹配；后续行为修改必须另建版本 |
| 保留失败、timeout、缺失的 denominator | 分析测试与汇总 16 行 | 不剔除未成功；未结束 outcome 为 unknown，非 false |
| 任务效果、通信与成本配对分析 | case events/status/audit，`summary.csv` / `analysis.json` | 16/16 完成并审计，11 成功、5 任务失败；结果和负面案例见 HYPERGRAPH_RESULTS.md |
| 原始轨迹与过程可追溯 | 每 case events、console、results/trajectories 链接 | 已结束 case 可查；链接指向原产物，归档搬运须连目标目录 |
| unsupported metrics 不伪造 | audit/analysis `unsupported_metrics` | 无人工 contract 的子任务 VMCR、NLP alignment、因果 useful messages、物理 HF 不提供伪数值 |

## 最终完成检查

1. v2 全部 16 个预定 case 正常结束、审计通过；11 次任务成功、5 次任务失败，没有选择性重跑。最终检查 15,668 条事件、9,664 张 PNG，结果和轨迹链接有效。合入新版前 493 个冻结文件 hash 全匹配，归档逐文件校验通过。
2. 完成 task-seed 配对、通信和 token 分析，保留 HR 容量死锁等负面结果，不将 2 seed 探索性结果称为统计证明。详见 [最终结果](../../HYPERGRAPH_RESULTS.md)。
3. 旧运行进程退出后才合入 provenance、refill abstention、成员顺序规范化修正。当前主目录 34 项测试通过，独立轨迹工具 2 项通过。
4. 新版 `hypergraph_gate_v6/audit.json` 总体 passed；P/HA/HR 分别 77/75/201 条事件，最终 validator 均为 episode_end；HR 有 overlap、2 次 active switch、31 投递/34 抑制。102 个 gate 冻结文件 hash 全匹配，真实 snapshot 含 map_memory 和 provenance，不再含 observed_cells。门禁进程与 Unity 均已退出。两步门禁不要求完成任务，也不计入效果统计。
5. 已更新适配说明与独立候选的晋升记录；v2 仍按旧源码分析，当前代码不能冒充其冻结版本。

本次目标的“适配并测试”已完成。HF、learned policy、真实故障/规模研究、ORCH 执行队列接入仍是明确未实现的扩展；合成 API 测试不等于对应真实能力。
