# Docker 构建镜像调试笔记

## 问题清单与解决方案

### 1\. Dockerfile 多阶段构建结构错误

**问题：**

```text
ERROR: failed to build: failed to solve: circular dependency detected on stage: builder
```

**原因：**

-   Dockerfile 中 `ARG env` 声明了两次，且没有第二个 `FROM` 语句
    
-   `COPY --from=builder` 在 builder 阶段内部执行，导致循环依赖
    

**解决：**

```dockerfile
# 正确的多阶段结构
FROM ... AS builder
...

# 必须有第二个 FROM
FROM alpine:3.21
COPY --from=builder ...
```

---

### 2\. SSH 私钥问题

**问题 1：权限太开放**

```text
Permissions 0644 for 'id_rsa' are too open
```

**解决：**

```bash
chmod 600 id_rsa
```

**问题 2：私钥格式错误（双重 base64 编码）**

```text
Load key "/root/.ssh/id_rsa": error in libcrypto
```

**解决：**

-   使用正确格式的私钥文件
    
-   或者从 `~/.ssh/` 复制有效的密钥
    

**问题 3：缺少 known\_hosts**

```text
Host key verification failed
```

**解决：**

```dockerfile
RUN ssh-keyscan -H code.youfi.com >> ~/.ssh/known_hosts
```

---

### 3\. Git 私有仓库访问问题

**问题：**

```text
go: code.athh.cc/...: no secure protocol found for repository
```

**原因：**

-   Git URL 替换配置不完整
    
-   Go 模块无法通过 SSH 访问私有仓库
    

**解决：**

```dockerfile
RUN git config --global url."git@code.youfi.com:".insteadOf "https://code.youfi.com/" \
    && git config --global url."git@code.youfi.com:".insteadOf "https://code.youfi.com" \
    && git config --global url."ssh://git@code.youfi.com/".insteadOf "https://code.youfi.com/"
```

或者在 go.mod 中直接使用 SSH URL：

```go
replace code.athh.cc/... => git@code.youfi.com:infra/centrifugal/centrifuge.git v0.0.10
```

---

### 4\. Go 版本不匹配问题

**问题：**

```text
go: go.mod requires go >= 1.24.0 (running go 1.23.2)
```

**方案 A：降低 go.mod 版本（推荐）**

```go
// go.mod
go 1.23
```

**方案 B：使用 GOTOOLCHAIN 自动下载**

```dockerfile
ENV GOTOOLCHAIN=auto
```

**方案 C：使用与基础镜像匹配的 Go 版本**

-   基础镜像：Go 1.23
    
-   go.mod：go 1.23
    

---

### 5\. 二进制文件复制问题

**问题：**

```text
cp: cannot stat '/src/centrifugo': No such file or directory
```

**原因：**

-   `go build` 没有正确执行或输出路径不对
    
-   目标目录不存在
    

**解决：**

```dockerfile
# 1. 确保 go build 输出正确的文件名
RUN go build -o ${service}

# 2. 先创建目标目录再复制
RUN mkdir -p /app/bin /app/config \
    && cp /src/${service} /app/bin/ \
    && cp /src/config.yaml.${env} /app/config/config.yaml
```

---

### 6\. Docker 缓存优化

**问题：** 每次构建都重新下载 Go toolchain 和依赖

**优化方案：**

#### 6.1 缓存 Go toolchain

```dockerfile
# 先触发 toolchain 下载（这一层会被缓存）
ENV GOTOOLCHAIN=auto
WORKDIR /tmp
RUN go version

# 再复制代码
COPY . /src
WORKDIR /src
```

#### 6.2 缓存 Go 依赖（可选）

```dockerfile
# 先复制 go.mod/go.sum，下载依赖
COPY go.mod go.sum ./
RUN go mod download

# 再复制其余代码
COPY . .
```

---

## 调试技巧

### 1\. 添加调试输出

**查看目录内容：**

```dockerfile
RUN echo "=== Before build ===" \
    && ls -la /src \
    && echo "=== Checking config file ===" \
    && ls -la /src/config.yaml.* \
    && go build -v -o ${service} \
    && echo "=== After build ===" \
    && ls -la /src/${service}
```

**查看文件内容：**

```dockerfile
RUN cat /src/go.mod | head -20
```

**查看环境变量：**

```dockerfile
RUN echo "=== ENV ===" \
    && env | grep -E "^GO|^PATH"
```

---

### 2\. 测试 SSH 连接

**基础测试：**

```dockerfile
RUN ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 git@code.youfi.com 2>&1 || true
```

**预期输出：**

```text
Welcome to GitLab, @username!
```

**带密钥路径测试：**

```dockerfile
RUN ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes \
    -i ~/.ssh/id_rsa git@code.youfi.com 2>&1 || true
```

---

### 3\. 测试 Git 配置

**查看所有配置：**

```dockerfile
RUN git config --list
```

**查看 URL 替换规则：**

```dockerfile
RUN git config --list | grep insteadof
```

**预期输出：**

```text
url.git@code.youfi.com:.insteadof=https://code.youfi.com/
url.ssh://git@code.youfi.com/.insteadof=https://code.youfi.com/
```

---

### 4\. 测试 Git 访问

**测试仓库访问：**

```dockerfile
RUN GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" \
    git ls-remote git@code.youfi.com:infra/centrifugal/centrifuge.git 2>&1 || true
```

**预期输出：**

```text
<commit-hash>	HEAD
<commit-hash>	refs/heads/master
...
```

**测试克隆：**

```dockerfile
RUN GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no" \
    git clone git@code.youfi.com:infra/centrifugal/centrifuge.git /tmp/test-clone 2>&1 || true
```

---

### 5\. 调试 SSH 密钥

**检查密钥文件：**

```dockerfile
RUN ls -la ~/.ssh/ \
    && cat ~/.ssh/id_rsa | head -5
```

**检查密钥权限：**

```dockerfile
RUN stat -c "%a %n" ~/.ssh/id_rsa
```

**预期输出：**

```text
600 /root/.ssh/id_rsa
```

**手动测试密钥：**

```dockerfile
RUN chmod 600 ~/.ssh/id_rsa \
    && ssh-add -l 2>&1 || true
```

---

### 6\. 调试 Go 构建

**查看 Go 环境：**

```dockerfile
RUN go env
```

**查看 Go 版本：**

```dockerfile
RUN go version
```

**测试依赖下载：**

```dockerfile
RUN go mod download -x 2>&1 | head -50
```

**查看模块依赖树：**

```dockerfile
RUN go list -m all | head -30
```

**详细构建输出：**

```dockerfile
RUN go build -v -x -o ${service} 2>&1 | tail -50
```

---

### 7\. 分步调试 Dockerfile

把复杂的 RUN 命令拆分成多步，便于定位问题：

```dockerfile
# 第 1 步：测试配置文件存在
RUN test -f "/src/config.yaml.${env}" && echo "Config file exists"

# 第 2 步：测试 Git 配置
RUN git config --global url."git@code.youfi.com:".insteadOf "https://code.youfi.com/"

# 第 3 步：测试 SSH 密钥
RUN mkdir -p ~/.ssh && cat id_rsa > ~/.ssh/id_rsa && chmod 600 ~/.ssh/id_rsa

# 第 4 步：测试 SSH 连接
RUN ssh -o StrictHostKeyChecking=no git@code.youfi.com 2>&1 || true

# 第 5 步：测试 Go 构建
RUN go build -v -o ${service}
```

---

### 8\. 使用中间镜像调试

**构建到某一步然后进入容器：**

```bash
# 修改 Dockerfile，在问题步骤前添加 STOP
# 然后构建并进入容器手动调试
docker build -t debug-image .
docker run -it debug-image bash
```

**使用 docker build --target：**

```bash
# 构建到指定阶段
docker build --target builder -t builder-image .

# 进入容器
docker run -it builder-image bash
```

---

### 9\. 清理缓存重新构建

**完全清理缓存：**

```bash
docker builder prune -a -f
docker build --no-cache .
```

**查看构建缓存：**

```bash
docker buildx du
```

---

### 10\. 常见错误快速定位

| 错误信息 | 可能原因 | 调试命令 |
| --- | --- | --- |
| `checksum database disabled` | GOSUMDB=off 但需要验证 | `go env GOSUMDB` |
| `no secure protocol found` | Git URL 替换失败 | `git config --list \| grep insteadof` |
| `bad permissions` | SSH 密钥权限不对 | `stat -c "%a" ~/.ssh/id_rsa` |
| `not found` | 文件路径不对 | `ls -la /src/` |
| `exit code: 137` | OOM 内存不足 | 增加 Docker 内存限制 |

---

## 构建命令

```bash
# 首次构建（下载 toolchain 和依赖）
docker build --no-cache --build-arg service=centrifugo --build-arg env=test-sg-tx .

# 后续构建（使用缓存，速度快）
docker build --build-arg service=centrifugo --build-arg env=test-sg-tx .
```