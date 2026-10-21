<p align="center">
  <img src="assets/banner.svg" alt="DSH WhaleSong for FL Studio" width="100%">
</p>

<p align="center">
  <b>用一句话，把 8 小节旋律写进 FL Studio。</b><br>
  DeepSeek Harness → FL Studio 钢琴卷帘，只暴露三个 MCP 工具。
</p>

<p align="center">
  <a href="README.md">English</a> · <b>简体中文</b>
</p>

<p align="center">
  <a href="https://github.com/q6y6y6/dsh-whalesong-fl"><img alt="repo" src="https://img.shields.io/badge/github-dsh--whalesong--fl-181717?logo=github"></a>
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="platform" src="https://img.shields.io/badge/platform-macOS-lightgrey?logo=apple">
  <img alt="FL Studio" src="https://img.shields.io/badge/FL%20Studio-2026-orange">
  <img alt="tools" src="https://img.shields.io/badge/MCP-3%20tools-8b5cf6">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
</p>

---

## 它能做什么

你描述想要的旋律，DSH 找到目标通道，按参考风格生成音符，并写入当前聚焦的
FL Studio 钢琴卷帘。

- **目标校验**——当前 Piano Roll 不属于你指定的通道时，拒绝写入。
- **一次写入**——整段 8 小节一次提交，自动备份，并校验音符数变化。
- **不抢焦点**——触发键直接发给 FL 进程，DSH 通常保持在前台。
- **只有三个工具**——`melody_context`、`melody_write`、`melody_restore`
  （schema 约 1.4 KB）。

![WhaleSong 写入的 Piano Wide 旋律](assets/piano-wide.jpg)

<sub>草稿：`Piano Wide` 通道，24 个音符，C#4–C#5，
A–G#m–G–F#m–E 半音下行。没有混音、插件、Playlist 或渲染。</sub>

## 环境要求

| | |
|---|---|
| 系统 | macOS（在 macOS 27 / Apple silicon 上验证） |
| DAW | FL Studio 2026（验证版本 26.1.7，旧版本可能可用） |
| Python | 3.10+（推荐 3.12），以及 [`uv`](https://github.com/astral-sh/uv) |
| MIDI | 在 Audio MIDI Setup 中启用一条 IAC 总线 |
| 宿主 | 支持 MCP 的 DeepSeek Harness |

## 快速开始

```bash
git clone https://github.com/q6y6y6/dsh-whalesong-fl.git
cd dsh-whalesong-fl

uv venv .venv --python 3.12
.venv/bin/python scripts/setup.py
.venv/bin/python scripts/deploy_controller.py --dry-run
.venv/bin/python scripts/deploy_controller.py
.venv/bin/python scripts/doctor.py --live
```

`setup.py` 会安装桥接层和三工具 MCP server，并把当前路径写进 DSH bundle。

## FL Studio 设置

1. **启用 IAC 总线**——Audio MIDI Setup → Window → Show MIDI Studio →
   IAC Driver → *Device is online*。
2. **选择控制器**——`Options → MIDI Settings → Input`：启用 IAC 总线，
   `Controller type = FLStudioMCP`。
3. **选中钢琴卷帘脚本**——打开目标通道的 Piano Roll →
   `Scripts → ComposeWithLLM`（只需选一次）。
4. **升级后重载**——部署新控制器后，在 MIDI Settings 里重新选一次
   `FLStudioMCP`，让 FL 加载新脚本；这也会启用控制器的 `app.getContext`
   （标题、pattern、tempo、拍号）。


## DSH 设置

`packages/dsh-bundle/cordis.patch.yml` 会插入 MCP server：

```yaml
- insert:
    - id: fl-studio-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: fl
        transport: stdio
        command: /absolute/path/to/.venv/bin/python
        args: ['-m', 'fl_melody.server']
        cwd: /absolute/path/to/dsh-whalesong-fl
        toolCallTimeoutMs: 30000
        failOnStartupError: false
```

在 DSH 的 Plugins 页面安装 bundle，或把生成的配置块追加到 profile。
`scripts/setup.py --install-profile` 会在条目不存在时执行这一步（先备份
profile）。工具会以 `mcp__fl__melody_context`、`mcp__fl__melody_write`、
`mcp__fl__melody_restore` 出现。

## 使用

先打开目标通道的 Piano Roll，然后在 DSH 里说：

> 我创建了一个 **Piano Wide** 通道，请为我在其中写一个 8 小节的旋律，
> 风格类似XXX。

执行过程：

1. `melody_context("Piano Wide")` 检查目标、已有音符、pattern、tempo 和拍号。
2. DSH 按参考风格生成旋律。以XXX为例：E 大调、6/8、
   63 dotted-quarter BPM，调用时传 `beats_per_bar=3`。
3. `melody_write` 先备份，再一次写入全部音符，并校验音符数变化。
4. 回报通道、pattern、小节数、音符数、音域和 `backup_id`。


也可以直接跑桥接烟雾测试：

```bash
.venv/bin/python scripts/melody_smoke.py --channel "Piano Wide"
```

## 工具

| 工具 | 作用 |
|---|---|
| `melody_context(channel)` | 目标/就绪状态、pattern、tempo、拍号、音符摘要 |
| `melody_write(channel, notes, mode, bars, beats_per_bar)` | 备份、追加/替换、校验 |
| `melody_restore(backup)` | 恢复一次写入前的状态 |

音符格式为 `{midi, start, duration, velocity}`，时间单位是**四分音符拍**。
`bars` 默认 8；`beats_per_bar` 在 4/4 为 4，在 6/8 为 3。`mode` 默认
`append`；`replace` 会先清空目标。备份写在 `backups/melody/`，回执里返回
`backup_id`。

## 工作原理

```text
DSH skill: fl-melody
  → fl-melody MCP server（3 个工具）
    → fl-studio-bridge（MIDI 命令文件 + 触发音符）
      → FL Studio 内的 device_FLStudioMCP.py
        → 当前钢琴卷帘里的 ComposeWithLLM.pyscript
```

每次写入只产生一个 JSON 请求。触发键通过 Cmd+Opt+Y 直接发给 FL 进程；随后
检查请求是否被消费、状态文件是否变化。后置条件失败时保留备份并明确报告失败，
不会假装成功。

## 范围

v0 刻意只做旋律。它**不会**：

- 调整混音台、路由或自动化；
- 加载插件或新建通道；
- 放置或编辑 Playlist 片段；
- 保存工程、修改 tempo/拍号或渲染音频；
- 自动试听。

把 6/8 旋律写进 4/4 工程时，会显示成 6 个 4/4 小节。想要正确的重音和 8 小节
结构，请在 FL 里设置工程拍号和速度。

## 常见问题

| 现象 | 处理 |
|---|---|
| `Piano Roll is not focused` / 标题不匹配 | 打开目标通道的 Piano Roll 后重试；不要写到别的通道。 |
| `the Piano Roll script did not consume the request` | 在 Scripts 菜单里选一次 `ComposeWithLLM`，再重试。 |
| `No channel matching "Piano"` | 检查通道名；工具会返回相近的匹配项。 |
| `connected: false` | 确认 FL 在运行、IAC 输入已启用、`Controller type = FLStudioMCP`。 |
| `app.getContext` 不可用 | 在 MIDI Settings 里重新选一次 `FLStudioMCP`；在此之前会走 OCR fallback。 |
| 听起来比参考曲快/慢 | 在 FL 里设置工程 tempo 和拍号；旋律工具不会改它们。 |

完整检查：`.venv/bin/python scripts/doctor.py --live`。

## 仓库结构

```text
packages/fl-melody/   三工具 MCP server
packages/fl-v0/       MIDI + 钢琴卷帘桥接（控制器、pyscript、utils）
packages/dsh-bundle/  DSH profile 补丁、icon、locale
.dsh/skills/          fl-melody 工作流与风格指导
scripts/              setup、deploy_controller、doctor、melody_smoke、OCR 辅助
docs/                 架构与 v0 范围/验证记录
assets/               banner 与演示图
archive/              暂缓的内核和旧文档（gitignored）
```

## 致谢

FL 侧桥接基于 [karl-andres/fl-studio-mcp](https://github.com/karl-andres/fl-studio-mcp)
（MIT）。

## 许可证

MIT——见 [LICENSE](LICENSE)。
