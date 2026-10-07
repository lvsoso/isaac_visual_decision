# 测试报告 · v0.1.0

> **最新已完成：**Intern中文空间描述／双视角：保留41蓝shadow7/7，新增45黄shadow7/7后通过双色准入；46蓝／47黄各一回合受限Isaac技能选择接管均物理成功，各7次官方choice直接执行、776物理更新，无错误／重试／超时。本轮21次新推理，历史蓝7次未重跑。修复后的宿主GPU PID监督本轮实际通过，模型／Isaac已关闭。只限已知固定仿真场景，非实体／泛化／端到端定位验证。详见 [接管结果与原始证据](docs/Intern双视角受限仿真接管结果.md)。以下阶段中止记录保持历史原样。

> **最新在线阶段：**新41组Intern中文空间描述／双视角，在真实L40／Isaac完成蓝色7/7、七次新推理、776物理更新，固定执行器抓放成功；模型未控制。随后容器／宿主机GPU PID比较错误导致监督流程中止，42黄色shadow及43／44控制未启动。独立证据复核通过，官方lower与transport并列最高时choice为lower，原样保留；不能把蓝色单回合称为两色组合准入或自主成功。修复与386CPU回归／两视口各79项UI验证已完成，但修复后GPU监督、黄色与接管仍未验证。原启动中止批次不覆盖、无自动重跑。详见 [阶段结果](docs/Intern双视角在线影子阶段结果.md)。

> **Jev在线门槛：**此前35／36真实Isaac影子两色各5/7、固定执行器成功；用户要求7/7，Jev不进入接管。详见 [Jev在线结果](docs/Jev在线影子结果.md)。以下为保留的历史实验记录。

> **完整Jev组已验证：**新34组14次真实HTTPS推理，jev-1.13.0 / jev_sdk_basic_v1；14HTTP200、14独立request ID、零重试，两色各5/7参考一致项（相同英文Intern各2/7）。输入／HTTP字节逐份冻结核验，安全原正文在业务校验前保存；官方SDK0.7.2随后离线解析14/14成功，未额外调用或修改官方值。完整HTML保留全部概率、输入、响应与新批次出处；复用28条历史Intern，不补旧32或诊断33。321CPU测试、门禁10项契约及96.83%语句行覆盖（非分支）；桌面/窄屏各387项UI检查，离线重建字节一致。**无新Isaac/GPU物理或机器人接管，不是自主成功率**。详见 [完整结果](docs/Jev英文无图对照结果.md)。

> **后续Jev策略更新：**用户要求SDK examples风格，当前Jev使用 `jev_sdk_basic_v1`：直接保留官方choice/概率/confidence，取消总和、argmax与confidence公式门禁；保留基础结构/候选/有限范围/模型/安全归档检查。Intern不变。311CPU测试及7种官方SDK模拟响应通过；语句行覆盖89.66% / 85.42%（非分支覆盖）。33诊断原响应仅离线再检查，新策略下可通过；旧批次和历史工件不改写，无新增API或Isaac/GPU验证。详见 [策略说明](docs/Jev基础校验策略.md)。

> **2026-10-07 独立Jev诊断：**用户另授权1次新调用，原英文请求与jev-1.13.0不变。官方SDK0.7.2、SDK/HTTP重试0、一次性传输预算；HTTP200完整原始解码正文和request ID在业务校验前归档。官方SDK解析成功，八概率总和1.00，transport0.61为最高候选，confidence0.55与公式0.554285714的差值超过原0.001阈值——确认新响应与项目精度假设不兼容；**旧概率和错误未重现，不能还原旧正文或补入正式评分**。正式阈值没有修改。307CPU测试、9捕获契约及7种官方SDK模拟响应通过；语句行覆盖93.75% / 90%（非分支覆盖）。核查官方wheel SHA256与安装源文件，独立环境，无Isaac/GPU物理/机器人控制。详见 [单次诊断和完整真实返回](docs/Jev单次诊断结果.md)。

> **2026-10-07 最新部分结果：**目标名称单字段绑定中文Intern14次及英文Intern14次真实L40 CUDA/BF16无图建议完成，分别两色1/7、2/7；28份请求与事前哈希一致、28份tokenizer-only零视觉输入。Jev第一份HTTP推理响应触发概率范围 / 总和校验后立即停止，0条已验证决策、其余13份未发送、无重试。原客户端校验发生在归档之前，正文丢失，无法展示概率或区分具体API异常与兼容原因；**Jev不打分，本次42次计划未完成**。之后安全失败响应归档缺陷经3项RED→GREEN修复，**298/298 CPU测试通过**，5个核心模块语句行覆盖90%–100%（不是分支覆盖）；不补回原正文，也没有新真实请求。部分结果HTML桌面 / 窄屏各215项通过，仅展示28条完成决策。无新Isaac / 渲染 / 自主控制，CPU / 浏览器不是GPU物理验证。详见 [部分结果及原响应缺口说明](docs/无图目标绑定与Jev部分结果.md)。

> **2026-10-06 方法纠正：**28批次无图组保留了需要看图的指令与criteria，提示与输入不匹配。其42次真实工件与历史报告继续保留，但撤回把2/7→7/7当作公平视觉收益或合理无图能力的解释。用户要求使用优化提示重测，设计见 [输入匹配提示修正](plans/modality-aware-prompts.md)；修正后的GPU结果须另批次报告，不能用修改过的提示冒充旧响应。

> **最新修正验证：**`modality_aware_v1` 移除无图看图要求及虚构相机输入。271/271 CPU复验通过；此前16项新契约RED→GREEN，11个所选函数行覆盖最低83.33%。SSH恢复后，**42/42真实L40 CUDA/BF16推理完成**：无图两色1/7、单图蓝5/7黄6/7、双图两色7/7。请求冻结哈希42/42、零视觉输入14/14、双图14/14输入 / 选择 / 全部概率精确复现；服务0→42，结束仅自建服务关闭且GPU计算进程为空。真实HTML桌面 / 窄屏各556项检查通过，离线重建仅归一化两处来源路径后字节一致。**CPU / 浏览器不替代Isaac GPU物理验证，本轮无新Isaac、渲染或自主控制；新比较包含提示适配，不是纯图片因果效应。** 详见 [输入匹配提示结果](docs/输入匹配提示对照结果.md) / [HTML](docs/reports/modality_prompts_20261006.html)。此前合成页面检查554项及Chrome退出超时记录继续保留，与真实模型证据分开。

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

### 静态颜色GPU配对验证（采集证据提交时正式推理进行中）

- 采集源码提交 `9fb6bf9`。`23_static_blue_capture` / `24_static_yellow_capture` 均在L40完成：各776次物理更新、七个同步双视图观测、无超时、最终XY误差0.0219928092m，方块最终坐标完全相同。七个对应阶段的全部关节、机器人根/方块位姿、仿真时间、本体状态和目标工具信息**逐项完全一致**，不是只对比最终成功。
- `25_static_paired_capture` 合并原始28PNG，哈希与来源一致；14对目标ROI暖色变化176–673像素，均超过最低20像素门槛。额外逐对目视核验可见框边缘确实蓝/黄不同，阶段1第一视图有机械臂遮挡但仍可见对应边缘。批准凭据绑定snapshots和28图哈希，不以ROI阈值替代实际框边缘确认。
- 证据摘要见 `test_reports/gpu_static_capture_20261006.json`；全部目标框放大对照见 `factorial_goal_color_review_20261006.png`；下降/释放前的两相机原始图见 `factorial_lower_release_views_20261006.png`（仅加展示标签，不作为模型输入）。模型接收原640×480 PNG，不接收拼图/裁剪/标注。
- 采集证据提交 `6d63d72` 时，正式 `26_static_factorial_replay` 已启动，仍需完成全部56次响应和因子/图片/来源核验后才能报告八组模型结果。上述两次物理成功来自固定执行器；模型没有控制权。

### 八组合正式真实模型结果（完成）

- `26_static_factorial_replay` **56 / 56真实推理完成**，28单图/28双图，无API错误、无mock、无截断，`model_had_control=false`。逐请求核验有序PNG/RGB哈希、实际processor图像网格、完整候选概率/argmax、温度和模型来源；首尾服务数值配置与源码哈希一致。再次检查全部因子配对：A只变图片，B只增目标辅助块，C只增第二图及描述，原图片字节不变，无方块真值/私有核验字段/期望动作入模型。

| 颜色 | 目标/工具辅助 | 单视图一致项 | 双视图一致项 |
|---|---|---:|---:|
| 蓝 | 无 | 5/7 | 4/7 |
| 蓝 | 有 | 5/7 | 5/7 |
| 黄 | 无 | 5/7 | 4/7 |
| 黄 | 有 | 5/7 | 5/7 |

- 八组最后两步均 **0 / 2**：应lower仍选transport，应release官方仍选lift。两组无辅助双图在release阶段的lift与release是**完全相同的最高概率平局**，保留官方lift，没有人为破平局计成功。六组5/7动作序列相同；两组4/7另错在第二步（蓝选grasp、黄选pre_grasp）。
- 颜色使可见框边缘更清楚，但四种背景下的一致项差值都是0；目标辅助使双图恢复第二步、对lower概率有5.18–9.18个百分点增益，但仍未改变最后两步的官方选择；双图增加release概率2.95–6.73个百分点，却在无辅助时新增第二步错误。不能把“概率上升”或更显眼当成模型控制成功。
- 单图HTTP中位7.950秒（7.899–8.133），双图15.636秒（15.555–15.714）；完整输入1666–2669 tokens <8192。校准概率不是机器人成功概率。
- 完整八组表、末两步的竞争概率、四种条件配对差值及边界说明见 [三因素组合实验结果](docs/三因素组合实验结果.md)，机器可读原始概率/来源哈希见 `test_reports/gpu_static_factorial_20261006.json`。这只是同一固定场景七个相关状态的配对诊断，不是独立泛化评测或模型接管测试；未启动visual，也不继续在原七个状态上调整词句制造成功。

### 单文件离线HTML分析报告

- 用户要求HTML用于分析，新增 `tools/make_factorial_report.py` 与只读模板 `visual_lab/factorial_report.html`。产物 [docs/reports/factorial_20261006.html](docs/reports/factorial_20261006.html) 内嵌全部28张原始PNG、56份实际state/questions及完整响应，不需要网络、模型或机器人；点击8×7矩阵、三个因素和阶段可查看原图、官方选择/参考、完整概率、最高分平局及单因素配对差值。支持CSV和请求/响应JSON语义导出；原字节文件哈希另保留，不宣称下载的重新序列化JSON具有相同文件哈希。
- 六项报告契约/注入拒绝测试先实际RED（缺生成器），后GREEN；包括显式mock警告、真实模式拒绝替身/不完整/篡改工件、安全script数据嵌入、拒绝覆盖。记录见 `unittest_factorial_report_red_20261006.txt` / `unittest_factorial_report_green_20261006.txt`。
- 当前完整 **206 / 206 CPU测试通过**，并从原真实工件重建的HTML与归档文件逐字节一致；所选19个函数CPU行覆盖均≥80%，生成器88.41%，见 `unittest_factorial_html_20261006.txt` / `coverage_factorial_html_20261006.json`。这项CPU离线构建验证不重复调用模型，不替代前述GPU证据。
- 实际Chrome执行桌面1440px和窄屏500px的报告交互，每套296条检查通过：56个单元格的选择/概率/原图数量/实际state一致，因素选择、平局、条件差值、JSON/CSV导出及明暗主题有效，图片自然尺寸640×480，页面无全局横向溢出。记录见 `factorial_html_browser_20261006.json`。请求390px窗口被本机Chrome限制为500px，**未宣称390px实际浏览器验证**；CLI完成DOM/截图后未退出，按有界流程清理自己的测试进程，生命周期问题未冒充干净退出。

### 中英文 / 颜色指认 / 空间表达：实现验证（正式推理前）

- 用户确认后，预先固定六文案 × 两颜色 × 七状态的84请求设计；见 `plans/prompt-language-spatial.md`。只复用已有原图，不控制机器人或重新运行物理，不根据响应选择文案。
- 新22项契约测试实际RED后GREEN：数值 / 图片 / 机器ID在语言对照中不变，颜色只变两个目标句，空间表达保留带符号工具几何及参考警告，私有真值 / 参考动作白名单隔离，先冻结全部输入，不覆盖、不跳过失败或改最高概率平局；HTML内嵌全部输入 / 原图，拒绝篡改 / 替身并安全转义元数据。RED/GREEN记录见 `test_reports/unittest_prompt_variants_*_20261006.txt`。
- 完整 **228 / 228 CPU测试通过**，新增实现12个函数行覆盖均≥80%（最低81.82%）；见 `test_reports/coverage_prompt_variants_20261006.json`。另在本地离线构造84份真实原图请求，并核验14份英文中性请求匹配26批次、14份已有响应的原PNG/RGB与processor /温度来源；不发生新模型调用。
- 以上只是CPU合同 / 离线证据核验，**尚不能证明中文、目标颜色指认或空间表达会改善模型**。正式GPU推理结果后续单独归档；本轮不声称新的Isaac GPU渲染 / 新物理抓放成功。

### 中英文 / 颜色指认 / 空间表达：84次正式真实推理完成

- 实现提交 `ea37453` 推送并安全快进同步后，`runs/27_prompt_language_spatial` **84/84真实推理完成**，无API错误、无mock、无截断；全部使用相同两相机原PNG及目标配置 / 实测关节模型FK辅助。没有新Isaac进程、物理更新或渲染，不重新声称物理成功，模型仍无控制权。
- 英文中性 / 原始数值蓝黄均5/7；中文等义表达蓝6/7、黄7/7。两语言分别明确实际框颜色后分数及逐步官方选择不变。英文空间描述退到两色4/7（第二步新增错误），中文空间描述两色均7/7（纠正蓝框第一步）。中文六组的最后lower / release均2/2，英文六组均0/2。
- 独立逐请求核验84个组合 / 阶段、全部预先冻结请求哈希、有序PNG/RGB及两图processor网格、完整候选/argmax/confidence、温度与来源稳定，无私有真值 / 参考动作入state；实际请求与本地推理前输入核查全部一致。14份英文中性请求与26批次逐字节相同，新推理得到的全部概率和选择也14/14完全一致。首尾正式服务计数72→156，无额外重试。完整概率 / 来源证据归档于 `test_reports/gpu_prompt_language_spatial_20261006.json`。
- 本轮两个最高分平局分别位于黄框英文明确颜色原始的第二步（pre_grasp / approach，官方approach）及黄框中文明确颜色原始的第四步（lift / transport，官方lift），均保留官方输出。最后两步中文正确选择没有依靠平局；不混入26批次无辅助双图的释放平局记录。
- 输入2338–2669 tokens <8192；六种文案HTTP中位15.579–15.739秒，范围15.510–15.928秒。更高一致项不意味着更高目标概率：蓝框中性中文lower概率28.42%低于英文33.70%，但其候选排序成为最高；中文空间描述的lower约25.9%，仅领先第二候选1.57 / 1.58个百分点，不能当成稳健自主控制证据。
- 最终完整 **228/228 CPU测试通过**，12个所选函数行覆盖最低81.82%，HTML生成器96.23%；归档真实84响应HTML离线重建逐字节一致，见 `unittest_prompt_final_20261006.txt` / `coverage_prompt_final_20261006.json`。推理前输入核查及合成HTML浏览器验证单独保留，不冒充正式GPU结果。
- [新的离线HTML](docs/reports/prompt_language_spatial_20261006.html) 内嵌28原图与84完整输入/响应；真实Chrome桌面1440px / 窄屏500px每套462项交互检查通过，84单元格与实际state/PNG、全部14配对、两个原始平局、CSV/JSON导出及主题有效。截图目视检查通过；原图自然尺寸640×480，无全局横向溢出。CLI完成DOM/截图后仍需有界清理自己的测试进程，未称干净退出；见 `prompt_html_browser_real_20261006.json`。合成夹具两套459项另见 `prompt_html_browser_synthetic_20261006.json`，明确不是模型质量证据。
- 结果及方法见 [提示表达对照结果](docs/提示表达对照结果.md)。本轮固定六种文案和顺序后没有按响应改词；只是已观察过的单一场景七个相关状态，不是84个独立任务、泛化显著性或自主抓放成功率。即使中文空间描述两色均7/7，也不自动运行visual / 扩展独立场景。

### 无图 / 单图 / 双图：实现验证，正式GPU推理待执行

- 用户确认执行图片删除诊断。修改前main / origin/main=`224df70`且工作区干净；先固定 [42次设计](plans/image-ablation.md) 和18项新测试，实际RED为17项缺少实验API / tokenizer审计 / 重放及报告实现、1项默认无图拒绝通过，原输出归档 `unittest_image_ablation_red_20261006.txt`，测试与计划已提交推送 `b31d954`。
- GREEN实现显式 `--allow-text-only-ablation` 实验服务；make_request / validate_request / 默认bridge仍拒绝空图片，仿真流程未变。实验请求仅删除 `images` 为0/1/2张原PNG，固定中文明确颜色 / 空间描述及全部state/questions，包括原相机文字。无黑图或占位图，无私有方块真值 / 参考动作入state，无机器人控制。
- 已检查固定官方inference.py：无图分支调用tokenizer，有图调用processor。只增加审计代理，不改官方源码、模板或张量；无图核验完整token数、0视觉特殊token / 0RGB / 0grid。有图保持原processor.tokenizer，新增缓存清空保证不会把前次图像审计当作无图证据。新HTTP集成测试证明无图内部路径为空、response图片计数0 / 哈希为空，默认接口仍拒绝。
- 追加9项边界 / 安全合同，捕获并修正新HTML的嵌入JSON转义缺失：27项中1项真实RED，随后全部GREEN；两次RED原始输出均保留。最终完整 **255/255 CPU测试通过**，18个所选请求 / 审计 / 重放 / 报告函数行覆盖最低90.00%，非模型或全工程覆盖；生成器90.48%。见 `unittest_image_ablation_full_20261006.txt` / `coverage_image_ablation_20261006.json`。
- 本地构造42份真实冻结输入，同一颜色 / 阶段的state/questions逐字不变，0/1/2图各14份；14份双图请求与27批次 `zh_named_relative` 文件逐字节一致，旧14份真实响应离线审计通过。这是推理前输入核查，不是新的模型调用，见 `image_input_review_20261006.json`。
- 新离线HTML用显式mock响应 / 旧原PNG夹具验证：Chrome桌面1440px / 窄屏500px每套397项交互检查通过，42格、六配对的全部七阶段、0/1/2图片精确导出、无图页不出现img、完整概率、主题和CSV有效。目视检查通过，无全局横向溢出；CLI完成DOM/截图后有界清理自己的进程，未宣称干净退出。见 `image_html_browser_synthetic_20261006.json`，明确不是模型质量证据。
- 本节截至实现提交只验证CPU合同、保存工件离线审计和报告展示；**42次正式真实推理尚未执行**。原8765模型服务已停止、GPU空闲；准备以独立环境 / loopback8766启动实验专用服务，实验结束仅清理本轮自建进程，不运行新的Isaac / 物理 / 相机。

### 无图 / 单图 / 双图：42次正式真实推理完成

- 实现 `afc4b1f` 推送并安全同步后，实验loopback8766服务完成 `runs/28_image_ablation` **42/42真实CUDA/BF16推理**，无API错误、无mock、无截断。固定中文明确颜色 / 空间描述的state/questions，只删减images；默认生产接口仍不接受无图。本轮没有启动Isaac、推进物理或新渲染，模型无控制权。
- 两色结果完全一致：**无图2/7、单图6/7、双图7/7**；最后lower / release分别0/2、1/2、2/2。无图官方建议两色均 `[pre_grasp, approach, approach, abort, abort, abort, lift]`。蓝单图最后选lower / lift，黄单图最后选lift / release；双图两色都是完整参考顺序。逐状态推理不是实际执行abort后又继续的机器人轨迹。
- 42份输入与推理前本地请求哈希完全匹配；14份无图确认为空images / 0PNG路径 / 0图片响应计数 / 空哈希列表 / 首图哈希null，官方tokenizer_only分支实际编码中0RGB、0image-grid、四种视觉特殊token全部计数0。另28份有图响应逐条核对原PNG / RGB顺序及1 / 2图processor网格；全部42个argmax / confidence / 完整候选 / 温度 / 首尾来源审计通过。服务计数0→42，无额外重试。
- 14份双图请求与27批次中文明确颜色 / 空间描述逐字节相同；重新推理的choice与全部候选概率也14/14精确相同。桥接 / 协议源码为显式无图支持及审计变更，旧 / 新来源均记录，不声称服务源码完全相同；官方inference / 模型配置 / 模板 / revision及温度1.99241824不变。
- 本轮七处最高概率完全平局均保留官方选择：两色无图第二步pre_grasp / approach（选approach）、第四步lift / abort（选abort）；黄无图第六步lift / abort（选abort）；蓝单图第六步transport / lower（选lower）、第七步lift / release（选lift）。蓝单图6/7中下降依赖官方平局选择，释放虽也并列最高仍不计成功。双图无最高分平局，但lower仅领先1.57 / 1.58个百分点，不能当作稳健接管证据。
- 无图1724–1728tokens，HTTP中位0.291秒；单图2031–2035tokens，中位8.136秒；双图2338–2342tokens，中位16.037秒，均低于8192。完整耗时范围保留，没有删除慢请求；服务日志说明使用torch实现而非未安装的可选fast path，本轮未额外安装模型依赖。加载 / 推理 / 生成报告 / 清理自建服务共约370秒，服务已关闭，结束及下载核查时GPU计算进程为空，没有终止他人进程。
- 完整机器可读证据及哈希见 `test_reports/gpu_image_ablation_20261006.json`；原42份请求 / 响应、远端HTML及运维日志完整保留。[归档离线HTML](docs/reports/image_ablation_20261006.html) 内嵌28原PNG与42实际输入 / 响应；0图页明确没有发图片，不展示参考图冒充输入。
- 真实数据Chrome桌面1440px / 窄屏500px每套**404项交互检查通过**，含42格完整概率、六配对全部七阶段、七个官方平局、0/1/2图精确JSON和42行CSV导出。目视检查通过，无全局横向溢出；CLI完成DOM / 截图后有界清理自身进程，未称干净退出，见 `image_html_browser_real_20261006.json`。实现阶段mock夹具的397项单独保留，不混作真实模型证据。
- 最终归档前完整 **255/255 CPU测试再次通过**，18个所选函数行覆盖最低90.00%，生成器90.48%；42真实响应报告离线重建逐字节一致，见 `unittest_image_final_20261006.txt` / `coverage_image_final_20261006.json`。CPU / 浏览器只验证合同及展示，不替代真实GPU推理，也不构成新的物理抓放或渲染验证。
- [方法与详细结论](docs/无图单图双图对照结果.md)：图片删除使这版固定输入无法维持原7/7，支持本场景图片有明显贡献；不能据此声称模型理解了所有图像三维关系、纯文本推理普遍弱或自主抓放可靠。无图保留原“查看图像”前提，未优化纯文本提示；abort也可能是缺少夹持证据时的保守选择，模型没有提供解释，不能断言内部原因。不自动启动visual / 新场景。
