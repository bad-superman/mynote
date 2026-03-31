# 📘 Go Module 私有仓库 & 多级路径问题总结

## 一、问题背景

在使用 Go Modules 时，引入私有仓库依赖：

```go
require code.youfi.com/infra/centrifugal/centrifuge v0.0.1
```

但执行：

```bash
go mod download
```

报错：

```text
reading ... at revision ...:
git ls-remote https://code.youfi.com/infra/centrifugal.git
```

👉 实际仓库却是：

```text
code.youfi.com/infra/centrifugal/centrifuge.git
```

---

## 二、核心问题本质

### ❗ 1. Go Module 解析规则

Go 会将 module path 拆分为：

```text
module path = repo root + 子目录（可选）
```

并尝试推断 Git 仓库位置：

```text
code.youfi.com/infra/centrifugal/centrifuge
↓
推断 repo：
1. infra/centrifugal.git   ❗（优先尝试）
2. 不会优先尝试 centrifugal/centrifuge.git
```

👉 导致：

```text
仓库路径推断错误 → clone 失败
```

---

### ❗ 2. 关键认知

> Go 先“找仓库”，再“用 git 拉代码”

| 阶段  | 行为  |
| --- | --- |
| ① 解析 module path | 推断 repo 路径 ❗ |
| ② 调用 git | SSH / HTTPS |
| ③ 下载代码 | 权限控制 |

👉 你当前失败在 **第 ① 步**

---

### ❗ 3. SSH / HTTPS 不影响该问题

```text
错误原因：repo 推断失败 ❌
不是：协议问题 ❌
```

---

## 三、为什么旧路径可以用？

旧路径：

```text
code.nexita.net/inno/youfi/server/centrifugal/centrifuge
```

👉 能正常使用的原因：

### ✅ 服务端返回 go-import meta

```html
<meta name="go-import"
      content="code.nexita.net/... git ssh://git@xxx/.../centrifuge.git">
```

👉 作用：

```text
告诉 Go：不要猜仓库路径，直接用这里
```

---

### ❌ 新域名没有该能力

```text
code.youfi.com
```

👉 没有 go-import meta → Go 开始猜 → 猜错

---

## 四、问题分类总结

| 问题类型 | 是否当前问题 |
| --- | --- |
| go.mod 语法错误 | ❌（已解决） |
| SSH 权限问题 | ❌   |
| 仓库不存在 | ❌   |
| ❗ module path 与 repo 不匹配 | ✅ 根因 |
| ❗ 缺少 go-import 支持 | ✅ 根因 |

---

## 五、解决方案

---

### ✅ 方案一：改 Module Path（推荐）

#### ✔ 原则：

```text
module path == 仓库路径
```

#### ✔ 示例：

```bash
repo:   code.youfi.com/infra/centrifugal-protocol.git
module: code.youfi.com/infra/centrifugal-protocol
```

#### ✔ 优点：

-   最简单
    
-   最稳定
    
-   无需额外设施
    

---

### ✅ 方案二：Mono-repo（支持多级路径）

#### ✔ 结构：

```text
infra/centrifugal.git
 ├── go.mod
 └── centrifuge/
     └── go.mod
```

#### ✔ 使用：

```go
require code.youfi.com/infra/centrifugal/centrifuge v0.0.1
```

---

### ✅ 方案三：go-import 网关（推荐企业级）

#### ✔ 原理：

通过 HTTP 返回：

```html
<meta name="go-import" content="xxx git ssh://xxx.git">
```

👉 告诉 Go repo 真实位置

---

#### ✔ 实现方式

### 1️⃣ GitLab Pages（静态方案）

-   每个路径一个 `index.html`
    
-   手动维护
    

👉 适合小规模

---

### 2️⃣ Nginx 动态网关（推荐）

```nginx
location ~ ^/(.*)$ {
    if ($arg_go-get = "1") {
        return 200 '<meta name="go-import" content="$host/$1 git ssh://git@$host/$1.git">';
    }
}
```

👉 优点：

-   自动支持所有路径
    
-   无需维护
    
-   企业级方案
    

---

### ⚠️ 方案四：replace（仅临时）

```go
replace xxx => /local/path
```

👉 仅用于：

-   本地开发
    
-   调试
    

❌ 不适合 CI / 生产

---

## 六、私有仓库标准配置

### ✅ 1. GOPRIVATE

```bash
go env -w GOPRIVATE=code.youfi.com
```

---

### ✅ 2. git 使用 SSH

```bash
git config --global url."ssh://git@code.youfi.com/".insteadOf "https://code.youfi.com/"
```

---

## 七、最佳实践（强烈建议）

---

### 🔥 1. 一仓一 Module（推荐）

```text
infra/centrifugal-protocol.git
infra/order-service.git
infra/match-engine.git
```

---

### 🔥 2. Module 路径必须与 repo 对齐

```go
module code.youfi.com/infra/xxx
```

---

### 🔥 3. 避免这种结构（高风险）

```text
infra/centrifugal/protocol.git ❌
```

---

### 🔥 4. 企业级推荐架构

```text
                ┌──────────────┐
                │ go command   │
                └──────┬───────┘
                       │
               ?go-get=1
                       │
        ┌──────────────▼──────────────┐
        │ go-import 网关（Nginx）      │
        └──────────────┬──────────────┘
                       │
              ssh://git@repo.git
                       │
                ┌──────▼──────┐
                │ GitLab Repo │
                └─────────────┘
```

---

## 八、一句话总结

> ❗ Go module 的核心不是“怎么拉代码”，而是“怎么找到仓库”
> 
> 👉 找错仓库，协议再对也没用

---