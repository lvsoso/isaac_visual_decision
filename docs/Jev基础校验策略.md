# Jev按官方SDK examples风格读取结果

2026-10-07用户要求：Jev不再采用额外严格数值推导校验，按官方SDK examples风格直接读取结果。新策略标识为 `jev_sdk_basic_v1`，仅用于Jev；Intern原校验不变。

## 现在如何检查

- 读取官方 `choice`、`probabilities`、`confidence`，不重新选最大值，不归一化，不重算或替换confidence。
- **不再用概率总和、choice是否argmax、confidence公式差异拒绝响应。**这些量仍可在诊断中显示，但只是信息。
- 保留项目必要的基础检查：响应结构与choice类型、合法的八候选标签、有限数值和[0,1]范围、固定真实模型身份、非mock及token usage结构。
- 保留安全归档、认证回显拒绝、响应大小限制与禁止自动重试。

这是**官方SDK examples的直接消费方式加项目安全/审计检查**，并非宣称与SDK底层schema完全等同。官方SDK底层仅做类型等检查，并没有全部范围/候选身份约束；项目仍需要这些基础约束才能安全归档并与固定候选比较。参考 [SDK usage examples](https://docs.typesafe.ai/sdk/python/usage.md) 与 [响应字段](https://docs.typesafe.ai/sdk/python/api/types/responses.md)；已核验SDK0.7.2来源见 [核查记录](../test_reports/jev_sdk_reference_review_20261007.json)。

## 既有诊断与历史结果

此前保存的真实响应 `transport / p=0.61 / confidence=0.55` 已经**离线**通过新校验，原JSON未改变。SDK style直接保留这三个返回值，不需要为0.55与公式0.5542857的差异再请求一次或改数值。

旧32批次仍为停止状态，原响应仍不可恢复；33单次诊断的原始summary、独立审计和证据包保持当时严格规则下的结果，不覆盖成新的历史结果。新规则只用于未来运行及明确标注的离线再检查，不把诊断补成正式14状态评分。

本轮只修改校验与测试，**没有新Jev调用，没有重跑14状态，没有Isaac/GPU物理验证**。继续正式比较需要另行授权并冻结新批次；运行health/manifest会记录 `validation_policy`。

验证：311项CPU测试通过，7种官方SDK0.7.2模拟响应通过；两个修改模块的AST语句行覆盖89.66% / 85.42%（非分支覆盖）。[新规则离线再检查](../test_reports/jev_sdk_basic_offline_recheck_20261007.json) 与 [测试日志](../test_reports/unittest_jev_sdk_basic_green_20261007.txt) 单独记录，不覆盖先前证据。首次RED因测试缩进错误未有效执行行为契约，修正后用历史实现做行为RED，日志均保留，之后新实现GREEN。
