#!/usr/bin/env python3
"""Single command surface for the issue-desk profile.

The desk talks to the reporter and hands the investigation to the
issue-analysis board. It does not investigate. Everything it is allowed to
run goes through one of these subcommands:

  trace    summarize one Jaeger trace (find the failing service)
  search   list Jaeger traces for an account identifier in a time window
  service  list deploy service names containing a keyword
  catalog  list services by business line, or count a text in a service's code
  now      print the current time in Asia/Shanghai and US Eastern
  submit   create the board graph and subscribe the current chat to it
  status   show where a submitted issue is, or print its final report
  answer   pass the reporter's reply to a blocked intake card
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JAEGER_SCRIPTS = HERE.parent.parent / "jaeger-trace" / "scripts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(JAEGER_SCRIPTS))

import adjust_graph as ag  # noqa: E402
import find_service  # noqa: E402
import submit_issue as si  # noqa: E402

# The gateway's terminal may not have ~/.local/bin on PATH.
HERMES = shutil.which("hermes") or "/home/roy/.local/bin/hermes"
REPORT_LIMIT = 9000
SERVICE_SOURCES = ("reporter", "trace", "identifier", "catalog")
WINDOW_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$")

# Stage cards the chat follows. Root and intake wake the desk so it can
# relay the report or ask for a missing input; the rest post one line each.
WAKE_STAGES = ("root", "intake")
PASSIVE_STAGES = ("code", "runtime", "verifier", "synthesizer")


class DeskError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def build_body(*, issue: str, service: str, environment: str, window_start: str,
               window_end: str, expected: str | None, trace_id: str | None,
               identifier: str | None, evidence: str | None, service_source: str) -> str:
    for label, value in (("--window-start", window_start), ("--window-end", window_end)):
        if not WINDOW_RE.match(value.strip()):
            raise DeskError(f"{label} must be 'YYYY-MM-DD HH:MM[:SS]' in Asia/Shanghai")
    if not issue.strip():
        raise DeskError("--issue is empty")
    issue_lines = [issue.strip()]
    if expected and expected.strip():
        issue_lines.append(f"\n期望行为：{expected.strip()}")
    evidence_lines = []
    if trace_id:
        evidence_lines.append(f"- trace_id: {trace_id.strip()}")
    if identifier:
        evidence_lines.append(f"- identifier: {identifier.strip()}")
    if evidence and evidence.strip():
        evidence_lines.append(f"- reporter: {evidence.strip()}")
    if not evidence_lines:
        # A trace or an account only helps to find the service. Once the
        # service is known the board works from the code and the logs.
        evidence_lines.append(
            "- no trace id or account identifier; work from the description, "
            "the deployed code, and the logs in the time window")
    evidence_lines.append(f"- service located by: {service_source}")
    return (
        "## Issue\n" + "\n".join(issue_lines) + "\n\n"
        f"## Service\n{service.strip()}\n\n"
        f"## Environment\n{environment.strip().lower()}\n\n"
        f"## Time Window\n{window_start.strip()} 至 {window_end.strip()} (Asia/Shanghai)\n\n"
        "## Evidence\n" + "\n".join(evidence_lines) + "\n"
    )


def default_key(body: str, session: dict) -> str:
    """Same reporter, same content -> same graph. A retry never duplicates."""
    seed = "\n".join([session.get("chat_id") or "", session.get("user_id") or "", body])
    return "desk:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]


def session_from_env(environ: dict) -> dict:
    """The gateway bridges the current chat into HERMES_SESSION_* variables."""
    get = lambda name: (environ.get(name) or "").strip()  # noqa: E731
    return {
        "platform": get("HERMES_SESSION_PLATFORM").lower(),
        "chat_id": get("HERMES_SESSION_CHAT_ID"),
        "chat_type": get("HERMES_SESSION_CHAT_TYPE").lower(),
        "thread_id": get("HERMES_SESSION_THREAD_ID"),
        "user_id": get("HERMES_SESSION_USER_ID"),
        "user_id_alt": get("HERMES_SESSION_USER_ID_ALT"),
    }


def subscription(task_id: str, session: dict, mode: str, board: str) -> dict | None:
    """The subscription row for the current chat, or None outside a chat."""
    if not session.get("platform") or not session.get("chat_id"):
        return None
    if session["platform"] in {"local", "cli", "tui"}:
        return None
    chat_type = {"direct": "dm", "private": "dm", "p2p": "dm"}.get(
        session.get("chat_type") or "", session.get("chat_type") or "")
    return {
        "board": board,
        "task_id": task_id,
        "platform": session["platform"],
        "chat_id": session["chat_id"],
        "chat_type": chat_type if chat_type in {"dm", "group", "channel", "thread"} else None,
        "thread_id": session.get("thread_id") or None,
        "user_id": session.get("user_id") or None,
        "user_id_alt": session.get("user_id_alt") or None,
        "delivery_mode": mode,
    }


# The row is written without an owner profile, which `hermes kanban
# notify-subscribe` cannot do. The desk is served through
# gateway.profile_routes and has no Feishu adapter of its own; the notifier
# skips a row owned by such a profile, and a row owned by `default` wakes
# the default profile. An unowned row is delivered by the gateway's own
# adapter, and the wake has no profile, so the route sends it to the desk.
SUBSCRIBE_SNIPPET = """
import json, os, sys
import hermes_cli
# Same bootstrap as the hermes launcher: top-level modules live in the checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(hermes_cli.__file__))))
from hermes_cli import kanban_db as kb
a = json.loads(sys.argv[1])
with kb.connect_closing(board=a["board"]) as conn:
    if kb.get_task(conn, a["task_id"]) is None:
        sys.exit(3)
    kb.add_notify_sub(
        conn, task_id=a["task_id"], platform=a["platform"], chat_id=a["chat_id"],
        thread_id=a["thread_id"], user_id=a["user_id"], user_id_alt=a["user_id_alt"],
        chat_type=a["chat_type"], notifier_profile=None,
        delivery_mode=a["delivery_mode"],
    )
    rows = [r for r in kb.list_notify_subs(conn, a["task_id"])
            if r.get("platform") == a["platform"] and r.get("chat_id") == a["chat_id"]]
    sys.exit(0 if rows and not any(r.get("notifier_profile") for r in rows) else 4)
"""


def hermes_python(hermes: str) -> str:
    """The interpreter the hermes launcher runs under; it can import hermes_cli."""
    try:
        with open(hermes, "rb") as handle:
            first = handle.readline().decode("utf-8", errors="replace").strip()
    except OSError:
        first = ""
    if first.startswith("#!"):
        candidate = first[2:].split()[0] if first[2:].split() else ""
        if candidate and Path(candidate).name.startswith("python") and Path(candidate).exists():
            return candidate
    return "/home/roy/.hermes/hermes-agent/venv/bin/python3"


def subscribe(row: dict, environ: dict, hermes: str) -> bool:
    done = si._run([hermes_python(hermes), "-c", SUBSCRIBE_SNIPPET, json.dumps(row)], environ)
    return done.returncode == 0


def cmd_submit(args, *, environ: dict | None = None, hermes: str = HERMES) -> dict:
    environ = dict(os.environ if environ is None else environ)
    if args.service_source == "catalog" and not getattr(args, "reporter_confirmed", False):
        # A catalog description is a weak signal, and a wrong service costs a
        # whole board run on the wrong repository.
        raise DeskError(
            "A service picked from the catalog is a guess until the reporter agrees. "
            "Tell the reporter the service name and its catalog description, ask whether "
            "to submit against it, and pass --reporter-confirmed only after they say yes.",
            code=3)
    body = build_body(
        issue=args.issue, service=args.service, environment=args.env,
        window_start=args.window_start, window_end=args.window_end,
        expected=args.expected, trace_id=args.trace_id, identifier=args.identifier,
        evidence=args.evidence, service_source=args.service_source,
    )
    session = session_from_env(environ)
    key = args.key or default_key(body, session)
    result = si.submit(
        body, key=key, title=None, deployed_commit=None,
        board=args.board, workspace=si.WORKSPACE,
        evidence_root=Path(args.evidence_root), env=environ, hermes=hermes,
        dry_run=args.dry_run, verify_service=not args.no_verify_service,
    )
    if args.dry_run:
        return {**result, "body": body}
    subscribed: list[str] = []
    failed: list[str] = []
    for stages, mode in ((WAKE_STAGES, "notify+wake"), (PASSIVE_STAGES, "notify")):
        for stage in stages:
            row = subscription(result[stage], session, mode, args.board)
            if row is None:
                continue
            (subscribed if subscribe(row, environ, hermes) else failed).append(stage)
    return {
        "root": result["root"],
        "root_status": result["root_status"],
        "key": key,
        "evidence_dir": result["evidence_dir"],
        "chat_subscribed": subscribed,
        "chat_subscribe_failed": failed,
        "note": (
            "The board now owns the investigation. Tell the reporter the root id and stop."
            if subscribed and not failed else
            "The chat subscription failed for: " + ", ".join(failed) + ". The report may "
            "not arrive on its own. Tell the reporter the root id and that they should "
            "ask for the status later."
            if failed else
            "No chat subscription was made; the report will not arrive on its own. "
            "Tell the reporter the root id and check later with: status --root <id>"
        ),
    }


def load_root(task_id: str, **kw) -> tuple[str, dict, dict]:
    """Accept the root id or any stage card id and return the root.

    A wake names the card that changed, which is often the intake card.
    Stage card bodies carry the root id under '## Root Task'.
    """
    shown = si.show_task(task_id, **kw)
    try:
        return task_id, shown, ag.parse_root(shown)
    except ag.AdjustError:
        body = str((shown.get("task") or {}).get("body") or "")
        match = re.search(r"^## Root Task\n(t_[0-9a-f]+)\s*$", body, flags=re.M)
        if not match or match.group(1) == task_id:
            raise DeskError(
                f"{task_id} is not a card created by issue_desk.py submit", code=3) from None
    root_id = match.group(1)
    root = si.show_task(root_id, **kw)
    return root_id, root, ag.parse_root(root)


def _last_block_reason(shown: dict) -> str:
    for event in reversed(shown.get("events") or []):
        if isinstance(event, dict) and event.get("kind") == "blocked":
            payload = event.get("payload") or {}
            if isinstance(payload, dict) and payload.get("reason"):
                return str(payload["reason"])[:300]
    return ""


def cmd_status(args, *, environ: dict | None = None, hermes: str = HERMES) -> str:
    environ = dict(os.environ if environ is None else environ)
    kw = {"board": args.board, "env": environ, "hermes": hermes}
    root_id, root, info = load_root(args.root, **kw)
    route = {"route": "why", "extra_runtime": {}}
    route_file = info["evidence"] / "route.json"
    if route_file.exists():
        loaded = json.loads(route_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            route.update(loaded)
    cards = [(stage, info["graph"][stage]) for stage in si.ORDER]
    cards += [(f"runtime:{name}", card) for name, card in (route.get("extra_runtime") or {}).items()]
    lines = [
        f"root: {root_id} {root['task']['status']}",
        f"title: {root['task'].get('title') or ''}",
        f"route: {route.get('route')}",
        "stages:",
    ]
    for stage, card in cards:
        shown = si.show_task(card, **kw)
        status = shown["task"]["status"]
        extra = ""
        if status == "blocked":
            extra = f" — {_last_block_reason(shown) or 'no reason recorded'}"
        lines.append(f"- {stage}: {card} {status}{extra}")
    report = info["evidence"] / "analysis.md"
    lines.append(f"report: {report} ({'written' if report.exists() else 'not written yet'})")
    if args.report:
        if not report.exists():
            lines.append("The report does not exist yet. Do not write one yourself.")
        else:
            text = report.read_text(encoding="utf-8", errors="replace")
            lines.append("----- analysis.md -----")
            lines.append(text[:REPORT_LIMIT])
            if len(text) > REPORT_LIMIT:
                lines.append(f"… truncated at {REPORT_LIMIT} characters; full file: {report}")
    return "\n".join(lines) + "\n"


def cmd_answer(args, *, environ: dict | None = None, hermes: str = HERMES) -> dict:
    environ = dict(os.environ if environ is None else environ)
    kw = {"board": args.board, "env": environ, "hermes": hermes}
    text = args.text.strip()
    if not text:
        raise DeskError("--text is empty")
    root_id, _, info = load_root(args.root, **kw)
    intake = info["graph"]["intake"]
    status = si.show_task(intake, **kw)["task"]["status"]
    if status != "blocked":
        raise DeskError(
            f"intake {intake} is {status}, not blocked; there is nothing to answer", code=3)
    for cmd in (
        ["comment", intake, f"Reporter answer:\n{text}"],
        ["unblock", intake, "--reason", "reporter supplied the missing input"],
    ):
        done = si._run([hermes, "kanban", "--board", args.board, *cmd], environ)
        if done.returncode != 0:
            detail = (done.stderr or done.stdout).decode("utf-8", errors="replace").strip()
            raise DeskError(detail or f"{cmd[0]} failed", code=1)
    return {"root": root_id, "intake": intake,
            "intake_status": si.show_task(intake, **kw)["task"]["status"]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="issue_desk.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    trace = sub.add_parser("trace", help="Summarize one Jaeger trace.")
    trace.add_argument("--env", required=True, choices=["test", "qa", "prod"])
    trace.add_argument("--trace-id", required=True)

    search = sub.add_parser("search", help="List traces for an account identifier.")
    search.add_argument("--env", required=True, choices=["test", "qa", "prod"])
    search.add_argument("--identifier", required=True)
    search.add_argument("--start", required=True)
    search.add_argument("--end", required=True)

    service = sub.add_parser("service", help="List deploy service names containing a keyword.")
    service.add_argument("--env", required=True)
    service.add_argument("--keyword", required=True)

    catalog = sub.add_parser(
        "catalog", help="List services by business line, or count a text in a service's code.")
    catalog.add_argument("--line", help="Only business lines containing this word.")
    catalog.add_argument("--text", help="Exact text to count in --service.")
    catalog.add_argument("--service", action="append", default=[],
                         help="Catalog name to search; up to 3.")

    sub.add_parser("now", help="Print the current time in Asia/Shanghai and US Eastern.")

    submit = sub.add_parser("submit", help="Create the board graph for one issue.")
    submit.add_argument("--issue", required=True, help="What happened, in the reporter's words.")
    submit.add_argument("--expected", help="What the reporter expected instead.")
    submit.add_argument("--service", required=True, help="Exact name printed by 'service'.")
    submit.add_argument("--env", required=True, choices=["test", "qa", "prod"])
    submit.add_argument("--window-start", required=True)
    submit.add_argument("--window-end", required=True)
    submit.add_argument("--trace-id")
    submit.add_argument("--identifier")
    submit.add_argument("--evidence", help="Error text, alert text, or other facts from the reporter.")
    submit.add_argument("--service-source", required=True, choices=SERVICE_SOURCES)
    submit.add_argument("--reporter-confirmed", action="store_true",
                        help="With --service-source catalog: the reporter agreed to this service.")
    submit.add_argument("--key", help="Stable issue key; derived from the content when omitted.")
    submit.add_argument("--board", default=si.BOARD)
    submit.add_argument("--evidence-root", default=str(si.EVIDENCE_ROOT))
    submit.add_argument("--dry-run", action="store_true")
    submit.add_argument("--no-verify-service", action="store_true", help=argparse.SUPPRESS)

    status = sub.add_parser("status", help="Show the stages of a submitted issue.")
    status.add_argument("--root", required=True, help="Root id, or any stage card id of the issue.")
    status.add_argument("--report", action="store_true", help="Also print analysis.md.")
    status.add_argument("--board", default=si.BOARD)

    answer = sub.add_parser("answer", help="Pass the reporter's reply to a blocked intake.")
    answer.add_argument("--root", required=True, help="Root id, or any stage card id of the issue.")
    answer.add_argument("--text", required=True)
    answer.add_argument("--board", default=si.BOARD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "trace":
            import jaeger_trace
            return jaeger_trace.main(["--env", args.env, "--trace-id", args.trace_id])
        if args.command == "search":
            import jaeger_search
            return jaeger_search.main(["--env", args.env, "--identifier", args.identifier,
                                       "--start", args.start, "--end", args.end])
        if args.command == "service":
            return find_service.main(["--env", args.env, "--keyword", args.keyword])
        if args.command == "now":
            from datetime import datetime
            from zoneinfo import ZoneInfo
            moment = datetime.now(ZoneInfo("Asia/Shanghai"))
            eastern = moment.astimezone(ZoneInfo("America/New_York"))
            print(f"Asia/Shanghai: {moment:%Y-%m-%d %H:%M} ({moment:%A})")
            print(f"US Eastern:    {eastern:%Y-%m-%d %H:%M} ({eastern:%A}, UTC{eastern:%z})")
            return 0
        if args.command == "catalog":
            import service_catalog
            forwarded = []
            if args.line:
                forwarded += ["--line", args.line]
            if args.text:
                forwarded += ["--text", args.text]
            for name in args.service:
                forwarded += ["--service", name]
            return service_catalog.main(forwarded)
        if args.command == "submit":
            print(json.dumps(cmd_submit(args), ensure_ascii=False, indent=2))
            return 0
        if args.command == "status":
            sys.stdout.write(cmd_status(args))
            return 0
        if args.command == "answer":
            print(json.dumps(cmd_answer(args), ensure_ascii=False, indent=2))
            return 0
    except (DeskError, si.SubmitError, ag.AdjustError) as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    return 2


if __name__ == "__main__":
    sys.exit(main())
