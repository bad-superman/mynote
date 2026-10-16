# REA 安装与使用

## 背景

REA 是 npm 包 `rea-agents`。它给编程助手加一个本地 MCP 服务，以及调查流程技能 `reverse-engineer-anything`。适合分析已发布的二进制、安装包、固件、Electron/JavaScript 或浏览器目标。完整源码仓库的普通阅读不要用它。

官方来源只有这三处：

- npm 包 `rea-agents`
- <https://github.com/morluto/rea>
- <https://rea.tools>

2026-10-16 在这台 Mac 上把 `6.5.0` 接到 Cursor。Node 是 `v26.8.1`，npm 是 `11.19.0`。

## 结论

- 用 `setup --client cursor` 安装。`npx` 前面的 `-y` 只同意下载包，不批准改配置。
- 这次只改了 Cursor。检测到的 Claude Code、Codex、Hermes 没有写入。
- MCP 命令钉死安装时的版本：`npx -y rea-agents@6.5.0 mcp`。
- 技能装在 `~/.agents/skills/reverse-engineer-anything`，版本 42，207 个工具。
- 原有 `~/.cursor/mcp.json` 条目保留，修改前的副本在 `~/.cursor/mcp.json.rea.backup`。
- Hopper、Ghidra、IDA、JADX 这次没有装。静态 JavaScript 检查不需要它们；原生深度分析需要其中一台引擎。

## 核心步骤

Node 要求：`^22.19.0 || ^24.11.0 || >=26.0.0`。

先看计划，确认路径后再执行：

```bash
npx -y rea-agents@latest setup --client cursor --dry-run --json
npx -y rea-agents@latest setup --client cursor --yes --json
```

`--dry-run` 只打印计划，退出码 0，状态是 `planned`。`--yes` 必须带明确范围；没有 `--client` 时，它只刷新已经存在的 REA 注册，不会给每个检测到的客户端都装一遍。

这次计划实际写了两处：

| 动作 | 路径 |
| --- | --- |
| 更新 MCP | `~/.cursor/mcp.json`，备份 `~/.cursor/mcp.json.rea.backup` |
| 安装技能 | `~/.agents/skills/reverse-engineer-anything` |

写入后重新加载 Cursor 的 MCP。doctor 不能证明当前会话已经连上 REA。

装好之后：

- 调查已发布产物时，让助手按 `reverse-engineer-anything` 走。工具已经在当前会话里就直接分析，不要每次先跑 setup。
- 看 `.exe`、`.dylib`、`.so`、Mach-O，需要 Hopper、Ghidra、IDA 里的一个。
- 看 APK 或 JAR，需要自己提供 JADX。REA 不下载 Ghidra、IDA、JADX。
- 没有 MCP 时，JavaScript 或 ASAR 可以直接走 CLI：

```bash
npx -y rea-agents@6.5.0 analyze-javascript-application /absolute/path/to/app --json
```

可选引擎只在需要时配置：

| 引擎 | 用途 | 接入 |
| --- | --- | --- |
| Hopper | macOS 上的商业反汇编器，REA 的交互式原生引擎 | `setup` 会单独询问；非交互还要 `--install-hopper` |
| Ghidra | 免费反汇编和反编译 | 自备 12.1.x，设置 `GHIDRA_INSTALL_DIR`，JDK 21 |
| IDA | 商业反汇编器 | 自备 IDA MCP，设置 `REA_IDA_MCP_CONFIG` |
| JADX | Java / Android 反编译 | 自备 `jadx-headless-mcp` 0.7.1 JAR，设置 `REA_JADX_MCP_JAR` |

刷新已有注册时，再跑一遍 `setup`，先看 dry-run。`rea update` 只更新全局安装的 npm 包，不会改已经写进 Cursor 的 MCP 命令。

## 常见坑

- 第一次 `npx` 会下载 Frida 预编译包。这台机器花了数分钟，期间看起来像卡住。
- 非交互终端里 setup 不会弹出确认。先 `--dry-run`，再 `--client cursor --yes`。
- MCP 命令钉死 `rea-agents@6.5.0`。以后 `@latest` 变了，旧注册不会自己升级。
- 技能目录或它管理的 `references` 目录如果是符号链接，setup 会拒绝安装技能。这次装到了 `~/.agents/skills`，没有碰到 `~/.cursor/skills` 里的链接。
- 不要下载第三方的 Windows 单文件包。
- Hopper 有自己的许可证。演示版有限制，而且要单独批准。
- 只重载 MCP 不够时，看客户端的 MCP 启动错误，不要反复 setup。

## 验证

```bash
npx -y rea-agents@6.5.0 doctor --client cursor --skill --json
```

2026-10-16 的结果：

- 范围内 `healthy` 为 true。检查项是 Node `26.8.1`、Cursor 注册、技能身份。
- `environment_healthy` 为 false。Hopper、Ghidra、IDA、JADX 都未配置，这是预期结果。
- Cursor 注册状态 `aligned`，命令是 `npx -y rea-agents@6.5.0 mcp`。
- 技能状态 `aligned`，`installed_version` 42，`installed_tool_count` 207。
- `~/.cursor/mcp.json` 里同时有 `rea` 和原来的 `sourceinsight`。

当前会话里还要能看到 REA 工具，才算连接完成。

## 回退

`uninstall` 只删除 REA 自己的客户端注册和技能文件。Hopper、Node、证据文件和其他技能会留下。`--purge-data` 再额外删除 REA 缓存和状态。

```bash
npx -y rea-agents@6.5.0 uninstall --help
npx -y rea-agents@6.5.0 uninstall
```

如果只想恢复 Cursor 配置，使用 `~/.cursor/mcp.json.rea.backup`。恢复前确认这份备份之后没有别人改过 `mcp.json`。setup 不会覆盖第一份 `.rea.backup`。
