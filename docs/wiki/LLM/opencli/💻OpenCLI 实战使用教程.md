# 一、OpenCLI 是什么

OpenCLI 本质是：

> **把“网站 / App / API”变成命令行工具（CLI）**

比如：

```bash
opencli bilibili hot
opencli zhihu hot
opencli twitter search "AI"
```

它的核心能力是：

-   把网站变成 CLI 命令
    
-   复用你浏览器登录态（不用再登录）
    
-   支持 JSON / table / md 输出
    
-   可做自动化脚本 / AI agent 工具
    

---

# 二、安装 OpenCLI

## 1\. Node 安装（推荐）

```bash
npm install -g @jackwener/opencli
```

安装后验证：

```bash
opencli --help
```

---

## 2\. 检查环境（很重要）

```bash
opencli doctor
```

用于检查：

-   Chrome bridge 是否正常
    
-   浏览器插件是否安装
    
-   daemon 是否启动
    

---

# 三、最基础使用

## 1\. 查看所有可用站点

```bash
opencli list
```

👉 会列出支持的站点（如 bilibili / zhihu / github 等）

---

## 2\. 调用网站命令

### 示例 1：B站热榜

```bash
opencli bilibili hot
```

### 示例 2：知乎热榜

```bash
opencli zhihu hot
```

### 示例 3：HackerNews（无需浏览器）

```bash
opencli hackernews top --limit 5
```

---

# 四、输出格式控制（非常重要）

OpenCLI 支持多种输出格式：

## 1\. JSON（最适合脚本 / AI）

```bash
opencli bilibili hot -f json
```

👉 推荐默认用这个（结构稳定）

---

## 2\. 表格（人类阅读）

```bash
opencli bilibili hot -f table
```

---

## 3\. Markdown

```bash
opencli bilibili hot -f md
```

---

## 4\. CSV（数据分析）

```bash
opencli bilibili hot -f csv
```

---

# 五、浏览器能力（核心功能）

OpenCLI 很关键的一点是：

> 可以操作“已登录的浏览器”

---

## 1\. 安装浏览器插件

打开：

```text
chrome://extensions
```

开启：

-   开发者模式
    
-   加载 unpacked 插件（OpenCLI extension）
    

---

## 2\. 检查连接

```bash
opencli doctor
```

---

## 3\. 浏览器控制（自动化）

### 打开网页

```bash
opencli browser my open https://www.zhihu.com
```

---

### 获取页面状态

```bash
opencli browser my state
```

---

### 抽取内容

```bash
opencli browser my extract "title"
```

---

### 执行 JS

```bash
opencli browser my eval "document.title"
```

---

# 六、session（非常重要）

OpenCLI 的浏览器操作是“会话制”的：

```bash
opencli browser my-session open https://example.com
```

之后所有操作都基于这个 session：

```bash
opencli browser my-session state
opencli browser my-session extract "main"
```

关闭 session：

```bash
opencli browser my-session close
```

---

# 七、CLI 自动化能力（重点）

OpenCLI 的真正价值在于：

## 👉 把网站变成脚本工具

例如：

### 1\. 批量抓取 B站热榜

```bash
opencli bilibili hot -f json > hot.json
```

---

### 2\. AI 管道处理

```bash
opencli zhihu hot -f json | jq '.data'
```

---

### 3\. 自动化工作流

```bash
opencli hackernews top -f json \
| jq '.[] | .title'
```

---

# 八、Tab 自动补全（提升效率）

## Zsh

```bash
echo 'eval "$(opencli completion zsh)"' >> ~/.zshrc
```

## Bash

```bash
echo 'eval "$(opencli completion bash)"' >> ~/.bashrc
```

---

# 九、插件扩展能力

OpenCLI 可以扩展：

## 1\. 本地 CLI

```bash
~/.opencli/clis/<site>/
```

---

## 2\. 插件模式

```bash
opencli plugin create my-tool
```

---

## 3\. 外部工具封装

```yaml
~/.opencli/external-clis.yaml
```

# 远程控制

```text
# ssh 
ssh -N -R 19825:127.0.0.1:19825 remote
```