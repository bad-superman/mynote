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
it collects the report, submits the graph, passes the board's questions
to the reporter, and relays the report. See
[Feishu front desk](#feishu-front-desk).

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

Exit code 4 means the trace is gone. Do not retry it. Two lines of the
summary say where the failure is: `deepest_error` is the error span
furthest down the call chain, and `unanswered_calls` lists failed outgoing
calls with no span under them, where the trace ends at the caller.

The deployed commit is resolved by intake with
`scripts/deployed_version.py`. With `--expect-path <directory>` it also
reports whether that directory exists in the deployed commit, which is how
a service found in the source catalog is confirmed. Deploy timestamps are
`Asia/Shanghai`.
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
means no match, 6 means Nex failed twice in a row. `submit_issue.py
--verify-service` refuses a `Service` that is neither an exact deploy name
nor `unresolved`. `issue_desk.py submit` puts a name in `Service` only
when it is an exact deploy name; anything else the reporter said goes
into `Evidence` as a hint and `Service` is `unresolved`.

### Locating the service

Intake locates the service of an issue submitted as `unresolved`:

1. the reporter's hint in `Evidence`, when it lists exactly one deploy
   name;
2. the trace: the service of `deepest_error`;
3. the description, through the source catalog.

```bash
C=/home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/service_catalog.py
python3 $C [--line <word>]                           # business lines, services, descriptions
python3 $C --tree --service <catalog-name>           # directories, three levels deep
python3 $C --tree --service <catalog-name> --path <directory>   # one directory, with files
python3 $C --text "<exact text>" --service <catalog-name>       # match count and file names
```

The script calls sourceinsight over HTTP with the token in the intake
profile's `.env`. It prints service names, directory and file names, and
match counts, never source lines. Run by a board card it is limited to 12
lookups per card (`lookups_left` in the output; exit code 3 when used
up); the counters are in
`/home/roy/dev/.hermes-issue-analysis/.catalog-lookups/`.

sourceinsight indexes production code. The catalog name is converted
with `find_service.py`, and the result is confirmed with
`deployed_version.py --expect-path <directory>`. When intake cannot
settle on one service it blocks with `needs_input` and a question for the
reporter.

Limits: the catalog has fewer services than Nex deploys, so a
description-only report about a service missing from the catalog goes
back to the reporter. A system that is not deployed through Nex cannot be
the issue's service; it can only appear as a boundary (see below).

### Routes

The script always builds the full graph:

```text
intake -> code -> runtime -> verifier -> synthesizer -> root
```

Runtime has intake and code as parents, because it checks the 待验证 list
at the end of `code.md`. Two stages may change the graph, through
`adjust_graph.py` only:

```bash
# intake: record the service it located for an issue submitted as unresolved
python3 .../scripts/adjust_graph.py --root <root-id> \
  --service <deploy-name> --located-by <trace|description|reporter>

# intake: the report asks for a fact (what happened), not for a cause in the code
python3 .../scripts/adjust_graph.py --root <root-id> --route fact

# intake: a second service has its own error span in the trace
# code:   the conclusion depends on the next hop of the failing path
python3 .../scripts/adjust_graph.py --root <root-id> --add-runtime <deploy-name> \
  [--reason "<what to check there>"]
```

- `--service` is accepted only when the issue's `Service` is `unresolved`
  and before the code card starts. The name is written as a `## Service`
  comment on the code, runtime, verifier, synthesizer, and root cards.
- `--route fact` archives the code card, which also releases runtime. The
  verifier and synthesizer are told through a `## Route` comment and do
  not expect `code.md`. A report that asks why the code behaves as it
  does keeps the code card.
- `--add-runtime` creates one more runtime card for the named service
  (at most two per issue) with intake and code as parents, and makes the
  verifier, synthesizer, and root wait for it. `--reason` goes into the
  card's `## Why` section. Its report is `runtime-<service>.md`. The
  deployed commit is resolved only for the issue's main service.
- `--route fact` and `--add-runtime` cannot be combined, and nothing is
  accepted after the verifier has started. The state is in
  `<evidence-dir>/route.json`.

### Boundaries and the two ratings

The code stage names the next hop of the failing path under 下一跳 in
`code.md`. When `find_service.py` has no deploy name for it, the next hop
is a boundary: an external system, or a service that is not deployed
through Nex. No card can look inside it.

The verifier rates 故障点 (where the failure surfaced) and 原因 (why it
happened) separately. With a boundary that the conclusion depends on,
原因 is 低 whatever the story looks like, because nobody examined the
place where the cause would be; 故障点 can still be 高. `analysis.md`
then says where the failure surfaced, that the cause was not examined,
who has to continue, and what to hand them.

原因 is 高 when the item that states it counts and holds, or when the
cause was read directly in the deployed code, with file and line, and no
item contradicts it. 故障点 is 高 whenever 原因 is.

### Checking the list against the logs

`code.md` ends with 待验证: statements with the service, where to look,
and what would be seen. Runtime gives each a verdict, 成立, 不成立, or
查不到, with one command per question:

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/log_search.py \
  --env <test|qa|prod> --service <deploy-name> \
  --start "<window start>" --end "<window end>" \
  [--text "<part of the log line>"] [--trace-id <trace_id>] [--samples N]
```

It prints `hits`, the time of the `first` and the `last` matching line,
and up to ten lines, earliest first. It knows the log cluster and the log
source, so the stage does not look them up or parse the platform's JSON.

- `--text` is an exact, case-sensitive part of the line. The platform
  has no AND and no field syntax, so it is one text per call. The code
  stage therefore gives the fixed part of the log statement as the code
  writes it.
- `--trace-id` selects one trace's lines. The platform drops the text
  when a trace id is given, so with both the script fetches the trace's
  lines (500 at most) and matches the text itself.
- `hits: 0` comes with `lines_in_window`, the number of lines the service
  wrote in the window. No match refutes something only when the service
  was logging; with 0 lines the logs are missing and decide nothing.
- Exit code 4: the log platform has no logs for that service in that
  environment. Exit code 6: the platform failed, after one retry for a
  timeout.

The board cannot read database tables or Redis: `nex db` lists instances
only. A statement only the database could decide may be the last item of
the list; runtime marks it 查不到 and the report hands the question and
the table to a person, without a query: the person who knows the schema
writes it.

### Checking the list against the deployed code

Finding nothing refutes something only when the service would have
written the text. A search for a function name or a line of code finds
nothing whatever happened. So a log item of 待验证 has to quote a text
that a log statement of the deployed commit writes, and one script
decides whether it does:

```bash
# the log statements of one file, each with the text to search for
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/check_list.py logs \
  --evidence-dir <evidence-dir> --file <path or file name> [--around <line>]

# every item of the list in code.md
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/check_list.py check \
  --evidence-dir <evidence-dir>
```

Both read the commit named in `<evidence-dir>/deployed.json` through
`git show`, never the working tree. `logs` prints the line, the level,
and the fixed part of each statement's text: what stands before the
first value filled in at run time. `check` prints one line per item:

| Status | Meaning | A search that finds nothing |
|---|---|---|
| 已确认 | the quoted text is written by a log statement within three lines of the cited line | decides the item, when `lines_in_window` is above 0 |
| 未确认 | the statement is outside the repository (`不在本仓库：…`), belongs to another service, is at debug level, or is not Go | decides nothing: 查不到 |
| 通过 | a metric item or a database item | not applicable |
| 要改 | the item breaks the form: no location, two texts, a text no statement writes, more than five items | decides nothing: 查不到 |

去哪查 has four forms: `日志 "<原文>"（<file>:<line>）`,
`日志 "<原文>"（不在本仓库：<谁打印的>）`, `指标 <指标名>`, and
`数据库（看板查不了）：<表名和条件>`.

Each stage runs the check itself, so the result does not depend on what
an earlier stage did with it:

- code takes its log items from `logs`, runs `check` after writing
  `code.md`, fixes what is marked 要改 (twice at most), and removes what
  still fails. A path that writes no log gets a list without log items.
  The stage works in a fixed order: pin the commit, read the path, list
  the log statements, write `code.md`, look up the next hop, check the
  list. The file is written before the last two steps because a run
  that reaches its turn limit (`max_turns: 90` in the profile) without
  the file has produced nothing; a retry continues from the file.
- runtime runs `check` first. A hit decides any item. Finding nothing
  decides only an item marked 已确认.
- the verifier copies each item's status into `verification.md` and
  counts a verdict that rests on finding nothing only for 已确认.

What counts as a log statement: a call to a level method (`Infof`,
`Errorw`, `Printf`, ...) on something named like a logger (`log`,
`logger`, `gologger`, `u.log.WithContext(ctx)`, `helper`, `zap`).
`fmt.Errorf` and `errors.New` build an error and write nothing. The
searchable text stops at format verbs, escapes, and the characters a
JSON log line may store escaped (`"`, `\`, `<`, `>`, `&`).

Limits: only Go is read. A text written by a library is never 已确认,
because its statement is not in the repository. The code of a next-hop
service is not resolved, so its items are 未确认. A logger that is not
named like one is not recognised, which errs on the side of 未确认.

The check shows where a text comes from. It does not show that the text
has anything to do with the statement of its item. An item may quote a
real log text that is unrelated to what it claims, for example an error
text that is absent on any normal day, and "holds" because nothing was
found. Such an item is 已确认 and counts. The same goes for a search
that runtime adds on its own, with a text that was never checked. Read
an item that holds by finding nothing with that in mind; a hit is the
stronger evidence.

In practice the code stage also uses the outside-repository form for a
text it extended with a run-time value (`服务=TRS`) and for a text that
only commented-out code contains. Both are 未确认, which is the right
status: only a hit decides them.

The verifier sorts each item's evidence into 有命中, trace, or 零命中,
and writes 计入 or 不计. An item that is 不计 is treated like 查不到. The
synthesizer cites only items that count.

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

`notify` posts one line per terminal event and uploads the files a
finished card names. `notify+wake` also wakes the agent in that chat so it
can read the report and answer; from the command line that agent is the
default profile, not the desk (see the table under
[Feishu front desk](#feishu-front-desk)). `wake` posts nothing and only
wakes the agent. The desk uses `wake` for every card of an issue it
submits; see [What reaches the chat](#what-reaches-the-chat).

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
| `now` | current time in Asia/Shanghai and US Eastern |
| `submit ...` | settle environment, window, and service; build the graph; subscribe the chat |
| `status --root <id> [--report]` | located service, stage statuses, block kinds and reasons; with `--report`, `analysis.md` once the root is done |
| `answer --root <id> --text` | pass the reporter's answer to the card that asked |
| `notice --task <id> [<id> ...]` | what a board notification means for the reporter: `silent`, `ask`, `stuck`, or `report` |

The desk has no command that looks anything up. Finding the service is
intake's job.

`submit` needs `--issue`, and then either `--trace-id` or `--env` with
`--window-start` and `--window-end`:

- With a trace id it asks the Jaeger servers in turn (the reporter's
  environment first) and takes the environment from the one that holds
  the trace. The window is the trace's own span, 15 minutes either side,
  unless the reporter gave one.
- When the trace is found nowhere, or there is none, the environment and
  the window have to come from the reporter. Exit code 3 says which is
  missing.
- `--service` takes the reporter's words. An exact deploy name is used;
  anything else becomes a hint in `Evidence`, with the deploy names that
  contain it, and `Service` is `unresolved`.
- A window the reporter gave is checked against the clock, because the
  desk model adds the year to a date like "11 月 24 日" and does not
  always add this one. A window that starts in the future, or more than
  twelve months ago, is moved to the most recent date with that month,
  day, and time when that date is at most 300 days back; the output then
  has `time_window_note` and the desk gives the reporter the window the
  board investigates. Otherwise exit code 3 asks for the date. A window
  that starts within the last twelve months is taken as it is, and so is
  the window of a trace.

`submit` reads the chat from the gateway session (`HERMES_SESSION_*`), so
the model never handles a chat id. It subscribes the root and the five
stages with `wake`. Run from a terminal, it submits without a
subscription and says so.

`answer` goes to intake or to the main runtime card, whichever is
blocked. It refuses a card whose block kind is `capability`,
`dependency`, or `transient`: those are not questions for the reporter.
Extra runtime cards have no chat subscription and do not ask.

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

#### What reaches the chat

From the desk and the board the reporter gets four kinds of message and
nothing else:

| Message | When |
|---|---|
| the desk's own reply | the reporter wrote: a question for what is missing, the short note after `submit`, the status when they ask |
| a question from the board | intake or runtime blocked with `needs_input` |
| a stage that stopped | a card is blocked for another reason, gave up, or went to triage; or the root closed without `analysis.md` |
| the report | the root card is done and `analysis.md` exists |

Two things keep the rest out of the chat.

The desk's `config.yaml` turns off what the gateway would send from
inside a turn. It is read at the start of each turn, so a change needs no
restart:

```yaml
display:
  platforms:
    feishu:
      tool_progress: "off"
      interim_assistant_messages: false
      long_running_notifications: false
      busy_ack_detail: false
```

The subscriptions are `wake`, so the gateway posts no line and uploads
no file when a card changes. It puts a `[kanban] Task <id> ...` message
into the reporter's session instead, and the desk has to decide whether
the reporter hears of it. It does not decide from the text of that
message. It runs

```bash
issue-desk notice --task <id> [<id> ...]
```

with every id the message names, and the output says what the reply is:

| Verdict | Card state | Reply |
|---|---|---|
| `silent` | a stage finished; a card is being retried; the root is not done; an answered question | the last line of the output, `NO_REPLY`, and nothing else |
| `ask` | intake or runtime blocked with `needs_input` | the question as it stands, then `answer` with the reply |
| `stuck` | blocked for another reason, `gave_up`, triage, or a done root without `analysis.md` | which stage stopped and why; nothing is asked |
| `report` | the root is done and `analysis.md` exists | the report, relayed by the checklist the output ends with |

A reply that is exactly `NO_REPLY` is dropped by the gateway
(`gateway/response_filters.py`); anything else is sent. The synthesizer
finishing is `silent` although it has written `analysis.md`: the
coordinator may still send the issue through another round, and the
report goes out when the root closes. For the same reason
`status --report` shows the report only when the root is done.

The terminal tool passes at most `tool_output.max_bytes` characters of a
command's output to the model, 12000 for the desk. `notice` and
`status --report` size the report to what is left after their own lines,
about 10,300 characters. A longer report is shown from both ends with a
line that says how much of the middle is left out; the path of the whole
file is in the output. Several ids in one command share the room: what
does not fit is named with the command to run next.

What is decided by code and what by the model:

- No tool bubbles, no words from inside a turn, no heartbeat, no line
  per card, and no upload: decided by the config and the subscription
  mode.
- Which notification is worth a message: decided by `notice` from the
  board's state.
- Staying silent on a `silent` verdict and writing the message on the
  others: the desk model, following `notice`. Measured on a temp board
  with `deepseek-v4-flash` on 2026-11-25, with the wording as it is now:
  330 of 330 `silent` notifications stayed silent, and all 24 `ask` and
  all 82 `report` notifications were written. Of 47 `stuck`
  notifications one got a greeting in English instead of the notice;
  `SOUL.md` now says that a board notification is never an off-topic
  message, and the 21 after that were written. With the wording before
  this one, 2 of 244 `silent` turns sent a line: once a sentence about
  waiting, once `NO_REPLY` with two stray characters behind it, which no
  wording prevents. A gateway plugin on `transform_llm_output` could take
  the model out of the `silent` case; it is not installed, and loading it
  needs a gateway restart.

The settings above cover what a turn sends while it runs. The gateway
can still send a line of its own when a turn fails, for example on a
provider error, and when the reporter writes while a turn is running:
that message interrupts the turn. If the interrupted turn was the one
relaying the report, the reporter gets the report by asking for it
(`status --root <id> --report`).

`SOUL.md` and the skill are read when a session starts, so a chat that
was open before a change needs `/new`. A subscription keeps the mode it
was made with. The issues submitted before 2026-11-25 have `notify` and
`notify+wake` subscriptions; all of their cards were done by then, so
they send nothing more unless a card is reopened.

To get one line and the `analysis.md` upload from the gateway when the
root closes, in addition to the relayed report, give the root card
`notify+wake` in `issue_desk.py` (`DELIVERY_MODE` is used for all six
cards). The upload happens only when the coordinator names the file in
its completion.

A report needs what happened, plus a trace id or the environment and the
time. A service name, an account, an order id, and an error text are
passed on when the reporter volunteers them and are never asked for at
the desk. When a stage needs one to check something, it blocks with
`needs_input`, the desk relays the question, and `answer` returns the
reply. When intake cannot settle on one service, the question asks the
reporter to be more specific. Nothing is forwarded to another person.

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
intake -> code -> runtime -> verifier -> synthesizer -> root
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
route.json              # located service, route, extra runtime cards; only when the graph changed
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
- Nex: logs through `log_search.py`, and metrics. It cannot read a
  database table or Redis. Intake uses it once to resolve the deployed
  commit and the deploys in the window; runtime quotes that instead of
  asking again.
- Jaeger: one summary at intake, by trace id. Runtime reads it once more
  only when a 待验证 item is about the timing or order of calls. The desk
  asks the servers which of them holds a trace, to learn the environment.
- sourceinsight: intake's service lookup only, through
  `service_catalog.py`, which prints names and counts. It shows production
  code, which is not always what runs in `test` or `qa`; the code stage
  reads the deployed commit instead.
- Normal repository tools: validate decisive source-level claims.
- `check_list.py`: reads the deployed commit through `git show`, lists
  the log statements of a file, and checks the 待验证 list. Code,
  runtime, and the verifier each run it. Go sources only.

No individual tool is a root-cause proof. The final report must connect the
symptom, code path, deployed commit, runtime signal, and data state where
applicable.
