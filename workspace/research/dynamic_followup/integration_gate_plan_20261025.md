# 已修复路径的最小集成门禁

预先指定：Suppress_Fire_Extinguish_Second_Fire、seed137、2步、超时900秒，使用当前工作树的消息解析/时间标签修复，以及独立验证过的guarded构建。固定输出 `/data1/gzy/crew_dynamic_followup_20261025_integration_gate`，不覆盖、不自动重试。

独立源码、独立Unity构建路径、独立原生日志和模型日志，不改变正在运行的Cycle003/seed256。它是新版本集成门禁，不是完整任务重复或新任务成功样本。

检查：

- 程序正常结束、实际2步、机制审计及源码完整性通过。
- 构建hash明确对应guarded程序集，原生异常如有则保留并分析。
- 实际动作提示含当前step/version和message_history，历史项保留发送step/version；没有TTL、自动删消息或动作权限扩张。
- 原始组数由模型决定，不要求多组或强迫跨边消息；不存在的事件后重组不作为两步门禁要求。

两步不会覆盖第二火点事件或完整任务，不能据此得出任务收益。门禁通过后也不立即重启完整case；先完成当前预定seed256的审查。
