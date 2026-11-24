# Reference

## Board and profiles

The current board is `issue-analysis`. Its configuration is maintained in:

```text
/home/roy/.hermes/config.yaml
/home/roy/.hermes/kanban/boards/issue-analysis/board.json
```

New issues are submitted with `scripts/submit_issue.py`. `--triage` remains
available for recovery, but the decomposer does not build the fixed graph
and new tasks should not use it.

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

`issue-desk` is not a stage. It is the profile that answers 老铁 on Feishu:
it collects the report, finds the deploy service name, submits the graph,
and relays the report. See [Feishu front desk](#feishu-front-desk).

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

Write the canonical body to a file, then:

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/submit_issue.py \
  --body-file /tmp/issue.md \
  --idempotency-key "AEV-example" \
  --chat-id oc_xxx \
  --chat-type dm \
  --delivery-mode notify
```

`--chat-id` is optional. Omit it when nobody is waiting in Feishu. The
script prints the root id, the five stage ids, and the evidence directory.
Running it again with the same key returns the same cards.

Jaeger lookup, for `test`, `qa`, and `prod` only:

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/jaeger-trace/scripts/jaeger_trace.py \
  --env qa --trace-id <trace_id> --raw-out <evidence-dir>/jaeger-intake.json
```

Exit code 4 means the trace is gone. Do not retry it.

The deployed commit is resolved by intake with
`scripts/deployed_version.py`. Deploy timestamps are `Asia/Shanghai`.
Deploy clusters are `tx-youfi-test-sg`, `tx-youfi-qa-sg`, and
`aws-youfi-prod-hk`. Log clusters are the other naming scheme:
`tx-sg-youfi-test`, `tx-sg-youfi-qa`, and `aws-hk-youfi-prod`.

`--idempotency-key` is required. Use a stable issue id, not a timestamp.
The returned `root` is the task id to watch.

### Service names

The board keys every stage on the Nex deploy name. Two other name spaces
look similar and are not interchangeable:

| Source | Order service | Account service |
|---|---|---|
| Nex deploy name (submit this) | `trade.order-service.job` | `ams.account.job` |
| sourceinsight catalog | `trade.order.service` | `ams.account.service` |
| Jaeger | `OrderService.grpc` | `ams.account.job.grpc` |

Some services use one name everywhere (`risk.risk.service`,
`quote.market.service`). Look the deploy name up by keyword:

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/find_service.py \
  --env qa --keyword order
```

It prints the deploy names in that environment that contain the keyword,
and `exact: true` when the keyword is itself a deploy name. Exit code 4
means no match, 6 means Nex failed. `submit_issue.py --verify-service`
refuses a `Service` that is not an exact deploy name; `issue_desk.py
submit` always verifies.

### Routes

The script always builds the full graph. Intake may change it once, before
code and runtime start:

```bash
# The report asks for a fact (what happened), not for a cause in the code.
python3 .../scripts/adjust_graph.py --root <root-id> --route fact

# The trace shows a second service with its own error span.
python3 .../scripts/adjust_graph.py --root <root-id> --add-runtime <deploy-name>
```

- `--route fact` archives the code card. The verifier and synthesizer are
  told through a `## Route` comment and do not expect `code.md`. A report
  that asks why the code behaves as it does keeps the code card.
- `--add-runtime` creates one more runtime card for the named service
  (at most two per issue) and makes the verifier, synthesizer, and root
  wait for it. Its report is `runtime-<service>.md`. The deployed commit
  is resolved only for the primary service.
- The two cannot be combined, and neither is accepted after the verifier
  has started. The choice is recorded in `<evidence-dir>/route.json`.

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
  --delivery-mode notify
```

`notify` posts one line per terminal event. `notify+wake` also wakes the
agent in that chat so it can read the report and answer; from the command
line that agent is the default profile, not the desk (see the table under
[Feishu front desk](#feishu-front-desk)).

### Feishu front desk

Every Feishu chat with 老铁 is handled by the `issue-desk` profile. The
route is in the root config and is read at gateway start:

```yaml
gateway:
  multiplex_profiles: true
  multiplex_profile_allowlist: [issue-desk]
  profile_routes:
    - name: feishu-issue-desk
      platform: feishu
      profile: issue-desk
```

The Feishu credentials and the pairing list stay on the default profile.
Removing `profile_routes` and restarting the gateway gives Feishu back to
the default profile.

The desk has two toolsets, `terminal` and `skills`. Its skill allows one
command, a wrapper around `scripts/issue_desk.py`:

```bash
/home/roy/.hermes/profiles/issue-desk/bin/issue-desk <subcommand>
```

| Subcommand | Use |
|---|---|
| `trace --env --trace-id` | Jaeger summary for one trace |
| `search --env --identifier --start --end` | traces of one account in a window, failing first |
| `service --env --keyword` | deploy names containing the keyword |
| `catalog [--line]` | services by business line with their descriptions |
| `catalog --text --service` | how often a text occurs in up to three services |
| `now` | current time in Asia/Shanghai and US Eastern |
| `submit ...` | verify the service, build the graph, subscribe the chat |
| `status --root <id> [--report]` | stage statuses, block reasons, `analysis.md` |
| `answer --root <id> --text` | pass the reporter's answer to a blocked intake |

`submit` reads the chat from the gateway session (`HERMES_SESSION_*`), so
the model never handles a chat id. It subscribes the root and intake with
`notify+wake` and the other four stages with `notify`. Run from a
terminal, it submits without a subscription and says so.

The desk's subscriptions have no owner profile (`notifier_profile` is
NULL), and that is deliberate. The desk has no Feishu adapter of its own,
and the gateway notifier treats the three cases differently:

| Owner on the row | Passive line | Wake |
|---|---|---|
| `issue-desk` | not delivered | not delivered |
| `default` | delivered | answered by the default profile |
| none | delivered | routed to `issue-desk` |

`hermes kanban notify-subscribe` always writes an owner, so `issue_desk.py`
writes the row through `kanban_db.add_notify_sub`. For the same reason a
subscription made by hand should use `--delivery-mode notify`.

A report needs the environment, the time window, what happened, and the
service. A trace id or an account identifier is optional: they are two of
the ways to find the service, and once the service is known the board
works from the deployed code and the logs in the window.

`catalog` calls sourceinsight over HTTP from the script
(`scripts/service_catalog.py`), with the token in the desk's `.env`. It
is not configured as an MCP server: a multiplexed gateway connects only
the default profile's MCP servers, so MCP tools declared in a routed
profile do not exist in its Feishu sessions. The script prints names,
descriptions, hit counts, and file names, never source lines.

A service picked from the catalog is a guess, so `submit
--service-source catalog` is refused without `--reporter-confirmed`: the
desk names the service and asks the reporter first. When the desk cannot
settle on one deploy name it asks the reporter to be more specific. It
does not forward the question.

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
intake -> code and runtime -> verifier -> synthesizer -> root
```

`promote` is only for a `todo` or `blocked` card whose parents are already
done. A card left in `triage` is from the old path. Inspect the decomposer
before promoting it:

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

Keep every stage report for one issue under the root directory:

```text
/home/roy/dev/.hermes-issue-analysis/<root-id>/
```

Expected files:

```text
intake.md
deployed.json
code.md
runtime.md
verification.md
analysis.md
jaeger-intake.json
jaeger-runtime.json
route.json              # only when intake changed the graph
runtime-<service>.md    # one per extra runtime card
code-worktree/          # detached checkout at the deployed commit, when needed
```

`analysis.md` is written only by `issue-synthesizer`. After the root is
archived, remove a detached worktree with:

```bash
git -C <checkout> worktree remove --force \
  /home/roy/dev/.hermes-issue-analysis/<root-id>/code-worktree
```

## Tool boundaries

- Feishu Project / Meego: resolve issue details and project metadata.
- CodeGraph: narrow repository navigation at the deployed commit.
- Nex: logs, metrics, and bounded read-only storage queries. Intake uses it
  once to resolve the deployed commit.
- Jaeger: one summary at intake and one detailed read at runtime, by trace id.
  The desk may also list one account's traces in a window to find the
  failing service.
- sourceinsight: the desk's service catalog only, through `issue_desk.py
  catalog`. It shows production code,
  which is not always what runs in `test` or `qa`; stages read the deployed
  commit instead.
- Normal repository tools: validate decisive source-level claims.

No individual tool is a root-cause proof. The final report must connect the
symptom, code path, deployed commit, runtime signal, and data state where
applicable.
