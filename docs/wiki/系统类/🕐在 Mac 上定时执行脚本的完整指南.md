# 🕐在 Mac 上定时执行脚本的完整指南

在 macOS 上定时执行脚本有多种方法，以下是三种主要方式及其详细说明：

## 1\. 使用 launchd（推荐方法）

launchd 是 macOS 的原生守护进程管理系统，比 cron 更强大且支持更多功能。

### 创建 plist 文件

1.  在 `~/Library/LaunchAgents/` 目录创建 plist 文件：
    

```bash
nano ~/Library/LaunchAgents/com.user.myscript.plist
```

2.  添加以下内容（每日中午12点执行）：
    

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.myscript</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>  <!-- 使用 zsh 或 bash -->
        <string>/Users/YourUsername/path/to/your_script.sh</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>12</integer>  <!-- 中午12点 -->
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/tmp/myscript.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/myscript_error.log</string>
</dict>
</plist>
```

### 加载并启用服务

```bash
# 加载服务
launchctl load ~/Library/LaunchAgents/com.user.myscript.plist

# 立即启动一次（可选）
launchctl start com.user.myscript

# 检查状态
launchctl list | grep com.user.myscript
```

### 常用时间设置

| 间隔  | 设置示例 |
| --- | --- |
| 每天  | `<key>StartCalendarInterval</key>` + Hour/Minute |
| 每周  | 添加 `<key>Weekday</key>` (1=周日,7=周六) |
| 每月  | 添加 `<key>Day</key>` |
| 每分钟 | 使用 `<key>StartInterval</key><integer>60</integer>` |

## 2\. 使用 crontab（传统方法）

虽然 launchd 是推荐方式，但 cron 仍然可用：

1.  编辑 crontab：
    

```bash
crontab -e
```

2.  添加定时任务（每天中午12点执行）：
    

```bash
0 12 * * * /bin/zsh /Users/YourUsername/path/to/your_script.sh >> /tmp/cron.log 2>&1
```

3.  保存并退出（在 nano 中按 Ctrl+O, Enter, Ctrl+X）
    

### cron 时间格式

```text
* * * * * 命令
│ │ │ │ │
│ │ │ │ └── 星期几 (0 - 6) (0为星期日)
│ │ │ └──── 月份 (1 - 12)
│ │ └────── 日 (1 - 31)
│ └──────── 小时 (0 - 23)
└────────── 分钟 (0 - 59)
```

### 调试单个任务

```text
# 1. 手动模拟 cron 环境
env -i /bin/bash -c "cd / && /path/to/script.sh"

# 2. 使用 cron 调试模式
# 创建测试 crontab
echo "* * * * * echo '测试: \$(date)' >> /tmp/cron_test.log" | crontab -

# 3. 检查一分钟后的结果
sleep 61
cat /tmp/cron_test.log
```

## 3\. 使用 Automator 应用程序（图形界面）

适合不需要复杂调度的简单任务：

1.  打开 Automator（应用程序 → 实用工具）
    
2.  选择 "应用程序" 类型
    
3.  添加 "运行 Shell 脚本" 操作
    
4.  输入脚本内容
    
5.  保存为应用程序（如：MyScript.app）
    
6.  在系统设置中设置定时：
    

-   打开 "系统设置" → "通用" → "登录项"
    
-   添加 MyScript.app
    
-   点击 "i" 图标设置执行时间
    

## 脚本调试技巧

1.  **测试脚本**：
    

```bash
# 直接运行测试
/bin/zsh /path/to/your_script.sh

# 检查输出
echo $?
```

2.  **查看日志**：
    

```bash
# launchd 日志
tail -f /tmp/myscript.log
tail -f /tmp/myscript_error.log

# cron 日志
tail -f /tmp/cron.log
```

3.  **环境变量问题**： 在脚本开头添加环境变量：
    

```bash
#!/bin/zsh

# 加载用户环境
source ~/.zshrc

# 脚本内容...
```

## 高级技巧

### 网络依赖检测

```bash
#!/bin/zsh

# 等待网络连接
while ! ping -c 1 -W 5 8.8.8.8 &> /dev/null; do
    sleep 10
done

# 执行网络相关操作
curl -O https://example.com/file
```

### 防止脚本重复运行

```bash
#!/bin/zsh

LOCK_FILE="/tmp/myscript.lock"

if [ -e "$LOCK_FILE" ]; then
    echo "Script is already running. Exiting."
    exit 1
fi

# 创建锁文件
touch "$LOCK_FILE"

# 主脚本内容...

# 清理锁文件
rm -f "$LOCK_FILE"
```

### 邮件通知

```bash
#!/bin/zsh

# 执行脚本
/path/to/your_script.sh

# 检查退出状态
if [ $? -ne 0 ]; then
    # 发送错误通知
    echo "Script failed!" | mail -s "Script Error" your@email.com
fi
```

## 常见问题解决

1.  **脚本不执行**：
    

-   检查文件权限：`chmod +x /path/to/your_script.sh`
    
-   检查脚本路径是否正确
    
-   验证环境变量：在脚本中添加 `env > /tmp/script_env.log`
    

2.  **launchd 任务不运行**：
    

```bash
# 重新加载
launchctl unload ~/Library/LaunchAgents/com.user.myscript.plist
launchctl load ~/Library/LaunchAgents/com.user.myscript.plist

# 查看系统日志
log show --predicate 'process == "launchd"' --last 24h
```

3.  **cron 任务不运行**：
    

```bash
# 检查 cron 服务状态
launchctl list | grep cron

# 查看系统日志
grep cron /var/log/system.log
```

## 安全注意事项

1.  避免在脚本中使用明文密码
    
2.  对敏感操作使用权限控制
    
3.  定期审查定时任务
    
4.  使用专用用户账户执行特权操作
    

选择合适的方法取决于您的需求：

-   需要复杂调度 → 使用 launchd
    
-   简单定时任务 → 使用 crontab
    
-   图形界面偏好 → 使用 Automator