# 🚀 Teleport Community Edition 安装与入门教程

## 📌 前置条件

在开始之前，请准备好以下环境：

✔️ 一台 **Linux 服务器**（支持 SSH 登录、运行软件、开 443 端口） ✔️ 如果要在公网部署：一个 **域名**（比如 `teleport.example.com`） ✔️ 一个 **DNS A 记录** 指向服务器 IP ✔️ 一个 **多因素认证（MFA）应用**（如 Authy / Google Authenticator / 1Password）

> 对于在本地 Docker 容器测试，可省略域名和 DNS 相关设置。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 🧠 Teleport 架构简介

Teleport Community Edition 主要包含：

-   **Auth Service**：证书授权与认证服务
    
-   **Proxy Service**：入口代理，处理用户请求
    
-   **SSH Service**：提供 SSH 访问功能
    

这些组件合并运行在一个实例中即可完成最基本的部署。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 🪄 一、配置 DNS（仅公网部署）

为你的域名添加 DNS A 记录指向服务器 IP：

| 子域名 | 用途  |
| --- | --- |
| `teleport.example.com` | 用于 Web UI 和用户访问 |
| `*.teleport.example.com` | 用于应用访问的动态子域名 |

如果在 Docker 容器本地测试，可跳过此步骤。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 🛠 二、在 Linux 主机上安装 Teleport

### 1\. 下载并安装 Teleport 二进制

在服务器终端运行：

```bash
curl https://cdn.teleport.dev/install.sh | bash -s 18.6.1
```

这将自动下载安装脚本并将 Teleport 安装到系统中。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

### 2\. 生成配置文件

根据你的部署类型生成配置：

#### 公网部署（使用 Let’s Encrypt 自动证书）

```bash
sudo teleport configure -o file \
  --acme \
  --acme-email=you@example.com \
  --cluster-name=teleport.example.com
```

-   `--acme` 表示使用 Let’s Encrypt 自动获取 HTTPS 证书
    
-   `--cluster-name` 填你的域名
    
-   `--acme-email` 填一个邮箱用于证书通知
    
-   需要打开 **443 HTTPS** 端口供 Let’s Encrypt 验证和用户访问 ([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))
    

#### 本地 Docker / 私有网络测试

如果是在 Docker 或无公开域名环境下，可以生成自签证书配置：

```bash
teleport configure -o file \
  --cluster-name=localhost \
  --public-addr=localhost:443 \
  --cert-file=/path/to/cert.pem \
  --key-file=/path/to/key.pem
```

📌 注意：本地测试需提前准备好自签证书或用 Docker 环境提供证书文件。([Teleport](https://goteleport.com/docs/get-started/deploy-community/ "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## ▶️ 三、启动 Teleport

### 启动服务

1.  启用 Systemd 系统服务：
    

```bash
sudo systemctl enable teleport
sudo systemctl start teleport
```

2.  或直接用命令启动（适合容器或开发场景）：
    

```bash
teleport start --config="/etc/teleport.yaml"
```

---

## 🌐 四、访问 Teleport 控制台

打开浏览器访问：

-   如果是公网部署： `https://teleport.example.com`
    
-   如果是在 Docker 本地测试： `https://localhost:3080`
    

你应该能看到 Teleport 的 **欢迎界面**。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 👤 五、创建用户 & 配置 MFA

1.  在服务器上创建管理员用户：
    

```bash
sudo tctl users add teleport-admin --roles=editor,access --logins=root,ubuntu,ec2-user
```

-   `teleport-admin` 是用户名
    
-   `--roles` 定义权限角色
    
-   `--logins` 指定用户可登录的 Linux 系统账号 ([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))
    

2.  上述命令会输出一个注册链接，比如：
    

```text
https://teleport.example.com/web/invite/abcd1234...
```

打开该链接设置用户密码并扫描 MFA 二维码。

📌 用户设置完成后，Teleport 会强制开启 MFA。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 💻 六、通过命令行登录

1.  在本地终端安装 Teleport 客户端 `tsh`（各平台支持）：
    

```bash
# 示例 macOS
curl -O https://cdn.teleport.dev/teleport-18.6.1.pkg
```

2.  登录到 Teleport 集群：
    

```bash
tsh login --proxy=teleport.example.com --user=teleport-admin
```

登录后，你将获得短期证书用于后续访问。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 🖥 七、通过 Teleport 访问服务器

成功登录后，你可以通过 Web UI 访问服务器终端：

👉 点击服务器节点，然后选择 **Connect** 或使用 `tsh` 远程连接：

```bash
tsh ssh root@<server-name>
```

这样你就能通过 Teleport 进行 SSH 访问。([Teleport](https://goteleport.com/docs/get-started/deploy-community/?utm_source=chatgpt.com "Step 1 - Deploy Teleport Community Edition | Teleport"))

---

## 🌐 八、添加 Web App Resource

Teleport 的 Application Service 可以把内网 Web 服务注册到集群中，再通过 Teleport Web UI 访问。

例如，将运行在 Teleport Agent 所在机器 `9000` 端口的服务注册为 `xianyuassistant`：

```yaml
version: v3

teleport:
  nodename: app-agent
  data_dir: /var/lib/teleport
  proxy_server: teleport.example.com:443
  join_params:
    token_name: <包含 node、app 角色的新令牌>
    method: token

auth_service:
  enabled: "no"

proxy_service:
  enabled: "no"

ssh_service:
  enabled: "yes"

app_service:
  enabled: "yes"
  apps:
    - name: xianyuassistant
      uri: http://localhost:9000/
      public_addr: ""
      insecure_skip_verify: false
```

> `localhost:9000` 指的是 **Teleport Application Service 所在机器**，不是访问者的电脑。Teleport 只负责代理，后端 Web 服务仍需单独启动。

修改配置后重启 Agent。Linux 使用：

```bash
sudo systemctl restart teleport
```

如果 macOS 使用 launchd，服务标签为 `Teleport Service`：

```bash
sudo launchctl kickstart -k 'system/Teleport Service'
```

### App Resource 显示但访问时报 Access Denied

可能看到以下提示：

```text
Access Denied
Unable to serve application requests. Please try again.
If the issue persists, verify if the Application Services are connected to Teleport.
```

此提示不一定是用户 RBAC 权限问题。先检查 Agent 日志：

```bash
sudo journalctl -u teleport -f

# macOS launchd 安装方式
tail -f /var/log/teleport-stderr.log
```

如果日志包含：

```text
Instance identity is missing required system roles, missing_roles:[App]
Instance identity does not include required system role, role:App
token expired or not found
```

说明现有 Agent 身份只有 `Node` 角色。虽然配置中启用了 `app_service`，但 Agent 无法获取 `App` 角色证书，因此不会向集群提供有效的 Application Service 心跳。

在 Auth Server 上生成一个包含 `node` 和 `app` 角色的新加入令牌：

```bash
sudo tctl tokens add --type=node,app --ttl=1h
```

将新令牌写入配置：

```yaml
teleport:
  join_params:
    token_name: <新令牌>
    method: token
```

再次重启 Teleport。成功日志应包含：

```text
additional_system_roles:[Node App]
All applications successfully started
```

同时检查后端端口：

```bash
nc -vz 127.0.0.1 9000
curl -I http://127.0.0.1:9000/
```

排查顺序：

1. 后端服务是否监听配置中的端口。
2. Teleport Agent 是否加载了最新配置。
3. Agent 身份是否包含 `App` 角色。
4. 加入令牌是否存在、未过期，并允许 `app` 角色。
5. 日志是否出现 `All applications successfully started`。

如果使用独立配置启动第二个 Teleport 进程，应为它设置独立的 `data_dir`。多个进程共用同一个目录可能产生 `debug.sock: address already in use` 等冲突。

---

## 👑 九、SSH 登录时 root 用户不再显示

Teleport 升级后，Web UI 或 Teleport Connect 可能不再在 SSH Username 下拉框中显示 `root`。这通常不是 Teleport 取消了 root 登录，而是新版 UI 只显示当前用户对目标服务器实际拥有权限的 SSH 登录名。

SSH 登录名由用户当前生效角色的 `spec.allow.logins` 决定。要让 UI 显示 `root`，可以在 Web UI 中创建专用角色：

1. 进入 **Zero Trust Access → Roles**。
2. 点击 **Create New Role**。
3. 切换到 **YAML editor**。
4. 创建以下角色。

```yaml
kind: role
version: v8
metadata:
  name: ssh-root
spec:
  allow:
    logins:
      - root
    node_labels:
      "*": "*"
```

5. 进入 **Zero Trust Access → Users**。
6. 找到用户并选择 **Options → Edit**。
7. 在 **User Roles** 中添加 `ssh-root`。
8. 完全退出当前集群并重新登录，以获取包含新角色的证书。

`node_labels: "*": "*"` 允许使用该角色访问所有节点。生产环境建议限制到明确标签：

```yaml
spec:
  allow:
    logins:
      - root
    node_labels:
      env: production
```

重新登录后，可直接验证：

```bash
tsh ssh root@<server-name>
```

### root 仍未显示时的检查项

检查用户所有角色中是否存在：

```yaml
spec:
  deny:
    logins:
      - root
```

`deny` 的优先级高于 `allow`，任意生效角色拒绝 `root` 都会使其不可用。

如果角色使用变量：

```yaml
allow:
  logins:
    - "{{internal.logins}}"
```

则用户 traits 中也需要包含 `root`：

```yaml
spec:
  traits:
    logins:
      - root
```

其他注意事项：

- SSO 用户应在身份提供商的组映射或 Teleport SSO connector 中授予 `ssh-root`，不要直接修改临时用户。
- 仅出现在可申请角色中的 `root`，在角色尚未申请并获批前不会显示。
- 如果使用 Agentless OpenSSH，Teleport RBAC 通过后仍需检查目标机的 `sshd_config`，例如 `PermitRootLogin` 是否禁用了 root。

---

## 🎯 总结

这套流程可以帮助你：

✅ 安装并启动 Teleport Community Edition ✅ 配置 HTTPS 和证书（支持 Let’s Encrypt） ✅ 创建用户并启用 MFA ✅ 使用 Web UI 和 CLI 访问受保护的服务器 ✅ 注册 Web App Resource 并排查 Application Service 连接问题 ✅ 恢复 SSH root 登录名

---
