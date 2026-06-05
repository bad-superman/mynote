## 常用命令

/init

初始化项目，保存到CLAUDE.md文件

/memory

实时添加记忆

/compact

压缩上下文

/clear

清空上下文

/btw

不阻断任务问问题

/add-dir

添加目录

## 快捷键

### 三种模式切换（Shift + Tab）

1.  Normal：询问是否应用修改
    
2.  Auto-accept：自动模式，自动接受所有编辑
    
3.  Plan：计划模式，只出方案，不修改文件
    

### 停止（Esc）

## Tmux配置

```text
# 支持 Claude Code 的通知、进度条、Shift+Enter
#set -g allow-passthrough on
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'

# 鼠标支持
set -g mouse on
```

## Worktree使用

命令

```text
cluade —worktree
cluade -w 
```

cluade默认使用git远程的HEAD作为\`基准分支\`

使用worktree最好配置git worktree使用

1.  使用git worktree指定基准分支创建工作分支
    
2.  切换到分支目录
    

```text
git fetch origin

git worktree add -b feature-login ../feature-login origin/develop

cd ../feature-login

claude
```

脚本

```text
#!/usr/bin/env bash
# start_claude_worktree.sh
#
# 用法:
#   ./start_claude_worktree.sh <新分支名> [基准分支]
#
# 示例:
#   ./start_claude_worktree.sh feature-login
#   ./start_claude_worktree.sh feature-login develop

#set -euo pipefail

if [ -z "${1:-}" ]; then
            echo "请提供新分支名"
                echo "用法: $0 <新分支名> [基准分支]"
                    exit 1
fi

NEW_BRANCH="$1"
BASE_BRANCH="${2:-}"

# 检查是否在 git 仓库中
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            echo "错误：当前目录不在 git 仓库中"
                exit 1
fi

# 获取 git 项目根目录和项目名
REPO_ROOT="$(git rev-parse --show-toplevel)"
PROJECT_NAME="$(basename "$REPO_ROOT")"

# 如果新分支名包含 /，用于目录名时替换成 -
SAFE_NEW_BRANCH="$(echo "$NEW_BRANCH" | sed 's#[/\\ ]#-#g')"

# worktree 目录：../项目名_新分支名
WORKTREE_DIR="$(dirname "$REPO_ROOT")/${PROJECT_NAME}_${SAFE_NEW_BRANCH}"

# 如果没有传基准分支，则使用当前分支
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(git branch --show-current)"
  if [ -z "$BASE_BRANCH" ]; then
    echo "错误：当前处于 detached HEAD 状态，请显式指定基准分支"
    echo "用法: $0 <新分支名> [基准分支]"
    exit 1
  fi

  BASE_REF="origin/$BASE_BRANCH"
else
  # 如果指定了基准分支，优先使用 origin/基准分支
  BASE_REF="origin/$BASE_BRANCH"
fi

# 检查新分支是否已存在
if git show-ref --verify --quiet "refs/heads/$NEW_BRANCH"; then
            echo "错误：分支已存在：$NEW_BRANCH"
                exit 1
fi

# 检查 worktree 目录是否已存在
if [ -e "$WORKTREE_DIR" ]; then
            echo "错误：worktree 目录已存在：$WORKTREE_DIR"
                exit 1
fi

echo "Fetching latest changes from origin..."
git fetch origin

# 如果指定的 origin/基准分支不存在，则回退到本地基准分支
if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
            BASE_REF="$BASE_BRANCH"
fi

echo "Creating worktree..."
echo "  project:  $PROJECT_NAME"
echo "  branch:   $NEW_BRANCH"
echo "  base:     $BASE_REF"
echo "  dir:      $WORKTREE_DIR"

git worktree add -b "$NEW_BRANCH" "$WORKTREE_DIR" "$BASE_REF"
# 设置 upstream 为远程同名分支（如果还不存在，第一次推送会创建）
git push -u origin "$NEW_BRANCH"

echo "Entering worktree..."
cd "$WORKTREE_DIR"

echo "Starting Claude..."
claude
```