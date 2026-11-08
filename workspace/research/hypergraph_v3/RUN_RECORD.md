# 启动与记录

2026-10-11 01:29（Asia/Shanghai）启动 24-case v3 批次。启动前主测试 35 项、分析工具 4 项通过；新增主测试确保动态火场不捏造固定进度分母。v6 gate 的冻结源码未改变，plan 校验通过。

冻结文件 493 个，归档 `benchmark_runs/hypergraph_campaign_v3/frozen_sources.tar.gz` 大小 131,818,695 bytes，SHA256：`d846681519dce6d7f2654c8626611bc81dcf7f0ebc43e8a86baaadf98ed81692`。

运行入口为 `research/tools/expanded_campaign.py`，监督进程信息记录在批次目录 `expanded_supervisor.json`，实验子进程信息在各 case 的 `live_process.json`。原 runner 逐 case 校验冻结源码、清理自己创建的进程组，并保留 timeout/故障。报告每 20 秒检查已结束 case，不对 live case 评分。

当前进度以 `LIVE_ANALYSIS.md` 和 `campaign_controller.log` 为准，不以本静态启动记录冒充完成情况。实验结束时原 driver 自动输出标准配对分析，扩展 supervisor 输出资源和通信分析；不承诺自动自然语言语义判断。未结束任务为 unknown，不能计为失败或成功。
