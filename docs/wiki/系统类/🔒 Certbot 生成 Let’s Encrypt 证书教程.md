# 🔒 Certbot 生成 Let’s Encrypt 证书教程

## 📌 前置条件

-   一台 Linux 服务器（Ubuntu/Debian/CentOS/RHEL 均可）
    
-   域名已解析到服务器公网 IP
    
-   服务器开放 **80（HTTP）端口**用于域名验证
    
-   安装对应 Web 服务器（Nginx 或 Apache）或打算用 **Standalone 模式**
    

---

## 1️⃣ 安装 Certbot

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install certbot -y
# 安装 Nginx 插件（可选）
sudo apt install python3-certbot-nginx -y
# 安装 Apache 插件（可选）
sudo apt install python3-certbot-apache -y
```

### CentOS / RHEL

```bash
sudo yum install epel-release -y
sudo yum install certbot python3-certbot-nginx -y
sudo yum install python3-certbot-apache -y
```

---

## 2️⃣ 生成证书

Certbot 支持多种验证模式：

### 方式 A：Webroot 模式（适合已有 Web 服务）

```bash
sudo certbot certonly \
  --webroot -w /var/www/html \
  -d example.com -d www.example.com
```

参数说明：

-   `--webroot -w /var/www/html`：网站根目录，用于放置验证文件
    
-   `-d example.com -d www.example.com`：域名列表，可多个
    
-   执行后会生成证书，默认路径：
    
    -   `/etc/letsencrypt/live/example.com/fullchain.pem`（完整证书）
        
    -   `/etc/letsencrypt/live/example.com/privkey.pem`（私钥）
        

---

### 方式 B：Standalone 模式（无 Web 服务或测试用）

```bash
sudo certbot certonly --standalone -d example.com -d www.example.com
```

-   Certbot 会启动临时 HTTP 服务监听 80 端口完成验证
    
-   成功后证书同样存放在 `/etc/letsencrypt/live/` 下
    

---

### 方式 C：自动配置 Nginx / Apache（推荐生产环境）

#### Nginx

```bash
sudo certbot --nginx -d example.com -d www.example.com
```

-   Certbot 会自动修改 Nginx 配置，加入 HTTPS 配置
    
-   证书自动生效，且生成自动续期任务
    

#### Apache

```bash
sudo certbot --apache -d example.com -d www.example.com
```

-   功能与 Nginx 类似，会自动启用 HTTPS
    

---

## 3️⃣ 测试证书续期

Let’s Encrypt 证书有效期 90 天，需要自动续期。Certbot 安装后会默认创建系统定时任务（cron 或 systemd timer）

手动测试续期命令：

```bash
sudo certbot renew --dry-run
```

-   输出 `Congratulations, all renewals succeeded.` 表示续期功能正常
    
-   建议每天或每周检查一次
    

---

## 4️⃣ 使用证书（示例）

假设你用 Teleport / Nginx / Apache：

### Teleport 配置

```yaml
https_key_file: /etc/letsencrypt/live/example.com/privkey.pem
https_cert_file: /etc/letsencrypt/live/example.com/fullchain.pem
```

### Nginx 配置（HTTPS）

```nginx
server {
    listen 443 ssl;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3080;
    }
}
```

---

## 5️⃣ 常用命令总结

| 命令  | 说明  |
| --- | --- |
| `sudo certbot certonly --standalone -d example.com` | 单独生成证书 |
| `sudo certbot --nginx -d example.com` | 自动 Nginx 配置并生成证书 |
| `sudo certbot renew --dry-run` | 测试续期 |
| `/etc/letsencrypt/live/example.com/fullchain.pem` | 证书路径 |
| `/etc/letsencrypt/live/example.com/privkey.pem` | 私钥路径 |

---

# ✅ 用 Certbot + Cloudflare 插件申请泛域名证书

> 泛域名证书（`*.example.com`）**必须使用 DNS 验证**，HTTP 验证无效。

---

## 🔹 1. 创建 Cloudflare API Token

Cloudflare 后台 → **My Profile → API Tokens → Create Token**

权限：

```text
Zone → DNS → Edit
Zone → Zone → Read
```

Zone 资源选择你的域名。

---

## 🔹 2. 写 API 凭证文件

```bash
mkdir -p /root/.secrets
nano /root/.secrets/cloudflare.ini
```

内容：

```text
dns_cloudflare_api_token = 你的token
```

权限必须：

```bash
chmod 600 /root/.secrets/cloudflare.ini
```

---

## 🔹 3. 申请泛域名证书

```bash
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
  -d example.com \
  -d "*.example.com"
```

成功后证书路径：

```text
/etc/letsencrypt/live/example.com/
├── fullchain.pem
└── privkey.pem
```

---

## 🔹 4. 自动续期（默认已开启）

```bash
certbot renew --dry-run
```

---

## 🔹 5. 续期后自动重启服务（如 Teleport）

```bash
nano /etc/letsencrypt/renewal-hooks/deploy/restart-service.sh
```

```bash
#!/bin/bash
systemctl restart teleport
```

```bash
chmod +x /etc/letsencrypt/renewal-hooks/deploy/restart-service.sh
```

---

## 🚨 CentOS pip 版本过低导致安装失败（遇到的坑）

报错本质：

```text
ModuleNotFoundError: setuptools_rust
```

原因：

| 问题  | 说明  |
| --- | --- |
| CentOS Python 太老 | 3.6 / 2.7 |
| cryptography 现在依赖 Rust | 需要新编译环境 |
| pip 在源码编译 | 直接炸 |

👉 **原因是系统太旧。**

---

### 🏆 解决方案：用 Snap 版 Certbot（官方推荐）

绕过系统 Python 依赖地狱。

---

1.  🔹 安装 snapd
    

```bash
yum install snapd -y
systemctl enable --now snapd.socket
ln -s /var/lib/snapd/snap /snap
```

重新登录 shell。

---

2.  🔹 安装官方 certbot
    

```bash
snap install core
snap refresh core

snap install --classic certbot
ln -s /snap/bin/certbot /usr/bin/certbot
```

---

3.  🔹 安装 Cloudflare 插件
    

```bash
snap set certbot trust-plugin-with-root=ok
snap install certbot-dns-cloudflare
```

验证：

```bash
certbot plugins | grep cloudflare
```

---

4.  🔹 再执行申请命令（同上）
    

```bash
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
  -d example.com \
  -d "*.example.com"
```

---

## 🎯 总结对比

| 场景  | 做法  |
| --- | --- |
| 申请泛域名证书 | 必须 DNS-01（Cloudflare 插件） |
| pip 安装报 cryptography / rust 错 | 别折腾，直接 snap |
| 生产环境稳定方案 | **snap certbot + Cloudflare DNS** |