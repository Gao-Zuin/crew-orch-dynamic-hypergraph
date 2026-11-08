# 固定边与可变边的配对分析门禁

`analyze_matrix.py` 按D×R四格、fixed/adaptive两臂，每组四种子检查32个事件流、16个配对。单火结构组默认种子为42/256/503/819；复合组经过Full_Game原火点核验，默认种子为42/256/503/314。命令：

```bash
python ORCH/crew-algorithms/crew_algorithms/wildfire_alg/config/resource_scheduling/analyze_matrix.py benchmark_runs/structure_matrix --output benchmark_runs/structure_matrix/analysis.json
python ORCH/crew-algorithms/crew_algorithms/wildfire_alg/config/resource_scheduling/analyze_matrix.py benchmark_runs/composite_matrix --family composite --output benchmark_runs/composite_matrix/analysis.json
```

缺失、中断、任务/种子错位、组织条件错误、未用相同初始图、模型/最大步数/信息条件不一致、不同完成时域或动态公告不在第8步的配对均标为`unusable`。只有合格配对计算adaptive减fixed的公告→首次拓扑变化、朝新区域行动、本人视野内首次火格目视候选、首名/两名消防员进场时延。负数表示可变边更早；某臂没有该事件则指标为null，不能当作无限慢或0。静态D=0格保留为终态和资源效应对照，没有新任务响应指标。

该脚本的结果仍主要是响应代理：`TASK_SOURCE_VIEW_FIRE_SIGHTING` 只给出源码视野范围内的正向火格证据，不是逐区域火情完成证明，不能计算“第二火点解决速度”或宣布组织调整产生收益。`TASK_LOCAL_EVENT_CUE_DELIVERED`、目视候选及能力目录可支持信息路由与专家共享过程分析，但还需核对部署构建、事件来源和因果链。正式效应估计需补逐区域结果、记录版本/提示hash，并在预先冻结的完整配对集上计算种子内差值和置信区间；不要只选成功运行。
