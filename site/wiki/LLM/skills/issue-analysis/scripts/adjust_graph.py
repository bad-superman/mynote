#!/usr/bin/env python3
"""Let intake trim or extend the fixed issue-analysis graph.

The submit script always builds the full graph, so an intake that never
calls this still gets the complete investigation. Intake calls it for two
cases only:

- the reporter asked what happened, not why: archive the code card;
- more than one service failed: add a runtime card per extra service.

State is kept in <evidence-dir>/route.json so a retry does not add cards
twice and later stages can read which route was taken.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import submit_issue as si

ROUTES = ("why", "fact")
MAX_EXTRA_RUNTIME = 2
OPEN_BEFORE_START = {"todo", "ready", "blocked", "triage"}
CLOSED = {"done", "archived"}

EXIT_USAGE = 2
EXIT_STATE = 3


class AdjustError(Exception):
    def __init__(self, message: str, code: int = EXIT_STATE):
        super().__init__(message)
        self.code = code


def parse_root(shown: dict) -> dict:
    """Read stage ids, evidence dir, and the original issue from the root card."""
    graph: dict[str, str] = {}
    evidence = None
    for item in shown.get("comments") or []:
        body = str(item.get("body") or "") if isinstance(item, dict) else ""
        if not body.startswith("## Stage\nroot\n"):
            continue
        match = re.search(r"^## Evidence Directory\n(.+)$", body, flags=re.M)
        if match:
            evidence = match.group(1).strip()
        for stage, task_id in re.findall(r"^- (\w+): (t_[0-9a-f]+)\s*$", body, flags=re.M):
            graph[stage] = task_id
    missing = [stage for stage in si.ORDER if stage not in graph]
    if missing or not evidence:
        raise AdjustError(
            "root card has no graph comment from submit_issue.py "
            f"(missing: {', '.join(missing) or 'evidence directory'})")
    body = str((shown.get("task") or {}).get("body") or "")
    marker = "## Original Issue\n"
    if marker not in body:
        raise AdjustError("root card body has no '## Original Issue' section")
    original = body.split(marker, 1)[1]
    sections = si.parse_sections(original)
    return {
        "graph": graph,
        "evidence": Path(evidence),
        "original": original,
        "service": si.field_value(sections["Service"]),
        "environment": si.field_value(sections["Environment"]),
    }


def service_slug(service: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", service)


def extra_runtime_body(service: str, root_id: str, evidence: Path, original: str) -> str:
    return (
        "## Stage\nruntime\n\n"
        f"## Target Service\n{service}\n\n"
        f"## Root Task\n{root_id}\n\n"
        f"## Evidence Directory\n{evidence}\n\n"
        f"## Report\nruntime-{service_slug(service)}.md\n\n"
        "## Deployed Commit\n"
        "The commit in intake.md belongs to the issue's main service, not to this one. "
        "Do not quote it as this service's version.\n\n"
        "## Rules\n"
        "Investigate only the Target Service, inside the issue's time window. "
        "Report what its logs, metrics, and trace spans show; say so plainly when it is healthy. "
        "Write the Report file named above, not runtime.md.\n\n"
        f"## Original Issue\n{original.rstrip()}\n"
    )


def _comment_once(task_id: str, text: str, shown: dict, *, board: str, env: dict, hermes: str) -> None:
    for item in shown.get("comments") or []:
        if isinstance(item, dict) and str(item.get("body") or "").strip() == text.strip():
            return
    done = si._run([hermes, "kanban", "--board", board, "comment", task_id, text], env)
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).decode("utf-8", errors="replace").strip()
        raise AdjustError(detail or f"comment on {task_id} failed", code=1)


def adjust(root_id: str, *, route: str | None, add_runtime: list[str],
           board: str = si.BOARD, workspace: str = si.WORKSPACE,
           env: dict | None = None, hermes: str = "hermes",
           verify_service: bool = True, service_lookup=None) -> dict:
    if route is not None and route not in ROUTES:
        raise AdjustError(f"route must be one of {', '.join(ROUTES)}", code=EXIT_USAGE)
    env = dict(os.environ if env is None else env)
    kw = {"board": board, "env": env, "hermes": hermes}

    root = si.show_task(root_id, **kw)
    if root["task"]["status"] in CLOSED:
        raise AdjustError(f"root {root_id} is already {root['task']['status']}")
    info = parse_root(root)
    graph, evidence = info["graph"], info["evidence"]

    verifier = si.show_task(graph["verifier"], **kw)
    if verifier["task"]["status"] not in OPEN_BEFORE_START:
        raise AdjustError(
            f"verifier {graph['verifier']} is {verifier['task']['status']}; "
            "the graph can only be adjusted before verification starts")
    synthesizer = si.show_task(graph["synthesizer"], **kw)

    state_path = evidence / "route.json"
    state = {"route": "why", "archived": [], "extra_runtime": {}}
    if state_path.exists():
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state.update({k: loaded[k] for k in state if k in loaded})

    wanted: list[str] = []
    for service in add_runtime:
        name = service.strip()
        if not name or name == info["service"] or name in wanted:
            continue
        wanted.append(name)
    new_services = [name for name in wanted if name not in state["extra_runtime"]]
    if len(state["extra_runtime"]) + len(new_services) > MAX_EXTRA_RUNTIME:
        raise AdjustError(
            f"at most {MAX_EXTRA_RUNTIME} extra runtime services per issue; "
            f"already added: {', '.join(state['extra_runtime']) or 'none'}", code=EXIT_USAGE)
    if route == "fact" and (wanted or state["extra_runtime"]):
        raise AdjustError(
            "route fact cannot be combined with extra runtime services; "
            "a cross-service failure needs the code stage", code=EXIT_USAGE)
    if route == "why" and state["route"] == "fact":
        raise AdjustError("the code card is already archived; route fact cannot be undone here")
    if verify_service:
        for name in new_services:
            try:
                si.check_service(name, info["environment"], lookup=service_lookup)
            except si.SubmitError as exc:
                raise AdjustError(str(exc), code=exc.code) from exc

    if route == "fact" and state["route"] != "fact":
        code = si.show_task(graph["code"], **kw)
        status = code["task"]["status"]
        if status != "archived":
            if status not in OPEN_BEFORE_START:
                raise AdjustError(
                    f"code card {graph['code']} is {status}; it can only be archived before it starts")
            # Archiving a scratch or worktree card deletes its directory.
            # Stage cards share dir:/home/roy/dev and must stay that way.
            if code["task"].get("workspace_kind") != "dir":
                raise AdjustError(
                    f"code card {graph['code']} workspace is "
                    f"{code['task'].get('workspace_kind')!r}, not 'dir'; refusing to archive")
            done = si._run([hermes, "kanban", "--board", board, "archive", graph["code"]], env)
            if done.returncode != 0:
                detail = (done.stderr or done.stdout).decode("utf-8", errors="replace").strip()
                raise AdjustError(detail or "archive code card failed", code=1)
        state["route"] = "fact"
        if graph["code"] not in state["archived"]:
            state["archived"].append(graph["code"])
        note = (
            "## Route\nfact\n\n"
            f"Intake archived the code card {graph['code']}: the reporter asked what happened, "
            "not why. There is no code.md and no analyzed commit for this issue. "
            "If runtime evidence cannot answer the question, list a code follow-up in `followups`.\n"
        )
        for task_id, shown in ((graph["verifier"], verifier), (graph["synthesizer"], synthesizer),
                               (root_id, root)):
            _comment_once(task_id, note, shown, **kw)

    for name in new_services:
        created = si.create_task({
            "title": f"收集 {name} 的运行时证据",
            "assignee": si.ASSIGNEE["runtime"],
            "workspace": workspace,
            "idempotency_key": f"issue:{root_id}:runtime:{name}",
            "body": extra_runtime_body(name, root_id, evidence, info["original"]),
            "skills": si.SKILLS["runtime"],
            "parents": [graph["intake"]],
        }, **kw)
        card = created["id"]
        for child in (graph["verifier"], graph["synthesizer"], root_id):
            parents = set(si.show_task(child, **kw).get("parents") or [])
            si.link_parent(card, child, existing=parents, **kw)
        state["extra_runtime"][name] = card
    if new_services:
        note = (
            "## Extra Runtime\n"
            + "\n".join(
                f"- {name}: {card} -> runtime-{service_slug(name)}.md"
                for name, card in state["extra_runtime"].items())
            + "\n\nThese cards cover services other than the issue's main service. "
            "Their reports carry no deployed commit.\n"
        )
        for task_id in (graph["verifier"], graph["synthesizer"], root_id):
            _comment_once(task_id, note, si.show_task(task_id, **kw), **kw)

    evidence.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    final = si.show_task(root_id, **kw)
    return {
        "root": root_id,
        "root_status": final["task"]["status"],
        "route": state["route"],
        "archived": state["archived"],
        "extra_runtime": state["extra_runtime"],
        "root_parents": final.get("parents") or [],
        "route_file": str(state_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trim or extend an issue-analysis graph.")
    parser.add_argument("--root", required=True, help="Root task id from the card's '## Root Task'.")
    parser.add_argument("--route", choices=ROUTES,
                        help="fact archives the code card; why keeps the full graph.")
    parser.add_argument("--add-runtime", action="append", default=[], metavar="SERVICE",
                        help="Exact deploy service name; repeat for a second service.")
    parser.add_argument("--board", default=si.BOARD)
    parser.add_argument("--workspace", default=si.WORKSPACE)
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument("--no-verify-service", action="store_true")
    args = parser.parse_args(argv)
    if args.route is None and not args.add_runtime:
        parser.error("give --route, --add-runtime, or both")
    try:
        result = adjust(
            args.root,
            route=args.route,
            add_runtime=args.add_runtime,
            board=args.board,
            workspace=args.workspace,
            hermes=args.hermes,
            verify_service=not args.no_verify_service,
        )
    except (AdjustError, si.SubmitError) as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
