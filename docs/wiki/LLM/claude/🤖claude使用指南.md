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
#!/bin/bash
# start_claude_worktree.sh
# 用法: ./start_claude_worktree.sh <新分支名> [基准分支]
# 示例: ./start_claude_worktree.sh feature-login develop

# 检查参数
if [ -z "$1" ]; then
            echo "请提供新分支名"
                echo "用法: $0 <新分支名> [基准分支]"
                    exit 1
fi

NEW_BRANCH="$1"
BASE_BRANCH="${2:-develop}"  # 默认基准分支 develop
WORKTREE_DIR="../$NEW_BRANCH"

echo "Fetching latest changes from origin..."
git fetch origin

echo "Creating worktree: $WORKTREE_DIR from $BASE_BRANCH..."
git worktree add -b "$NEW_BRANCH" "$WORKTREE_DIR" "origin/$BASE_BRANCH"

echo "Entering worktree..."
cd "$WORKTREE_DIR" || exit 1

echo "Starting Claude..."
claude
```