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

### 近接触精度与连续到位窗口

- 用户提供的真实 `runs/09_baseline` 记录确认所有动作阶段达到其控制器/夹爪判据，无超时、无异常；抬起结束时方块中心高度约 0.284027 m，但 transport 结束后已落地到约 `[0.491681, 0.130952, 0.025]`。最终 XY 误差约 0.369141 m，`physical_completion=false`、`strict_success=false`，不能把 `completed` 当成物理成功。
- 搬运期间夹爪目标保持 0.5 rad、实测约 0.500070 rad，日志不支持“程序提前张爪”的解释。用户图片看起来是指尖夹住方块上部；approach 的模型工具 Z 在 0.228816 m，目标 0.21 m，仍高约 18.8 mm 时即被 2 cm 容差放行。浅抓是本轮排查假设，未证明接触摩擦、运输加速度或模型几何误差不是其他原因。
- approach/lower 默认改为 5 mm 模型工具误差并要求连续 12 帧达标，越界清零，仍在原有阶段预算内执行。其他运动保持 2 cm；闭爪/张爪最少 60 帧、目标坐标、物理步长、摩擦、驱动增益、运输速度和最终物理评分不变。新设置是项目集成试验参数，不是官方推荐值或实际夹爪精度保证。
- 配置加载会为旧文件填入明确的新默认值，检查正数、整数、近接触阈值不能比普通运动更宽、稳定窗口能否容纳在预算中。阶段日志记录实际阈值及连续达标帧数；baseline 和模型模式使用相同规则，未添加基于私有方块真值的控制分支或掉落恢复。
- 新增 13 项 CPU 回归测试，覆盖 19 mm 过早结束、连续窗口/越界重置、最后一帧到位与超时、错误配置/旧配置、保持原运输容差和控制目标。最新 CPU 测试 **126 / 126 通过**，原始输出见 `test_reports/unittest_near_pose_20261006.txt`。
- **调整后的抓取深度、接触、搬运保持和完整物理抓放仍待真实 GPU 复跑验证。** CPU 替身没有模拟指垫、摩擦或刚体抓持；真实模型仍未验证。

### 真实 GPU 基线、模型链路与目标框可见性试验

- 在远端 L40 / Isaac Sim 6.0.1，提交 `748f144` 的 `runs/02_baseline` 成功；随后 `runs/13_baseline_repeat` 与 `14_baseline_repeat` 两轮自动 headless GPU 复跑均退出 0、`strict_success=true`，最终 XY 误差约 0.021993 m，776 次物理更新，所有八个阶段到位。它们是同一个固定场景的重复运行，不证明随机场景泛化或真机安全。
- 自动运行前为 Isaac 设置 `OMNI_KIT_ALLOW_ROOT=1`、`LD_LIBRARY_PATH=""`。此前未清空的 SSH 环境优先加载系统 Python 3.12.3 动态库、混用 Isaac 扩展，在 Kit async_engine 启动阶段崩溃；该启动失败记录保留在 `runs/12_baseline_repeat`，不能算作抓持回归。清空后实际解释器为 Isaac 自带 3.12.13。
- 独立 Conda 模型环境 `/root/gpufree-data/envs/ivd-model`（Python 3.12.14）安装固定 Torch 2.9.1 / Torchvision 0.24.1 / Transformers 5.14.1，`pip check` 和 L40 上实际 BF16 CUDA 矩阵运算通过。完整模型快照及小文件哈希已核对，服务仅绑定 loopback，加载的官方 inference.py SHA256 为 `c904e2c67ca0775621a22375ee373d2ba30b52117cda870c6c9ef74143b29863`。
- `runs/15_model_probe` 完成一次真实相机图片推理，约 9 秒；`runs/16_shadow` 的七次真实模型调用全部完成，约 7.8–8.8 秒/次，物理抓放仍成功。但建议为 `[approach, approach, grasp, lift, lift, grasp, lift]`，仅 3/7 与固定序列一致；后半段在抬起、到目标上方、放低后仍选 lift/grasp/lift，不满足当前 visual 接管门槛。图片 SHA256 和对应状态已核对，未给模型私有方块/目标坐标。shadow 成功不是模型控制成功。
- 本轮先只把非碰撞目标框线由 4 mm 加宽到 20 mm，边中心、颜色、相机、动作描述、物理参数与成功阈值均不变。新增五项 CPU 检查，覆盖 USD 几何、投影宽度、配置/颜色不变、自定义目标和缺失方块；RED 有两个预期失败，旧框线默认投影不足 1 像素。GREEN 全部 **131 / 131 CPU 测试通过**，原始输出见 `test_reports/unittest_goal_visibility_20261006.txt`，装饰方法可执行行覆盖 20/20；编译与 diff 检查通过。**本轮加宽后的 GPU 可见性、baseline 和 shadow 效果仍待复跑；不预先宣称已修复模型判断。**

### 加宽目标框的 GPU 对照与动作描述调整

- `fa5ffa9` 同步后，真实 GPU `runs/17_goal_baseline` 与 `18_goal_shadow` 均退出 0、物理成功、最终 XY 误差仍约 0.021993 m。检查实际相机图片确认加宽的蓝框清楚可辨，但 shadow 七个建议仍为 `[approach, approach, grasp, lift, lift, grasp, lift]`，与 `16_shadow` 完全相同；单独加宽没有改变本次 argmax，不能声称解决了决策问题。概率有所变化，不证明模型已理解目标。
- 下一轮仅修改 `CRITERIA` / `INSTRUCTIONS`：明确每个技能的视觉/本体适用条件和排除条件，避免已经抬起仍 lift、已经闭爪仍 grasp；解释 0/0.5 rad 与手指连杆参考点。仍保留全部八个候选、原状态和真实图片，不加入方块/目标真值、不按上一阶段强制下一阶段，也不调整温度、权重、物理或目标框。
- 新增七项 CPU 文字契约回归检查：RED 有五项测试失败（含六个子例），证据/候选保留检查通过；GREEN 全部 **138 / 138 CPU 测试通过**，原始输出见 `test_reports/unittest_action_descriptions_20261006.txt`，编译与 diff 检查通过。这些测试只守住提示文字与请求契约，不能替代真实模型判断验证。**提交 `efc3a8f` 时新文字的同图重放和新 GPU shadow 尚未验证；后续结果见下节。已有诊断图片不是独立测试集。**

### 新动作描述的真实同图重放与 GPU shadow

- `efc3a8f` 推送并安全同步到 GPU 主机后，`runs/19_prompt_replay` 完成七次真实模型推理，不运行或移动机器人。以 `18_goal_shadow` 的原 PNG 字节和对应状态重放，只改变问题文字；全部图片/状态、八个候选及顺序相同，响应图片 SHA256 与观测一致。与固定 baseline 的一致项由 **3/7 增加至 5/7**。
- 随后新运行 `runs/20_prompt_shadow`，Isaac 启动环境明确设置 `OMNI_KIT_ALLOW_ROOT=1`、`LD_LIBRARY_PATH=""`，仍使用独立模型服务。退出 0，七次真实推理完成，约 7.85–8.17 秒/次，776 次物理更新、21 帧记录；物理抓放成功、无超时，最终 XY 误差约 0.021993 m。建议与同图重放相同，仍为 **5/7**。

| 决策 | 固定 baseline 执行 | 旧文字 `18` | 新文字同图重放 `19` | 新文字新 shadow `20` |
|---|---|---|---|---|
| 1 | pre_grasp | approach | pre_grasp | pre_grasp |
| 2 | approach | approach | approach | approach |
| 3 | grasp | grasp | grasp | grasp |
| 4 | lift | lift | lift | lift |
| 5 | transport | lift | transport | transport |
| 6 | lower | grasp | transport | transport |
| 7 | release | lift | lift | lift |

- 重新读取远端原始文件，核对每次模型调用的请求/观测状态、PNG 哈希、响应及日志概率；官方 inference.py 哈希和温度不变。`17`、`18`、`20` 的完整仿真配置相同，`18` → `20` 的运行源码哈希仅 `visual_lab/protocol.py` 改变。摘要、全部候选概率及源文件 SHA256 归档于 `test_reports/gpu_prompt_comparison_20261006.json`；原始图片、请求/响应、日志及 HTML 保留在远端各 run 目录，未覆盖既有实验。
- **改善只发生在初始对齐与抓起后的搬运选择；到目标上方和放低后的判断仍不合理，不满足 visual 接管门槛，因此未运行 visual，`model_had_control=false`。** shadow 的物理成功来自固定执行器，不是模型控制成功；新 shadow 仍是同一固定场景，不是独立泛化测试。不能把 5/7 报告成机器人任务成功率，也不继续针对七张诊断图片反复改词。遮挡、单目高度歧义或模型场景理解不足只是后续待检验假设。
- 补充两项 CPU 输入拒绝测试，覆盖非字典状态及七种畸形证据/题目子例；全部 **140 / 140 CPU 测试通过**，输出见 `test_reports/unittest_prompt_verification_20261006.txt`。完整测试执行下，`make_request` 可执行行覆盖 10/10、`validate_request` 23/23，记录见 `test_reports/coverage_prompt_verification_20261006.json`；仅为这两个函数的 CPU 行执行覆盖，不是全仓库、分支或模型质量覆盖。Python 编译、SHA256 清单与 diff 检查通过；该轮没有再修改动作文字、相机、物理、模型或评分规则。

### 三因素八组合：实现及 CPU 验证

- 用户确认先做八组，目标信息只使用目标配置与实测关节控制工具点 FK，不提供方块真值。计划经反向审查，见 `plans/factorial-visual-decision.md`；新增独立 `collect_factorial.py` / `tools/run_factorial.py`，不切换默认 baseline/shadow/visual 的行为。蓝/亮黄 × 无/有目标辅助 × 单/双同时视图，共56次诊断推理；模型不控制机器人。
- RED 的26项相关测试实际执行，11个预期错误：原bridge拒绝双图，缺少能力声明/processor观察器，配对实验模块尚未实现；记录见 `test_reports/unittest_factorial_red_20261006.txt`。GREEN 补齐双图有限接口、逐图内容/顺序/清理、实际 processor 图像输入审计、无私有真值白名单、同参考点目标距离与同渲染步双相机；相关26项通过，记录见 `test_reports/unittest_factorial_green_20261006.txt`。
- 增加采集/重放合成场景、故障停止、颜色恢复、lower目标一致性、路径/哈希与旧目录保护、56次真实localhost HTTP替身请求回归。该替身不运行真实权重，不属于模型质量证据。反向审查还发现需要显式拒绝截断和真实模式下的合成采集来源；两项RED实际失败、GREEN通过，记录见 `test_reports/unittest_factorial_gates_red_20261006.txt` / `unittest_factorial_gates_green_20261006.txt`。processor调用显式 `truncation=False`，官方编码器在前向前检查完整长度并拒绝超长；真实重放拒绝合成manifest。当前完整 **185 / 185 CPU 测试通过**，记录见 `test_reports/unittest_factorial_20261006.txt`。所选15个纯CPU构造/审计/采集编排/重放函数行覆盖均≥80%，见 `test_reports/coverage_factorial_20261006.json`；不是整个仓库、GPU入口或权重加载覆盖。编译、SHA256及diff检查通过。
- **在实现提交45ce2e9时，双视图GPU同步渲染、实际颜色/地板对比、物理baseline和八组真实模型结果尚未执行。** 默认单图历史记录仍保留；所有新组颜色中性文字及相机说明属于共同协议变化，不能把历史5/7与新对照的差值直接归给三因素。只有完成全部56个有效响应才标记完整，最后两阶段仍为关键诊断；不声称模型接管或泛化。

### GPU颜色对照失败与受控恢复

- `21_factorial_capture` 已在L40成功执行固定抓放，776次物理更新、七个观测、28张RGB、最终XY误差0.0219928092m。物理不推进的采集检查通过，但**颜色处理不可靠**：原第一视图黄先采集的阶段3/5/7，目标ROI暖色像素变化极少或没有。原像素检查见 `test_reports/factorial_render_checks_20261006.json`。物理成功不使颜色实验有效。
- `22_factorial_replay` 在发现该问题时主动SIGTERM项目自己的重放进程；15个响应文件保留，后端共完成16请求（包括中止时在途请求），双图官方processor确实接受有序两图。**不使用部分结果作因素优劣结论**。21/22各增加 `INVALIDATED.json`，保留原summary、图片和响应；新增RED/GREEN回归，禁止使用已失效采集源启动任何重放。
- 两个额外冻结场景GPU诊断：USD颜色设置正确、dispatcher渲染计数增加，但额外app更新和重建render product均未稳定消除旧颜色影响。没有盲目改光照/渲染设置；原因尚未定位到具体RTX/Replicator机制。诊断源代码、图片与JSON留在远端 `ivd-ops/20261006/render_refresh_diagnosis` / `render_fresh_products_diagnosis`。
- 恢复策略：分别在场景创建时固定蓝/黄色（默认原蓝色不变），不再live改色；同一固定技能轨迹执行两次，严格核对七阶段全部物理状态、本体状态及工具目标完全相同，再验证14对实际目标ROI颜色变化，原像素配对后进行56次真实重放。不提供方块真值、不调整物理评分或提示词，也不启动visual；新的静态GPU结果仍待执行。
- 失败与两次GPU诊断原始摘要/来源哈希归档于 `test_reports/gpu_factorial_recovery_20261006.json`。静态颜色/严格状态配对九项RED实际失败、GREEN通过，记录见 `test_reports/unittest_static_color_red_20261006.txt` / `unittest_static_color_green_20261006.txt`；失效源拒绝见 `unittest_invalid_capture_red_20261006.txt` / `unittest_invalid_capture_green_20261006.txt`。补充路径/覆盖保护与像素拒绝测试后，全套 **200 / 200 CPU测试通过**，所选18个函数均≥80%CPU行覆盖，见 `unittest_static_recovery_20261006.txt` / `coverage_static_recovery_20261006.json`；仍不代表GPU或模型判断质量。

### 静态颜色GPU配对验证（正式推理进行中）

- 采集源码提交 `9fb6bf9`。`23_static_blue_capture` / `24_static_yellow_capture` 均在L40完成：各776次物理更新、七个同步双视图观测、无超时、最终XY误差0.0219928092m，方块最终坐标完全相同。七个对应阶段的全部关节、机器人根/方块位姿、仿真时间、本体状态和目标工具信息**逐项完全一致**，不是只对比最终成功。
- `25_static_paired_capture` 合并原始28PNG，哈希与来源一致；14对目标ROI暖色变化176–673像素，均超过最低20像素门槛。额外逐对目视核验可见框边缘确实蓝/黄不同，阶段1第一视图有机械臂遮挡但仍可见对应边缘。批准凭据绑定snapshots和28图哈希，不以ROI阈值替代实际框边缘确认。
- 证据摘要见 `test_reports/gpu_static_capture_20261006.json`；全部目标框放大对照见 `factorial_goal_color_review_20261006.png`；下降/释放前的两相机原始图见 `factorial_lower_release_views_20261006.png`（仅加展示标签，不作为模型输入）。模型接收原640×480 PNG，不接收拼图/裁剪/标注。
- 正式 `26_static_factorial_replay` 已启动，仍需完成全部56次响应和因子/图片/来源核验后才能报告八组模型结果。上述两次物理成功来自固定执行器；模型没有控制权。
