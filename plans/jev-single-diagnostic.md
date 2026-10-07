# Jev单次官方SDK诊断

用户在2026-10-07明确选择「单次诊断」：仅1次新的API推理，独立工件，不补进旧32批次，不继续其余13份，不自动重试。开始前main/origin/main=`f568a02`且工作区干净。

## 只读核查发现

- 原请求仅model/state/questions，指定jev-1.13.0、英文、一题choice八候选；结构符合官方文档。
- Choice文档称概率和为1，SDK字段说明是approximately1；官方源码类型模型未看到范围或概率和校验/归一化。项目额外要求和偏差≤0.001，当前没有旧原响应，不能断言是容差导致。
- SDK支持原始HTTP响应与x-typesafe-request-id；默认重试需显式`RetryPolicy(max_retries=0)`关闭。DEBUG正文不脱敏，不启用DEBUG。
- 官方源码核查commit `f078f1e208a0d885154dc758344ae4fce77ac168`；PyPI当前版本0.7.2，wheel SHA256 `0a961148187d52e18276ed7f2d02617cfac48e3b97673cb631a8749397d43d1e`。独立临时环境安装，不混入Isaac、模型或CPU测试环境。

## 执行门禁

1. 先实际RED测试与Git检查点，再实现安全捕获与离线分析并GREEN。
2. 输入逐字节来自`test_reports/jev_first_request_20261007.json`，SHA256 `26700b30b63147c7a542b41fb6e7aa61b923fdcebc3afceaaffa113058b4d245`；不改提示、几何、候选或模型版本。
3. SDK显式官方HTTPS根、禁代理/重定向、禁SDK和HTTP重试。传输层设置一次性预算和落盘的调用门禁，第二次请求拒绝。
4. SDK发送前保存确切正文并核验解码后的state/questions/candidates不变；认证头不保存。
5. 接收后先做大小限制与私密密钥回显检查，再保存安全原始HTTP正文、状态、允许列表响应头、request ID和SHA256；然后才允许SDK/项目业务校验。密钥只在调用进程读取，不进日志或Git。
6. 同一份响应离线经官方SDK和项目各自解析，记录八概率、精确十进制/浮点总和、范围、候选集合、argmax、confidence公式、model与usage；不归一化、不换答案、不放宽正式校验。
7. 若故障重现展示真实返回值；若未重现明确「新诊断不能还原旧响应」，不声称找到旧故障根因。只验证接口与解析，不运行Isaac/机器人，也不做14状态能力分数。
8. 验证并提交推送origin/main；旧工件保持不变。

官方资料：
- https://docs.typesafe.ai/sdk/python/usage.md
- https://docs.typesafe.ai/sdk/python/api/types/responses.md
- https://docs.typesafe.ai/sdk/python/api/clients/sync.md
- https://docs.typesafe.ai/primitives/choice.md
- https://github.com/typesafe-ai/typesafe-sdk-python
