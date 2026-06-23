# hapi 升级问题排查总结（npm / nvm / prefix）

这次问题本质上是：

```text
hapi CLI 的显示版本
与 npm package version 不一致
```

同时过程中还暴露出了：\*\*nvm + npm prefix\*\* 混用的环境问题。

---

# 一、问题现象

执行：

```bash
npm install -g @twsxtd/hapi
```

后：

```bash
npm list -g @twsxtd/hapi
```

显示：

```text
@twsxtd/hapi@0.20.2
```

但：

```bash
hapi --version
```

输出：

```text
hapi version: 0.17.4
```

看起来像：

```text
升级失败
```

---

# 二、实际原因

最终确认：

```text
升级其实已经成功
```

真正的问题是：

```text
hapi --version 输出的版本号没有更新
```

即：

| 项目  | 实际版本 |
| --- | --- |
| npm wrapper | 0.20.2 |
| binary package | 0.20.2 |
| version 输出 | 0.17.4（旧值） |

---

# 三、排查过程

---

## 1 检查 npm 安装版本

执行：

```bash
npm list -g @twsxtd/hapi
```

结果：

```text
@twsxtd/hapi@0.20.2
```

说明：

```text
npm 包已经升级
```

---

## 2 检查实际执行路径

执行：

```bash
which hapi
```

结果：

```text
~/.nvm/versions/node/v25.7.0/bin/hapi
```

说明：

```text
当前 shell 执行的是 nvm 环境中的 hapi
```

---

## 3 检查 binary symlink

执行：

```bash
ls -l ~/.nvm/versions/node/v25.7.0/bin/hapi
```

发现：

```text
hapi -> ../lib/node_modules/@twsxtd/hapi/bin/hapi.cjs
```

说明：

```text
CLI 实际是 npm wrapper
```

---

## 4 检查 wrapper 源码

执行：

```bash
cat ~/.nvm/versions/node/v25.7.0/bin/hapi | head
```

发现：

```js
const RELEASE_URL = 'https://github.com/tiann/hapi/releases';
```

说明：

```text
真正运行的是下载的 binary
npm 包只是 wrapper
```

---

## 5 检查 shell cache

执行：

```bash
hash -r
```

重新执行：

```bash
hapi --version
```

无变化。

说明：

```text
不是 shell cache 问题
```

---

## 6 检查 binary package

执行：

```bash
grep -R "0.20.2" ~/.nvm/versions/node/v25.7.0/lib/node_modules/@twsxtd/hapi
```

发现：

```text
@twsxtd/hapi-linux-x64/package.json
version: 0.20.2
```

说明：

```text
真正的 Linux binary package 已经升级到 0.20.2
```

---

## 7 最终确认

执行：

```bash
strings <binary> | grep 0.17
```

发现 binary 内部仍包含：

```text
0.17.4
```

最终确认：

```text
hapi --version 输出逻辑存在 bug
```

而不是升级失败。

---

# 四、同时发现的 npm 环境问题

过程中还发现：

```bash
npm ls -g --depth=0
```

显示：

```text
/home/roy/.npm-global/lib
```

但：

```bash
which hapi
```

却走：

```text
~/.nvm/versions/node/v25.7.0/bin/hapi
```

说明：

```text
同时存在两套 npm global 环境
```

---

# 五、问题根源

用户同时使用了：

| 组件  | 路径  |
| --- | --- |
| nvm | ~/.nvm |
| 自定义 npm prefix | ~/.npm-global |

属于：

```text
nvm + npm prefix 混用
```

这会导致：

-   全局包安装位置混乱
    
-   PATH 优先级冲突
    
-   CLI 版本不一致
    
-   升级后不生效
    
-   不同 Node 版本共享 global package
    

---

# 六、最终修复方案

---

## 1 删除 npm prefix

执行：

```bash
npm config delete prefix
```

恢复 npm 默认行为。

---

## 2 重载 shell

执行：

```bash
exec $SHELL
```

---

## 3 验证 prefix

执行：

```bash
npm config get prefix
```

应输出：

```text
~/.nvm/versions/node/v25.7.0
```

---

## 4 清理 PATH

检查：

```bash
echo $PATH
```

删除：

```text
~/.npm-global/bin
```

相关配置。

---

## 5 重新安装全局工具

执行：

```bash
npm install -g @twsxtd/hapi
npm install -g pnpm
npm install -g @openai/codex
```

---

# 七、最终结论

这次问题：

```text
不是 hapi 没升级
```

而是：

```text
hapi --version 输出错误版本号
```

同时：

```text
暴露了 npm prefix 与 nvm 混用问题
```

最终：

-   hapi 实际已经升级成功
    
-   npm 环境也完成了规范化整理。