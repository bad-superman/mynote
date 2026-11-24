#!/usr/bin/env python3
"""Find Jaeger traces for one account identifier inside a time window.

Used when a reporter has no trace id. The search starts at the public
gateway, whose spans carry the account identifiers, and prints one redacted
line per trace. Tag values never reach stdout; pick a trace id from the list
and read it with jaeger_trace.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import jaeger_trace as jt

ENTRY_SERVICE = "open-gateway.http"

# Identifier tags present on gateway spans, tried in this order. Order ids
# are not tagged on gateway spans and cannot be searched.
IDENTIFIER_KEYS = ("uid", "customer_id", "customer_number", "account", "trade_account_id")

MAX_WINDOW_SECONDS = 24 * 3600
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")

EXIT_USAGE = 2
EXIT_NOT_FOUND = 4
EXIT_FETCH = 1


def parse_local_time(text: str) -> int:
    """Parse an Asia/Shanghai wall-clock time into epoch microseconds."""
    value = text.strip()
    for fmt in TIME_FORMATS:
        try:
            naive = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return int(naive.replace(tzinfo=jt.SHANGHAI).timestamp() * 1_000_000)
    raise ValueError(f"unrecognized time {text!r}; use 'YYYY-MM-DD HH:MM[:SS]' in Asia/Shanghai")


def search_url(base: str, *, service: str, key: str, value: str,
               start_us: int, end_us: int, limit: int) -> str:
    query = urllib.parse.urlencode({
        "service": service,
        "tags": json.dumps({key: value}, separators=(",", ":")),
        "start": start_us,
        "end": end_us,
        "limit": limit,
    })
    return f"{base}/api/traces?{query}"


def fetch_json(url: str, *, timeout: float = 30.0) -> tuple[int, dict | None]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    try:
        doc = json.loads(body.decode("utf-8", errors="replace")) if body else None
    except json.JSONDecodeError:
        doc = None
    return status, doc if isinstance(doc, dict) else None


def describe(trace: dict, *, entry_service: str) -> dict:
    """Reduce one trace to the fields that are safe to print."""
    spans = [s for s in (trace.get("spans") or []) if isinstance(s, dict)]
    processes = trace.get("processes") if isinstance(trace.get("processes"), dict) else {}
    span_ids = {str(s.get("spanID")) for s in spans}

    def has_parent(span: dict) -> bool:
        return any(
            isinstance(ref, dict) and ref.get("refType") == "CHILD_OF"
            and str(ref.get("spanID")) in span_ids
            for ref in span.get("references") or []
        )

    ordered = sorted(spans, key=lambda s: int(s.get("startTime") or 0))
    entry = next(
        (s for s in ordered if jt._service(s, processes) == entry_service and not has_parent(s)),
        None,
    ) or next((s for s in ordered if not has_parent(s)), None) or (ordered[0] if ordered else {})

    services: list[str] = []
    error_services: list[str] = []
    for span in ordered:
        name = jt._service(span, processes)
        if name not in services:
            services.append(name)
        if jt._is_error(jt._tag_map(span)) and name not in error_services:
            error_services.append(name)

    starts = [int(s["startTime"]) for s in spans if s.get("startTime") is not None]
    ends = [int(s["startTime"]) + int(s.get("duration") or 0)
            for s in spans if s.get("startTime") is not None]
    entry_tags = jt._tag_map(entry) if entry else {}
    operation = str(entry.get("operationName") or "?") if entry else "?"
    if len(operation) > 80:
        operation = operation[:79] + "…"
    return {
        "trace_id": str(trace.get("traceID") or (spans[0].get("traceID") if spans else "")),
        "start_us": min(starts) if starts else 0,
        "duration_ms": (max(ends) - min(starts)) / 1000 if starts else 0.0,
        "method": entry_tags.get("http.method", ""),
        "operation": operation,
        "http_status": entry_tags.get("http.status_code", ""),
        "services": services,
        "error_services": error_services,
    }


def render(rows: list[dict], *, env: str, entry_service: str, matched_key: str,
           start_us: int, end_us: int, max_lines: int) -> str:
    # Failing traces first, newest first inside each group.
    ordered = sorted(rows, key=lambda r: (not r["error_services"], -r["start_us"]))
    failing = sum(1 for r in rows if r["error_services"])
    lines = [
        f"env: {env}",
        f"entry_service: {entry_service}",
        f"window: {jt._fmt_time(start_us)} ~ {jt._fmt_time(end_us)}",
        f"matched_key: {matched_key}",
        f"trace_count: {len(rows)}",
        f"traces_with_errors: {failing}",
        "traces:",
    ]
    for row in ordered[:max_lines]:
        status = f" http={row['http_status']}" if row["http_status"] else ""
        method = f"{row['method']} " if row["method"] else ""
        errors = ",".join(row["error_services"]) or "-"
        lines.append(
            f"- {row['trace_id']} {jt._fmt_time(row['start_us'])} "
            f"{row['duration_ms']:.1f}ms {method}{row['operation']}{status} "
            f"error_services={errors} services={','.join(row['services'])}"
        )
    if len(ordered) > max_lines:
        lines.append(f"… {len(ordered) - max_lines} more traces omitted; narrow the window")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List Jaeger traces for one account identifier in a time window.")
    parser.add_argument("--env", required=True, choices=sorted(jt.ENV_BASES))
    parser.add_argument("--identifier", required=True,
                        help="uid, customer id/number, account, or trade account id")
    parser.add_argument("--start", required=True, help="'YYYY-MM-DD HH:MM[:SS]' Asia/Shanghai")
    parser.add_argument("--end", required=True, help="'YYYY-MM-DD HH:MM[:SS]' Asia/Shanghai")
    parser.add_argument("--key", choices=IDENTIFIER_KEYS,
                        help="Search only this tag instead of trying each identifier tag.")
    parser.add_argument("--service", default=ENTRY_SERVICE)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-lines", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    identifier = args.identifier.strip()
    if not identifier or any(ch.isspace() for ch in identifier):
        print("identifier must be a single token", file=sys.stderr)
        return EXIT_USAGE
    try:
        start_us = parse_local_time(args.start)
        end_us = parse_local_time(args.end)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    if end_us <= start_us:
        print("--end must be later than --start", file=sys.stderr)
        return EXIT_USAGE
    if end_us - start_us > MAX_WINDOW_SECONDS * 1_000_000:
        print("window is longer than 24 hours; narrow it", file=sys.stderr)
        return EXIT_USAGE

    base = jt.ENV_BASES[args.env]
    keys = (args.key,) if args.key else IDENTIFIER_KEYS
    for key in keys:
        url = search_url(base, service=args.service, key=key, value=identifier,
                         start_us=start_us, end_us=end_us, limit=args.limit)
        try:
            status, doc = fetch_json(url, timeout=args.timeout)
        except urllib.error.URLError as exc:
            print(f"jaeger search failed: {exc.reason}", file=sys.stderr)
            return EXIT_FETCH
        if doc is None or status >= 400:
            print(f"jaeger returned HTTP {status}", file=sys.stderr)
            return EXIT_FETCH
        traces = [t for t in (doc.get("data") or []) if isinstance(t, dict)]
        if not traces:
            continue
        rows = [describe(t, entry_service=args.service) for t in traces]
        sys.stdout.write(render(
            rows, env=args.env, entry_service=args.service, matched_key=key,
            start_us=start_us, end_us=end_us, max_lines=args.max_lines,
        ))
        return 0

    print(
        f"env: {args.env}\nentry_service: {args.service}\n"
        f"window: {jt._fmt_time(start_us)} ~ {jt._fmt_time(end_us)}\n"
        f"trace_count: 0\n"
        f"reason: no trace carries this identifier in the window "
        f"(tried {', '.join(keys)}), or the traces are no longer retained\n",
        end="",
    )
    return EXIT_NOT_FOUND


if __name__ == "__main__":
    sys.exit(main())
