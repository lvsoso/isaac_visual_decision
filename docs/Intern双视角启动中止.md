# Intern双视角两阶段实验：启动检查中止，未执行接管

用户授权先蓝黄在线shadow、两色均7/7且物理成功后才各一回合受限Isaac接管。冻结计划 `0126b98` 已推送，22项新CPU契约与365项回归通过；但实际远端启动暴露了CPU模拟未覆盖的启动器环境变化。

- [失败过程与完整冻结／生命周期HTML](reports/candidate_control_startup_20261007.html)
- [失败审计JSON](../test_reports/candidate_control_startup_audit_20261007.json) · [原始证据包](../test_reports/candidate_control_startup_evidence_20261007.tar.gz)

## 实际发生了什么

- 2026-10-07 08:54:54–08:55:02 UTC，L40加载了独立Intern模型服务，CUDA/BF16来源／模板／校准检查通过。
- 首个蓝shadow入口在Isaac初始化之前退出，错误为 `Set OMNI_KIT_ALLOW_ROOT=1 and LD_LIBRARY_PATH="" before Isaac`。
- 服务完成计数始终为0：**0次预测、0个Isaac场景初始化、0次机械臂动作、0个完成shadow、0个模型接管回合**。模型权重加载不是模型决策测试。
- 黄色shadow及两个控制回合未启动，无自动重试、无基线回退。自建模型服务关闭，GPU计算进程为空。

## 原因与限定修复

驱动器确实以 `OMNI_KIT_ALLOW_ROOT=1` 和 `LD_LIBRARY_PATH=""` 调用Isaac的 `python.sh`。但官方 `setup_python_env.sh` 会把Isaac自带的kit／插件库加入 `LD_LIBRARY_PATH`，使进入Python后不再为空。新入口错误地把“启动前清空”当成“启动后必须仍为空”，因此拒绝了正常官方环境。

修复应区分：
1. 驱动器记录并声明**调用python.sh前**的空库路径；
2. 入口允许官方启动器添加Isaac目录内的自带库；
3. 仍拒绝系统Python库、相邻目录伪装、相对路径和缺失启动前声明；
4. 分别归档启动前环境和启动后实际库路径，不伪造“启动后仍为空”。

这是工程启动错误，**不能记成模型不达7/7，也不能声称已完成接管测试**。原失败计划、日志和工件保留，不覆盖或续跑本批；修复后CPU检查不能代替新GPU验证。后续真实实验须用新的冻结计划／输出目录，经用户确认再运行。

原失败证据包SHA256：`acfad897b219e674eaef701c5be92c56eedb208c82703f3be21a9c85419a44c1`。

修复增加 `--check-launch-only`：仅使用官方python.sh验证启动环境，不访问模型HTTP，不创建SimulationApp、场景、动作或回合目录。驱动器对新批次要求计划中明确指定新的 `experiment_dir`，旧计划不自动复用。

## 修复验证状态

- 修复 `8f7547f` 已提交推送并安全快进至GPU主机，Notebook未跟踪文件保留。
- 6项启动契约及完整 **372项CPU回归**通过；失败报告离线复建字节一致。
- [实际官方启动器环境检查](../test_reports/candidate_launch_remote_check_20261007.json)通过：允许Isaac自身kit／插件库，并保留启动前空LD声明。模型调用0、SimulationApp未启动、回合目录未创建、GPU计算进程前后均为空。
- 上述启动器检查**不是在线shadow或模型控制试验**。原37–40批次仍是未完成；等待用户确认后才以新计划／目录进行真实GPU试验。
