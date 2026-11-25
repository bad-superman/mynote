#!/usr/bin/env python3
"""Single command surface for the issue-desk profile.

The desk talks to the reporter and hands the investigation to the
issue-analysis board. It does not investigate, and it does not locate the
service: intake does that, from the trace or from the source catalog.
Everything the desk is allowed to run goes through one of these
subcommands:

  now      print the current time in Asia/Shanghai and US Eastern
  submit   create the board graph and subscribe the current chat to it
  status   show where a submitted issue is, or print its final report
  answer   pass the reporter's reply to the card that asked for it
  notice   say what a board notification means for the reporter
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
JAEGER_SCRIPTS = HERE.parent.parent / "jaeger-trace" / "scripts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(JAEGER_SCRIPTS))

import adjust_graph as ag  # noqa: E402
import deployed_version as dv  # noqa: E402
import find_service  # noqa: E402
import jaeger_trace  # noqa: E402
import submit_issue as si  # noqa: E402

# The gateway's terminal may not have ~/.local/bin on PATH.
HERMES = shutil.which("hermes") or "/home/roy/.local/bin/hermes"
# The desk profile caps terminal output at this many characters
# (tool_output.max_bytes) and drops the middle of anything longer. An
# output that carries analysis.md is kept under the cap by giving the
# report the room its other lines leave.
TERMINAL_OUTPUT_CAP = 12000
OUTPUT_ROOM = TERMINAL_OUTPUT_CAP - 60
WINDOW_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$")
SHANGHAI = ZoneInfo("Asia/Shanghai")
ENVIRONMENTS = ("qa", "test", "prod")
# How far the time window reaches on each side of a trace.
TRACE_PADDING_MINUTES = 15
MAX_HINT_NAMES = 10

# The chat follows every card of the issue, because any of them can get
# stuck and the root alone would then never report. A card only wakes the
# desk. The other delivery modes make the gateway post a line and upload
# the stage's files each time a card finishes, and the reporter asked for
# the report, not for progress. `notice` tells the desk which wakes are
# worth a message.
SUBSCRIBED_STAGES = ("root", "intake", "code", "runtime", "verifier", "synthesizer")
DELIVERY_MODE = "wake"
# The stages that may ask the reporter a question, in the order they run.
ASKING_STAGES = ("intake", "runtime")
# What the desk replies when a notification is not for the reporter. The
# gateway drops a reply that is exactly this and sends nothing.
SILENT_REPLY = "NO_REPLY"
QUESTION_LIMIT = 2000


# How far back the most recent date with a window's month and day may lie
# for `settle_window` to take it without asking the reporter.
RECENT_DAYS = 300


class DeskError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def trace_window(trace: dict) -> tuple[str, str] | None:
    """The trace's own time span, padded and rounded outward to whole minutes."""
    facts = jaeger_trace.analyze(trace)
    if facts["start_us"] is None or facts["end_us"] is None:
        return None
    padding = timedelta(minutes=TRACE_PADDING_MINUTES)
    start = datetime.fromtimestamp(facts["start_us"] // 1_000_000, SHANGHAI) - padding
    end = datetime.fromtimestamp(-(-facts["end_us"] // 1_000_000), SHANGHAI) + padding
    start = start.replace(second=0)
    if end.second:
        end = end.replace(second=0) + timedelta(minutes=1)
    return f"{start:%Y-%m-%d %H:%M}", f"{end:%Y-%m-%d %H:%M}"


def _moment(value: str) -> datetime | None:
    for form in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, form).replace(tzinfo=SHANGHAI)
        except ValueError:
            continue
    return None


def _most_recent(begin: datetime, now: datetime) -> datetime | None:
    """The latest moment with this month, day, and time that is not after now."""
    for year in (now.year, now.year - 1):
        try:
            moment = begin.replace(year=year)
        except ValueError:  # 29 February
            continue
        if moment <= now:
            return moment
    return None


def settle_window(start: str, end: str, *, now: datetime) -> tuple[str, str, str | None]:
    """The window to investigate, and a note when it is not the one passed.

    The reporter says "11 月 24 日 10 点" and the desk adds the year. The
    year it adds is not always this one, and a window in another year
    sends the whole investigation to logs that do not exist. Told so,
    the desk asked the reporter which year they meant more often than it
    corrected the window, so the script takes the most recent such date
    itself and says that it did.

    A window that starts within the last twelve months is the most
    recent such date already and is taken as it is.
    """
    begin, finish = _moment(start), _moment(end)
    if begin is None or finish is None:
        return start, end, None  # build_body rejects the format
    if finish < begin:
        raise DeskError(f"The time window ends ({end}) before it starts ({start}). "
                        "Correct it and submit again.")
    recent = _most_recent(begin, now)
    if recent == begin:
        return start, end, None
    form = "%Y-%m-%d %H:%M:%S" if len(start) > 16 else "%Y-%m-%d %H:%M"
    where = "in the future" if begin > now else f"{(now - begin).days} days ago"
    where += f": it is now {now:%Y-%m-%d %H:%M} in Asia/Shanghai."
    if recent is None or (now - recent).days > RECENT_DAYS:
        # Last year's date, or a slip of the reporter or of the desk:
        # only the reporter knows.
        known = (f" The most recent such date is {recent:{form}}, {(now - recent).days} days ago."
                 if recent else "")
        raise DeskError(f"The time window starts at {start}, "
                        f"{'which is ' if begin > now else ''}{where}{known} Ask the reporter "
                        "which date and time they mean, then submit again.", code=3)
    moved = f"{recent:{form}}", f"{recent + (finish - begin):{form}}"
    return (*moved, f"You passed {start} 至 {end}, which starts {where} A date given without a "
                    f"year means the most recent such date, so the board investigates "
                    f"{moved[0]} 至 {moved[1]}. Give the reporter that window.")


def resolve_report(*, env: str | None, window_start: str | None, window_end: str | None,
                   trace_id: str | None, service_text: str | None,
                   find_trace=None, lookup=None, now: datetime | None = None) -> dict:
    """Settle the environment, the time window, and the service of a report.

    A trace answers the first two: it lives on one Jaeger server only, and
    it carries its own timestamps. Without a trace the reporter has to say
    both. A service is taken from the reporter only when it is an exact
    deploy name; anything else goes to intake as a hint.
    """
    if bool(window_start) != bool(window_end):
        raise DeskError("give both --window-start and --window-end, or neither")
    notes: list[str] = []
    environment = (env or "").strip().lower() or None
    trace_id = (trace_id or "").strip() or None
    from_trace = None
    if trace_id:
        order = tuple(dict.fromkeys(([environment] if environment else []) + list(ENVIRONMENTS)))
        found = (find_trace or jaeger_trace.find_env)(trace_id, envs=order)
        if found["env"]:
            notes.append(f"trace found on the {found['env']} Jaeger server")
            if environment and environment != found["env"]:
                notes.append(f"the reporter said {environment}; the server that holds the trace decides")
            environment = found["env"]
            from_trace = trace_window(found["trace"])
        else:
            silent = ", ".join(found.get("unreachable") or [])
            notes.append("trace not found on any Jaeger server, it may have expired"
                         + (f"; no answer from: {silent}" if silent else ""))
    if not environment:
        raise DeskError(
            ("The trace was not found on any Jaeger server, so the environment is unknown. "
             if trace_id else "Without a trace the environment is unknown. ")
            + "Ask the reporter which environment (qa, test, or prod) and pass --env.", code=3)

    moved = None
    if window_start and window_end:
        start, end, moved = settle_window(window_start.strip(), window_end.strip(),
                                          now=now or datetime.now(SHANGHAI))
    elif from_trace:
        start, end = from_trace
        notes.append(f"time window taken from the trace, {TRACE_PADDING_MINUTES} minutes either side")
    else:
        raise DeskError(
            "It is not known when this happened. Ask the reporter once, then pass "
            "--window-start and --window-end.", code=3)

    service = si.UNRESOLVED
    name = (service_text or "").strip().strip("`")
    if not name or name == si.UNRESOLVED:
        notes.append("the reporter named no service; intake locates it")
    else:
        exact, near = False, "not looked up, it is not a single name"
        if not any(ch.isspace() for ch in name):
            try:
                result = (lookup or find_service.find)(name, environment)
            except (dv.ResolveError, subprocess.TimeoutExpired):
                near = "unknown, the deploy lookup failed"
            else:
                exact = bool(result.get("exact"))
                near = ", ".join((result.get("services") or [])[:MAX_HINT_NAMES]) or "none"
        if exact:
            service = name
            notes.append("service named by the reporter")
        else:
            notes.append(f"the reporter called the service {name!r}; deploy names containing it: "
                         f"{near}. A hint for intake, not a located service")
    return {"environment": environment, "window_start": start, "window_end": end,
            "window_moved": moved, "service": service, "notes": notes}


def build_body(*, issue: str, service: str, environment: str, window_start: str,
               window_end: str, expected: str | None, trace_id: str | None,
               identifier: str | None, evidence: str | None, notes: list[str]) -> str:
    for label, value in (("--window-start", window_start), ("--window-end", window_end)):
        if not WINDOW_RE.match(value.strip()):
            raise DeskError(f"{label} must be 'YYYY-MM-DD HH:MM[:SS]' in Asia/Shanghai")
    if not issue.strip():
        raise DeskError("--issue is empty")
    issue_lines = [issue.strip()]
    if expected and expected.strip():
        issue_lines.append(f"\n期望行为：{expected.strip()}")
    evidence_lines = []
    if trace_id and trace_id.strip():
        evidence_lines.append(f"- trace_id: {trace_id.strip()}")
    if identifier and identifier.strip():
        evidence_lines.append(f"- identifier: {identifier.strip()}")
    if evidence and evidence.strip():
        evidence_lines.append(f"- reporter: {evidence.strip()}")
    if not evidence_lines:
        # A trace or an account only helps to collect evidence. The board
        # can work from the description, the code, and the logs.
        evidence_lines.append(
            "- no trace id or account identifier; work from the description, "
            "the deployed code, and the logs in the time window")
    evidence_lines.extend(f"- {note}" for note in notes)
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


def cmd_submit(args, *, environ: dict | None = None, hermes: str = HERMES,
               find_trace=None, lookup=None, now: datetime | None = None) -> dict:
    environ = dict(os.environ if environ is None else environ)
    report = resolve_report(
        env=args.env, window_start=args.window_start, window_end=args.window_end,
        trace_id=args.trace_id, service_text=args.service,
        find_trace=find_trace, lookup=lookup, now=now,
    )
    body = build_body(
        issue=args.issue, service=report["service"], environment=report["environment"],
        window_start=report["window_start"], window_end=report["window_end"],
        expected=args.expected, trace_id=args.trace_id, identifier=args.identifier,
        evidence=args.evidence, notes=report["notes"],
    )
    session = session_from_env(environ)
    key = args.key or default_key(body, session)
    # The service is already settled above: an exact deploy name or unresolved.
    result = si.submit(
        body, key=key, title=None, deployed_commit=None,
        board=args.board, workspace=si.WORKSPACE,
        evidence_root=Path(args.evidence_root), env=environ, hermes=hermes,
        dry_run=args.dry_run, verify_service=False,
    )
    if args.dry_run:
        return {**result, "body": body}
    subscribed: list[str] = []
    failed: list[str] = []
    for stage in SUBSCRIBED_STAGES:
        row = subscription(result[stage], session, DELIVERY_MODE, args.board)
        if row is None:
            continue
        (subscribed if subscribe(row, environ, hermes) else failed).append(stage)
    return {
        "root": result["root"],
        "root_status": result["root_status"],
        "key": key,
        "service": report["service"],
        "environment": report["environment"],
        "time_window": f"{report['window_start']} 至 {report['window_end']}",
        **({"time_window_note": report["window_moved"]} if report["window_moved"] else {}),
        "evidence_dir": result["evidence_dir"],
        "chat_subscribed": subscribed,
        "chat_subscribe_failed": failed,
        "note": (
            "The board now owns the investigation. Tell the reporter the root id and that "
            "the report will arrive in this chat, then stop. Send nothing more until the "
            "board notifies you."
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

    A wake names the card that changed, which is often a stage card.
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


# The events that leave a card waiting for a person, and the statuses they
# leave it in.
STOP_EVENTS = ("blocked", "gave_up", "block_loop_detected")
STOPPED = ("blocked", "triage")


def _stop_cause(shown: dict, limit: int = 300) -> tuple[str, str | None]:
    """Reason and kind of the card's most recent stop.

    A worker that blocks its card names a kind, and `needs_input` is the one
    kind the reporter can do something about. When the dispatcher stops
    retrying a card it records `gave_up` with the last error and no kind.
    That comes back as the kind `gave_up`, so a question the card asked
    earlier is not taken for the reason it stands still now.
    """
    for event in reversed(shown.get("events") or []):
        if not isinstance(event, dict) or event.get("kind") not in STOP_EVENTS:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event["kind"] == "gave_up":
            return str(payload.get("error") or "")[:limit], "gave_up"
        return str(payload.get("reason") or "")[:limit], payload.get("kind") or None
    return "", None


def _route_state(evidence: Path) -> dict:
    state = {"route": "why", "extra_runtime": {}, "service": None, "located_by": None}
    route_file = evidence / "route.json"
    if route_file.exists():
        loaded = json.loads(route_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state.update(loaded)
    return state


def _service_text(info: dict, route: dict) -> str:
    if info["service"] != si.UNRESOLVED:
        return info["service"]
    if route.get("service"):
        return f"{route['service']} (located by {route.get('located_by')})"
    return "not located yet"


def _stage_cards(info: dict, route: dict) -> list[tuple[str, str]]:
    """The stage cards of an issue, in the order they run."""
    cards = [(stage, info["graph"][stage]) for stage in si.ORDER]
    cards += [(f"runtime:{name}", card) for name, card in (route.get("extra_runtime") or {}).items()]
    return cards


def _size(lines: list[str] | tuple[str, ...]) -> int:
    """Characters the lines take in an output, line ends included."""
    return sum(len(line) + 1 for line in lines)


def _report_lines(report: Path, room: int) -> list[str]:
    """analysis.md in at most `room` characters, without its middle when it is longer.

    A report opens with the conclusion and the cause and closes with the
    confidence and what a person still has to confirm. The desk needs both
    ends, so a long report loses evidence detail from the middle instead.
    """
    text = report.read_text(encoding="utf-8", errors="replace")
    title = "----- analysis.md -----"
    room -= _size([title]) + 1
    if len(text) <= room:
        return [title, text]
    marker = ("… [{} characters of the middle are left out here; "
              "the file named above has the whole report] …")
    kept = max(room - _size([marker.format(len(text))]) - 1, 0)
    head = kept * 6 // 10
    return [title, text[:head], marker.format(len(text) - kept), text[len(text) - (kept - head):]]


def cmd_status(args, *, environ: dict | None = None, hermes: str = HERMES) -> str:
    environ = dict(os.environ if environ is None else environ)
    kw = {"board": args.board, "env": environ, "hermes": hermes}
    root_id, root, info = load_root(args.root, **kw)
    route = _route_state(info["evidence"])
    lines = [
        f"root: {root_id} {root['task']['status']}",
        f"title: {root['task'].get('title') or ''}",
        f"service: {_service_text(info, route)}",
        f"route: {route.get('route')}",
        "stages:",
    ]
    for stage, card in _stage_cards(info, route):
        shown = si.show_task(card, **kw)
        status = shown["task"]["status"]
        extra = ""
        if status in STOPPED:
            reason, kind = _stop_cause(shown)
            extra = (f" ({kind})" if kind else "") + f" — {reason or 'no reason recorded'}"
        lines.append(f"- {stage}: {card} {status}{extra}")
    report = info["evidence"] / "analysis.md"
    # The synthesizer writes the report, and the coordinator may then send
    # the issue through another round. It is the report when the root is done.
    final = root["task"]["status"] == "done"
    state = "not written yet" if not report.exists() else "written" if final else "written, not final"
    lines.append(f"report: {report} ({state})")
    if args.report:
        if not report.exists():
            lines.append("The report does not exist yet. Do not write one yourself.")
        elif not final:
            lines += [
                "The board has not closed this issue. Until it does the report can change, so "
                "it is not shown and not sent.",
                "If the reporter asked for it, tell them where the stages stand and that the "
                "report comes when the board closes the issue.",
                "If a board notification brought you here, nothing has changed: your reply is "
                "what the notice output said.",
            ]
        else:
            after = ["-----",
                     "To relay this report to the reporter, write one message in Chinese.",
                     *RELAY]
            lines += [*_report_lines(report, OUTPUT_ROOM - _size(lines) - _size(after)), *after]
    return "\n".join(lines) + "\n"


# How the desk relays analysis.md. Printed with the report, so that a turn
# which starts from a board notification needs nothing else to write it.
RELAY = (
    "Keep the report's own content and add no analysis of your own. Cover:",
    "- 结论",
    "- 根因, with the deployed commit and the file and line the report names",
    "- 关键证据, facts and inferences kept apart as the report has them",
    "- 修复建议 and 验证方案",
    "- 置信度, both lines as the report has them: 故障点 is where it failed, 原因 is why. "
    "Do not merge them and do not quote only the higher one.",
    "- what still needs a person to confirm",
    "- the issue id, and the path of analysis.md written in backticks",
    "When the report says the cause lies in a system the board could not look inside, say "
    "that first and plainly: where the failure surfaced, that the cause was not examined, "
    "who has to continue, and what to give them. Do not present the report's hypotheses "
    "as the cause.",
)
NOT_FOR_THE_REPORTER = (
    "Nothing here is for the reporter, and that includes what this output says. Do not tell "
    "them that a stage is done, that the report is on its way, or that they have to wait: "
    "they get the report when it is final and no message before it. This verdict is final "
    "for this notification: run no other command for it, not status and not notice again.",
    # The desk sometimes asks about each card of one notification in a
    # command of its own, and then reads this next to a verdict that is
    # not silent.
    "If you checked other cards of the same notification in another command and one of "
    "them has a verdict other than silent, follow that verdict. Otherwise your whole reply "
    "is the next line, as plain text, with nothing before or after it:",
    SILENT_REPLY,
)
# The last lines of every output that is not silent. A desk that has just
# stayed silent on five stages must not stay silent on this one.
TO_THE_REPORTER = (
    "The reporter is the person in this chat. They see your message and not this output. "
    "Write it to them, in Chinese, so that it stands on its own, with no word about the "
    "verdict, this notification, or the commands you ran."
)
WRITE_IT_NOW = (
    "They are waiting for this message, and all it needs is in this output{also}: run no "
    "other command and load no skill. Write it now as your reply. Do not stay silent, also "
    "when another card you checked was silent."
)
UNREADABLE = (
    "The board did not answer, so it is not known what this notification means. Write the "
    "reporter one line: the state of their issue cannot be read right now and the "
    "maintainer has to look. Do not guess the state."
)


def _judge(task_id: str, kw: dict, room: int) -> tuple[str, list[str]]:
    """The verdict on one card and the lines that go with it, in at most `room` characters."""
    try:
        root_id, root, info = load_root(task_id, **kw)
    except DeskError:
        return "silent", [f"card: {task_id} is not a card of an issue submitted through this desk"]
    route = _route_state(info["evidence"])
    stage = "root" if task_id == root_id else next(
        (name for name, card in _stage_cards(info, route) if card == task_id), "card")
    shown = root if task_id == root_id else si.show_task(task_id, **kw)
    status = shown["task"]["status"]
    issue = f"issue: {root_id} {root['task'].get('title') or ''}".rstrip()
    stopped = (
        "The investigation stopped at this stage, and no report will come until the "
        "maintainer has looked. Write the reporter one short message: which issue "
        f"({root_id} and what it was about), which stage stopped, and the reason as it "
        "stands. It is not a question for them: ask them for nothing, do not run answer, "
        "and do not try to work around it."
    )

    if status in STOPPED:
        reason, kind = _stop_cause(shown, limit=QUESTION_LIMIT)
        card = f"card: {stage} {task_id} {status}" + (f" ({kind})" if kind else "")
        if status == "blocked" and kind == "needs_input" and stage in ASKING_STAGES and reason:
            return "ask", [
                issue, card, "question:", reason, "-----",
                "The board cannot go on without the reporter's answer. Write the reporter "
                f"one message: which issue ({root_id} and what it was about), then the "
                "question as it stands, candidates included. Do not answer it for them.",
                "When they answer, hand their words over, also when they say they do not "
                "have what was asked:",
                f'issue-desk answer --root {root_id} --text "<their answer>"',
            ]
        return "stuck", [issue, card, f"reason: {reason or 'no reason recorded'}", "-----", stopped]

    card = f"card: {stage} {task_id} {status}"
    report = info["evidence"] / "analysis.md"
    if stage != "root" or status != "done":
        # A stage that finished, a card the board is retrying, or a root
        # that waits for its stages or for a follow-up round. The desk
        # doubts a bare "silent" when the notification says that the
        # report is written, so the verdict says where the issue stands.
        root_status = root["task"]["status"]
        if root_status == "done":
            where = (f"issue: {root_id} is done: its report goes out on the notification for "
                     f"{root_id} itself, not on this one.")
        else:
            where = f"issue: {root_id} is {root_status}, not closed. "
            where += ("The board has not finished with it: it can still change analysis.md, and "
                      "it sends another notification when it closes the issue."
                      if report.exists() else "The board is still working on it.")
        return "silent", [card, where]
    if not report.exists():
        return "stuck", [
            issue, card, f"reason: the board closed the issue, but {report} does not exist",
            "-----", stopped]
    before = [issue, f"service: {_service_text(info, route)}", f"report: {report}"]
    after = [
        "-----",
        "The investigation is finished and this is its report. Write the reporter one "
        "message that relays it, starting with the issue and its 结论.",
        *RELAY,
    ]
    room -= _size(["verdict: report", *before, *after])
    return "report", [*before, *_report_lines(report, room), *after]


def cmd_notice(args, *, environ: dict | None = None, hermes: str = HERMES,
               retry_delay: float = 1.0) -> str:
    """What a board notification means for the reporter.

    The verdict comes from the state of the card the notification names and
    not from the wording of the notification. It is one of: silent, ask,
    stuck, report. A notification that names several cards gets one block
    for each card the reporter has to hear about, or a single silent block.
    Blocks that together would be more than the desk terminal passes on
    are left for a second call, which the output names.
    """
    environ = dict(os.environ if environ is None else environ)
    kw = {"board": args.board, "env": environ, "hermes": hermes}
    given = [args.task] if isinstance(args.task, str) else list(args.task)
    task_ids: list[str] = []
    for raw in given:
        found = re.findall(r"t_[0-9a-f]+", raw)
        if not found:
            raise DeskError(
                f"{raw!r} is not a task id. --task takes the ids the notification names, "
                "for example t_1a2b3c4d")
        task_ids += [task_id for task_id in found if task_id not in task_ids]

    several = [f"These are {len(task_ids)} separate matters. Cover each of them in the one message."]
    put_off = [f"{len(task_ids)} of them did not fit into this output. Before you write, run this as well:",
               f"issue-desk notice --task {' '.join(task_ids)}"]
    # Room for the blocks: the closing lines come after them, and with
    # several cards so may the two notes above, at their longest here.
    also = " and that command's"
    room = OUTPUT_ROOM - _size([TO_THE_REPORTER, WRITE_IT_NOW.format(also=also)]) - 1
    if len(task_ids) > 1:
        room -= _size(several) + _size(put_off)

    verdicts: list[tuple[str, list[str], str]] = []
    for task_id in task_ids:
        failure = ""
        for attempt in (1, 2):
            try:
                verdicts.append((*_judge(task_id, kw, room), task_id))
                break
            except (si.SubmitError, ag.AdjustError, OSError, ValueError) as exc:
                failure = str(exc) or type(exc).__name__
                if "no such task" in failure:
                    raise DeskError(
                        f"The board has no card {task_id}. Run the command again with the "
                        "task id exactly as the notification gives it.", code=3) from exc
                if attempt == 1:
                    time.sleep(retry_delay)
        else:
            verdicts.append(("stuck", [
                f"card: {task_id} could not be read", f"reason: {failure}", "-----",
                UNREADABLE], task_id))

    spoken = [(verdict, lines, task_id) for verdict, lines, task_id in verdicts
              if verdict != "silent"]
    if not spoken:
        cards = [line for _, lines, _ in verdicts for line in lines]
        return "\n".join(["verdict: silent", *cards, *NOT_FOR_THE_REPORTER]) + "\n"

    # Each block is no longer than the room. The short ones go first, so
    # that a long report is what waits for the second call.
    blocks: list[str] = []
    deferred: list[str] = []
    for verdict, lines, task_id in sorted(spoken, key=lambda item: _size(item[1])):
        block = "\n".join([f"verdict: {verdict}", *lines])
        if blocks and len(block) + 2 > room:
            deferred.append(task_id)
            continue
        blocks.append(block)
        room -= len(block) + 2
    closing: list[str] = []
    if len(spoken) > 1:
        closing.append(
            f"These are {len(spoken)} separate matters. Cover each of them in the one message.")
    if deferred:
        closing += [
            f"{len(deferred)} of them did not fit into this output. Before you write, run "
            "this as well:",
            f"issue-desk notice --task {' '.join(deferred)}",
        ]
    closing += [TO_THE_REPORTER, WRITE_IT_NOW.format(also=also if deferred else "")]
    return "\n\n".join([*blocks, "\n".join(closing)]) + "\n"


def cmd_answer(args, *, environ: dict | None = None, hermes: str = HERMES) -> dict:
    environ = dict(os.environ if environ is None else environ)
    kw = {"board": args.board, "env": environ, "hermes": hermes}
    text = args.text.strip()
    if not text:
        raise DeskError("--text is empty")
    root_id, _, info = load_root(args.root, **kw)
    seen: list[str] = []
    for stage in ASKING_STAGES:
        card = info["graph"][stage]
        shown = si.show_task(card, **kw)
        status = shown["task"]["status"]
        seen.append(f"{stage} {card} is {status}")
        if status != "blocked":
            continue
        reason, kind = _stop_cause(shown)
        if kind and kind != "needs_input":
            # A missing tool, a failed dependency, or a worker that kept
            # failing. Unblocking the card with the reporter's words would
            # only run the stage into the same wall.
            raise DeskError(
                f"{stage} {card} is blocked on {kind}, not on a question for the reporter: "
                f"{reason or 'no reason recorded'}. The reporter cannot fix this; say that "
                "the investigation is stuck on tooling and the maintainer has to look.", code=3)
        for cmd in (
            ["comment", card, f"Reporter answer:\n{text}"],
            ["unblock", card, "--reason", "reporter supplied the missing input"],
        ):
            done = si._run([hermes, "kanban", "--board", args.board, *cmd], environ)
            if done.returncode != 0:
                detail = (done.stderr or done.stdout).decode("utf-8", errors="replace").strip()
                raise DeskError(detail or f"{cmd[0]} failed", code=1)
        return {"root": root_id, "stage": stage, "card": card,
                "status": si.show_task(card, **kw)["task"]["status"]}
    raise DeskError("; ".join(seen) + ". No card is waiting for the reporter.", code=3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="issue_desk.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("now", help="Print the current time in Asia/Shanghai and US Eastern.")

    submit = sub.add_parser("submit", help="Create the board graph for one issue.")
    submit.add_argument("--issue", required=True, help="What happened, in the reporter's words.")
    submit.add_argument("--expected", help="What the reporter expected instead.")
    submit.add_argument("--trace-id", help="The environment and the time window are read from it.")
    submit.add_argument("--env", choices=ENVIRONMENTS,
                        help="Required without a trace; the reporter has to say it.")
    submit.add_argument("--window-start", help="Required without a trace, with --window-end.")
    submit.add_argument("--window-end")
    submit.add_argument("--service",
                        help="Only what the reporter said, word for word. Do not guess one.")
    submit.add_argument("--identifier", help="Account, order, or other id the reporter gave.")
    submit.add_argument("--evidence", help="Error text, alert text, or other facts from the reporter.")
    submit.add_argument("--key", help="Stable issue key; derived from the content when omitted.")
    submit.add_argument("--board", default=si.BOARD)
    submit.add_argument("--evidence-root", default=str(si.EVIDENCE_ROOT))
    submit.add_argument("--dry-run", action="store_true")

    status = sub.add_parser("status", help="Show the stages of a submitted issue.")
    status.add_argument("--root", required=True, help="Root id, or any stage card id of the issue.")
    status.add_argument("--report", action="store_true", help="Also print analysis.md.")
    status.add_argument("--board", default=si.BOARD)

    answer = sub.add_parser("answer", help="Pass the reporter's reply to the card that asked.")
    answer.add_argument("--root", required=True, help="Root id, or any stage card id of the issue.")
    answer.add_argument("--text", required=True)
    answer.add_argument("--board", default=si.BOARD)

    notice = sub.add_parser(
        "notice", help="Say what a board notification means for the reporter.")
    notice.add_argument("--task", required=True, nargs="+", metavar="TASK_ID",
                        help="Every task id the notification names.")
    notice.add_argument("--board", default=si.BOARD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "now":
            moment = datetime.now(SHANGHAI)
            eastern = moment.astimezone(ZoneInfo("America/New_York"))
            print(f"Asia/Shanghai: {moment:%Y-%m-%d %H:%M} ({moment:%A})")
            print(f"US Eastern:    {eastern:%Y-%m-%d %H:%M} ({eastern:%A}, UTC{eastern:%z})")
            return 0
        if args.command == "submit":
            print(json.dumps(cmd_submit(args), ensure_ascii=False, indent=2))
            return 0
        if args.command == "status":
            sys.stdout.write(cmd_status(args))
            return 0
        if args.command == "answer":
            print(json.dumps(cmd_answer(args), ensure_ascii=False, indent=2))
            return 0
        if args.command == "notice":
            sys.stdout.write(cmd_notice(args))
            return 0
    except (DeskError, si.SubmitError, ag.AdjustError) as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    return 2


if __name__ == "__main__":
    sys.exit(main())
