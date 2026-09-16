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

Create the root task on the `issue-analysis` board and route it to
`issue-coordinator`. Use `triage` so the configured decomposer can normalize
the input and create the staged graph.

`triage` is a temporary orchestration state. After creating a triage task, the
main worker should let the Gateway dispatcher run `auto_decompose`; it should
not immediately `promote`, manually `decompose`, or start specialist work unless
the user explicitly asks for operational recovery.

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
<qa | staging | prod | other>

## Time Window
<absolute time range with timezone, or unknown>

## Evidence
<trace/request id, error code, log keyword, or reproduction steps>
```

The default graph is:

```text
root -> intake -> (code + runtime) -> verifier -> synthesizer
```

Code and runtime branches should run in parallel. Downstream stages start only
after their real parent tasks complete.

## Feishu handoff contract

When the task is created from Feishu and the user expects an automatic report
back to Feishu, the creation path must leave a notification subscription:

- prefer a creation path that returns or records a subscription;
- if the create result says `subscribed=false`, or the task has no subscription
  row, subscribe the originating Feishu chat with `notify-subscribe`;
- use `notify+wake` when the final report should be read by the gateway agent
  and answered in the chat, not just posted as a passive Kanban event.

If no subscription can be created, tell the user the task id and that they must
check the board manually. Do not imply that a report will be pushed back.

## Preflight

Before relying on an unattended run, confirm the infrastructure is ready:

- Gateway is running and `kanban.dispatch_in_gateway=true`;
- `kanban.auto_decompose=true`;
- `auxiliary.kanban_decomposer` can call the intended endpoint;
- staged profiles exist and have useful descriptions;
- the worker environment can run CodeGraph and Nex;
- Feishu notification subscription exists for the root task.

If a preflight check fails, create a visible `capability` or `needs_input`
blocker, or return a short setup error instead of silently leaving a task in
`triage`.

## Operate the board

Use the commands in [reference.md](reference.md). The minimum lifecycle is:

1. Submit the root task with `create --triage`.
2. Confirm the task id and notification subscription.
3. Let Gateway auto-decompose the `triage` task.
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
