# 🏷systemd（systemctl）开机自启 + 守护进程完整教程

Linux 现在主流发行版（CentOS 7+/Rocky/Ubuntu/Debian）基本都使用 `systemd` 管理服务。

相比 `nohup`、`screen`、`tmux`：

-   支持开机自动启动
    
-   进程崩溃自动重启
    
-   日志统一管理
    
-   支持依赖管理
    
-   可查看运行状态
    
-   更适合长期运行服务
    

非常适合：

-   Node.js
    
-   Go
    
-   Python
    
-   Java
    
-   Docker
    
-   Claude Code / OpenCLI / Hapi Hub
    
-   AI 服务
    
-   Web 服务
    

---

# 一、systemd 核心概念

systemd 的服务文件叫：

```bash
xxx.service
```

通常放在：

```bash
/lib/systemd/system/
```

或者（推荐自定义服务）：

```bash
/etc/systemd/system/
```

推荐：

```bash
/etc/systemd/system/
```

因为：

-   不会被系统升级覆盖
    
-   更适合自己维护
    

---

# 二、最基础的 service 文件

创建：

```bash
vim /etc/systemd/system/demo.service
```

内容：

```ini
[Unit]
Description=demo service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/app/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

# 三、service 文件详解

---

## 1\. [Unit]

定义服务说明和依赖。

### Description

服务描述。

```ini
Description=demo service
```

查看状态时会显示。

---

## 2\. [Service]

核心配置。

---

### Type=simple

最常用。

```ini
Type=simple
```

表示：

-   启动后立即认为服务已运行
    
-   适用于：
    
    -   Node.js
        
    -   Go
        
    -   Python
        
    -   Java
        
    -   shell
        

---

### ExecStart

真正执行的命令。

```ini
ExecStart=/usr/bin/node app.js
```

注意：

-   必须写绝对路径
    
-   不能依赖 shell 环境
    

错误示例：

```ini
ExecStart=node app.js
```

因为 systemd 找不到 node。

---

### Restart

守护进程核心配置。

```ini
Restart=on-failure
```

含义：

| 配置  | 说明  |
| --- | --- |
| no  | 不自动重启 |
| always | 永远重启 |
| on-failure | 异常退出才重启（推荐） |

推荐：

```ini
Restart=on-failure
```

---

### RestartSec

重启等待时间。

```ini
RestartSec=5
```

避免疯狂重启。

---

### User

指定运行用户。

```ini
User=root
```

生产环境建议：

```ini
User=www
```

避免 root。

---

### WorkingDirectory

工作目录。

```ini
WorkingDirectory=/opt/app
```

很多 Node 项目必须配置。

---

### Environment

环境变量。

```ini
Environment="NODE_ENV=production"
Environment="PORT=3000"
```

Node/NVM 经常要配置 PATH。

---

# 四、Node.js + NVM 特别注意

很多人会遇到：

```bash
systemctl 启动失败
找不到 node
找不到 npm
```

因为：

systemd 不会加载：

```bash
.bashrc
.zshrc
.profile
```

所以：

NVM 环境失效。

---

## 正确做法

显式配置：

```ini
Environment="PATH=/root/.nvm/versions/node/v20.0.0/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="NVM_DIR=/root/.nvm"
```

并且：

```ini
ExecStart=/root/.nvm/versions/node/v20.0.0/bin/node app.js
```

必须使用绝对路径。

---

# 五、你的 Hapi Hub 配置（推荐版）

你的配置可以优化成：

```ini
[Unit]
Description=hapi hub
After=network.target

[Service]
Type=simple

User=root
WorkingDirectory=/root

ExecStart=/root/.nvm/versions/node/v16.20.2/bin/hapi hub

Environment="PATH=/root/.nvm/versions/node/v16.20.2/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NVM_DIR=/root/.nvm"

Restart=on-failure
RestartSec=5

LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

---

# 六、systemctl 常用命令

---

## 1\. 重新加载配置

修改 service 后必须执行：

```bash
systemctl daemon-reload
```

---

## 2\. 启动服务

```bash
systemctl start hapi
```

---

## 3\. 停止服务

```bash
systemctl stop hapi
```

---

## 4\. 重启服务

```bash
systemctl restart hapi
```

---

## 5\. 查看状态

```bash
systemctl status hapi
```

会显示：

-   是否运行
    
-   PID
    
-   启动日志
    
-   错误信息
    

---

## 6\. 设置开机自启

```bash
systemctl enable hapi
```

本质：

创建软链接到：

```bash
multi-user.target.wants
```

---

## 7\. 取消开机自启

```bash
systemctl disable hapi
```

---

## 8\. 查看是否开机启动

```bash
systemctl is-enabled hapi
```

---

# 七、查看日志（非常重要）

systemd 日志统一进入：

```bash
journalctl
```

---

## 查看服务日志

```bash
journalctl -u hapi
```

---

## 实时查看日志

类似：

```bash
tail -f
```

命令：

```bash
journalctl -u hapi -f
```

---

## 查看最近 100 行

```bash
journalctl -u hapi -n 100
```

---

## 查看本次启动日志

```bash
journalctl -u hapi -b
```

---

# 八、常见问题排查

---

## 1\. Exec format error

通常：

-   路径错误
    
-   文件没执行权限
    

检查：

```bash
which node
which hapi
```

---

## 2\. 服务秒退

查看：

```bash
systemctl status hapi
journalctl -u hapi -n 100
```

---

## 3\. systemctl 找不到 node

本质：

```bash
PATH 不存在
```

解决：

```ini
Environment="PATH=..."
```

---

## 4\. 服务疯狂重启

增加：

```ini
RestartSec=5
```

---

## 5\. 修改 service 不生效

忘记：

```bash
systemctl daemon-reload
```

---

# 九、推荐的生产配置

---

## Node.js 服务模板

```ini
[Unit]
Description=node app
After=network.target

[Service]
Type=simple

User=www
WorkingDirectory=/opt/app

ExecStart=/usr/bin/node server.js

Restart=on-failure
RestartSec=5

Environment="NODE_ENV=production"

LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

---

# 十、systemd vs nohup

| 功能  | systemd | nohup |
| --- | --- | --- |
| 开机启动 | 支持  | 不支持 |
| 崩溃重启 | 支持  | 不支持 |
| 日志管理 | 强   | 弱   |
| 状态查看 | 强   | 无   |
| 资源限制 | 支持  | 不支持 |
| 生产环境 | 推荐  | 不推荐 |

---

# 十一、推荐最佳实践

---

## 1\. service 文件放：

```bash
/etc/systemd/system/
```

---

## 2\. 永远使用绝对路径

不要：

```bash
node
npm
python
```

要：

```bash
/usr/bin/node
```

---

## 3\. 加 RestartSec

避免死循环。

---

## 4\. 使用普通用户运行

不要长期 root。

---

## 5\. 使用 journalctl 管理日志

不要自己写：

```bash
nohup.out
```

---

# 十二、完整部署流程（推荐）

---

## 1\. 创建 service

```bash
vim /etc/systemd/system/hapi.service
```

---

## 2\. 重载配置

```bash
systemctl daemon-reload
```

---

## 3\. 启动

```bash
systemctl start hapi
```

---

## 4\. 查看状态

```bash
systemctl status hapi
```

---

## 5\. 查看日志

```bash
journalctl -u hapi -f
```

---

## 6\. 设置开机启动

```bash
systemctl enable hapi
```

---

# 十三、查看所有服务

```bash
systemctl list-units --type=service
```

---

# 十四、查看开机启动服务

```bash
systemctl list-unit-files --type=service | grep enabled
```

---

# 十五、删除服务

---

## 停止

```bash
systemctl stop hapi
```

---

## 禁用开机启动

```bash
systemctl disable hapi
```

---

## 删除 service 文件

```bash
rm -f /etc/systemd/system/hapi.service
```

---

## 重载配置

```bash
systemctl daemon-reload
```

---

# 十六、适合长期运行的场景

systemd 非常适合：

-   AI Agent
    
-   Claude Code 中转
    
-   Hapi Hub
    
-   Open WebUI
    
-   Next.js
    
-   Golang API
    
-   Python FastAPI
    
-   Java Spring Boot
    
-   Redis/MySQL 外围服务
    
-   定时任务守护
    

---

# 十七、总结

核心就三步：

```bash
1. 写 service
2. systemctl enable
3. journalctl 看日志
```

生产核心配置：

```ini
Restart=on-failure
RestartSec=5
WorkingDirectory=
Environment=
```

Node.js + NVM：

一定要：

```ini
Environment="PATH=..."
```

否则 90% 会启动失败。

🏷