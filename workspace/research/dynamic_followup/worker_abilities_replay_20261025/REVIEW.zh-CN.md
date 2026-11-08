# 动作说明补传候选：控制层重放结果

2026-10-25。复用正在运行的seed137第0步世界快照event19和原组织器请求event21。baseline严格重放原输入；candidate仅增加快照已有的worker_abilities。各3次，模型deepseek-chat、temperature=0；不向Unity发动作、不修改真实轨迹。

## 观察

- 6次提案全部通过当前结构校验；这不等于方案语义可执行。
- 6次成员/leader结构完全相同：1–4为一组、leader1；5–8另一组、leader5。没有新增成员结构变化。
- candidate明确引用“refill to 5”，说明能够采用新增动作说明中的容量信息。
- 但 `0_with_worker_abilities.json` 仍要求3/4号“hold ready to relay water forward”，前线组依赖后方水供给；仅补传动作说明不能保证消除不存在的转水动作。
- `2_baseline.json` 明确出现“pending water delivery”和“refill handoffs”，说明该错误在原输入新采样中仍可复现。其余输出存在“等水到达”等歧义，不以关键词自动给出成功/失败标签。

成本：6次调用，输入6927、输出2789 token。每次请求、原始响应、结构化图均已保存。相同temperature仍有文字差异，不当作严格确定性复现。

## 决策

目前证据不支持声称“补传worker_abilities已修好错误分工”。保留为候选信息接线修复，暂不改正式运行实现、不追加转水禁令或强制组模板。继续观察完整轨迹中的执行者是否自行纠正，以及不可能的供给依赖是否实际造成停滞；之后再选择可验证的最小修正。

这里没有任何新的物理任务成功或失败证据，不能把这6次控制调用算成6条任务轨迹。
