# tmux 是一个多终端管理工具

## 安装

```markdown
# mac
brew install tmux
```

## 相关概念

-   **session** tmux 创建一个终端管理器，每创建一个 session 就是一个会话。会话会保持运行，可以随时断开再恢复。
    
-   **window** 一个 session 里面可以创建多个 window。
    
-   **pane** 一个 window 可以分割成多个 pane。
    
-   **prefix** 默认快捷键是 `Ctrl + b`，用于进入 tmux 命令模式，方便进行 session/window/pane 操作。
    

---

## 会话管理（Session）

### 创建 session

```bash
tmux
```

### 创建指定名称 session

```bash
tmux new -s name
```

### 查看 session 列表

```bash
tmux ls
```

### 进入已有 session

```bash
tmux a -t name
# 或
tmux a
```

### 退出 session（detach）

```bash
tmux detach
```

或：

```text
prefix + d
```

### 删除 session

```bash
tmux kill-session -t name
```

（当只有一个 window 时也可以直接 `exit` 退出）

---

## 窗口管理（Window）

### 创建 window

```text
prefix + c
```

### 切换 window

```text
prefix + 1 / 2 / 3   （按编号切换）
prefix + p           （上一个 window）
prefix + n           （下一个 window）
prefix + w           （列出所有 window 进行选择）
```

### 重命名 window

```text
prefix + ,
```

### 关闭 window

```text
prefix + &
```

---

## 面板管理（Pane）

### 创建 pane

```text
水平分割：prefix + %
垂直分割：prefix + "
```

### 切换 pane

```text
prefix + 方向键
prefix + o   （循环切换）
```

### 退出 pane

```bash
exit
```

### 放大/恢复 pane

```text
prefix + z
```

---

## .tmux.conf 配置

```bash
# 重新设置 prefix
set-option -g prefix C-a
unbind C-b
bind-key C-a send-prefix

# 使用 Ctrl + 方向键切换 pane
bind -n C-Left  select-pane -L
bind -n C-Right select-pane -R
bind -n C-Up    select-pane -U
bind -n C-Down  select-pane -D

# 使用 Shift + 方向键切换 window
bind -n S-Left  previous-window
bind -n S-Right next-window

# split window
bind-key h split-window -h
bind-key v split-window -v
```

---

## 重新加载配置

```bash
tmux source ~/.tmux.conf
```