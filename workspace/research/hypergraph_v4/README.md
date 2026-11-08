# 继续运行：救援与较长灭火窗口

2026-10-11 09:44（Asia/Shanghai），确认 v3 24/24 已正常完成、无遗留运行进程后，启动本批 8 次实验。

- 新任务：Rescue_Civilians_Known_Location_small，官方 seed 9502，原时域 25 步，目标 3 名平民。
- 灭火：Suppress_Fire_Extinguish，新官方 seed 6216，30 步窗口。原时域为 100 步；本批不称完整时域，也不是与旧 seed4936 的受控时域配对。
- 每个 task-seed 固定比较 P / HA / HR / HR-projector-off，保留全部结果，不重跑旧失败，不调 agent prompt 或规划。

runtime 与 v3 相同；仅 task/seed/horizon 和分析工具扩展。新 spec、独立 manifest、493 个源码/环境文件冻结；v6 gate 校验通过。分析工具 5 项测试通过，新增诊断要求“实际观察到起火，再观察到无活跃火”，不能把起火前 false 当作灭火成功。

原 game_type=3 validator 仍要求 burned-tree>0，未修改其评分。扩展分析中另列 observed clear after ignition，作为描述而非替代胜率，保留事件编号。修复评分规则须另行作为版本变更评估，不能偷偷回填旧分数。

进度及产物：[LIVE_ANALYSIS.md](../../benchmark_runs/hypergraph_campaign_v4/LIVE_ANALYSIS.md)、`campaign_controller.log`、每 case `events.jsonl` / `evidence_timeline.md` / 原始 results 和 PNG links。实验结束自动生成 `summary.csv`、`analysis.json`、`extended_analysis.json`。

监督进程初始 PID 2366693，真实存活以 ps 和日志为准，不依据历史 PID 判断仍在运行。预计约 1–2 小时，超时阈值 3000 秒/case，超时也保留；磁盘启动前约 155 GB 可用。不要重复启动同一目录。
