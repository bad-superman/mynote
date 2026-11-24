#!/usr/bin/env python3
"""Service catalog lookups for the issue desk, backed by sourceinsight.

The desk uses this to find which service owns a feature. It prints service
names and descriptions, and for a text search only how many times the text
occurs and in which files. Source lines never leave this script: the desk
does not read code, and the source is confidential.

sourceinsight indexes production code only. A catalog name is not a deploy
name; convert it with find_service.py before submitting.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://sourceinsight.yfinner.com/mcp"
AUTH_VAR = "SOURCEINSIGHT_AUTHORIZATION"
ENV_FILE = Path("/home/roy/.hermes/profiles/issue-desk/.env")
MAX_SEARCH_SERVICES = 3
MAX_PATHS = 3
MAX_HITS = 20


class CatalogError(Exception):
    def __init__(self, message: str, code: int = 6):
        super().__init__(message)
        self.code = code


def authorization(environ: dict | None = None, env_file: Path = ENV_FILE) -> str:
    """The gateway does not hand profile secrets to the terminal, so fall back to the file."""
    environ = os.environ if environ is None else environ
    value = (environ.get(AUTH_VAR) or "").strip()
    if value:
        return value
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(AUTH_VAR + "="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    except OSError:
        pass
    raise CatalogError(f"{AUTH_VAR} is not set and not in {env_file}")


def parse_response(body: str) -> dict:
    """The server answers with JSON or with one server-sent event carrying JSON."""
    text = body.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise CatalogError("sourceinsight returned no JSON-RPC message")


def call_tool(name: str, arguments: dict, *, auth: str, timeout: float = 30.0) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
    request = urllib.request.Request(
        URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Authorization": auth},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            message = parse_response(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise CatalogError(f"sourceinsight answered HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CatalogError(f"sourceinsight is unreachable: {exc}") from None
    except json.JSONDecodeError as exc:
        raise CatalogError(f"sourceinsight returned invalid JSON: {exc}") from None
    if "error" in message:
        raise CatalogError(f"sourceinsight error: {message['error'].get('message', 'unknown')}")
    result = message.get("result") or {}
    try:
        data = json.loads(result["content"][0]["text"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise CatalogError(f"sourceinsight returned an unexpected result for {name}") from None
    if result.get("isError") or (isinstance(data, dict) and data.get("error")):
        detail = data.get("error") if isinstance(data, dict) else "tool error"
        raise CatalogError(f"sourceinsight {name}: {detail}", code=4)
    return data


def list_catalog(*, line: str | None, call) -> dict:
    lines = [item["name"] for item in call("list_biz_lines", {}).get("biz_lines", [])
             if item.get("service_count")]
    if line:
        wanted = [name for name in lines if line.strip().lower() in name.lower()]
        if not wanted:
            raise CatalogError(
                f"no business line contains {line!r}; lines: {', '.join(lines)}", code=4)
        lines = wanted
    catalog = []
    for name in lines:
        services = call("list_services", {"biz_line": name}).get("services", [])
        catalog.append({
            "biz_line": name,
            "services": [{"catalog_name": s.get("service_name") or s.get("repo_id"),
                          "description": s.get("description") or ""} for s in services],
        })
    return {"ok": True, "source": "sourceinsight (production code)", "biz_lines": catalog}


def search_text(*, text: str, services: list[str], call) -> dict:
    text = text.strip()
    if len(text) < 3:
        raise CatalogError("--text must be at least 3 characters", code=2)
    if not services or len(services) > MAX_SEARCH_SERVICES:
        raise CatalogError(f"give 1 to {MAX_SEARCH_SERVICES} --service names", code=2)
    results = []
    for service in services:
        try:
            data = call("search", {"repo_id": service, "query": text, "max_hits": MAX_HITS})
        except CatalogError as exc:
            if exc.code != 4:
                raise
            results.append({"catalog_name": service, "error": str(exc)})
            continue
        hits = data.get("hits") or []
        paths: list[str] = []
        for hit in hits:
            path = str(hit.get("path") or "")
            if path and path not in paths:
                paths.append(path)
        results.append({
            "catalog_name": service,
            "occurrences": int(data.get("count") or len(hits)),
            "more": bool(data.get("truncated")),
            "files": paths[:MAX_PATHS],
        })
    return {"ok": True, "source": "sourceinsight (production code)", "text": text,
            "results": results}


def main(argv: list[str] | None = None, *, call=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--line", help="Only business lines containing this word.")
    parser.add_argument("--text", help="Count occurrences of this exact text in --service.")
    parser.add_argument("--service", action="append", default=[],
                        help=f"Catalog name to search; up to {MAX_SEARCH_SERVICES}.")
    args = parser.parse_args(argv)
    try:
        if call is None:
            auth = authorization()
            call = lambda name, arguments: call_tool(name, arguments, auth=auth)  # noqa: E731
        if args.text:
            result = search_text(text=args.text, services=args.service, call=call)
        elif args.service:
            raise CatalogError("--service needs --text", code=2)
        else:
            result = list_catalog(line=args.line, call=call)
    except CatalogError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return exc.code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
