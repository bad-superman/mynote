#!/usr/bin/env python3
"""Fetch one Jaeger trace and print a bounded, redacted summary.

The raw trace JSON can be hundreds of kilobytes and contains request
payloads, SQL, and account identifiers. This script writes that JSON only
when --raw-out is set, and the text it prints keeps a fixed tag allowlist.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ENV_BASES = {
    "test": "https://jaeger-test.yfinner.com",
    "qa": "https://jaeger-qa.yfinner.com",
    "prod": "https://jaeger.yfinner.com",
}

# Anything not listed here stays in the raw file and never reaches stdout.
# http.url, sql, headers, and account identifiers are intentionally absent.
TAG_ALLOWLIST = frozenset({
    "span.kind",
    "otel.status_code",
    "http.status_code",
    "http.method",
    "rpc.system",
    "rpc.service",
    "rpc.method",
    "rpc.grpc.status_code",
    "db.system",
    "db.operation",
    "peer.service",
    "error",
})

SHANGHAI = ZoneInfo("Asia/Shanghai")

EXIT_USAGE = 2
EXIT_UNSUPPORTED_ENV = 3
EXIT_NOT_FOUND = 4
EXIT_FETCH = 1


class TraceNotFound(Exception):
    pass


def unwrap_trace(doc: dict) -> dict | None:
    if isinstance(doc, dict) and isinstance(doc.get("spans"), list):
        return doc
    data = doc.get("data") if isinstance(doc, dict) else None
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict) and isinstance(data.get("spans"), list):
        return data
    return None


def is_not_found(status: int, doc: dict | None) -> bool:
    if status == 404:
        return True
    if not isinstance(doc, dict):
        return False
    for err in doc.get("errors") or []:
        if isinstance(err, dict) and err.get("code") == 404:
            return True
    return False


def _fmt_time(us: int) -> str:
    """Jaeger startTime and duration are both microseconds."""
    dt = datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc)
    return dt.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " Asia/Shanghai"


def _tag_map(span: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in span.get("tags") or []:
        if not isinstance(tag, dict):
            continue
        key = str(tag.get("key") or "")
        if key not in TAG_ALLOWLIST:
            continue
        value = tag.get("value")
        text = "" if value is None else str(value)
        if len(text) > 80:
            text = text[:79] + "…"
        out[key] = text
    return out


def _is_error(tags: dict[str, str]) -> bool:
    if tags.get("error", "").lower() == "true":
        return True
    status = tags.get("otel.status_code", "").upper()
    if status in {"ERROR", "STATUS_CODE_ERROR"}:
        return True
    http = tags.get("http.status_code")
    if http and http.isdigit() and int(http) >= 400:
        return True
    grpc = tags.get("rpc.grpc.status_code")
    if grpc not in (None, "", "0", "OK"):
        return True
    return False


def _service(span: dict, processes: dict) -> str:
    proc = processes.get(span.get("processID") or "", {})
    if isinstance(proc, dict) and proc.get("serviceName"):
        return str(proc["serviceName"])
    return "?"


def summarize(trace: dict, *, env: str, max_tree_lines: int = 60) -> str:
    spans = [s for s in (trace.get("spans") or []) if isinstance(s, dict)]
    processes = trace.get("processes") or {}
    if not isinstance(processes, dict):
        processes = {}
    trace_id = str(trace.get("traceID") or (spans[0].get("traceID") if spans else ""))

    by_id = {str(s.get("spanID")): s for s in spans if s.get("spanID")}
    children: dict[str, list[dict]] = {sid: [] for sid in by_id}
    roots: list[dict] = []
    for span in spans:
        parent = None
        for ref in span.get("references") or []:
            if isinstance(ref, dict) and ref.get("refType") == "CHILD_OF":
                parent = str(ref.get("spanID") or "")
                break
        if parent and parent in children and parent != str(span.get("spanID")):
            children[parent].append(span)
        else:
            roots.append(span)
    for kids in children.values():
        kids.sort(key=lambda s: int(s.get("startTime") or 0))
    roots.sort(key=lambda s: int(s.get("startTime") or 0))

    starts = [int(s["startTime"]) for s in spans if s.get("startTime") is not None]
    ends = [
        int(s["startTime"]) + int(s.get("duration") or 0)
        for s in spans
        if s.get("startTime") is not None
    ]

    lines = [
        f"trace_id: {trace_id}",
        f"env: {env}",
        "found: yes",
        f"span_count: {len(spans)}",
    ]
    if starts and ends:
        lines.append(f"start: {_fmt_time(min(starts))}")
        lines.append(f"end: {_fmt_time(max(ends))}")
        lines.append(f"duration_ms: {(max(ends) - min(starts)) / 1000:.1f}")

    seen: list[str] = []
    for span in sorted(spans, key=lambda s: int(s.get("startTime") or 0)):
        name = _service(span, processes)
        if name not in seen:
            seen.append(name)
    lines.append("services: " + (", ".join(seen) if seen else "(none)"))

    errors = []
    for span in spans:
        tags = _tag_map(span)
        if _is_error(tags):
            errors.append(span)
    lines.append(f"error_spans: {len(errors)}")
    for span in errors[:20]:
        tags = _tag_map(span)
        dur = int(span.get("duration") or 0) / 1000
        tag_text = " ".join(f"{k}={v}" for k, v in sorted(tags.items()))
        lines.append(
            f"- {_service(span, processes)} {span.get('operationName') or '?'} "
            f"{dur:.1f}ms {tag_text}".rstrip()
        )
    if len(errors) > 20:
        lines.append(f"- … {len(errors) - 20} more error spans omitted")

    lines.append("tree:")
    emitted = 0

    def walk(span: dict, depth: int) -> None:
        nonlocal emitted
        if emitted >= max_tree_lines:
            return
        dur = int(span.get("duration") or 0) / 1000
        mark = " !" if _is_error(_tag_map(span)) else ""
        lines.append(
            f"{'  ' * depth}{_service(span, processes)} "
            f"{span.get('operationName') or '?'} {dur:.1f}ms{mark}"
        )
        emitted += 1
        for child in children.get(str(span.get("spanID")), []):
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)
        if emitted >= max_tree_lines:
            break
    if emitted < len(spans):
        lines.append(f"… tree truncated at {max_tree_lines} lines ({len(spans)} spans)")
    return "\n".join(lines) + "\n"


def fetch_trace(base: str, trace_id: str, *, timeout: float = 20.0) -> tuple[int, dict | None]:
    url = f"{base}/api/traces/{trace_id}"
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
    if not isinstance(doc, dict):
        doc = None
    return status, doc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a redacted Jaeger trace summary.")
    parser.add_argument("--env", required=True, choices=sorted(ENV_BASES))
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--raw-out", help="Write the unmodified trace JSON here.")
    parser.add_argument("--max-tree-lines", type=int, default=60)
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    trace_id = args.trace_id.strip()
    if not trace_id or any(ch.isspace() for ch in trace_id):
        print("trace id must be a single token", file=sys.stderr)
        return EXIT_USAGE
    base = ENV_BASES[args.env]
    try:
        status, doc = fetch_trace(base, trace_id, timeout=args.timeout)
    except urllib.error.URLError as exc:
        print(f"jaeger fetch failed: {exc.reason}", file=sys.stderr)
        return EXIT_FETCH
    if is_not_found(status, doc):
        print(
            f"trace_id: {trace_id}\nenv: {args.env}\nfound: no\n"
            "reason: trace not found or no longer retained\n",
            end="",
        )
        return EXIT_NOT_FOUND
    if doc is None or status >= 400:
        print(f"jaeger returned HTTP {status}", file=sys.stderr)
        return EXIT_FETCH
    trace = unwrap_trace(doc)
    if trace is None:
        print("jaeger response did not contain a trace", file=sys.stderr)
        return EXIT_FETCH
    if args.raw_out:
        with open(args.raw_out, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
    sys.stdout.write(summarize(trace, env=args.env, max_tree_lines=args.max_tree_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
