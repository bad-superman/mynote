#!/usr/bin/env python3
"""Fetch one Jaeger trace and print a bounded, redacted summary.

The raw trace JSON can be hundreds of kilobytes and contains request
payloads, SQL, and account identifiers. This script writes that JSON only
when --raw-out is set, and the text it prints keeps a fixed tag allowlist.
"""

from __future__ import annotations

import argparse
import json
import re
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

# gRPC status codes by number. A reader shown a bare 13 guesses its name.
GRPC_CODES = (
    "OK", "Canceled", "Unknown", "InvalidArgument", "DeadlineExceeded",
    "NotFound", "AlreadyExists", "PermissionDenied", "ResourceExhausted",
    "FailedPrecondition", "Aborted", "OutOfRange", "Unimplemented",
    "Internal", "Unavailable", "DataLoss", "Unauthenticated",
)

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


def _grpc_errors(span: dict) -> str:
    """The gRPC code names in the span's status description, outermost first.

    Only the names are taken. The rest of the description is free text
    that can hold identifiers, and it stays in the raw file.
    """
    for tag in span.get("tags") or []:
        if isinstance(tag, dict) and tag.get("key") == "otel.status_description":
            found = re.findall(r"code = (\w+)", str(tag.get("value") or ""))
            return ">".join(name for name in found if name in GRPC_CODES)
    return ""


def _error_tags(span: dict) -> dict[str, str]:
    """The allowlisted tags of an error span, with the gRPC error spelled out."""
    tags = _tag_map(span)
    code = tags.get("rpc.grpc.status_code", "")
    if code.isdigit() and int(code) < len(GRPC_CODES):
        tags["rpc.grpc.status_code"] = f"{code}({GRPC_CODES[int(code)]})"
    named = _grpc_errors(span)
    if named:
        tags["grpc_error"] = named
    return tags


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


def analyze(trace: dict) -> dict:
    """The facts behind the summary: the call tree, bounds, and failure points."""
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

    depth: dict[str, int] = {}
    stack = [(root, 0) for root in roots]
    while stack:
        span, level = stack.pop()
        sid = str(span.get("spanID"))
        if sid in depth:
            continue
        depth[sid] = level
        stack.extend((child, level + 1) for child in children.get(sid, []))

    starts = [int(s["startTime"]) for s in spans if s.get("startTime") is not None]
    ends = [
        int(s["startTime"]) + int(s.get("duration") or 0)
        for s in spans
        if s.get("startTime") is not None
    ]

    services: list[str] = []
    for span in sorted(spans, key=lambda s: int(s.get("startTime") or 0)):
        name = _service(span, processes)
        if name not in services:
            services.append(name)

    errors = [span for span in spans if _is_error(_tag_map(span))]
    # The failure usually starts at the error span furthest from the entry
    # point; among equals, the one that started last.
    deepest = max(
        errors,
        key=lambda s: (depth.get(str(s.get("spanID")), 0), int(s.get("startTime") or 0)),
        default=None,
    )
    # A failed outgoing call with no span under it: the callee did not
    # answer, or is not traced. Either way the trace ends at the caller.
    unanswered = [
        span for span in errors
        if _tag_map(span).get("span.kind", "").lower() == "client"
        and not children.get(str(span.get("spanID")))
    ]
    return {
        "trace_id": trace_id,
        "spans": spans,
        "processes": processes,
        "children": children,
        "roots": roots,
        "start_us": min(starts) if starts else None,
        "end_us": max(ends) if ends else None,
        "services": services,
        "errors": errors,
        "deepest_error": deepest,
        "unanswered": unanswered,
    }


def service_of(span: dict | None, facts: dict) -> str | None:
    """The Jaeger service name of a span returned by analyze()."""
    return _service(span, facts["processes"]) if span else None


def summarize(trace: dict, *, env: str, max_tree_lines: int = 60) -> str:
    facts = analyze(trace)
    spans, processes, children = facts["spans"], facts["processes"], facts["children"]

    lines = [
        f"trace_id: {facts['trace_id']}",
        f"env: {env}",
        "found: yes",
        f"span_count: {len(spans)}",
    ]
    if facts["start_us"] is not None and facts["end_us"] is not None:
        lines.append(f"start: {_fmt_time(facts['start_us'])}")
        lines.append(f"end: {_fmt_time(facts['end_us'])}")
        lines.append(f"duration_ms: {(facts['end_us'] - facts['start_us']) / 1000:.1f}")

    lines.append("services: " + (", ".join(facts["services"]) if facts["services"] else "(none)"))

    errors = facts["errors"]
    lines.append(f"error_spans: {len(errors)}")
    for span in errors[:20]:
        tags = _error_tags(span)
        dur = int(span.get("duration") or 0) / 1000
        tag_text = " ".join(f"{k}={v}" for k, v in sorted(tags.items()))
        lines.append(
            f"- {_service(span, processes)} {span.get('operationName') or '?'} "
            f"{dur:.1f}ms {tag_text}".rstrip()
        )
    if len(errors) > 20:
        lines.append(f"- … {len(errors) - 20} more error spans omitted")

    deepest = facts["deepest_error"]
    lines.append(
        "deepest_error: "
        + (f"{_service(deepest, processes)} {deepest.get('operationName') or '?'}"
           if deepest else "none")
    )
    unanswered = facts["unanswered"]
    lines.append(f"unanswered_calls: {len(unanswered)}")
    for span in unanswered[:10]:
        dur = int(span.get("duration") or 0) / 1000
        lines.append(
            f"- {_service(span, processes)} -> {span.get('operationName') or '?'} {dur:.1f}ms"
        )

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

    for root in facts["roots"]:
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


def find_env(trace_id: str, *, envs: tuple[str, ...] = ("qa", "test", "prod"),
             timeout: float = 20.0) -> dict:
    """Ask each Jaeger server for the trace and stop at the first that has it.

    A trace id lives on one server only, so the server that answers is the
    environment the request ran in.
    """
    unreachable: list[str] = []
    for env in envs:
        try:
            status, doc = fetch_trace(ENV_BASES[env], trace_id, timeout=timeout)
        except OSError:
            # URLError for a refused or failed connection, TimeoutError for
            # a server that stops answering while the body is being read.
            unreachable.append(env)
            continue
        if is_not_found(status, doc) or doc is None or status >= 400:
            if not is_not_found(status, doc):
                unreachable.append(env)
            continue
        trace = unwrap_trace(doc)
        if trace is not None:
            return {"env": env, "trace": trace, "unreachable": unreachable}
    return {"env": None, "trace": None, "unreachable": unreachable}


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
