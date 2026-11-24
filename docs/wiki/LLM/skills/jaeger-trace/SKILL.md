---
name: jaeger-trace
description: "Look up one call trace by trace id, or list one account's traces in a time window, on the YouFi Jaeger servers."
version: 1.1.0
platforms: [linux, macos, windows]
environments: [kanban]
---

# Jaeger trace lookup

Do not call `curl` and do not paste a raw trace into a report or a Kanban
handoff. Run:

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/jaeger-trace/scripts/jaeger_trace.py \
  --env <test|qa|prod> \
  --trace-id <trace_id> \
  --raw-out <evidence-dir>/jaeger-<stage>.json
```

The script prints a short summary. The raw JSON, which can contain SQL,
account ids, and request payloads, stays in `--raw-out`.

Exit codes:

- `0`: summary printed. Quote services, times, and error spans from it.
- `4`: the trace does not exist or has aged out of retention. Record that
  once and continue. Do not retry the same id.
- `3`: this script has no server for the environment. `staging` and `other`
  have no Jaeger base URL; record the gap.
- anything else: record the stderr line and treat Jaeger as unavailable.

Servers, selected by `--env`:

- test: `https://jaeger-test.yfinner.com`
- qa: `https://jaeger-qa.yfinner.com`
- prod: `https://jaeger.yfinner.com`

## Find traces by account

When there is no trace id but the reporter gave an account identifier and
a time, list that account's requests at the gateway:

```bash
python3 /home/roy/source/mynote/docs/wiki/LLM/skills/jaeger-trace/scripts/jaeger_search.py \
  --env <test|qa|prod> \
  --identifier <uid | customer id | customer number | account | trade account id> \
  --start "YYYY-MM-DD HH:MM" --end "YYYY-MM-DD HH:MM"
```

The window is `Asia/Shanghai` and at most 24 hours. The script tries the
identifier as `uid`, `customer_id`, `customer_number`, `account`, then
`trade_account_id` on `open-gateway.http` and stops at the first tag that
matches; `--key` fixes the tag and `--service` changes the entry service.
It prints one line per trace, failing ones first, with the trace id,
operation, HTTP status, and services. Tag values are never printed. Exit
code 4 means no trace matched. Order ids are not tagged and cannot be
searched.

Read a listed trace with `jaeger_trace.py`.

Times in the summary are `Asia/Shanghai`. A trace can name several services;
the service in the issue is not always the one that failed.
