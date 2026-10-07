# 无图目标名称绑定与英文Jev：三组共42次

用户确认只重测无图。修改前main / origin/main=`b9a0da5`，工作区干净；先提交本设计和实际RED测试再实现。

- 复用29批次14份 `modality_aware_v1` 无图请求，只在 `state.goal_guidance.spatial_description` 前补一句：task中的蓝 / 黄轮廓线就是本goal_guidance中配置的地面框，“内部”指该轮廓线围成的地面区域。
- task、其余state、全部questions / 八候选及顺序、全部数值、图片空列表、相机空列表不变。不补框边界、拾取点、方块位置、夹持状态、动作标签或序列。
- 新批次 `30_goal_name_binding`，两色×七冻结状态=14次；固定种子交错，全部请求 / 哈希 / 顺序在首次推理前保存。不重跑单 / 双图或Isaac，不启动控制。
- 与29批次同一14份无图逐阶段配对，仅讨论目标名称绑定效果；保留旧1/7，失败立即停止、不重试、不根据分数改提示。冻结官方模型、模板、温度、候选与平局规则；核验真实CUDA/BF16、tokenizer路径、0视觉token / RGB / grid及服务0→14。
- 输出新JSON、Markdown和无图片的离线HTML，输入 / 响应 / 来源与旧结果可核查。CPU / 展示验证不替代GPU模型或Isaac物理验证。验证后提交推送origin/main、安全同步，结束只停止自建服务。

## Jev分离安排

用户明确Jev是TypeSafe System One，不支持图片，并要求英文task、状态说明、instructions与criteria。官方接口为 `POST https://api.typesafe.ai/v1/systemone`，需要 `TYPESAFE_API_KEY`。用户已提供仓库外本机 / 远端密钥路径，认证模型列表GET成功；不代表推理成功。不得保存密钥或Authorization到工件。

Jev英文输入须另行冻结，采用同一数值 / 信息边界，不补真值；model使用明确版本，不使用浮动latest冒充固定版本。Jev confidence并不等于最高候选概率，不能套用Intern的confidence校验或温度。官网“无类型错误”不等于任务决策正确；速度 / 校准宣传不作为本实验事实。

用户随后提供本机 / 服务器仓库外密钥文件，并确认增加Intern英文基线、本次同时测Jev。模型列表GET已认证成功（不是推理）。固定 `jev-1.13.0`，不用别名。正式范围：中文绑定Intern14次、英文Intern14次、英文Jev14次，共42次无图；三个分组独立计数 / 归档，英文两模型state/questions完全相同，Jev本机调用，Intern远端CUDA/BF16。英文是中文绑定提示的语义等价翻译，所有几何数值 / 精度、机器标识和八候选不变，全部42确切请求先冻结，不看结果改英文或加Jev专用技巧。JevAPI只将canonical request中的images=[]移除并添加model字段，禁止图片输入。

中文旧→中文新是单字段名称绑定对照；中文新→英文Intern含翻译因素；英文Intern→英文Jev是语言匹配模型 / 接口对照，不比较两者confidence为同一指标，也不声称已检验Jev的概率校准。三组API失败立即停止，不自动重试。API key不写仓库 / 请求JSON / 日志 / headers工件，禁止认证跟随重定向，错误仅保留状态码 / 类别，不保留可能回显密钥的响应正文。HTML完整归档实际请求 / 概率 / confidence来源，CPU与两种真实模型证据分开。

资料：https://typesafe.ai/blog/introducing-system-one-models-and-jev 、https://docs.typesafe.ai/introduction/quickstart 、https://docs.typesafe.ai/confidence 。

## 首次推理前全组门禁

`tools/freeze_text_study.py` 先保存中文 / 英文Intern / 英文Jev共42份canonical请求和42份不含认证的wire正文、文件SHA256、实际客户端JSON编码正文SHA256、全部顺序与实现SHA256。分组顺序固定为中文Intern、英文Intern、英文Jev；每组两色七状态以同一固定种子交错。每次发送前比对全组预冻结输入与正文哈希，不仅依赖分组自身冻结。中文批次30、英文Intern31、英文Jev32，均不覆盖旧工件；一个组失败不继续后续组、不重试。运行时间取真实UTC，文件名20261006只是沿用实验标识，可能在2026-10-07执行。
