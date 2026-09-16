# Reference

## Board and profiles

The current board is `issue-analysis`. Its configuration is maintained in:

```text
/home/roy/.hermes/config.yaml
/home/roy/.hermes/kanban/boards/issue-analysis/board.json
```

The staged profiles are:

```text
issue-coordinator
issue-intake
code-investigator
runtime-investigator
evidence-verifier
issue-synthesizer
```

The legacy `issue-analyzer` profile can remain for compatibility with old
tasks, but new tasks should use the staged workflow.

## Command cookbook

All examples target the board explicitly:

```bash
hermes kanban --board issue-analysis <command>
```

### Check board and gateway

```bash
hermes kanban boards list --json
hermes kanban boards show
hermes gateway status
```

`boards show` prints the currently active board. The examples below use
`--board issue-analysis` and do not require changing the global active board.

### Submit a task

Use `--triage` for the configured issue-analysis workflow:

```bash
hermes kanban --board issue-analysis create \
  "[qa][example-service] 请求失败" \
  --assignee issue-coordinator \
  --triage \
  --workspace dir:/home/roy/dev \
  --idempotency-key "issue:<stable-issue-key>" \
  --body "$(cat <<'EOF'
## Issue
<详细描述或飞书项目 issue 链接>

## Service
example-service

## Environment
qa

## Time Window
2026-09-15 10:00:00 至 2026-09-15 10:30:00 (Asia/Shanghai)

## Evidence
<trace id、request id、错误码、日志关键字或复现步骤>
EOF
)" \
  --json
```

When the source has no stable key, omit `--idempotency-key` instead of using
a changing timestamp. The returned `t_<...>` id is the root task id.

If the task was created from a Feishu conversation and the final report should
return there automatically, confirm a subscription exists:

```bash
hermes kanban --board issue-analysis notify-list <task-id>
```

If missing, subscribe the original Feishu chat:

```bash
hermes kanban --board issue-analysis notify-subscribe <task-id> \
  --platform feishu \
  --chat-id <oc_xxx> \
  --chat-type dm \
  --delivery-mode notify+wake
```

The `notify+wake` mode posts the terminal event and wakes the gateway agent so
it can read the report and answer in the Feishu chat. Use `notify` only for a
passive Kanban event message.

### Inspect progress and results

```bash
hermes kanban --board issue-analysis list --sort updated --json
hermes kanban --board issue-analysis list --status running --json
hermes kanban --board issue-analysis stats --json
hermes kanban --board issue-analysis show <task-id> --json
hermes kanban --board issue-analysis context <task-id>
hermes kanban --board issue-analysis tail <task-id>
hermes kanban --board issue-analysis runs <task-id> --json
hermes kanban --board issue-analysis log <task-id> --tail 12000
```

Use `show` for comments, child tasks, events, and handoffs. Use `context` to
inspect the assembled worker context, not to paste it into the main chat.
`tail` follows events until interrupted.

### Dispatch and diagnostics

The gateway normally runs the dispatcher. Use a dry run or one manual pass
when diagnosing dispatch:

```bash
hermes kanban --board issue-analysis dispatch --dry-run --json
hermes kanban --board issue-analysis dispatch --max 1 --json
hermes kanban --board issue-analysis diagnostics --json
hermes kanban --board issue-analysis diagnostics --severity error --json
```

Do not start the deprecated standalone Kanban daemon while the gateway is
running.

Expected unattended flow:

```text
triage -> auto-decompose -> todo -> ready -> running -> done
```

`promote` is not the normal action for `triage`; use it only for `todo` or
`blocked` recovery after dependencies are satisfied. If a task remains in
`triage`, inspect the auxiliary decomposer first:

```bash
hermes kanban --board issue-analysis diagnostics --json
hermes kanban --board issue-analysis log <task-id> --tail 12000
rg -n "kanban_decomposer|decompose: API call failed|AuthenticationError" \
  /home/roy/.hermes/logs/agent.log /home/roy/.hermes/logs/errors.log
```

### Recover a task

```bash
# Add a durable operator note.
hermes kanban --board issue-analysis comment <task-id> "已确认时间窗口，继续查询"

# Release a stale running claim and let the dispatcher retry.
hermes kanban --board issue-analysis reclaim <task-id> \
  --reason "worker stale or process exited"

# Change the profile; --reclaim is required for a running task.
hermes kanban --board issue-analysis reassign <task-id> runtime-investigator \
  --reclaim --reason "原 profile 不匹配"

# Supply the missing prerequisite, then return the task to the queue.
hermes kanban --board issue-analysis unblock <task-id> \
  --reason "已补充服务和时间窗口"

# Manual recovery for a todo/blocked task.
hermes kanban --board issue-analysis promote <task-id> \
  "人工确认依赖已满足"
```

Use `block` for a real external prerequisite:

```bash
hermes kanban --board issue-analysis block <task-id> \
  --kind needs_input \
  "缺少服务对应仓库和问题发生时间窗口"
```

`dependency` is for a parent task that is still open; `needs_input` and
`capability` require human action; `transient` is for a bounded retryable
failure.

### Complete or archive

Workers should normally complete their own tasks through the Kanban tool.
Operators generally only inspect or recover them. For explicit administrative
cleanup:

```bash
hermes kanban --board issue-analysis archive <task-id>
hermes kanban --board issue-analysis attachments <task-id> --json
hermes kanban --board issue-analysis attach <task-id> /path/to/report.md
```

Do not manually complete a specialist task unless its handoff and artifacts
have been verified.

### Capability preflight

Run these checks before treating the workflow as fully unattended:

```bash
hermes gateway status
hermes profile list
hermes kanban --board issue-analysis diagnostics --json
command -v codegraph
command -v nex
nex --help
```

For systemd-managed Gateway, verify the service `PATH` includes tool install
locations such as `/home/roy/.nex/bin`; an interactive shell finding `nex` does
not guarantee Kanban workers can find it.

## Evidence directory

Keep stage reports under:

```text
/home/roy/dev/.hermes-issue-analysis/<task-id>/
```

Expected reports:

```text
intake.md
code.md
runtime.md
verification.md
analysis.md
```

## Tool boundaries

- Feishu Project / Meego: resolve issue details and project metadata.
- CodeGraph: narrow repository navigation and call relationships.
- Nex: deployment, logs, metrics, and bounded read-only storage queries.
- Normal repository tools: validate decisive source-level claims.

No individual tool is a root-cause proof. The final report must connect the
symptom, code path, deployed commit, runtime signal, and data state where
applicable.
