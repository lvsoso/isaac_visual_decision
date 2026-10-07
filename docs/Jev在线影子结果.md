# Jev真实Isaac在线shadow：两色各5/7，不进入模型控制

**真实L40／Isaac在线影子验证已完成，蓝、黄各5/7，未达到用户要求的7/7门槛。Jev保留为对照，不进入模型控制环节。**机器人始终由固定执行器控制，未启动任何模型接管。

- [离线HTML：14份真实审计帧、实际无图输入、原响应与全部概率](reports/jev_online_shadow_20261007.html)
- [完整审计JSON](../test_reports/jev_online_shadow_20261007.json) · [运行生命周期](../test_reports/jev_online_shadow_lifecycle_20261007.json)
- [原始GPU／HTTP证据包](../test_reports/jev_online_shadow_evidence_20261007.tar.gz) · [实际执行记录](../test_reports/jev_online_shadow_execution_20261007.txt)
- [推理前冻结计划](../test_reports/jev_shadow_plan_20261007.json) · [模型接管候选门槛](模型接管候选门槛.md)

## 结果与门槛

| 项目 | 蓝框，35组 | 黄框，36组 |
|---|---:|---:|
| 实时Jev建议与七参考动作一致 | **5/7** | **5/7** |
| 有效真实API调用 | 7 | 7 |
| 固定执行器完整抓放／最终物理评分 | 通过 | 通过 |
| Isaac物理更新 | 776 | 776 |
| 方块最终XY误差 | 约2.20cm | 约2.20cm |
| 模型实际控制 | 无 | 无 |
| 模型接管候选资格 | **未通过** | **未通过** |

两色建议都是 `[pre_grasp, approach, pre_grasp, transport, transport, lower, release]`。仍然是 **grasp建议pre_grasp、lift建议transport** 两处不一致；未用归一化、重选答案、动作掩码或补测制造7/7。固定执行器成功不等于模型成功。

## 真实运行与输入边界

- 2026-10-07 **08:25:12–08:28:02 UTC**，在NVIDIA L40启动两个全新Isaac回合；每回合实时取当前本体状态和实测关节FK，等待API期间物理暂停，14次前后私有快照均一致。
- 英文无图请求：相机图像仅供审计；物体位置、holding、期望动作和阶段编号不进入模型输入。目标描述来自配置与FK，不是视觉定位。
- 与旧34组沿用同一场景、固定轨迹和英文描述；提示仅预先冻结地把offline action suggestions改为online shadow action suggestions。本轮新测量的14份state恰与旧离线state数值相同，这符合确定性固定轨迹，**不是重放旧请求**。实际调用有14个新的request ID，在线源码与快照／动作证据保留。
- 冻结实现 `783b584`、计划 `210f4c0` 在GPU／API启动前已提交推送；新35／36目录独立，不续跑或覆盖32／33／34历史组。
- Isaac启动设置 `OMNI_KIT_ALLOW_ROOT=1`、`LD_LIBRARY_PATH=""`。每次云调用由独立模型Python子进程处理密钥；未将模型依赖安装进Isaac。

## 调用与证据

- 固定 `jev-1.13.0` 和 `jev_sdk_basic_v1`；14次POST、14份HTTP200、14个独立request ID，无错误、无自动重试。此处使用项目HTTPS客户端，**不声称网络请求由官方SDK发送**。
- 原始HTTP正文／允许列表头在业务校验前保存；choice、八候选概率与confidence原样保留。私密密钥不进入代码、报告或证据包。
- 从Isaac端测得的**独立子进程端到端等待时间**中位数约 **1374.8ms**，范围1219.6–1519.2ms；含Python启动、模型列表检查、HTTPS、归档与IPC，**不能直接当成纯推理时间，或与旧594ms HTTP计时比较**。
- 返回usage合计input_tokens=24,176、output_tokens=1,118，不推算费用。
- 原始证据包SHA256：`8da18caf380c9edad91ab7ee16cd3684ef90c94de314a77fbf52de86acdcc792`。
- 独立离线审计核验真实PNG哈希／尺寸、输入无真值泄露、冻结提示／源码、原HTTP请求响应与业务JSON一致、暂停快照一致、固定阶段序列、物理评分及门槛。未另行从保存关节数组独立重算FK。
- 两个Isaac进程和一次性worker均正常退出，运行后GPU计算进程为空；远端Notebook检查点保留。
- 343项CPU回归测试通过，其中7项保存证据的复建／篡改拒绝测试；HTML／JSON离线重建字节一致。桌面1440px与窄屏500px各138项浏览器检查通过，覆盖14帧、原始概率、输入／响应正文和无图／未接管说明。

## 后续范围

Jev当前组合不再进入接管。其他组合即使历史离线回放7/7，也须完成各自的真实在线shadow并达到门槛，才可列为后续受限仿真接管候选；本轮未运行其他组合或授权其接管。

本页的GPU物理结果来自真实远端Isaac运行；CPU契约／离线审计／浏览器检查仅验证代码和报告，不替代GPU验证。两色固定轨迹的小样本不能代表泛化、自主任务成功率或安全认证。
