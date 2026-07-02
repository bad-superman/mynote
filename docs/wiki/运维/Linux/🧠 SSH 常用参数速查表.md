# 🧠 SSH 常用参数速查表

## 1\. 基础连接类

| 参数  | 作用  | 示例  |
| --- | --- | --- |
| `-p` | 指定端口 | `ssh -p 2222 user@host` |
| `-l` | 指定用户名 | `ssh -l root host` |
| `-i` | 指定私钥 | `ssh -i ~/.ssh/id_rsa user@host` |
| `-v` | 调试模式 | `ssh -v user@host` |
| `-vvv` | 更详细调试 | `ssh -vvv user@host` |

---

## 2\. 执行命令类

| 参数  | 作用  | 示例  |
| --- | --- | --- |
| `-t` | 强制分配 TTY | `ssh -t host "top"` |
| `-T` | 不分配 TTY | `ssh -T git@github.com` |
| `-q` | 安静模式 | `ssh -q host` |
| `-o` | 指定配置参数 | `ssh -o StrictHostKeyChecking=no host` |

---

## 3\. 隧道 / 端口转发（重点）

| 参数  | 类型  | 作用  | 示例  |
| --- | --- | --- | --- |
| `-L` | 本地转发 | 本地 → 远程 | `ssh -L 8080:127.0.0.1:80 host` |
| `-R` | 远程转发 | 远程 → 本地 | `ssh -R 9000:localhost:3000 host` |
| `-D` | 动态代理 | SOCKS5 代理 | `ssh -D 1080 host` |
| `-N` | 无命令 | 只建立隧道 | `ssh -N -L ... host` |

---

## 4\. 后台运行 / 守护

| 参数  | 作用  | 示例  |
| --- | --- | --- |
| `-f` | 进入后台运行 | `ssh -f -N -L ... host` |
| `-n` | stdin 重定向 | 常配合后台使用 |

👉 常见组合：

```bash
ssh -f -N -L 3307:127.0.0.1:3306 user@host
```

---

## 5\. 安全与认证

| 参数  | 作用  | 示例  |
| --- | --- | --- |
| `-o StrictHostKeyChecking=no` | 跳过 host key 检查 | 自动化脚本常用 |
| `-o UserKnownHostsFile=/dev/null` | 不记录 known\_hosts | CI 环境 |
| `-o PasswordAuthentication=no` | 禁用密码登录 | 强制密钥登录 |
| `-A` | 代理 SSH key | 跳板机场景 |

---

## 6\. 连接控制

| 参数  | 作用  | 示例  |
| --- | --- | --- |
| `-o ConnectTimeout=5` | 连接超时 | `ssh -o ConnectTimeout=5 host` |
| `-o ServerAliveInterval=60` | 心跳保持 | 防止断线 |
| `-o ServerAliveCountMax=3` | 心跳失败次数 | 稳定长连接 |

---

## 7\. 压缩与性能

| 参数  | 作用  | 示例  |
| --- | --- | --- |
| `-C` | 启用压缩 | 低带宽优化 |
| `-o Compression=yes` | 等价写法 | 同上  |

---

## 8\. 文件传输相关（SCP/SFTP）

| 工具  | 参数  | 作用  |
| --- | --- | --- |
| `scp` | `-r` | 递归复制 |
| `scp` | `-P` | 指定端口 |
| `sftp` | `-b` | 批处理模式 |