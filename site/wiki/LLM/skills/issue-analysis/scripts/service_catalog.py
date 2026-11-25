#!/usr/bin/env python3
"""Find which service owns a feature, using the sourceinsight MCP server.

Intake uses this to locate the service of an issue that arrived with a
description only. It prints service names and descriptions, the directory
layout of a service, and for a text search how many times the text occurs
and in which files. Source lines never leave this script: locating a
service does not need them, and the source is confidential.

sourceinsight indexes production code only. A catalog name is not a deploy
name; convert it with find_service.py, and check the result with
deployed_version.py --expect-path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://sourceinsight.yfinner.com/mcp"
AUTH_VAR = "SOURCEINSIGHT_AUTHORIZATION"
ENV_FILE = Path("/home/roy/.hermes/profiles/issue-intake/.env")
MAX_SEARCH_SERVICES = 3
MAX_PATHS = 3
MAX_HITS = 20
TREE_DEPTH = 3
MAX_TREE_DIRECTORIES = 300
# Listed, but not walked: they hold dependencies, not the service's own code.
DEPENDENCY_DIRECTORIES = frozenset({"third_party", "vendor", "node_modules"})
# A board card may run this script a fixed number of times. Locating a
# service takes about six lookups; a card that needs more is searching
# without a lead and should ask the reporter instead.
MAX_LOOKUPS_PER_CARD = 12
TASK_VAR = "HERMES_KANBAN_TASK"
BUDGET_DIR = Path("/home/roy/dev/.hermes-issue-analysis/.catalog-lookups")
EXIT_BUDGET = 3


class CatalogError(Exception):
    def __init__(self, message: str, code: int = 6):
        super().__init__(message)
        self.code = code


def authorization(environ: dict | None = None, env_file: Path = ENV_FILE) -> str:
    """Hermes does not hand profile secrets to the terminal, so fall back to the file."""
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


def _list(call, service: str, path: str, depth: int) -> tuple[list[dict], bool]:
    data = call("list_tree", {"repo_id": service, "path": path, "depth": depth})
    entries = [e for e in data.get("entries") or [] if isinstance(e, dict) and e.get("path")]
    return entries, bool(data.get("truncated"))


def tree(*, service: str, path: str | None, call) -> dict:
    """The directory layout of one service: module names, not code.

    Without a path it lists directories three levels deep. With a path it
    lists that one directory, file names included.
    """
    base = {"ok": True, "source": "sourceinsight (production code)", "service": service}
    if path and path.strip("/. "):
        where = path.strip().strip("/")
        entries, cut = _list(call, service, where, 1)
        return {**base, "path": where,
                "directories": sorted(e["path"] for e in entries if e.get("type") == "dir"),
                "files": sorted(e["path"] for e in entries if e.get("type") != "dir"),
                "more": cut}

    entries, cut = _list(call, service, ".", TREE_DEPTH)
    directories = {e["path"] for e in entries if e.get("type") == "dir"}
    unfinished: list[str] = []
    if cut:
        # The server stops at a fixed number of entries, files included.
        # Ask again one top-level directory at a time.
        top, _ = _list(call, service, ".", 1)
        directories = set()
        for entry in top:
            if entry.get("type") != "dir":
                continue
            directories.add(entry["path"])
            if entry["path"] in DEPENDENCY_DIRECTORIES:
                continue
            below, below_cut = _list(call, service, entry["path"], TREE_DEPTH - 1)
            directories.update(e["path"] for e in below if e.get("type") == "dir")
            if below_cut:
                unfinished.append(entry["path"])
    listed = sorted(directories)
    result = {**base, "path": ".", "depth": TREE_DEPTH,
              "directories": listed[:MAX_TREE_DIRECTORIES], "more": unfinished}
    if unfinished or len(listed) > MAX_TREE_DIRECTORIES:
        result["hint"] = "The listing is incomplete. Look inside one directory with --path <directory>."
    return result


def spend(task: str, budget_dir: Path = BUDGET_DIR) -> int:
    """Count one lookup against a card and return how many it has left."""
    path = budget_dir / (re.sub(r"[^A-Za-z0-9_.-]", "_", task) + ".json")
    try:
        used = int(json.loads(path.read_text(encoding="utf-8"))["used"])
    except (OSError, ValueError, KeyError, TypeError):
        used = 0
    if used >= MAX_LOOKUPS_PER_CARD:
        raise CatalogError(
            f"This card has used its {MAX_LOOKUPS_PER_CARD} lookups. Decide with what you "
            "have: record the service, or block with kind=needs_input and ask the reporter "
            "one specific question.", code=EXIT_BUDGET)
    budget_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"used": used + 1, "limit": MAX_LOOKUPS_PER_CARD}) + "\n",
                    encoding="utf-8")
    return MAX_LOOKUPS_PER_CARD - used - 1


def main(argv: list[str] | None = None, *, call=None, environ: dict | None = None,
         budget_dir: Path = BUDGET_DIR) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--line", help="Only business lines containing this word.")
    parser.add_argument("--text", help="Count occurrences of this exact text in --service.")
    parser.add_argument("--tree", action="store_true",
                        help="Print the directory layout of one --service.")
    parser.add_argument("--path", help="With --tree: list this one directory, files included.")
    parser.add_argument("--service", action="append", default=[],
                        help=f"Catalog name; one for --tree, up to {MAX_SEARCH_SERVICES} for --text.")
    args = parser.parse_args(argv)
    task = ((os.environ if environ is None else environ).get(TASK_VAR) or "").strip()
    left: list[int] = []
    try:
        if call is None:
            auth = authorization()
            call = lambda name, arguments: call_tool(name, arguments, auth=auth)  # noqa: E731
        if task:
            # Charged when the server is first asked, so a usage error is free.
            ask = call

            def call(name, arguments):
                if not left:
                    left.append(spend(task, budget_dir))
                return ask(name, arguments)
        if args.tree:
            if len(args.service) != 1:
                raise CatalogError("--tree needs exactly one --service", code=2)
            result = tree(service=args.service[0], path=args.path, call=call)
        elif args.path:
            raise CatalogError("--path needs --tree", code=2)
        elif args.text:
            result = search_text(text=args.text, services=args.service, call=call)
        elif args.service:
            raise CatalogError("--service needs --tree or --text", code=2)
        else:
            result = list_catalog(line=args.line, call=call)
    except CatalogError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return exc.code
    if left:
        result["lookups_left"] = left[0]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
