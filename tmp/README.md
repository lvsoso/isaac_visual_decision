# 综合报告交付

- [HTML阅读版](项目阶段总结与开源方案对照报告.html)：内嵌三张SVG和既有接管录像代表帧，无脚本、无远程字体或其他外部资源请求；可离线阅读、浏览器打印。
- [Markdown原稿](项目阶段总结与开源方案对照报告.md)：正文、设备配置、实验过程、结果、开源对照和证据索引；图示占位注释供构建使用，其后链接可单独打开图示。
- [信息流架构](figures/system-information-flow.html)、[实验阶段进程](figures/experiment-progression.html)、[输入匹配结果](figures/matched-input-results.html)：三份独立HTML／inline SVG。

## 阅读与复建

直接用浏览器打开HTML即可。窄屏图表在局部容器内滚动，打印采用A4横向。无需启动模型、Isaac或服务器。

录像和完整证据仍位于原仓库；保持`tmp/`与`docs/`、`test_reports/`、`research/`的相对位置，链接才能正常打开。HTML正文、图示和代表帧不依赖这些外部文件读取，但视频不内嵌。

已安装Pandoc时，在仓库根目录运行：

```sh
python3 tmp/build-report.py
```

本次本地验证使用macOS上的Chrome：

```sh
python3 tmp/verify-report.py
```

验证脚本的Chrome路径及临时目录按本次本地环境固定，不是通用Linux验证入口。重跑会更新`verification.json`，需重新计算交付哈希。

生成器只读取Markdown、三张图示、模板和既有JPEG，输出本目录HTML。`report-template.html`负责默认浅色、中文回退字体与打印样式，不修改全局技能配置。

## 资料范围与验证

事实以2026-10-07保存的项目证据及本地固定版本开源调研为准。设备规格是用户提供的实例资源。外部项目未独立运行；CPU和浏览器检查不能替代历史Isaac GPU验证。本次仅文档交付，没有新模型调用或仿真实验，暂缓TODO不变。

`verification.json`记录文档构建、技能self-check、相对链接与桌面／窄屏浏览器检查范围；`SHA256SUMS.txt`记录本目录交付文件哈希。浏览器截图是文档排版检查，不是新增仿真输入或成功证据。

本次三张图均通过技能self-check；70个本地链接／锚点检查通过；Chrome实际1440px／500px阅读版与三张独立图示排版检查通过，正文无全局横向溢出、图中文字未重叠，窄屏可滚动到图示右端。实际打印／PDF输出未验证，不能将存在打印CSS表述为打印效果已验收。

综合时项目已发布基线为`2701788`；外部调研逐仓库固定提交列在报告附录C。所有既有实验文件保持不变。
