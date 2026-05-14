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