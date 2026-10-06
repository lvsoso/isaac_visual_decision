# 仓库工作约定

- 每轮仓库修改完成并验证后，必须提交到 Git 并推送到 `origin/main`，不得只保留本地修改或本地提交。
- 不使用强制推送，不覆盖或丢弃他人改动。若推送失败，明确说明原因与尚未同步的提交。
- CPU 测试不能替代 Isaac Sim GPU 验证；报告中明确区分已验证内容与仍需远端验证的内容。
- 在目标 GPU 云主机启动 Isaac Sim 前，必须为该进程设置 `OMNI_KIT_ALLOW_ROOT=1`、`LD_LIBRARY_PATH=""`；不要让系统 Python 动态库优先于 Isaac 自带库。模型依赖安装在独立环境，不混入 Isaac。
