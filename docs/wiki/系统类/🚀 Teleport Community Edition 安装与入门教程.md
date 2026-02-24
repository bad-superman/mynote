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

## 🎯 总结

这套流程可以帮助你：

✅ 安装并启动 Teleport Community Edition ✅ 配置 HTTPS 和证书（支持 Let’s Encrypt） ✅ 创建用户并启用 MFA ✅ 使用 Web UI 和 CLI 访问受保护的服务器

---