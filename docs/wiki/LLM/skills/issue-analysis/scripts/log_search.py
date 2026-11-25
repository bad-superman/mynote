#!/usr/bin/env python3
"""Count and sample one service's log lines in a time window.

The runtime stage checks one statement at a time: how many lines contain a
text or belong to a trace, when the first and the last were written, and
what a few of them say. One call answers that, so the stage does not have
to look up the log cluster or parse the platform's JSON itself.

What the log platform was seen to do (qa, 2026-11-25), which this script
relies on:

- `--query` is an exact, case-sensitive substring of the raw line. A
  phrase must be in double quotes; a bare phrase with a space is rejected.
  There is no AND and no field syntax.
- `--trace-id` selects the lines of one trace, and then drops `--query`.
- An unknown service, cluster, or log source is a NOT_FOUND error, not an
  empty result.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

import deployed_version as dv

APPKEY = "youfi"
LOG_CLUSTERS = {
    "qa": "tx-sg-youfi-qa",
    "test": "tx-sg-youfi-test",
    "prod": "aws-hk-youfi-prod",
}
DEFAULT_SAMPLES = 3
MAX_SAMPLES = 10
MAX_ROWS = 500          # the most the platform returns for one search
LINE_WIDTH = 300
NEX_TIMEOUT = 60

EXIT_USAGE = 2
EXIT_NOT_FOUND = 4
EXIT_TOOL = 6

_TIME = "%Y-%m-%d %H:%M:%S"


def search(*, service: str, env: str, start: str, end: str,
           text: str | None = None, trace_id: str | None = None,
           samples: int = DEFAULT_SAMPLES, runner=None) -> dict:
    """Count the service's lines in the window that match, and sample them."""
    runner = runner or _default_runner
    environment = dv.normalize_env(env)
    window_start, window_end = dv.parse_window(start), dv.parse_window(end)
    if window_end <= window_start:
        raise dv.ResolveError(EXIT_USAGE, "end_must_be_after_start")
    if text is not None:
        if not text.strip():
            raise dv.ResolveError(EXIT_USAGE, "text_is_empty")
        if '"' in text or "\\" in text:
            raise dv.ResolveError(
                EXIT_USAGE, "text_has_a_quote_or_backslash",
                hint="search a part of the line without double quotes or backslashes")
    if trace_id is not None:
        trace_id = trace_id.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{16}|[0-9a-f]{32}", trace_id):
            raise dv.ResolveError(EXIT_USAGE, "trace_id_must_be_16_or_32_hex_digits")
    shown = max(1, min(samples, MAX_SAMPLES))

    cluster = LOG_CLUSTERS[environment]
    base = [
        dv.NEX, "logs", "platform", "search",
        "--appkey", APPKEY,
        "--service-name", service,
        "--cluster", cluster,
        "--log-source", f"{APPKEY}-{service}",
        "--from", str(int(window_start.timestamp() * 1000)),
        "--to", str(int(window_end.timestamp() * 1000)),
    ]

    def ask(*, rows: int, order: str = "asc", by_trace: bool = False,
            by_text: bool = False) -> tuple[int, list[dict]]:
        cmd = list(base)
        if by_trace:
            cmd += ["--trace-id", trace_id]
        if by_text:
            cmd += ["--query", f'"{text}"']
        cmd += ["--rows", str(rows), "--sort-order", order, "-o", "json"]
        doc = _call(runner, cmd, service=service, environment=environment)
        hits = [item for item in doc.get("hits") or [] if isinstance(item, dict)]
        return int(doc.get("total") or 0), hits

    result = {
        "ok": True,
        "service": service,
        "environment": environment,
        "log_cluster": cluster,
        "window_start": window_start.strftime(_TIME),
        "window_end": window_end.strftime(_TIME),
        "text": text,
        "trace_id": trace_id,
    }

    if trace_id and text is not None:
        trace_lines, fetched = ask(rows=MAX_ROWS, by_trace=True)
        matched = [item for item in fetched if text in _raw(item)]
        result["trace_lines"] = trace_lines
        total, first_hits = len(matched), matched[:shown]
        last_hit = matched[-1] if matched else None
        if trace_lines > len(fetched):
            result["note"] = (
                f"the trace has {trace_lines} lines here; only the first "
                f"{len(fetched)} were searched for the text")
    else:
        total, first_hits = ask(rows=shown, by_trace=bool(trace_id), by_text=text is not None)
        if total > len(first_hits):
            _, newest = ask(rows=1, order="desc", by_trace=bool(trace_id),
                            by_text=text is not None)
            last_hit = newest[0] if newest else None
        else:
            last_hit = first_hits[-1] if first_hits else None

    result["hits"] = total
    result["samples"] = [_sample(item) for item in first_hits]
    if total:
        result["first"] = _time(first_hits[0])
        result["last"] = _time(last_hit) if last_hit else _time(first_hits[-1])
    elif (trace_id or text is not None) and not result.get("trace_lines"):
        # No match means something only when the service logged at all.
        everything, _ = ask(rows=1)
        result["lines_in_window"] = everything
        if not everything:
            result["note"] = (
                "the service has no log lines at all in this window (not "
                "collected, expired, or not running); this search cannot decide "
                "anything")
    return result


def _call(runner, cmd: list[str], *, service: str, environment: str) -> dict:
    """Run one nex search. A request that timed out is tried once more."""
    error: dict = {}
    for _ in range(2):
        try:
            completed = runner(cmd, timeout=NEX_TIMEOUT)
        except subprocess.TimeoutExpired:
            error = {"code": "TIMEOUT", "message": f"no answer in {NEX_TIMEOUT}s"}
            continue
        if completed.returncode == 0 and (completed.stdout or b"").strip():
            return _load(completed.stdout)
        error = _error(completed)
        if error["code"] == "NOT_FOUND":
            raise dv.ResolveError(
                EXIT_NOT_FOUND, "no_log_config", service=service,
                environment=environment, detail=error["message"])
        if not (error.get("retryable") or "timeout" in error["message"].lower()):
            break
    raise dv.ResolveError(
        EXIT_TOOL, "nex_log_search_failed",
        nex_error=error.get("code", ""), detail=error.get("message", ""))


def _load(raw: bytes) -> dict:
    # Log lines can carry raw newlines and tabs, which JSON does not allow.
    clean = re.sub(rb"[\x00-\x1f]", b" ", raw)
    try:
        doc = json.loads(clean.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise dv.ResolveError(EXIT_TOOL, "nex_returned_bad_json", detail=str(exc)[:200])
    if not isinstance(doc, dict):
        raise dv.ResolveError(EXIT_TOOL, "nex_returned_non_object")
    return doc


def _error(completed) -> dict:
    text = (completed.stderr or completed.stdout or b"").decode("utf-8", errors="replace").strip()
    try:
        body = json.loads(text).get("error") or {}
    except (ValueError, AttributeError):
        body = {}
    return {
        "code": str(body.get("code") or f"exit_{completed.returncode}"),
        "message": str(body.get("message") or text[:300]),
        "retryable": bool(body.get("retryable")),
    }


def _raw(item: dict) -> str:
    return str(item.get("message") or item.get("msg") or "")


def _time(item: dict) -> str:
    return str(item.get("_logtime") or item.get("logtime") or item.get("ts") or "")


def _sample(item: dict) -> dict:
    text = " ".join(str(item.get("msg") or item.get("message") or "").split())
    if len(text) > LINE_WIDTH:
        text = text[:LINE_WIDTH] + "…"
    return {
        "time": _time(item),
        "level": str(item.get("level") or ""),
        "caller": str(item.get("caller") or ""),
        "line": text,
    }


def render(result: dict) -> str:
    lines = [
        f"service: {result['service']} ({result['environment']}, "
        f"log cluster {result['log_cluster']})",
        f"window: {result['window_start']} to {result['window_end']} Asia/Shanghai",
    ]
    if result.get("trace_id"):
        lines.append(f"trace_id: {result['trace_id']}")
    if result.get("text") is not None:
        lines.append(f'text: "{result["text"]}"')
    if "trace_lines" in result:
        lines.append(f"trace_lines: {result['trace_lines']}")
    lines.append(f"hits: {result['hits']}")
    if "lines_in_window" in result:
        lines.append(f"lines_in_window: {result['lines_in_window']}")
    if result["hits"]:
        lines.append(f"first: {result['first']}")
        lines.append(f"last: {result['last']}")
        lines.append(f"samples: {len(result['samples'])} of {result['hits']}, earliest first")
        for sample in result["samples"]:
            head = " ".join(part for part in (sample["time"], sample["level"], sample["caller"]) if part)
            lines.append(f"  {head} {sample['line']}")
    if result.get("note"):
        lines.append(f"note: {result['note']}")
    return "\n".join(lines)


def _default_runner(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def main(argv: list[str] | None = None, *, runner=None) -> int:
    parser = argparse.ArgumentParser(
        description="Count and sample one service's log lines in a time window.")
    parser.add_argument("--env", required=True, help="qa, test, or prod")
    parser.add_argument("--service", required=True, help="deploy service name")
    parser.add_argument("--start", required=True, help="'YYYY-MM-DD HH:MM[:SS]' Asia/Shanghai")
    parser.add_argument("--end", required=True, help="'YYYY-MM-DD HH:MM[:SS]' Asia/Shanghai")
    parser.add_argument("--text", help="exact, case-sensitive part of the log line")
    parser.add_argument("--trace-id", help="only the lines of this trace")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES,
                        help=f"lines to show, earliest first (default {DEFAULT_SAMPLES}, "
                             f"at most {MAX_SAMPLES})")
    args = parser.parse_args(argv)
    try:
        result = search(service=args.service, env=args.env, start=args.start, end=args.end,
                        text=args.text, trace_id=args.trace_id, samples=args.samples,
                        runner=runner)
    except dv.ResolveError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return exc.code
    print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
