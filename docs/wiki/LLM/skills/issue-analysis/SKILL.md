---
name: issue-analysis
description: "Use when a user needs to submit, monitor, recover, or consume a software issue investigation on the Hermes issue-analysis Kanban board."
disable-model-invocation: true
---

# issue-analysis

This skill is the operating guide for the `issue-analysis` Kanban board. The
main worker submits and observes the task; specialist workers inspect code and
runtime evidence, then a synthesizer writes the final report. Detailed worker
implementation belongs in the board configuration and the linked reference
documents, not in this skill.

## When to use

Use it when the user:

- asks why a software issue, task, alert, or request failed;
- provides a detailed issue or a Feishu Project issue URL;
- provides, or expects to provide, the service and environment;
- asks to submit, check, retry, unblock, or explain an existing
  `issue-analysis` task.

Do not run a full Kanban investigation for a generic code question or a
standalone log explanation that does not need repository and runtime evidence.

## Trigger and submit

Create the graph with the fixed submit script. Do not use `--triage` and do
not call `decompose`. The decomposer rebuilds the graph with an LLM, drops
the stage skills, and sometimes starts code and runtime before intake.

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/issue-analysis/scripts/submit_issue.py \
  --body-file <issue.md> \
  --idempotency-key "<stable-issue-key>"
```

Add `--title` when the default `[environment][service] symptom` title is a
poor summary. Add `--deployed-commit <hash>` only when the user already
knows the commit that was running. Add `--chat-id <oc_xxx>` when the report
should return to the Feishu chat that asked; the subscription is attached
to the root, which completes last.

The script rejects a body that is missing any of the five sections below.
Do not invent a missing service, environment, time window, or repository.
Ask for the missing input before submitting.

`Service` must be the Nex deploy name, which often differs from the name
in the source catalog or in Jaeger (`trade.order-service.job`, not
`trade.order.service` or `OrderService.grpc`). Look it up with
`scripts/find_service.py --env <env> --keyword <word>` and add
`--verify-service` so a wrong name is refused before any card exists.

Required task fields:

- title: `[<environment>][<service>] <short symptom>`;
- body: `Issue`, `Service`, `Environment`, `Time Window`, and `Evidence`;
- workspace: `dir:/home/roy/dev` when stages share checkout and reports;
- idempotency key: a stable issue key when the source can be retried safely.

Do not invent a missing service, environment, time window, or repository. Ask
for the missing input, or leave the task blocked with a typed reason.

Canonical body:

```markdown
## Issue
<detailed description or Feishu Project issue URL>

## Service
<service name>

## Environment
<qa | test | staging | prod | other>

## Time Window
<absolute time range with timezone, or unknown>

## Evidence
<trace/request id, error code, log keyword, or reproduction steps>
```

The script builds this graph. Code and runtime start only after intake has
resolved the deployed commit. The root is a child of all five stages, so it
runs last and a Feishu subscription on it fires after the report exists.

```text
intake -> code ----+
      -> runtime --+-> verifier -> synthesizer
                         \__________________/
                                   |
                                  root (issue-coordinator)
```

Intake may change the graph once, with `scripts/adjust_graph.py`, before
code and runtime start:

- **fact route**: the report asks what happened, not why the code behaves
  that way. The code card is archived and the rest runs as drawn. Any
  question about business logic keeps the code card.
- **extra runtime**: the trace shows another service with its own error
  span. One more runtime card is added for it (at most two) and the
  verifier waits for it.

Do not skip or add cards by hand; see [reference.md](reference.md#routes).

All five reports go in one directory,
`/home/roy/dev/.hermes-issue-analysis/<root-id>/`. Intake also writes
`deployed.json`. The synthesizer is the only writer of `analysis.md`.

## Feishu front desk

Reports that arrive through 老铁 on Feishu are not handled by this skill.
The gateway routes every Feishu chat to the `issue-desk` profile, whose
own skill collects the report, finds the deploy service name, submits the
graph, and relays `analysis.md` when the root finishes. The desk does not
investigate, and when it cannot settle on one service it asks the reporter
to be more specific. A report does not need a trace id or an account: the
environment, the time window, what happened, and the service are enough.

`issue_desk.py submit` subscribes the asking chat by itself: the root and
intake with `notify+wake`, the other stages with `notify`. A blocked
intake wakes the desk, which asks the reporter and passes the answer back
with `issue_desk.py answer`.

When submitting by hand for someone waiting in Feishu, pass `--chat-id`
and `--delivery-mode notify` to `submit_issue.py`. The chat then gets one
line when the root finishes, and the person can ask 老铁 for the report by
root id. Do not use `notify+wake` by hand: a subscription made from the
command line is owned by the default profile, so the wake would be
answered by the default profile and not by the desk. If no subscription
can be created, tell the user the task id and that they must check the
board manually. Do not imply that a report will be pushed back.

## Preflight

Before relying on an unattended run, confirm the infrastructure is ready:

- Gateway is running and `kanban.dispatch_in_gateway=true`;
- staged profiles exist and have useful descriptions;
- the worker environment can run CodeGraph, Nex, and the Jaeger summary script;
- `submit_issue.py` is used instead of `triage` for new issues;
- Feishu notification subscription exists for the root task;
- for the Feishu desk: `gateway.profile_routes` sends `feishu` to
  `issue-desk`, and `issue_desk.py catalog --line 风控` prints the catalog.

If a preflight check fails, create a visible `capability` or `needs_input`
blocker, or return a short setup error. Do not submit through `triage`
to get around a failed check.

## Operate the board

Use the commands in [reference.md](reference.md). The minimum lifecycle is:

1. Submit the graph with `submit_issue.py`.
2. Confirm the returned root id, `root_status` `todo`, and five parents.
3. Let the Gateway dispatcher run the stages. Do not promote the root.
4. Follow progress with `show`, `tail`, or `runs` only when the user asks for
   status or recovery.
5. Read the root handoff and `analysis.md` after the synthesizer completes.
6. Recover only the affected task, then re-check downstream dependencies.

The main worker should not claim specialist work or perform the code/runtime
investigation itself. It should return the root task id and a concise status
summary to the user.

## Read the result

Treat `analysis.md` and the root task handoff as the user-facing result. The
answer should distinguish:

- conclusion and root cause;
- facts, inferences, and unverified hypotheses;
- impact and affected versions;
- remediation and verification plan;
- confidence and remaining human checks.

Do not paste full source files, graph dumps, raw logs, or raw database results
into the main conversation. Use the report path and short handoffs as the
context boundary.

## Block and recover

Use typed reasons:

- `needs_input`: missing issue, service, environment, time range, identifier,
  or access prerequisite;
- `capability`: required Feishu Project, repository, CodeGraph, or Nex access
  is unavailable;
- `dependency`: waiting for a parent task;
- `transient`: bounded retryable tool or network failure.

When a task is stuck, inspect `diagnostics`, `runs`, and `log` first. Use
`reclaim` only for a stale/running worker, `reassign` when the profile is
wrong, `unblock` after the prerequisite is supplied, and `promote` only as a
manual recovery action. Do not duplicate a task graph during recovery.

## Boundaries

- analysis is read-only by default;
- never deploy, rollback, delete, update, insert, flush, or mutate production
  data;
- never modify application source during investigation;
- treat an unclear environment as production until confirmed;
- separate local code from deployed code and correlation from causal proof;
- if decisive evidence is missing, state what is missing and block.
