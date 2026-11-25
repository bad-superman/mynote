#!/usr/bin/env python3
"""Check the 待验证 list of code.md against the deployed source.

The runtime stage decides an item by searching the logs for a text. Finding
nothing refutes something only when the service would have written that
text: a search for a function name, or for a line of code, finds nothing
whatever happened. So a log item has to quote a text that a log statement
of the deployed commit writes, and say where that statement is.

Two commands, both reading the commit named in `<evidence-dir>/deployed.json`
(never the checkout's working tree):

  logs   list the log statements of one file, with the text to search for
  check  go through the 待验证 list and say for each item whether its text
         is confirmed, cannot be confirmed, or has to be rewritten

Only Go sources are read.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import deployed_version as dv

EXIT_NOT_FOUND = 4

CONFIRMED, OPEN, PASSED, FIX = "已确认", "未确认", "通过", "要改"
MAX_ITEMS = 5
NEAR = 3            # lines a citation may be off
SPAN = 40           # lines `logs --around` looks to either side
NEAREST = 5         # statements shown when none is that close
MAX_SHOWN = 40      # statements shown without --around
TEXT_WIDTH = 120
GIT_TIMEOUT = 60

LOG_FORM = '日志 "<原文>"（<文件>:<行号>）'
OUTSIDE_FORM = '日志 "<原文>"（不在本仓库：<谁打印的>）'


# ---------------------------------------------------------------- the list

_HEADING = re.compile(r"^#{1,3}\s", re.M)
_LIST_HEADING = re.compile(r"^#{2,3}\s*待验证[^\n]*$", re.M)
_ITEM = re.compile(r"^\s*(\d+)\s*[.、．)]\s*(?!\d)(.*)$")
_FIELD = re.compile(r"^\s*[-*•]\s*(要确认|服务|去哪查|不成立时会看到|成立时会看到)\s*[:：]\s*(.*)$")
_FIELDS = {"要确认": "statement", "服务": "service", "去哪查": "where",
           "成立时会看到": "holds", "不成立时会看到": "fails"}


class ListError(Exception):
    """code.md has no 待验证 section to check."""


@dataclass
class Item:
    """One entry of the 待验证 list, as the code stage wrote it."""
    number: int
    statement: str = ""
    service: str = ""
    where: str = ""
    holds: str = ""
    fails: str = ""


def parse_list(code_md: str) -> list[Item]:
    """The items under 待验证. The last such section wins when a retry added one."""
    headings = list(_LIST_HEADING.finditer(code_md))
    if not headings:
        raise ListError("code.md has no 待验证 section")
    body = code_md[headings[-1].end():]
    following = _HEADING.search(body)
    if following:
        body = body[:following.start()]

    items: list[Item] = []
    field = None
    for raw in body.splitlines():
        line = re.sub(r"\*\*|__", "", raw).rstrip()
        if not line.strip():
            continue
        started = _ITEM.match(line)
        if started:
            items.append(Item(int(started.group(1))))
            field = "statement"
            items[-1].statement = re.sub(r"^要确认\s*[:：]\s*", "", started.group(2).strip())
            continue
        if not items:
            continue
        labelled = _FIELD.match(line)
        if labelled:
            field = _FIELDS[labelled.group(1)]
            setattr(items[-1], field, labelled.group(2).strip())
        elif field:
            joined = f"{getattr(items[-1], field)} {line.strip()}".strip()
            setattr(items[-1], field, joined)
    return items


# ------------------------------------------------------- log statements

# A call is a log statement when its method is a level name and something
# on the way to it is named like a logger. `fmt.Errorf` and `errors.New`
# build an error; nothing reaches the log until a logger is called.
_METHOD = re.compile(
    r"^(?:(?:Trace|Debug|Info|Notice|Warn|Warning|Error|Fatal|Panic|DPanic|Print)"
    r"(?:f|w|ln|c|Context)?|Logf?)$")
_LOGGER = re.compile(r"(?:log|logger|logrus|logx|logging)$|^(?:zap|sugar|helper)$")
_WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+")
_SPRINT = {"Sprintf", "Sprint", "Sprintln"}

_TOKEN = re.compile(
    r"""
      (?P<comment>//[^\n]*|/\*.*?\*/)
    | (?P<raw>`[^`]*`)
    | (?P<str>"(?:\\.|[^"\\\n])*")
    | (?P<rune>'(?:\\.|[^'\\\n])+')
    | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<op>[()\[\]{}.])
    """,
    re.X | re.S)

_ESCAPE = re.compile(r"\\(?:[0-7]{3}|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)", re.S)
_VERB = re.compile(r"%(?:%|[-+# 0]*(?:\[\d+\])?(?:\*|\d+)?(?:\.(?:\*|\d+)?)?(?:\[\d+\])?[A-Za-z])")
# A JSON log line may store these escaped, so a searchable part stops at them.
_UNSAFE = re.compile(r'[<>&"\\\n\r\t]')
_LETTER = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]")


@dataclass(frozen=True)
class Statement:
    """One log statement: where it is and the parts of its text that never change."""
    line: int
    end_line: int
    method: str
    debug: bool
    texts: tuple[str, ...]


def log_statements(source: str) -> list[Statement]:
    """The log statements of one Go file, in source order."""
    tokens = _tokens(source)
    found = []
    for index, (kind, value, line) in enumerate(tokens):
        if kind != "id" or not _METHOD.match(value):
            continue
        if index < 2 or tokens[index - 1][:2] != ("op", "."):
            continue
        if index + 1 >= len(tokens) or tokens[index + 1][:2] != ("op", "("):
            continue
        if not any(_is_logger(name) for name in _receiver(tokens, index - 2)):
            continue
        call = _arguments(tokens, index + 2, formats=value.endswith("f"))
        if call is None:
            continue
        end_line, texts, names = call
        debug = value.startswith(("Debug", "Trace")) or (
            value.startswith("Log") and any(re.search(r"(?i)debug|trace", name) for name in names))
        found.append(Statement(line, end_line, value, debug, tuple(texts)))
    return found


def searchable(statement: Statement) -> str:
    """The text to search for one statement: its longest fixed part."""
    return max((part.strip() for part in statement.texts), key=len, default="")[:TEXT_WIDTH]


def _tokens(source: str) -> list[tuple[str, str, int]]:
    starts = [match.start() for match in re.finditer(r"\n", source)]
    tokens = []
    for match in _TOKEN.finditer(source):
        kind = match.lastgroup
        if kind in ("comment", "rune"):
            continue
        tokens.append((kind, match.group(), bisect.bisect_left(starts, match.start()) + 1))
    return tokens


def _receiver(tokens: list, index: int) -> list[str]:
    """The names on the way to a method, read backwards from the token before its dot."""
    names = []
    while index >= 0:
        kind, value, _ = tokens[index]
        if (kind, value) == ("op", ")"):
            depth = 0
            while index >= 0:
                if tokens[index][:2] == ("op", ")"):
                    depth += 1
                elif tokens[index][:2] == ("op", "("):
                    depth -= 1
                    if depth == 0:
                        break
                index -= 1
            index -= 1
            continue
        if kind != "id":
            break
        names.append(value)
        if index >= 1 and tokens[index - 1][:2] == ("op", "."):
            index -= 2
        else:
            break
    return names


def _is_logger(name: str) -> bool:
    return any(_LOGGER.search(word.lower()) for word in _WORDS.findall(name))


def _arguments(tokens: list, index: int, *, formats: bool):
    """Read a call's arguments from the token after its opening parenthesis.

    Returns the line of the closing parenthesis, the fixed parts of the
    strings that are logged, and the names used as direct arguments; None
    when the call never closes.
    """
    callees = [None]        # the function that opened each parenthesis
    braces = 0
    texts, names = [], []
    while index < len(tokens):
        kind, value, line = tokens[index]
        if kind == "op":
            if value == "(":
                before = tokens[index - 1]
                callees.append(before[1] if before[0] == "id" else None)
            elif value == ")":
                callees.pop()
                if not callees:
                    return line, texts, names
            elif value in "[{":
                braces += 1
            elif value in "]}":
                braces -= 1
        elif braces == 0:
            direct = len(callees) == 1
            sprint = len(callees) == 2 and callees[1] in _SPRINT
            if kind == "id" and direct:
                names.append(value)
            elif kind in ("str", "raw") and (direct or sprint):
                with_verbs = formats if direct else callees[1] == "Sprintf"
                texts.extend(_fixed_parts(kind, value[1:-1], with_verbs))
        index += 1
    return None


def _fixed_parts(kind: str, body: str, with_verbs: bool) -> list[str]:
    parts = _ESCAPE.split(body) if kind == "str" else [body]
    if with_verbs:
        parts = [piece for part in parts for piece in _VERB.split(part)]
    parts = [piece for part in parts for piece in _UNSAFE.split(part)]
    return [part for part in parts if _LETTER.search(part)]


# ---------------------------------------------------------------- the check

_QUOTED = re.compile(r'"([^"]*)"|“([^”]*)”|`([^`]*)`|「([^」]*)」')
_BRACKETED = re.compile(r"[（(]([^（()）]*)[)）]")
_FILE_LINE = re.compile(r"([\w./\-]+\.[A-Za-z0-9]+)\s*[:：]\s*(\d+)")
_OUTSIDE = re.compile(r"^不在本仓库\s*[:：]?\s*(.*)$")


@dataclass(frozen=True)
class Result:
    """What the check says about one item; number is None for the list as a whole."""
    number: int | None
    status: str
    detail: str


def check(items: list[Item], *, service: str, source) -> list[Result]:
    """Check each item against the commit `source` reads from.

    已确认: the quoted text is written by a log statement of the deployed
    code, so finding nothing can refute the item. 未确认: only a hit decides
    it. 通过: nothing to confirm. 要改: the item breaks the list's form.
    """
    database = [index for index, item in enumerate(items) if _kind(item) == "数据库"]
    misplaced = set() if database in ([], [len(items) - 1]) else set(database)

    results = []
    for index, item in enumerate(items):
        if index in misplaced:
            status, detail = FIX, "数据库项最多一条，并且放在最后"
        else:
            status, detail = _check_item(item, service, source)
        results.append(Result(item.number, status, detail))
    if len(items) > MAX_ITEMS:
        results.append(Result(None, FIX, f"最多 {MAX_ITEMS} 条，现在 {len(items)} 条；删掉最不关键的"))
    return results


def _kind(item: Item) -> str:
    for kind in ("日志", "指标", "数据库"):
        if item.where.startswith(kind):
            return kind
    return ""


def _check_item(item: Item, service: str, source) -> tuple[str, str]:
    missing = [label for label, name in _FIELDS.items() if not getattr(item, name)]
    if missing:
        return FIX, "缺少：" + "、".join(missing)
    kind = _kind(item)
    if kind == "指标":
        return PASSED, "指标项"
    if kind == "数据库":
        return PASSED, "数据库项，runtime 标查不到（看板不能查库）"
    if kind != "日志":
        return FIX, (f"去哪查要以 日志、指标 或 数据库 开头。日志写成 {LOG_FORM}，"
                     f"出处不在本仓库时写成 {OUTSIDE_FORM}")

    rest = item.where[len("日志"):]
    quoted = _QUOTED.search(rest)
    text = next((group for group in quoted.groups() if group), "").strip() if quoted else ""
    if not _LETTER.search(text):
        return FIX, "去哪查没有写要搜的原文；用引号写出日志语句里固定不变的一段"
    if "\\" in text:
        return FIX, f'"{text}" 里有反斜杠，日志平台搜不了；换一段不带反斜杠的原文'
    tail = rest[quoted.end():]
    if _QUOTED.search(_BRACKETED.sub("", tail)):
        return FIX, "一条只能搜一个文本（搜索没有 AND 和 OR）；留下最能说明问题的一个，其余的另起一条或删掉"

    if service not in item.service:
        return OPEN, (f"服务写的是 {item.service}，不是本单的服务 {service}，它的代码没有解析；"
                      "只有命中才算数")
    bracket = _BRACKETED.search(tail)
    cited = bracket.group(1).strip() if bracket else ""
    outside = _OUTSIDE.match(cited)
    if outside:
        who = outside.group(1).strip() or "没有写是谁打印的"
        return OPEN, f"出处不在本仓库（{who}）；只有命中才算数"
    located = _FILE_LINE.search(cited)
    if not located:
        return FIX, (f"去哪查没有写出处。写成 {LOG_FORM}，原文和行号用 logs 查；"
                     f"出处不在本仓库时写成 {OUTSIDE_FORM}")
    name, line = located.group(1), int(located.group(2))
    if not name.endswith(".go"):
        return OPEN, f"{name} 不是 Go 源码，只支持检查 Go；只有命中才算数"

    paths = _resolve(name, source.files())
    if not paths:
        return FIX, f"部署提交里没有 {name}"
    if len(paths) > 1:
        shown = "、".join(paths[:5])
        return FIX, f"有 {len(paths)} 个文件叫 {name}，写出从仓库根开始的路径：{shown}"
    path = paths[0]
    return _check_statement(text, path, line, log_statements(source.read(path)))


def _check_statement(text: str, path: str, line: int, found: list[Statement]) -> tuple[str, str]:
    def near(statement):
        return statement.line - NEAR <= line <= statement.end_line + NEAR

    def distance(statement):
        return abs(statement.line - line)

    writing = [statement for statement in found if any(text in part for part in statement.texts)]
    here = sorted((statement for statement in writing if near(statement)), key=distance)
    if here:
        best = here[0]
        if best.debug:
            return OPEN, (f"{path}:{best.line} 是 {best.method}，调试级别的日志在环境里可能不输出；"
                          "只有命中才算数")
        return CONFIRMED, f'日志 "{text}" {path}:{best.line} {best.method}'
    if writing:
        lines = "、".join(str(statement.line) for statement in sorted(writing, key=distance)[:3])
        return FIX, f'"{text}" 在 {path} 第 {lines} 行的日志语句里，不在第 {line} 行附近；把行号改成实际的行'
    if not found:
        return FIX, f"{path} 里没有日志语句，搜它的代码什么也搜不到；换一个会写日志的位置，或删掉这条"
    around = sorted((statement for statement in found if near(statement) and statement.texts),
                    key=distance)
    hint = f"logs --file {path} --around {line}"
    if around:
        best = around[0]
        return FIX, (f'{path}:{best.line} 的日志语句写的不是 "{text}"，它固定不变的原文是 '
                     f'"{searchable(best)}"；原文从日志语句里取，不带运行时才填入的部分。'
                     f"其他日志语句用 {hint} 看")
    return FIX, f"{path}:{line} 附近没有日志语句；用 {hint} 看这个文件在哪里写日志"


def _resolve(name: str, files: list[str]) -> list[str]:
    """The files of the commit a cited name can mean."""
    name = re.sub(r"^(?:\./)+", "", name.strip())
    if name in files:
        return [name]
    ending = [path for path in files if path.endswith("/" + name)]
    if ending:
        return ending
    inside = [path for path in files if name.endswith("/" + path)]
    return [max(inside, key=len)] if inside else []


def render_check(results: list[Result], *, service: str, commit: str) -> str:
    lines = [f"待验证清单检查：{service}，提交 {commit[:8]}"]
    if not results:
        lines.append("清单为空")
        return "\n".join(lines)
    for result in results:
        head = "清单：" if result.number is None else f"{result.number}. "
        lines.append(f"{head}{result.status} — {result.detail}")
    counts = "，".join(f"{status} {sum(1 for result in results if result.status == status)}"
                      for status in (CONFIRMED, OPEN, PASSED, FIX))
    lines += [
        f"合计：{counts}",
        f"{CONFIRMED}：这段文本确实由部署代码里的日志语句写出，零命中可以用来判定。",
        f"{OPEN}：只有命中才算数，零命中判查不到。",
        f"{FIX}：改好，或删掉这一条。",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- logs

def list_logs(source, name: str, *, around: int | None = None) -> dict:
    """The log statements of one file of the commit, each with its text to search."""
    if not name.strip().endswith(".go"):
        raise dv.ResolveError(dv.EXIT_USAGE, "only_go_sources_are_read", file=name)
    paths = _resolve(name, source.files())
    if not paths:
        raise dv.ResolveError(EXIT_NOT_FOUND, "no_such_file_in_commit", file=name)
    if len(paths) > 1:
        raise dv.ResolveError(dv.EXIT_USAGE, "file_name_is_ambiguous", file=name,
                              candidates=paths[:10])
    found = log_statements(source.read(paths[0]))
    if around is None:
        shown = found[:MAX_SHOWN]
    else:
        shown = [statement for statement in found if abs(statement.line - around) <= SPAN]
        if not shown:
            nearest = sorted(found, key=lambda statement: abs(statement.line - around))[:NEAREST]
            shown = sorted(nearest, key=lambda statement: statement.line)
    return {
        "file": paths[0],
        "total": len(found),
        "around": around,
        "shown": [{"line": statement.line, "method": statement.method,
                   "debug": statement.debug, "text": searchable(statement)}
                  for statement in shown],
    }


def render_logs(result: dict) -> str:
    total, shown, around = result["total"], result["shown"], result["around"]
    count = f"log statements: {total}"
    if len(shown) < total:
        if around is None:
            count += f", showing the first {len(shown)}; use --around <line> for the part you are reading"
        elif all(abs(row["line"] - around) <= SPAN for row in shown):
            count += f", showing {len(shown)} within {SPAN} lines of {around}"
        else:
            count += f", none within {SPAN} lines of {around}; showing the {len(shown)} nearest"
    lines = [f"file: {result['file']}", count]
    if not total:
        lines.append("this file writes nothing to the log; "
                     "a search for its code finds nothing whatever happened")
        return "\n".join(lines)
    for row in shown:
        text = f'"{row["text"]}"' if row["text"] else "(no fixed text: it logs only values)"
        note = "  (debug level: may not be written in this environment)" if row["debug"] else ""
        lines.append(f"{row['line']:>6}  {row['method']:<7} {text}{note}")
    lines.append(f'write an item as: 日志 "<the text, or a part of it>"（{result["file"]}:<line>）')
    return "\n".join(lines)


# --------------------------------------------------------------- the commit

class GitSource:
    """The files of one commit, read without touching the checkout's working tree."""

    def __init__(self, checkout: str | Path, commit: str):
        self._git = ["git", "-C", str(checkout)]
        self._commit = commit
        self._files: list[str] | None = None

    def files(self) -> list[str]:
        if self._files is None:
            listed = self._run("ls-tree", "-r", "-z", "--name-only", self._commit)
            self._files = [name for name in listed.split("\0") if name]
        return self._files

    def read(self, path: str) -> str:
        return self._run("show", f"{self._commit}:{path}")

    def _run(self, *args: str) -> str:
        try:
            done = subprocess.run([*self._git, *args], capture_output=True, timeout=GIT_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise dv.ResolveError(dv.EXIT_TOOL, "git_failed", detail=str(exc)[:300])
        if done.returncode != 0:
            detail = done.stderr.decode("utf-8", errors="replace").strip()[-300:]
            raise dv.ResolveError(dv.EXIT_TOOL, "git_failed", detail=detail)
        return done.stdout.decode("utf-8", errors="replace")


def _deployed(evidence_dir: Path) -> dict:
    path = evidence_dir / "deployed.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise dv.ResolveError(EXIT_NOT_FOUND, "no_deployed_json", path=str(path))
    commit = doc.get("analyzed_commit") or doc.get("deployed_commit")
    if not commit or not doc.get("checkout"):
        raise dv.ResolveError(EXIT_NOT_FOUND, "deployed_json_has_no_commit", path=str(path))
    return {"service": doc.get("service") or "", "commit": commit, "checkout": doc["checkout"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the 待验证 list of code.md against the deployed source.")
    commands = parser.add_subparsers(dest="command", required=True)
    logs = commands.add_parser(
        "logs", help="list the log statements of one file of the deployed commit")
    logs.add_argument("--evidence-dir", required=True)
    logs.add_argument("--file", required=True, help="path from the repository root, or a file name")
    logs.add_argument("--around", type=int, help="only the statements near this line")
    checking = commands.add_parser("check", help="check the 待验证 list of <evidence-dir>/code.md")
    checking.add_argument("--evidence-dir", required=True)
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    try:
        deployed = _deployed(evidence_dir)
        source = GitSource(deployed["checkout"], deployed["commit"])
        if args.command == "logs":
            print(render_logs(list_logs(source, args.file, around=args.around)))
            return 0
        report = evidence_dir / "code.md"
        try:
            items = parse_list(report.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise dv.ResolveError(EXIT_NOT_FOUND, "no_code_md", path=str(report))
        except ListError:
            raise dv.ResolveError(
                EXIT_NOT_FOUND, "no_list_in_code_md", path=str(report),
                hint="code.md ends with the sections 结论, 待验证, 下一跳")
        results = check(items, service=deployed["service"], source=source)
        print(render_check(results, service=deployed["service"], commit=deployed["commit"]))
        return 0
    except dv.ResolveError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
