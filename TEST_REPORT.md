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
