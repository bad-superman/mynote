# Go Modules 依赖管理

## 一、核心概念

| 概念  | 说明  |
| --- | --- |
| **go.mod** | 当前模块的“身份证”：模块路径、Go 版本、直接依赖及版本、replace/exclude。 |
| **go.sum** | 记录依赖（含间接）的校验和，用于校验下载内容是否被篡改。 |
| **模块路径 (module path)** | 如 `github.com/foo/bar`、`code.athh.cc/xxx`，全局唯一，一般对应可下载的仓库。 |
| **版本** | 语义化版本 `v1.2.3` 或伪版本 `v0.0.0-20240101120000-abcdef`。 |

---

## 二、依赖管理整体流程（六步）

```text
读 go.mod → 解析依赖图 → 决定拉取方式 → 拉取/缓存 → 校验 → 得到 build list → 编译
```

1.  **读 go.mod**：确定当前模块、直接依赖、replace/exclude。
    
2.  **解析依赖图**：对每个依赖读其 go.mod，递归得到整棵依赖树；replace 会改变“从哪取、取谁”。
    
3.  **决定拉取方式**：根据 GOPROXY / GONOPROXY（或 GOPRIVATE）决定走代理还是直连。
    
4.  **拉取与缓存**：下载到 `$GOMODCACHE`，或使用 replace 的本地目录。
    
5.  **校验**：根据 GOSUMDB / GONOSUMDB（或 GOPRIVATE）决定是否查 sumdb，并用 go.sum 校验。
    
6.  **build list**：得到参与编译的模块列表，再交给编译器。
    

---

## 三、各步骤详解

### 1\. 读 go.mod

-   从当前目录向上找 go.mod，确定**根模块**。
    
-   **require**：直接依赖及版本。
    
-   **replace**：
    
    -   `A => B v0.0.1`：用 B 的某版本替代 A。
        
    -   `A => ../local`：用本地目录替代 A。
        
-   **exclude**：排除某版本。
    

### 2\. 解析依赖图

-   对每个依赖，需要其 **go.mod**（来自缓存、代理或本地 replace）。
    
-   规则：
    
    -   先看 **replace**：若 A 被 replace，只解析替换目标（B 或本地目录）。
        
    -   否则按 **GOPROXY/GONOPROXY** 拉取模块的 .mod（和源码）。
        
-   约束：**require 的路径必须与依赖库里** `module` **行一致**，否则报<br>`module declares its path as ... but was required as ...`。
    

### 3\. 决定拉取方式（GOPROXY / GONOPROXY）

| 环境变量 | 作用  |
| --- | --- |
| **GOPROXY** | 代理列表，如 `https://goproxy.cn,direct`。请求顺序：代理 → 下一个 → … → direct 直连。 |
| **GONOPROXY** | glob 列表。**匹配的模块**拉取时**不走代理**，直连模块所在域名。 |

只设 GONOPROXY 时，**拉取**可直连，但 **sumdb 查询**仍可能走代理（见下）。

### 4\. 拉取与缓存

-   默认缓存目录：`$GOPATH/pkg/mod` 或 `$GOMODCACHE`。
    
-   replace 到本地目录时，不下载 zip，直接使用该目录的 go.mod 与源码。
    

### 5\. 校验（GOSUMDB / GONOSUMDB）

| 环境变量 | 作用  |
| --- | --- |
| **GOSUMDB** | 默认 `sum.golang.org`，用于查“某模块某版本”的官方校验和；请求常经 GOPROXY（如 `goproxy.cn/sumdb/sum.golang.org/...`）。 |
| **GONOSUMDB** | glob 列表。**匹配的模块**不查 sumdb，只依赖 **go.sum**；没有则首次下载后写入。 |

私有模块在 sum.golang.org 无记录，代理会 404，所以私有库要设 **GONOSUMDB**（或直接用 GOPRIVATE）。

### 6\. build list 与编译

-   上述步骤得到完整依赖图的一个线性列表（build list）。
    
-   编译时根据 import 在 build list 中找对应模块（含 replace 结果），用缓存或本地目录参与编译。
    

---

## 四、GOPRIVATE：私有库一条变量搞定

**GOPRIVATE** = 对匹配的模块**同时**“不走代理 + 不查 sumdb”。

```bash
export GOPRIVATE="*.athh.cc,*.nexita.net,*.inke.cn"
```

| 行为  | 效果  |
| --- | --- |
| 不走 GOPROXY | 拉取时直连私有域名，不经过 goproxy.cn 等。 |
| 不查 GOSUMDB | 不向 sum.golang.org 查校验和，只用 go.sum，避免 404。 |

与 GONOPROXY / GONOSUMDB 的关系：

-   **GOPRIVATE** 会**同时**影响“是否走代理”和“是否查 sumdb”。
    
-   若同时设置了 GOPRIVATE 与 GONOPROXY/GONOSUMDB，Go 会把 GOPRIVATE 的模式合并进去。
    
-   实践上：私有域名只设 **GOPRIVATE** 即可，不必再单独配 GONOPROXY/GONOSUMDB。
    

---

## 五、环境变量小结

| 变量  | 控制什么 | 典型值 |
| --- | --- | --- |
| **GOPROXY** | 拉取模块时使用的代理链 | `https://goproxy.cn,direct` |
| **GONOPROXY** | 哪些模块拉取时**不走**代理 | `*.athh.cc,code.nexita.net` |
| **GOSUMDB** | 校验和数据库地址 | 默认 `sum.golang.org` |
| **GONOSUMDB** | 哪些模块**不查** sumdb | `*.athh.cc,*.nexita.net` |
| **GOPRIVATE** | 哪些模块**既**不走代理**也**不查 sumdb | `*.athh.cc,*.nexita.net` |

---

## 六、常用命令在流程中的位置

| 命令  | 在流程里做什么 |
| --- | --- |
| **go mod tidy** | 根据代码 import 更新 require，删多余依赖，重算 go.sum；会触发解析→拉取→校验。 |
| **go get** | 增/改依赖版本，更新 go.mod 与 go.sum。 |
| **go build / go test** | 按 go.mod+go.sum 解析依赖，用缓存或 replace 目录编译。 |
| **go mod download** | 只做解析+拉取+校验，不编译，用于预填缓存。 |
| **go mod verify** | 用 go.sum 校验缓存中的包是否与记录一致。 |

---

## 七、实践注意点

1.  **“module declares its path as A but was required as B”**
    
    -   require/replace 用的路径必须和依赖库 go.mod 里 **module** 一致。
        
    -   要么 require 和 replace 都改成 A，要么该库的 go.mod 改成 B（一般不改库更好）。
        
2.  **私有库 404 / connection refused**
    
    -   设 **GOPRIVATE**（或 GONOPROXY + GONOSUMDB），保证私有路径不走代理、不查 sumdb。
        
    -   GONOPROXY 里不要写错域名（如 `code..nexita.net` 应为 `code.nexita.net` 或 `*.nexita.net`）。
        
3.  **replace 的两种用法**
    
    -   `replace A => B v0.0.1`：用 B 的版本替代 A；B 的 go.mod 里 **module** 必须是 B。
        
    -   `replace A => ../local`：用本地目录替代 A；**本地目录的 go.mod 里 module 必须写 A**（和 require 一致）。
        
4.  **本地开发多仓库**
    
    -   用 `replace code.athh.cc/.../centrifuge => ../centrifuge` 等指向本地目录。
        
    -   require 用与各仓库 go.mod 一致的路径（如统一用 `code.athh.cc/...`），避免路径不一致报错。
        

---

## 八、流程简图

```text
go.mod (require/replace)
       ↓
  解析依赖图（递归读各模块 go.mod，replace 优先）
       ↓
  GOPROXY / GONOPROXY（或 GOPRIVATE）→ 决定从代理还是直连拉
       ↓
  拉取 → 缓存 或 使用 replace 本地目录
       ↓
  GOSUMDB / GONOSUMDB（或 GOPRIVATE）→ 决定是否查 sumdb，go.sum 校验
       ↓
  build list → 编译
```