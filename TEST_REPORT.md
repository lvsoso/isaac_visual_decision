# 测试报告 · v0.1.0

执行日期：2026-10-05。以下是交付过程中真正执行的测试，不是计划中的测试。

## 已执行

| 检查 | 结果 | 范围 |
|---|---|---|
| Python 编译检查 | 通过 | 所有 Python 文件语法；不等于 GPU 依赖导入成功 |
| CPU 单元测试 | **63 / 63 通过** | 使用 stdlib unittest，Pillow 用于实际 PNG 解码 |
| localhost HTTP 合成闭环 | **7 次请求/响应完成** | 真 HTTP、本地 PNG 编码/解码、固定响应夹具、合成场景、统一日志 |
| 报告与 CSV | 生成成功 | 根据合成运行记录生成；已标记 synthetic/mock |
| CLI 参数帮助 | 生成成功 | run_isaac.py 与 serve_model.py 的 argparse 入口 |
| 静态预检工具 | 执行成功 | 检查本容器的可见运行条件；明确未验证 GPU 仿真 |

## 测试组成

`tests/test_core.py`：34 项。包括配置和预算验证、夹爪最少60帧/运动阶段最低步数、最后一帧到位优先、严格评分、有限概率、标签、概率总和、mock 拒绝、状态白名单与 PNG 格式。

`tests/test_bridge.py`：13 项。包括真正的 localhost HTTP 请求、认证、健康检查、PNG 解码/哈希、临时文件清理、畸形请求、推理忙碌和错误路径。模型对象使用测试替身，不加载真实权重。

`tests/test_runner.py`：10 项。包括 baseline 不调用模型、影子意见不控制动作、视觉中止不收回、决策次数上限、API 失败不回退、阶段超时即停、自动收回不新增模型题、报告和新目录保护。场景是显式合成替身。

`tests/test_upstream.py`：6 项。包括可信教程文件探测、类/构造参数契约检查、AST 加载不执行顶层启动代码。输入是合成类定义，不是实际启动 NVIDIA 应用。

## 原始记录

- `test_reports/unittest.txt`：测试名称、结果和实际总耗时。
- `test_reports/offline_smoke.txt`：合成闭环的七次动作及结果。
- `test_reports/environment.json`：实际 Python/Pillow/操作系统及未执行标记。
- `test_reports/preflight_container.json`：本容器静态预检输出。
- `test_reports/run_help.txt`、`server_help.txt`：入口参数。

运行环境：Python 3.13.5，Pillow 12.3.0，Linux x86_64。真实模型建议的 Python 3.12 环境是安装目标，不是本次 CPU 测试实际使用的解释器。当前容器没有安装 `isaacsim`。

## 没有执行，也没有声称通过

**Isaac Sim 启动、资产加载、RTX 相机渲染、cuMotion RMPflow 控制、夹爪接触和真实方块抓放，均未在本容器执行。**

**Intern-Decision 的真实权重加载、视觉前向计算、GPU 显存占用、推理延迟和机器人任务准确率，均未在本容器执行。**

ffmpeg 的真实 Isaac 视频编码未执行；本次没有提供真实相机截图或成功视频。任何 mock 记录中 `strict_success=true` 或 `physical_completion=true` 只是让合成坐标通过评分函数，不能当作物理仿真结果；它同时标有 `mock_backend=true`、`synthetic_fixture=true`、`real_model_evaluated=false`。

## 在目标主机还需要完成的验收

按手册分别运行 capture → baseline → 单图 probe → shadow → visual。保留终端日志和整个 run 目录。这样可以逐层判断是 API 契约、资产/相机、控制器、模型判断还是评分条件的问题，而不是用一个总成功率掩盖未验证环节。

## 2026-10-06 后续修复验证

以下为后续验证，不替换上面的 2026-10-05 原始记录。

- 本地环境：macOS x86_64、Python 3.13.3、Pillow 12.3.0，使用独立 `.venv-test`，未安装 Isaac Sim。
- CPU 测试：**74 / 74 通过**，命令 `.venv-test/bin/python -m unittest discover -s tests -v`；新增记录见 `test_reports/unittest_20261006.txt`。
- 新增相机几何取景测试 3 项：使用默认光学参数估计方块、目标框与远端实测初始夹爪区域是否在画面内。不验证网格遮挡、颜色或 GPU 渲染。
- 新增真实适配器的时间线顺序测试 8 项：用延迟生效的 timeline 替身复现播放请求被误判为暂停，覆盖 pre_grasp、录像恢复、settle、实际暂停、窗口关闭及物理未运行。修复前 4 项报出相同暂停异常、1 项错误分类失败；修复后全部通过。
- 用户提供的远端 Isaac Sim 6.0.1 baseline 记录显示 `runtime_error`，错误为 `Timeline paused during an execution segment`，停在首个 pre_grasp，方块未移动。修复将播放状态检查移到同一次应用更新之后，不额外增加物理更新，不放宽超时。
- **修复后的真实 GPU baseline 抓放仍待远端复跑，不能把 CPU 替身测试当成抓放成功。** 真实模型仍未验证。

### SSH 离线同步工具

- 新增 `tools/sync_remote.py`，通过 SSH/SCP 传输 Git bundle，只允许干净的 `main` 快进更新，不要求 GPU 机器访问 GitHub。密码由本地终端的 SSH 提示处理，不写入脚本、参数或仓库。
- 新增 15 项测试，使用临时的真实 Git 仓库验证提交更新与哈希、保留模型/结果、保护未提交及未跟踪文件、拒绝分叉历史、忽略文件冲突、目标根目录校验、Shell 参数引用、只检查模式和传输失败清理。
- 最新 CPU 测试 **89 / 89 通过**，原始输出见 `test_reports/unittest_sync_20261006.txt`。传输层在集成测试中用本地文件复制替代 SSH/SCP；尚未完成实际 GPU 主机的认证与代码同步，不能把这些测试当成真实远端部署成功。

### 同一帧关节目标写入与无运动诊断

- 用户提供的远端 baseline 首阶段运行 1000 帧后超时，末端误差约 1.000521 m，并确认机械臂没有运动。尚不能仅凭该记录证明底层目标覆盖就是唯一根因。
- 公开 NVIDIA experimental Articulation 的 tensor 子集目标 setter 会读取完整目标向量、替换选定 DOF 后整体回写。项目原先每帧先写机械臂、再写夹爪；新增延迟提交的 read/modify/write 替身可复现后一次写入抹掉待生效的机械臂目标。
- 执行器改为每帧一次合并目标写入，保留夹爪命令、索引映射及未控制关节；缺失、非有限、无效索引或长度不匹配的控制器指令会报错。没有改变阶段超时、容差或物理更新时间步。
- 新增 10 项 CPU 测试，覆盖覆盖风险、夹爪保持、索引顺序、未控制关节、输出校验及实测诊断字段。最新 CPU 测试 **99 / 99 通过**，原始输出见 `test_reports/unittest_commands_20261006.txt`。
- 阶段日志新增有效指令帧数、最后提交的关节目标、起止末端和关节位置、最大关节净位移，便于远端判断指令是否生效。**修改后是否消除真实主机的不运动现象，以及能否完成抓放，仍需真实 GPU baseline 复跑验证。**

### CUDA 物理状态与 USD 位姿同步

- 用户随后提供的真实 `runs/07_baseline/events.jsonl` 显示：首阶段有 1000 帧有效控制器指令，最大关节净位移约 1.904847 rad，末端起止读数却完全相同。它证明关节物理状态已有变化，不能再把画面不动解释为没有控制指令；本轮抓放仍失败。
- 对照公开 NVIDIA [SimulationManager](https://github.com/isaac-sim/IsaacSim/blob/main/source/extensions/isaacsim.core.simulation_manager/python/impl/simulation_manager.py) 和 [XformPrim](https://github.com/isaac-sim/IsaacSim/blob/main/source/extensions/isaacsim.core.experimental.prims/python/impl/xform_prim.py)：CUDA 设置启用 Fabric、抑制 readback 并关闭 USD 更新；默认 `GeomPrim.get_world_poses()` 使用 USD。项目此前没有消除该状态源不一致。公开 main 源码分析不等于已检查远端安装源码。
- 修复在设备配置之后、场景加载之前禁用物理 Fabric 更新并解除 readback 抑制，恢复 USD 位姿回写，保持 CUDA 物理设备与原有步数、容差及阶段预算不变。逐帧回写存在性能开销，本小场景优先保证状态一致。
- 实际同步配置写入 `runtime.physics_pose_sync`；若 Fabric 仍启用、USD 更新仍关闭或 readback 仍被抑制，直接报错，不静默继续使用陈旧坐标。
- 新增 6 项 CPU 回归测试：实际构造流程的配置顺序、默认末端/方块读数刷新、不变更设备且不额外步进，以及三种配置未生效的报错。最新 CPU 测试 **105 / 105 通过**，命令 `.venv-test/bin/python -m unittest discover -s tests -v`，原始输出见 `test_reports/unittest_pose_sync_20261006.txt`。
- 用户上传的根目录 `summary.json` 保留在本地并排除出版本管理/代码同步；未覆盖或删除原始实验文件。**USD 同步修复后的真实画面、末端到位和抓放成功仍待远端 GPU 验证；真实模型仍未验证。**

### 控制器工具点与手指连杆的阶段参考点

- 用户提供的真实 `runs/08_baseline` 日志与画面描述确认机械臂开始运动，USD 同步配置已生效。第一阶段仍超时：手指连杆终点为 `[0.59402138, 0.01116086, 0.42365772]`，控制器工具目标为 `[0.5, 0.0, 0.525]`，混用参考点得到约 0.138690 m 的误差；尚未进入 approach/grasp，不能描述成抓起方块后停住。
- 本地按公开 NVIDIA UR10 URDF 对该组实测关节角做独立 FK 计算，`tool0` 位置约为 `[0.50002856, -0.00006615, 0.52496442]`，距目标约 0.000080 m。这是公开模型的计算证据，不是远端实测工具点，也不证明实际 UR10e/夹爪与模型已标定一致。
- 执行器改用已加载 cuMotion 模型的 [Kinematics.position()](https://nvidia-isaac.github.io/cumotion/api/python_api.html#cumotion.Kinematics.position) 计算同一个控制工具点；输入为按模型关节名称重排的实测关节角，并用实际根位姿转换到世界坐标。关节命令没有生效时不会仅凭目标角判定到位。
- **阶段参考点的定义已修正，不能把以前手指误差与新的控制器模型工具误差当成同一个指标。** 不改目标、2 cm 容差、预算或步数；手指的 USD 实测坐标及原诊断误差、模型输入、最终方块物理评分均保留。日志明确标记 `controller_model_fk_from_measured_joints`，模型工具到位不等于物理抓取中心到位或抓取成功。
- 新增 8 项 CPU 回归测试，覆盖两种参考点混比、目标未生效拒绝成功、关节顺序、根旋转/平移、无效 FK/缺失关节及目标/模型输入不被重写。最新 CPU 测试 **113 / 113 通过**，原始输出见 `test_reports/unittest_reference_20261006.txt`。
- 根目录上传的 `summary.json` 和 `events.jsonl` 均保留在本地并排除出代码同步。**修正参考点后能否进入下降、抓牢并放下，仍待真实 GPU 复跑；UR10 模型与实际 UR10e/夹爪几何误差、接触和最终物理成功尚未验证。**
