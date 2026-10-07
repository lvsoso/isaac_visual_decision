# Jev在线影子验证，不接管

用户授权远端Isaac在线影子决策，并追加明确门槛：组合必须在shadow中达到7/7，未达标的Jev不进入模型控制。SSH已恢复；L40计算进程为空，远端旧HEADf568a02与Notebook检查点保留，代码只做安全快进。

## 范围与门禁
- 蓝、黄各一个新Isaac固定执行器回合，每回合最多7次真实Jev POST，共最多14次；错误停止，不补答案、不重试，不启动模型接管。
- 既有scene/controller/config不改；新独立Jev影子入口，不改变现有RGB/Intern shadow或visual接口。
- 在当前姿态暂停物理、采集实测关节FK及本体状态，构建英文无图请求；执行完成后再取下一状态，而不是离线重放旧14请求。
- 重用已审阅英文描述/八候选，只把offline action suggestions改为online shadow action suggestions，预先冻结模板和代码。未来测量数值无法事先冻结，每份实际请求在调用前保存并计算哈希；前后私有物理快照仅作一致性审计，不送模型。
- 云API在独立模型Python子进程调用，Isaac端不读密钥，不安装SDK或模型依赖到Isaac；保留安全原HTTP正文/status/requestID后才解析，基础策略jev_sdk_basic_v1。
- 请求失败、非法响应或等待期间物理状态变化立即停止，不悄悄回到基线。模型合法的abort等建议只记录，实际动作仍固定序列。
- 先RED→GREEN与Git推送，再冻结新计划并同步远端。启动环境OMNI_KIT_ALLOW_ROOT=1、LD_LIBRARY_PATH=""。仅关闭本轮创建的Isaac/子进程，保留用户SSH和Notebook文件。
- 接管候选门槛：回合完整、固定执行器物理成功、7次有效调用、无错误且7/7一致；蓝黄整体候选必须两者都过门槛。门槛通过只是未来受限仿真接管的候选资格，不是已经接管或安全认证。
- CPU契约与真实L40 Isaac/GPU结果分别报告；失败工件保留，旧32/33/34与历史HTML不覆盖。
