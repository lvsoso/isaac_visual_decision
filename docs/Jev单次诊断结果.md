# Jev单次官方SDK诊断：接口成功，发现confidence精度兼容问题

**1次新诊断调用完成，HTTP 200、官方SDK解析成功；项目原校验仍拒绝confidence。旧概率总和错误未重现，不能还原旧正文。**

- [真实返回JSON（完整原始解码正文，286字节）](../test_reports/jev_diagnostic_response_20261007.json)
- [实际发送正文](../test_reports/jev_diagnostic_request_20261007.json) · [HTTP状态 / request ID / SHA256](../test_reports/jev_diagnostic_response_meta_20261007.json)
- [诊断记录](../test_reports/jev_diagnostic_result_20261007.json) · [独立审计](../test_reports/jev_diagnostic_audit_20261007.json) · [完整证据包](../test_reports/jev_diagnostic_evidence_20261007.tar.gz)
- [官方SDK核查与固定版本来源](../test_reports/jev_sdk_reference_review_20261007.json)

## 原始返回

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "next_stage": {
      "type": "choice",
      "choice": "transport",
      "confidence": 0.55,
      "probabilities": {
        "release": 0.0,
        "approach": 0.03,
        "grasp": 0.04,
        "transport": 0.61,
        "lift": 0.01,
        "lower": 0.19,
        "pre_grasp": 0.01,
        "abort": 0.11
      }
    }
  },
  "usage": {"input_tokens": 1728, "output_tokens": 79}
}
```

此正文属于2026-10-07 **07:36:14 UTC**新独立诊断，不是先前丢失的32批次响应。服务Date头为07:36:16 GMT，与本机时钟有差异，两者如实保留。request ID为 `req_01a1154aa89d7d86bfcf5496735b1d72`；正文SHA256为 `61850593913d232e506cd387f0cca2fe6510bcb2c005bc8103f76baa228ad5fb`。

HTTP头标记gzip；证据保存的是**准确的解压后HTTP正文 / SDK解析输入**，不是TLS或压缩线上的字节。解压后复用响应时移除content-encoding，避免二次解压；原content-encoding仍保存在元数据。没有改动正文数值。

## 每层核验结果

| 层次 | 结果 |
|---|---|
| 请求 | 原英文state/questions、八候选与顺序不变；固定jev-1.13.0；没有images字段 |
| 网络 | 1次POST、HTTP 200、0重试；未继续其余13份 |
| 官方SDK | 固定typesafe-sdk0.7.2；调用解析与同正文离线解析均成功，没有修改概率 |
| 概率 | 八候选齐全、数值有限且在[0,1]，十进制总和1.00；transport0.61为唯一最高值 |
| 项目概率和校验 | 本次通过，**旧的总和错误未重现** |
| 项目confidence校验 | 本次失败：公式约0.554285714，API返回0.55，偏差约−0.004285714，超过原0.001容差 |

八候选Choice的官方公式是 `(p_max − 1/8) / (1 − 1/8)`。代入本次返回p_max=0.61，结果为97/175；返回confidence为11/20，两者相差−3/700。**公式结果保留两位小数正好是0.55**。这与舍入相容，暴露了本项目对公开数值精度的校验假设不兼容；没有服务器实现证据，不能声称已证明全API始终采用两位小数或某种舍入算法。

不能由此断言原32批次一定是舍入导致：那份正文未保存，而本次概率和恰好1.00。新的诊断只定位了一个可复现的项目兼容问题，不恢复旧数据，也不完成14状态模型评分。

## 为什么要参考SDK，但不能只看“SDK没报错”

官方 [Choice文档](https://docs.typesafe.ai/primitives/choice.md) 描述完整分布；[SDK字段说明](https://docs.typesafe.ai/sdk/python/api/types/responses.md) 使用“values sum to approximately 1”。核查固定源码与已安装0.7.2发现，ChoiceAnswer主要校验字段类型，没有项目的概率和 / 范围 / argmax / confidence公式检查，也没有自动归一化。

在独立环境中，用一个**合成的总和0.875**响应实际证明SDK接受而项目拒绝。这不是真实Jev错误证据，只说明SDK成功解析不等于满足项目所有数值契约。相反，项目0.001容差也是项目自行设定，不是官方明确承诺的精度。

SDK提供 `raw_http_response` 与 `request_id`，应保留状态、正文及 `x-typesafe-request-id`；显式 `RetryPolicy(max_retries=0)` 关闭重试。SDK DEBUG正文并不脱敏，本次禁用日志，并用传输层先检查私密回显、大小，再保存原始解码正文，最后才做业务校验。认证头、密钥和cookies没有进入工件。

## 后续方法（本轮尚未执行）

1. 先核实官方输出精度 / 舍入说明，或在新批次前明确声明精度兼容规则，再进行正式比较；不要为了让这份响应通过临时调分数。
2. 区分“API结构有效”“概率分布数值契约”“confidence舍入一致性”；原choice、概率、confidence全部保留，缺项 / 非有限 / 越界继续严格检查，不偷偷归一化或重选答案。
3. 若确认每个概率及confidence均按0.01就近舍入，可推导舍入误差上界，而不是沿用Intern精度要求；**这个前提目前未获得官方保证，本轮没有采用或修改任何正式阈值**。
4. 重新开展14状态Jev能力比较需要另获授权、冻结规则并使用新批次；不能把本次诊断补回32批次。

## 实测证据范围

- 实现提交 `8794e4c` 在第一次诊断推理前提交推送；输入源文件SHA256仍为 `26700b30b63147c7a542b41fb6e7aa61b923fdcebc3afceaaffa113058b4d245`。SDK实际JSON编码单独保存，结构 / 内容相同，不声称编码字节与原漂亮打印文件相同。
- 官方SDK wheel SHA256校验及相关已安装源文件逐字节匹配，依赖位于独立临时环境，不混入Isaac或模型环境。
- 307项CPU测试通过；9项捕获契约RED→GREEN，7种官方SDK MockTransport情形验证通过（概率和、gzip、HTTP错误、非JSON、私密回显、错误schema、超限）；两核心文件语句行覆盖93.75%与90%，不是分支覆盖。
- 真实只调用一次，后续审计 / SDK再解析均为离线，无新API调用。仅文本接口诊断，没有Isaac、GPU物理 / 渲染或机器人控制验证，也不是自主任务成功率或校准评测。
