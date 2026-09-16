# Hermes Kanban 使用与 issue-analysis 业务落地

## 背景

Hermes Kanban 适合把一个需要多步调查的工作拆成多个可恢复的任务。当前的 issue 分析需求包含：

- Issue 可能是详细描述，也可能是飞书项目链接；
- 必须关联服务名称和运行环境；
- 需要在 `~/dev` 下复用或 clone 项目代码；
- 需要用 CodeGraph 定位代码链路；
- 需要用 Nex 查询部署分支、提交、日志、监控和只读存储；
- 最后输出根因、影响范围、修复建议和验证方案。

如果这些工作全部交给一个 `issue-analyzer`，CodeGraph 输出、日志、数据库结果和反复查询会持续累积在同一个 Worker 上下文中。Kanban 的价值不是简单增加 Worker 数量，而是把调查过程切成有依赖关系的阶段，让每个阶段只保留完成自己职责所需的证据。

## 结论

推荐采用“短上下文 Worker + 持久化报告 + 结构化 handoff”的方式：

```text
issue-coordinator
        |
        +-- issue-intake
                |
                +-- code-investigator
                +-- runtime-investigator
                        ↓
                evidence-verifier
                        ↓
                issue-synthesizer
```

其中：

- `issue-intake` 只负责输入规范化；
- `code-investigator` 只负责代码和 CodeGraph；
- `runtime-investigator` 只负责 Nex 及必要的只读数据；
- `evidence-verifier` 只复核证据链；
- `issue-synthesizer` 只负责最终报告；
- `issue-coordinator` 负责拆分任务或在所有子任务完成后收口。

主对话和 Kanban Worker 通常是独立进程、独立会话，因此 Kanban Worker 的输出不会直接拼进主对话上下文。但单个 Worker 自己的上下文仍然可能变大，所以阶段隔离仍然必要。

## 一、Kanban 核心概念

### 1. Board

Board 是任务队列的隔离边界。当前 issue 分析使用：

```text
board: issue-analysis
database: ~/.hermes/kanban/boards/issue-analysis/kanban.db
workspace: /home/roy/dev
```

Board 级别的 `default_workdir` 用于给新任务提供项目工作目录。它不是仓库映射表，服务对应哪个仓库仍应由 Issue、项目配置或人工确认决定。

### 2. Task

常见状态：

```text
triage -> todo -> ready -> running -> review -> done
                                      |
                                      +-> blocked
```

- `triage`：输入还需要规范化或自动拆分；
- `todo`：等待父任务完成；
- `ready`：依赖满足，可以被 dispatcher 调度；
- `running`：Worker 正在执行；
- `review`：等待复核或人工审核；
- `blocked`：缺少权限、输入或外部条件；
- `done`：已完成并留下 handoff；
- `archived`：归档，不再参与调度。

### 3. Parent / Child

创建子任务时通过 `parents` 建立依赖：

```text
intake 完成
    -> code-investigator 和 runtime-investigator 同时进入 ready
    -> 两者都完成后，evidence-verifier 进入 ready
    -> verifier 完成后，issue-synthesizer 进入 ready
```

只连接真实的数据依赖。能独立查询的工作不要强行串行，否则会增加总耗时。

### 4. Workspace

| 类型 | 适用场景 | 生命周期 |
| --- | --- | --- |
| `scratch` | 临时处理、无需共享文件 | 完成后清理 |
| `dir:<path>` | 需要复用 `~/dev` 代码和跨阶段报告 | 持久保留 |
| `worktree` | 需要隔离分支进行代码修改 | 持久保留 |

Issue 分析默认只读，不应修改业务源码。当前流程使用 `dir:/home/roy/dev`，主要原因是不同阶段需要读取同一份报告和代码 checkout。若使用 `scratch`，必须通过 `kanban_complete(artifacts=[...])` 声明报告，否则任务完成后临时目录会被清理。

## 二、常用命令

### 1. 查看 Board 和调度器

```bash
hermes kanban boards list
hermes kanban boards show
hermes gateway status
```

网关内置 dispatcher 时，不需要单独启动一个 Kanban daemon。应避免同时运行两个 dispatcher，以免出现重复 claim 和并发调度。

### 2. 查看任务

```bash
hermes kanban --board issue-analysis list
hermes kanban --board issue-analysis list --json
hermes kanban --board issue-analysis stats
hermes kanban --board issue-analysis show t_xxxxxxxx --json
hermes kanban --board issue-analysis diagnostics --json
```

长时间运行时可以观察事件：

```bash
hermes kanban --board issue-analysis watch
```

### 3. 提交 Issue 分析任务

推荐让任务先进入 `triage`，让自动拆分器或协调器规范化输入：

```bash
hermes kanban --board issue-analysis create \
  "[qa][risk.risk.service] 收盘价报警频繁" \
  --assignee issue-coordinator \
  --triage \
  --workspace dir:/home/roy/dev \
  --body "$(cat <<'EOF'
## Issue
<详细描述或飞书项目 issue 链接>

## Service
risk.risk.service

## Environment
qa

## Time Window
2026-09-01 04:40:00 至 2026-09-01 05:00:00 (香港)

## Evidence
<trace id、request id、错误码、日志关键字或复现步骤>
EOF
)"
```

在支持 Hermes slash command 的飞书会话中，也可以提交：

```text
/kanban --board issue-analysis create "[qa][service] 简短现象" --assignee issue-coordinator --triage --body "..."
```

如果目标是“飞书发起，自动分析完成后回飞书”，创建任务后必须确认通知订阅。推荐使用 `notify+wake`，这样终态事件会唤醒 Gateway agent 读取报告并在原会话回复：

```bash
hermes kanban --board issue-analysis notify-list t_xxxxxxxx
hermes kanban --board issue-analysis notify-subscribe t_xxxxxxxx \
  --platform feishu \
  --chat-id oc_xxxxxxxx \
  --chat-type dm \
  --delivery-mode notify+wake
```

如果创建结果显示 `subscribed=false`，或者任务的 `session_id` 为空且没有订阅记录，就不能承诺自动回传报告。

### 4. 处理阻塞

阻塞原因应使用类型，不要只写“卡住了”：

```bash
hermes kanban --board issue-analysis block \
  t_xxxxxxxx \
  --kind needs_input \
  "缺少服务对应仓库地址和问题发生时间窗口"
```

常用类型：

- `needs_input`：缺少服务、环境、时间窗口、Issue 权限等输入；
- `capability`：缺少 Nex、飞书项目或仓库访问能力；
- `dependency`：等待其他任务完成；
- `transient`：临时网络或工具失败，可重试。

## 三、当前 issue-analysis 配置

当前相关配置位于 `~/.hermes/config.yaml`：

```yaml
kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 60
  failure_limit: 2
  orchestrator_profile: issue-coordinator
  default_assignee: issue-coordinator
  auto_decompose: true
  auto_decompose_per_tick: 1
  dispatch_stale_timeout_seconds: 14400
  max_in_progress_per_profile: 1
  auto_subscribe_on_create: true
  review_dispatch: false
```

配置含义：

- `orchestrator_profile`：拆分后的根任务由哪个 profile 继续处理；
- `default_assignee`：任务没有 assignee 时的兜底 profile；
- `auto_decompose`：是否自动处理 `triage` 任务；
- `auto_decompose_per_tick`：每次 dispatcher tick 最多拆分几个任务，当前为 1，用于限制辅助模型调用和突发 fan-out；
- `dispatch_stale_timeout_seconds`：4 小时没有有效进展时进入 stale 检查；
- `max_in_progress_per_profile`：同一 profile 同时最多运行 1 个 Worker；
- `auto_subscribe_on_create`：从持久会话创建任务时自动订阅终态事件；如果关闭，需要显式 `notify-subscribe`；
- `review_dispatch: false`：当前不自动派发独立 review Worker，证据复核通过显式阶段完成。

这里没有显式设置全局 `max_in_progress`，Hermes 会根据机器内存推导一个默认上限。如果宿主机资源较紧张，可以增加：

```yaml
kanban:
  max_in_progress: 3
```

### 自动拆分和显式协调器的区别

当前推荐路径是：

```text
用户创建 triage 任务
    -> Hermes auxiliary.kanban_decomposer 自动拆分
    -> 根任务 assignee 为 issue-coordinator
    -> 子任务按 profile description 路由
```

`triage` 是等待自动拆分的状态，不应直接 `promote`。如果 `triage` 长时间不动，优先检查 `auxiliary.kanban_decomposer` 的 endpoint、凭证、Gateway 是否读取到最新配置，以及 Gateway 日志中的 `decompose: API call failed`。

如果需要完全固定任务图，可以关闭 `auto_decompose`，创建一个普通的 `ready` 任务给 `issue-coordinator`，由它通过 `kanban_create` 显式创建 intake、代码、运行时、复核和汇总子任务。

因此，`profile.yaml` 中的 description 很重要。自动拆分器会根据 profile 描述选择 assignee，而不是只根据 profile 名称猜测。

## 四、各阶段职责

### 1. issue-intake

输入：

- Issue 文本或飞书项目 URL；
- 服务名；
- 环境；
- 时间窗口；
- trace、request id、错误码或日志关键字。

动作：

1. 读取 Issue 和评论；
2. 如果是飞书项目 URL，使用 `feishu-project` 或 `meegle` CLI 获取详情；
3. 规范化时间和时区；
4. 标记缺少的字段；
5. 不扫描仓库、不查询 Nex。

输出：

```text
/home/roy/dev/.hermes-issue-analysis/<task-id>/intake.md
```

### 2. code-investigator

动作：

1. 在 `/home/roy/dev` 下复用远程地址匹配的干净 checkout；
2. 仓库不存在时再 clone；
3. 记录仓库根目录、remote、分支和 commit；
4. 使用 CodeGraph 缩小入口、调用方、被调用方和影响面；
5. 用普通源码读取验证决定性结论；
6. 不查询线上部署和生产数据。

基础检查：

```bash
git rev-parse --show-toplevel
git status --short --branch
codegraph sync
codegraph status
```

不存在图谱时才初始化：

```bash
codegraph init -i
```

报告：

```text
/home/roy/dev/.hermes-issue-analysis/<task-id>/code.md
```

### 3. runtime-investigator

动作顺序：

1. `nex --help`；
2. 只查看当前问题需要的 Nex 子命令帮助；
3. 查询目标服务、环境的部署分支和 commit；
4. 按绝对时间窗口和最强标识符查询日志；
5. 只有日志和代码无法回答具体问题时，才查询指标、MySQL 或 Redis；
6. 所有查询只读、有时间范围、有行数和字段限制。

不要把原始日志、内部地址、账号记录、Cookie、Token 或数据库凭据写入报告。

报告：

```text
/home/roy/dev/.hermes-issue-analysis/<task-id>/runtime.md
```

### 4. evidence-verifier

只读取 intake、code、runtime 的 handoff 和报告，检查：

- Issue 服务和环境是否一致；
- 本地分析 commit 是否能和部署 commit 对比；
- 症状、代码路径和线上信号是否形成证据链；
- 哪些是事实、推断和待验证假设；
- 是否存在时效、权限或标识符缺口。

报告：

```text
/home/roy/dev/.hermes-issue-analysis/<task-id>/verification.md
```

### 5. issue-synthesizer

读取前置阶段的短摘要和报告，生成：

```text
/home/roy/dev/.hermes-issue-analysis/<task-id>/analysis.md
```

最终报告固定包含：

```text
结论
根因
证据
影响范围
修复建议
验证方案
置信度
残余风险与人工确认
```

汇总阶段不能因为“看起来缺证据”就重新拉取全部日志或重扫整个仓库。只允许做一个明确、范围很小的补充检查。

## 五、handoff 设计

### 1. handoff 的原则

- `summary` 面向下游 Worker，短而可执行；
- `metadata` 只放结构化事实；
- 完整内容写入阶段报告；
- 原始 CodeGraph 输出和 Nex 日志不进入 `summary`；
- 所有报告路径使用绝对路径；
- 结论必须区分 `事实`、`推断`、`待验证假设`。

示例：

```python
kanban_complete(
    summary="已确认入口为 AlertService.CheckClosePrice；本地 commit 为 abc123。代码存在未按标的做每日频控的路径，但仍需和 qa 部署 commit 及日志时间窗口核对。",
    metadata={
        "stage": "code",
        "repository": "/home/roy/dev/risk-service",
        "local_commit": "abc123",
        "entry_points": ["AlertService.CheckClosePrice"],
        "facts": ["同一标的的告警写入路径未发现日级去重条件"],
        "inferences": ["该逻辑可能导致同一标的重复告警"],
        "unknowns": ["qa 当前部署 commit"],
        "evidence_count": 3,
        "confidence": "中",
        "report_path": "/home/roy/dev/.hermes-issue-analysis/t_xxxxxxxx/code.md",
    },
    artifacts=["/home/roy/dev/.hermes-issue-analysis/t_xxxxxxxx/code.md"],
)
```

### 2. 推荐的字段范围

| 阶段 | metadata 重点 |
| --- | --- |
| intake | `service`、`environment`、`time_window`、`identifiers`、`missing_inputs` |
| code | `repository`、`local_commit`、`entry_points`、`facts`、`unknowns` |
| runtime | `deployed_branch`、`deployed_commit`、`deployment_status`、`facts`、`unknowns` |
| verifier | `verified_facts`、`supported_inferences`、`contradictions`、`missing_evidence` |
| synthesis | `root_cause`、`confidence`、`repository_commit`、`deployed_commit`、`residual_risk` |

`metadata` 不是日志仓库。字段数量和数组长度都应保持小，避免结构化字段反过来成为上下文膨胀来源。

## 六、完整业务流程

### 第一步：提交

提交者至少提供：

```text
Issue 描述或链接
服务名称
环境
问题发生时间窗口
一个可检索的标识符或关键字
```

生产环境或环境不明确时，按生产范围处理，不能默认查询测试环境。

### 第二步：输入规范化

`issue-intake` 将链接或描述转换为统一调查 brief。缺少服务、环境、仓库映射、Issue 权限或关键时间窗口时，任务进入 `blocked`，等待人补充。

### 第三步：并行取证

`code-investigator` 和 `runtime-investigator` 在 intake 完成后并行执行：

```text
代码侧：入口 -> 调用链 -> 缺陷机制 -> 本地 commit
运行侧：部署状态 -> 部署 commit -> 日志/指标 -> 数据状态
```

### 第四步：证据复核

`evidence-verifier` 不重新做大范围调查，只判断两条证据链是否能够对上，并指出：

- 本地代码不是部署代码；
- 日志相关性不是因果证明；
- 触发条件不是底层缺陷；
- 当前影响和历史影响不能混淆。

### 第五步：汇总

`issue-synthesizer` 读取 handoff 和报告，写入最终 `analysis.md`，然后完成根任务。飞书通知只应携带一段短结论和报告路径，完整报告通过附件或本地路径查看。

## 七、常见问题

### 1. triage 任务一直不动

检查：

```bash
hermes gateway status
hermes kanban --board issue-analysis diagnostics --json
```

常见原因：

- 网关没有运行；
- `auto_decompose` 被关闭；
- 辅助模型不可用；
- 辅助模型配置更新后 Gateway 没有重启，仍在使用旧 endpoint 或旧凭证；
- profile description 缺失或 assignee 不存在；
- Issue 仍然缺少必要输入。

不要先尝试 `promote triage -> ready`。`triage` 应由 `decompose` 或 `specify` 处理；自动模式下由 Gateway dispatcher 调用，手动恢复时才执行：

```bash
hermes kanban --board issue-analysis decompose t_xxxxxxxx --json
```

### 2. Worker 启动失败

查看任务详情和运行记录：

```bash
hermes kanban --board issue-analysis show t_xxxxxxxx --json
```

重点区分：

- `spawn_failed`：profile、权限、环境或启动配置问题；
- `timed_out`：任务超过 `max_runtime_seconds`；
- `crashed`：进程异常退出或资源不足；
- `reclaimed`：任务被调度器回收后重新排队。

### 3. 代码和运行时阶段没有并行

通常是依赖关系设置过宽。正确关系是：

```text
intake -> code
intake -> runtime
code + runtime -> verifier
```

同时，两个阶段必须使用不同 profile，并确认 `max_in_progress_per_profile` 没有把它们错误地路由到同一个 profile。

### 4. 汇总阶段上下文仍然很大

检查是否违反了 handoff 约定：

- 是否把完整日志放进 `summary`；
- 是否把 CodeGraph 全量输出放进评论；
- 是否在汇总阶段重新扫描仓库；
- 是否反复追加无结论评论；
- 是否把多个时间窗口的原始结果全部带入。

正确做法是保留报告文件，handoff 只保留短摘要和少量结构化字段。

### 5. 本地代码和部署代码对不上

这是正常风险，不应强行下结论。报告中必须分别记录：

```text
repository_commit: 本地分析 commit
deployed_commit: 线上实际部署 commit
```

如果两者不同，应降低置信度，并说明需要对部署 commit 做定向复核。

## 八、安全边界

- 默认只读；
- 不执行 deploy、rollback、delete、update、insert、flush；
- 不修改业务源码或共享 checkout；
- 不在生产环境执行无范围查询；
- 不保存或转发 Token、Cookie、密码、数据库凭据和内部地址；
- 日志、数据库和用户记录必须脱敏、限量；
- CodeGraph 是定位证据，不是最终结论；
- Nex 返回的是线上观测，不自动等同于根因；
- 缺权限或缺关键输入时阻塞任务，不猜测补齐。

## 九、验证清单

使用脱敏测试 Issue 验证以下行为：

- [ ] 任务以 `triage` 进入 `issue-analysis` Board；
- [ ] dispatcher 自动拆分，且每轮不超过 `auto_decompose_per_tick`；
- [ ] 创建自飞书的任务具备通知订阅，终态事件能回到原会话；
- [ ] intake 完成后，代码和运行时任务并行；
- [ ] 子任务 handoff 保持短小；
- [ ] CodeGraph 和 Nex 原始输出没有进入汇总上下文；
- [ ] verifier 等待两个证据任务完成；
- [ ] synthesizer 生成 `analysis.md`；
- [ ] 根任务完成后能在 Kanban 查看摘要、metadata 和报告；
- [ ] `.codegraph/` 未被 Git 跟踪；
- [ ] 失败、阻塞和缺少权限的任务能给出明确原因。
