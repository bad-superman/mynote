# Espanso 安装与使用

## 背景

Espanso 是 macOS 上的文本展开工具。在任意输入框打一个短触发词，当前位置会换成保存好的模板。Cursor、Codex、Claude 共用同一份模板，不依赖各家自己的 slash command。

官方安装说明：<https://espanso.org/docs/install/mac/>

这台 Mac 的配置根目录是：

```text
/Users/roy/Library/Application Support/espanso/
├── config/default.yml    # 怎么展开：快捷键、粘贴方式
└── match/base.yml        # 展开什么：触发词和模板正文
```

`config/default.yml` 已经存在。模板不写在这个文件里。

## 结论

- 用 Homebrew 安装：`brew install espanso`。装完后应用在 `/Applications`。
- 行为配置只放 `config/default.yml`。触发词和正文只放 `match/base.yml`。
- 多行模板加 `force_clipboard: true`，整段一次粘贴。终端里的 Claude、Codex 不会把每个换行当成发送。
- 模板很多时，用 Option+Space 打开搜索条，选中后填进当前输入框。
- `espanso service register` 是 Linux 的 systemd 注册命令，macOS 不用。

## 核心步骤

支持 macOS 10.13 及以上，Intel 和 Apple Silicon 都可以。

Homebrew：

```bash
brew install espanso
```

如果以前用过旧 tap，先去掉再装：

```bash
brew untap federico-terzi/espanso
brew untap espanso/espanso
```

也可以从官网下载 Universal 磁盘映像，把应用拖进 `/Applications`。

打开 Espanso。菜单栏出现图标后就可以用。系统弹出授权时，到「系统设置 → 隐私与安全性 → 辅助功能」允许 Espanso。触发词完全不生效时，再打开「输入监听」。

内置测试：在文本框输入 `:espanso`，应展开成 `Hi there!`。

新增模板时编辑 `match/base.yml`。文件不存在就新建：

```yaml
matches:
  - trigger: ":review"
    force_clipboard: true
    replace: |
      先看当前改动，按严重程度列出必须改的问题。
      每条写清文件和原因，不要改代码。

  - trigger: ":commit"
    force_clipboard: true
    replace: "用一句中文写提交说明，说明为什么改，不要罗列文件名。"
```

保存后默认会自动重新加载。没有生效再执行：

```bash
espanso restart
```

终端里找不到 `espanso` 时，把命令加进 PATH：

```bash
espanso env-path register
```

`config/default.yml` 只在要改行为时动。搜索条快捷键的官方默认值是 `ALT+SPACE`，在 Mac 上就是 Option+Space：

```yaml
search_shortcut: ALT+SPACE
```

触发词用平时不会打出来的写法，官方示例就是 `:espanso`。光标停在目标输入框里输入触发词，模板会填在那里，后面还可以继续补这次的具体要求。

## 常见坑

- 把模板写进 `config/default.yml` 不会生效。正文只放 `match/` 目录。
- macOS 自带的「文本替换」在 Cursor 和终端里经常不展开。跨工具填充用 Espanso。
- 多行内容如果逐键输入，终端里的换行可能被当成发送。多行条目加上 `force_clipboard: true`。
- 密码框里 macOS Secure Input 会挡住展开。菜单栏图标异常时，先关掉密码管理器或浏览器里的密码插件，或点菜单栏里的 SecureInput auto-fix。
- 辅助功能权限授给了旧的签名时，触发词会失效，搜索条仍可能可用。从辅助功能和输入监听里删掉 Espanso，退出全部 Espanso 进程后再打开，重新授权。

## 验证

1. 菜单栏有 Espanso 图标。
2. 文本框输入 `:espanso`，出现 `Hi there!`。
3. 输入自己添加的触发词，例如 `:review`，正文出现在光标处。
4. 同一触发词在 Cursor 输入框和终端里的 Claude 或 Codex 都能展开。

命令可用时：

```bash
espanso status
```

## 回退

暂停使用：退出菜单栏里的 Espanso，或执行 `espanso stop`。已写入的模板文件还在。

只删某一条模板：从 `match/base.yml` 去掉对应的 `trigger` 条目，然后 `espanso restart`。

完整卸掉 Homebrew 安装：

```bash
espanso stop
brew uninstall espanso
```

磁盘映像安装的应用直接从 `/Applications` 移除。配置目录 `/Users/roy/Library/Application Support/espanso/` 会留下，不需要保留时再手动删除。
