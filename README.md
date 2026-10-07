# Isaac Visual Decision Lab · v0.1.0

**Isaac Sim 6.1 / UR10e + Robotiq 2F-140 / RGB / Intern-Decision / cuMotion RMPflow**

这份代码把“模型看图选择抓放阶段”和“控制器执行连续运动”分开，提供实际入口、模型 HTTP 服务、检查工具和实验日志。无需手工把伪代码补成程序。

> **验证状态：**最新271项CPU测试通过；已有固定执行器Isaac GPU抓放及84次提示表达对照。**旧机械删图的无图提示要求看图，2/7不作为合理无图能力或公平视觉收益结论。** [输入匹配提示42次真实GPU重测已完成](docs/输入匹配提示对照结果.md)：无图两色1/7、单图蓝5/7黄6/7、双图两色7/7。仅为固定轨迹建议一致项；提示适配不是纯图片因果效应，未验证模型自主抓放或泛化，未开放visual接管。详见 [TEST_REPORT.md](TEST_REPORT.md)。
>
> **能力边界：**模型通过真实 RGB 选择动作阶段；底层技能仍然使用配置中的已知抓取点、放置点。它不是从 RGB 估计任意物体三维位置的端到端抓取系统，也没有实现任意扰动后的完整恢复。

## 先读哪里

| 文档 | 内容 |
|---|---|
| [完整操作手册](docs/操作手册.md) | 从环境、权重下载到相机、基线、单图、影子模式、视觉闭环及录像 |
| [三因素八组合结果](docs/三因素组合实验结果.md) / [交互式HTML](docs/reports/factorial_20261006.html) | 颜色、目标/工具距离、单/双视图的56次真实模型配对推理及边界 |
| [提示表达对照结果](docs/提示表达对照结果.md) / [交互式HTML](docs/reports/prompt_language_spatial_20261006.html) | 中英文、明确目标颜色、厘米/相对位置描述的84次真实推理及完整输入 |
| [旧图片删除结果与限制](docs/无图单图双图对照结果.md) / [历史HTML](docs/reports/image_ablation_20261006.html) | 42次真实推理原样保留用于复盘；无图提示要求看图，不是合格纯文本基线 |
| [输入匹配提示结果](docs/输入匹配提示对照结果.md) / [离线HTML](docs/reports/modality_prompts_20261006.html) | 优化无图、准确单图说明及原双图的42次真实推理；包含旧 / 新无图完整对照 |
| [优化提示修正](docs/优化提示修正.md) | 修正看图要求失配的过程、提示边界与CPU验证 |
| [概念与实验边界](docs/概念与实验边界.md) | FSM、视觉、本体感知、宏动作、概率、特权信息与实验解释 |
| [来源与改动](docs/来源与改动.md) | 官方来源、模型固定版本、与原 Tutorial 9 的区别 |
| [测试报告](TEST_REPORT.md) | 实测内容与未验证内容；对应原始日志 |
| [同步到远端](docs/同步到远端.md) | 从 Mac 通过 SSH 同步已提交代码，GPU 机器无需访问 GitHub |

## 实际数据流

```text
Isaac Sim：渲染当前 RGB + 读取机械臂本体状态
  → HTTP 请求：PNG 字节 + state + next_stage 选择题
  → 本包 serve_model.py
  → 官方权重目录中的 DecisionEngine.predict()
  → choice + 全部候选概率
  → 校验输出
  → Tutorial 9 的目标生成/场景/RMPflow + 本包阶段执行器
  → 到位或超时后再次观察
```

选择题：`pre_grasp / approach / grasp / lift / transport / lower / release / abort`。

`release` 成功后自动 `retract` 并等候相同的静置时间；`abort`、API 错误或阶段超时不会悄悄切回基线。

## 四个实际运行模式

| `--mode` | 使用相机 | 调用真实模型 | 谁控制动作 |
|---|---:|---:|---|
| `capture` | 是 | 否 | 仅初始化、预热和拍照，不执行抓放阶段 |
| `baseline` | 是 | 否 | 固定阶段序列 |
| `shadow` | 是 | 是 | 固定序列；模型意见仅记录 |
| `visual` | 是 | 是 | 视觉决策模型 |

另有显式 `mock` 模式，只检查接口，不是模型实验。`shadow` 和 `visual` 会拒绝本包标记为 mock 的服务。

## 快速命令索引

完整环境准备必须按手册完成。下面三条环境变量需要在相关终端中设置：

```bash
export LAB="$HOME/isaac_visual_decision"       # ZIP 解压后的目录
export ISAAC_ROOT="/实际的/isaac-sim"           # 包含 python.sh 的安装目录
export MODEL_DIR="$HOME/models/Intern-Decision-4B"
```

模型进程，使用独立 Python 3.12 环境：

```bash
cd "$LAB"
python serve_model.py --checkpoint "$MODEL_DIR" --trust-model-code
```

Isaac 进程，使用发行包自己的 Python：

```bash
cd "$ISAAC_ROOT"
./python.sh "$LAB/run_isaac.py" --isaac-root "$ISAAC_ROOT" \
  --mode capture --headless --run-dir "$LAB/runs/01_capture"

./python.sh "$LAB/run_isaac.py" --isaac-root "$ISAAC_ROOT" \
  --mode baseline --headless --run-dir "$LAB/runs/02_baseline"

./python.sh "$LAB/run_isaac.py" --isaac-root "$ISAAC_ROOT" \
  --mode shadow --headless --run-dir "$LAB/runs/03_shadow"

./python.sh "$LAB/run_isaac.py" --isaac-root "$ISAAC_ROOT" \
  --mode visual --headless --record-every 6 --run-dir "$LAB/runs/04_visual"
```

**不要一次性串行粘贴这四次运行：先检查每一步输出，再进入下一步。** `--run-dir` 必须是尚不存在的新目录；重复实验换一个名称。

生成可浏览的本地报告、实际录像：

```bash
python "$LAB/tools/make_report.py" "$LAB/runs/04_visual"
# 录像需要先用 --record-every 6 采集连续帧，并另行安装 ffmpeg。
python "$LAB/tools/make_video.py" "$LAB/runs/04_visual"
```

## 目录结构

```text
run_isaac.py                  Isaac 独立应用入口
serve_model.py                本地模型 HTTP 入口
configs/default.json         场景、相机、时限与评分配置
visual_lab/
  upstream.py                检查并加载本机 NVIDIA 教程的场景类
  sim.py                     RMPflow/夹爪/物理阶段执行
  capture.py                 Replicator RGB；拍照不推进物理时间
  protocol.py                真正发送给模型的题目和候选条件
  server.py                  PNG HTTP → 官方 DecisionEngine
  client.py                  有超时、有校验、无静默回退的 HTTP 客户端
  core.py                    状态白名单、输出校验、到位和成功判定
  runner.py                  baseline/shadow/visual 调度
  audit.py                   图片、请求、响应、阶段和结果记录
  png.py                     Isaac 端不依赖 Pillow 的 PNG 编码
 tools/                      下载、预检、单图探测、报告、录像、合成测试
 tests/                      CPU 测试；不伪装成真实仿真测试
 docs/                       中文文档
 test_reports/               本次已运行测试的原始输出
```

本包不包含 Isaac 安装程序、NVIDIA 机器人资产或模型权重，不修改 Isaac 自带文件，不向真实机械臂发命令。第三方材料的许可见 [NOTICE.md](NOTICE.md)。
