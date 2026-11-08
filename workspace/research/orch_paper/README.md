# ORCH论文与官方实现审计

- `arxiv_2609.11737.pdf/.txt`：论文原文及文本版。
- [官方阶段切换全量审计](OFFICIAL_PHASE_TRANSITION_AUDIT_20261108.md)：覆盖索引中全部493条DeepSeek `WILDFIRE*`轨迹，473条master log可解析；检查纵向Manager自报进度、`NEXT_PHASE`、`ADD_PHASES`恢复语义、越域阶段和日志可审计性。
- `analyze_official_phase_transitions.py`：可重复生成审计数据。
- `OFFICIAL_PHASE_TRANSITIONS_493_RUNS.json`：560次阶段切换的逐事件结果。
- [影子validator审计](SHADOW_TRANSITION_VALIDATOR_AUDIT_20261108.md)：联合官方560次阶段切换和本地15条明确顺序任务，区分能力过滤、完成证据请求、可恢复中断、不可满足的正水量补水指令与已验证顺序；不修改历史动作。
- `shadow_transition_validator.py` / `SHADOW_TRANSITION_VALIDATOR.json`：影子分类工具和逐条结果。
- [冻结提示A/B](COMMITMENT_PROMPT_AB_AUDIT_20261108.md)：5个原始worker上下文、每条件3次。朴素承诺账本把12/12个正水量案例导向无效补水路径；领域规则提示让12/12使用余水前往下游，并保留满水正对照。该实验只测下一动作，不是Unity任务收益。
- `run_commitment_prompt_ab.py` / `COMMITMENT_PROMPT_AB_5_CASES_3X_DOMAIN.json`：可重复脚本、冻结prompt哈希、逐次回复与用量。
- [砍树错误前置条件审计](../bottom_up_reports/CUT_TREE_FALSE_PREREQUISITE_AUDIT_20261108.md)：错误动作知识如何从worker扩散到leader与超图结构；包含三条完整轨迹、固定时域进程AUC和4个冻结prompt的三条件A/B。
- `run_cut_tree_affordance_ab.py` / `CUT_TREE_AFFORDANCE_AB_4_CASES_3X_3COND.json`：动作规则能消除找水循环，但纯文字责任合同仍出现目标冲突与不可解析输出。
- [目标责任影子索引](../bottom_up_reports/TARGET_RESPONSIBILITY_SHADOW_AUDIT_20261108.md)：区分图内双主责、条件备用和消息改派；R3六个图外完成均有leader明确接管证据，说明validator不能把“非图主责”一律阻止。
