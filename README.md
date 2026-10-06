# Isaac Visual Decision Lab · v0.1.0

**Isaac Sim 6.1 / UR10e + Robotiq 2F-140 / RGB / Intern-Decision / cuMotion RMPflow**

这份代码把“模型看图选择抓放阶段”和“控制器执行连续运动”分开，提供实际入口、模型 HTTP 服务、检查工具和实验日志。无需手工把伪代码补成程序。

> **验证状态：**已经完成 CPU 单元测试和本地 HTTP 合成闭环测试；没有在交付环境中运行 Isaac Sim、RTX 相机或真实 Intern-Decision 权重。因此它是依据官方接口实现、带测试的集成代码，不是已经在某台 GPU 上验证过抓放成功率的发行版。详细记录见 [TEST_REPORT.md](TEST_REPORT.md)。
>
> **能力边界：**模型通过真实 RGB 选择动作阶段；底层技能仍然使用配置中的已知抓取点、放置点。它不是从 RGB 估计任意物体三维位置的端到端抓取系统，也没有实现任意扰动后的完整恢复。

## 先读哪里

| 文档 | 内容 |
|---|---|
| [完整操作手册](docs/操作手册.md) | 从环境、权重下载到相机、基线、单图、影子模式、视觉闭环及录像 |
| [概念与实验边界](docs/概念与实验边界.md) | FSM、视觉、本体感知、宏动作、概率、特权信息与实验解释 |
| [来源与改动](docs/来源与改动.md) | 官方来源、模型固定版本、与原 Tutorial 9 的区别 |
| [测试报告](TEST_REPORT.md) | 实测内容与未验证内容；对应原始日志 |

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
