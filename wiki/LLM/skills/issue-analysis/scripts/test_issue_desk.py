import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import adjust_graph as ag
import deployed_version as dv
import issue_desk as desk
import submit_issue as si
from fake_board import FakeBoard

BASE = dict(
    issue="下单后订单一直是处理中",
    service="trade.order-service.job",
    environment="QA",
    window_start="2026-11-24 10:00",
    window_end="2026-11-24 10:30",
    expected="订单应在几秒内成交或被拒绝",
    trace_id=None,
    identifier="12345",
    evidence="页面提示 system busy",
    notes=["service named by the reporter"],
)

FEISHU_GROUP = {
    "HERMES_SESSION_PLATFORM": "feishu",
    "HERMES_SESSION_CHAT_ID": "oc_group",
    "HERMES_SESSION_CHAT_TYPE": "group",
    "HERMES_SESSION_THREAD_ID": "",
    "HERMES_SESSION_USER_ID": "ou_reporter",
    "HERMES_SESSION_PROFILE": "issue-desk",
}

# 2026-11-25 10:13:34 to 10:13:39 Asia/Shanghai, in Jaeger's microseconds.
TRACE_START = 1_795_572_814_000_000
TRACE = {
    "traceID": "abc",
    "processes": {"p1": {"serviceName": "ams.account.job.grpc"}},
    "spans": [{"traceID": "abc", "spanID": "s1", "operationName": "/x", "processID": "p1",
               "startTime": TRACE_START, "duration": 5_000_000, "references": [],
               "tags": [{"key": "error", "value": True}]}],
}


def trace_on(env):
    """A Jaeger lookup that finds the trace on one server, or on none."""
    def find(trace_id, *, envs):
        find.asked = envs
        if env in envs:
            return {"env": env, "trace": TRACE, "unreachable": []}
        return {"env": None, "trace": None, "unreachable": []}
    return find


def deploy_names(*names):
    def lookup(keyword, environment):
        lookup.asked.append(keyword)
        found = sorted(name for name in names if keyword in name)
        return {"exact": keyword in names, "services": found}
    lookup.asked = []
    return lookup


def no_lookup(keyword, environment):
    raise AssertionError(f"unexpected service lookup for {keyword!r}")


# The moment the tests run at: the evening after the windows they submit.
NOW = datetime(2026, 11, 25, 20, 0, tzinfo=desk.SHANGHAI)


def resolve(**kw):
    given = dict(env=None, window_start=None, window_end=None, trace_id=None,
                 service_text=None, find_trace=trace_on(None), lookup=no_lookup, now=NOW)
    given.update(kw)
    return desk.resolve_report(**given)


class BuildBodyTest(unittest.TestCase):
    def test_body_has_the_five_sections_the_board_requires(self):
        body = desk.build_body(**BASE)
        sections = si.parse_sections(body)
        self.assertEqual(si.field_value(sections["Service"]), "trade.order-service.job")
        self.assertEqual(si.field_value(sections["Environment"]), "qa")
        self.assertIn("2026-11-24 10:00 至 2026-11-24 10:30 (Asia/Shanghai)", sections["Time Window"])
        self.assertIn("期望行为：订单应在几秒内成交或被拒绝", sections["Issue"])
        self.assertIn("- identifier: 12345", sections["Evidence"])
        self.assertIn("- reporter: 页面提示 system busy", sections["Evidence"])
        self.assertIn("- service named by the reporter", sections["Evidence"])

    def test_trace_id_is_written_where_intake_looks_for_it(self):
        body = desk.build_body(**{**BASE, "trace_id": "abc123", "identifier": None, "evidence": None})
        self.assertIn("- trace_id: abc123", si.parse_sections(body)["Evidence"])

    def test_a_report_needs_no_trace_and_no_account(self):
        body = desk.build_body(**{**BASE, "identifier": None, "evidence": "  "})
        self.assertIn("- no trace id or account identifier", si.parse_sections(body)["Evidence"])

    def test_a_report_without_a_service_is_marked_for_intake(self):
        body = desk.build_body(**{**BASE, "service": si.UNRESOLVED})
        self.assertEqual(si.field_value(si.parse_sections(body)["Service"]), "unresolved")

    def test_a_vague_time_is_rejected(self):
        with self.assertRaises(desk.DeskError):
            desk.build_body(**{**BASE, "window_start": "今天上午"})


class WindowTest(unittest.TestCase):
    """The reporter says "11 月 24 日 10 点" and the desk has to add the year.

    The year it adds is not always this one.
    """

    def window(self, start, end, **kw):
        report = resolve(env="qa", window_start=start, window_end=end, **kw)
        return report["window_start"], report["window_end"], report["window_moved"]

    def refused(self, start, end, code, **kw):
        with self.assertRaises(desk.DeskError) as caught:
            self.window(start, end, **kw)
        self.assertEqual(caught.exception.code, code)
        return str(caught.exception)

    def test_a_recent_window_is_taken_as_it_is(self):
        self.assertEqual(self.window("2026-11-24 10:00", "2026-11-24 10:30"),
                         ("2026-11-24 10:00", "2026-11-24 10:30", None))

    def test_a_window_that_is_still_open_is_taken_as_it_is(self):
        self.assertEqual(self.window("2026-11-25 19:50", "2026-11-25 20:20"),
                         ("2026-11-25 19:50", "2026-11-25 20:20", None))

    def test_a_window_some_months_back_is_taken_as_it_is(self):
        self.assertIsNone(self.window("2026-02-01 10:00", "2026-02-01 10:30")[2])

    def test_an_earlier_year_becomes_the_most_recent_such_date(self):
        for year, days in (("2025", 366), ("2024", 731)):
            start, end, moved = self.window(f"{year}-11-24 10:00", f"{year}-11-24 10:30")
            self.assertEqual((start, end), ("2026-11-24 10:00", "2026-11-24 10:30"))
            self.assertEqual(moved, (
                f"You passed {year}-11-24 10:00 至 {year}-11-24 10:30, which starts {days} days "
                "ago: it is now 2026-11-25 20:00 in Asia/Shanghai. A date given without a year "
                "means the most recent such date, so the board investigates 2026-11-24 10:00 至 "
                "2026-11-24 10:30. Give the reporter that window."))

    def test_this_morning_with_last_years_date_is_this_morning(self):
        # Said at 20:00 on 25 November: "11 月 25 日 10 点" was ten hours ago.
        self.assertEqual(self.window("2025-11-25 10:00", "2025-11-25 10:15")[:2],
                         ("2026-11-25 10:00", "2026-11-25 10:15"))

    def test_a_window_over_midnight_keeps_its_length(self):
        self.assertEqual(self.window("2024-11-23 21:30", "2024-11-24 06:00")[:2],
                         ("2026-11-23 21:30", "2026-11-24 06:00"))

    def test_next_years_date_becomes_the_most_recent_such_date(self):
        start, end, moved = self.window("2027-11-24 10:00", "2027-11-24 10:30")
        self.assertEqual((start, end), ("2026-11-24 10:00", "2026-11-24 10:30"))
        self.assertIn("which starts in the future: it is now 2026-11-25 20:00 in Asia/Shanghai. "
                      "A date given without a year means the most recent such date", moved)

    def test_a_date_of_the_last_twelve_months_is_taken_as_it_is(self):
        # It is the most recent such date already, so nothing says the year is wrong.
        for start, end in (("2026-01-10 10:00", "2026-01-10 10:30"),
                           ("2025-11-26 10:00", "2025-11-26 10:30")):
            self.assertEqual(self.window(start, end), (start, end, None))

    def test_a_future_time_with_no_recent_date_goes_to_the_reporter(self):
        # "12 月 24 日" said in November: was it last December, or a slip?
        for start, end, recent, days in (
                ("2026-12-24 10:00", "2026-12-24 10:30", "2025-12-24 10:00", 336),
                ("2026-11-25 22:00", "2026-11-25 22:30", "2025-11-25 22:00", 364)):
            message = self.refused(start, end, 3)
            self.assertEqual(message, (
                f"The time window starts at {start}, which is in the future: it is now "
                f"2026-11-25 20:00 in Asia/Shanghai. The most recent such date is {recent}, "
                f"{days} days ago. Ask the reporter which date and time they mean, then submit "
                "again."))

    def test_an_older_year_with_no_recent_date_goes_to_the_reporter(self):
        message = self.refused("2025-01-10 10:00", "2025-01-10 10:30", 3)
        self.assertIn("starts at 2025-01-10 10:00, 684 days ago: it is now", message)
        self.assertIn("The most recent such date is 2026-01-10 10:00, 319 days ago.", message)

    def test_29_february_has_no_date_in_most_years(self):
        message = self.refused("2024-02-29 10:00", "2024-02-29 10:30", 3)
        self.assertNotIn("The most recent such date", message)
        self.assertIn("Ask the reporter which date and time they mean", message)

    def test_a_window_that_ends_before_it_starts_is_the_desks_to_correct(self):
        message = self.refused("2026-11-24 10:30", "2026-11-24 10:00", 2)
        self.assertIn("ends (2026-11-24 10:00) before it starts (2026-11-24 10:30)", message)

    def test_seconds_are_kept(self):
        self.assertIsNone(self.window("2026-11-24 10:00:05", "2026-11-24 10:00:44")[2])
        self.assertEqual(self.window("2024-11-24 10:00:05", "2024-11-24 10:00:44")[:2],
                         ("2026-11-24 10:00:05", "2026-11-24 10:00:44"))

    def test_a_time_that_is_not_a_time_is_left_to_the_format_check(self):
        self.assertEqual(self.window("今天上午", "今天中午"), ("今天上午", "今天中午", None))

    def test_the_window_of_a_trace_is_not_questioned(self):
        # A trace carries its own timestamps. Nobody added a year to them.
        later = datetime(2028, 1, 1, tzinfo=desk.SHANGHAI)
        report = resolve(trace_id="abc", find_trace=trace_on("qa"), now=later)
        self.assertEqual(report["window_start"], "2026-11-25 09:58")
        self.assertIsNone(report["window_moved"])


class TraceGivesTheScopeTest(unittest.TestCase):
    def test_a_trace_supplies_the_environment_and_the_window(self):
        report = resolve(trace_id="abc", find_trace=trace_on("qa"))
        self.assertEqual(report["environment"], "qa")
        self.assertEqual((report["window_start"], report["window_end"]),
                         ("2026-11-25 09:58", "2026-11-25 10:29"))
        self.assertIn("trace found on the qa Jaeger server", report["notes"])

    def test_the_window_the_reporter_gave_is_kept(self):
        report = resolve(trace_id="abc", find_trace=trace_on("qa"),
                         window_start="2026-11-25 10:00", window_end="2026-11-25 10:15")
        self.assertEqual((report["window_start"], report["window_end"]),
                         ("2026-11-25 10:00", "2026-11-25 10:15"))

    def test_the_server_that_holds_the_trace_decides_the_environment(self):
        find = trace_on("qa")
        report = resolve(trace_id="abc", env="test", find_trace=find)
        self.assertEqual(report["environment"], "qa")
        self.assertEqual(find.asked[0], "test")
        self.assertTrue(any("reporter said test" in note for note in report["notes"]))

    def test_a_trace_that_is_gone_leaves_the_reporters_scope(self):
        report = resolve(trace_id="abc", env="prod",
                         window_start="2026-11-25 10:00", window_end="2026-11-25 10:15")
        self.assertEqual(report["environment"], "prod")
        self.assertTrue(any("not found" in note for note in report["notes"]))

    def test_a_trace_that_is_gone_and_no_environment_is_asked_for(self):
        with self.assertRaises(desk.DeskError) as caught:
            resolve(trace_id="abc")
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("environment", str(caught.exception))


class NoTraceTest(unittest.TestCase):
    def test_the_environment_is_required(self):
        with self.assertRaises(desk.DeskError) as caught:
            resolve(window_start="2026-11-25 10:00", window_end="2026-11-25 10:15")
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("environment", str(caught.exception))

    def test_the_time_is_required(self):
        with self.assertRaises(desk.DeskError) as caught:
            resolve(env="qa")
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("when", str(caught.exception))

    def test_half_a_window_is_a_usage_error(self):
        with self.assertRaises(desk.DeskError) as caught:
            resolve(env="qa", window_start="2026-11-25 10:00")
        self.assertEqual(caught.exception.code, 2)


class ServiceTest(unittest.TestCase):
    SCOPE = dict(env="qa", window_start="2026-11-25 10:00", window_end="2026-11-25 10:15")

    def test_an_exact_deploy_name_is_used(self):
        report = resolve(**self.SCOPE, service_text="risk.risk.service",
                         lookup=deploy_names("risk.risk.service", "trade.riskcontrol-service.job"))
        self.assertEqual(report["service"], "risk.risk.service")

    def test_any_other_name_is_passed_to_intake_as_a_hint(self):
        report = resolve(**self.SCOPE, service_text="risk",
                         lookup=deploy_names("risk.risk.service", "trade.riskcontrol-service.job"))
        self.assertEqual(report["service"], si.UNRESOLVED)
        hint = "\n".join(report["notes"])
        self.assertIn("'risk'", hint)
        self.assertIn("risk.risk.service, trade.riskcontrol-service.job", hint)

    def test_a_phrase_is_a_hint_and_is_not_looked_up(self):
        report = resolve(**self.SCOPE, service_text="风控 服务")
        self.assertEqual(report["service"], si.UNRESOLVED)
        self.assertIn("风控 服务", "\n".join(report["notes"]))

    def test_no_service_is_left_to_intake(self):
        report = resolve(**self.SCOPE)
        self.assertEqual(report["service"], si.UNRESOLVED)
        self.assertIn("intake locates it", "\n".join(report["notes"]))

    def test_a_failed_lookup_leaves_the_name_as_a_hint(self):
        def lookup(keyword, environment):
            raise dv.ResolveError(dv.EXIT_TOOL, "nex_services_failed")
        report = resolve(**self.SCOPE, service_text="risk.risk.service", lookup=lookup)
        self.assertEqual(report["service"], si.UNRESOLVED)
        hint = "\n".join(report["notes"])
        self.assertIn("'risk.risk.service'", hint)
        self.assertIn("lookup failed", hint)


class KeyTest(unittest.TestCase):
    def test_same_reporter_and_content_gives_the_same_key(self):
        session = desk.session_from_env(FEISHU_GROUP)
        body = desk.build_body(**BASE)
        self.assertEqual(desk.default_key(body, session), desk.default_key(body, session))
        self.assertRegex(desk.default_key(body, session), r"^desk:[0-9a-f]{20}$")

    def test_another_reporter_or_another_window_gives_another_key(self):
        session = desk.session_from_env(FEISHU_GROUP)
        other = desk.session_from_env({**FEISHU_GROUP, "HERMES_SESSION_USER_ID": "ou_other"})
        body = desk.build_body(**BASE)
        later = desk.build_body(**{**BASE, "window_end": "2026-11-24 11:00"})
        self.assertNotEqual(desk.default_key(body, session), desk.default_key(body, other))
        self.assertNotEqual(desk.default_key(body, session), desk.default_key(later, session))


class BoardCase(unittest.TestCase):
    def setUp(self):
        self.board = FakeBoard().install(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="issue-desk-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_desk(self, *argv, **kw):
        args = desk.build_parser().parse_args(list(argv))
        handler = {"submit": desk.cmd_submit, "status": desk.cmd_status,
                   "answer": desk.cmd_answer, "notice": desk.cmd_notice}[args.command]
        kw.setdefault("environ", {})
        if args.command == "submit":
            kw.setdefault("now", NOW)
        return handler(args, **kw)

    def submit(self, *extra, **kw):
        kw.setdefault("find_trace", trace_on(None))
        kw.setdefault("lookup", no_lookup)
        return self.run_desk(
            "submit", "--issue", "期权到期后没有自动行权", "--env", "qa",
            "--window-start", "2026-11-25 10:00", "--window-end", "2026-11-25 10:30",
            "--evidence-root", str(self.tmp), *extra, **kw)

    def graph(self, root):
        return ag.parse_root(self.board.show_task(root))["graph"]

    def notice(self, *task_ids):
        return self.run_desk("notice", "--task", *task_ids, retry_delay=0)

    def assertVerdict(self, text, verdict):
        self.assertEqual(text.splitlines()[0], f"verdict: {verdict}", text)

    def assertSilent(self, text):
        self.assertVerdict(text, "silent")
        # The last line is the reply itself; the gateway drops exactly this.
        self.assertEqual(text.rstrip("\n").splitlines()[-1], "NO_REPLY")
        # The desk may have asked about each card of one notification in a
        # command of its own. Silence for one card must not undo a message
        # another card calls for.
        self.assertIn("one of them has a verdict other than silent, follow that verdict",
                      text.rstrip("\n").splitlines()[-2])
        # A summary in the notification can make the desk go and look, and
        # what it finds can make it tell the reporter to wait.
        self.assertIn("run no other command for it, not status and not notice again", text)
        self.assertIn("Do not tell them that a stage is done, that the report is on its way, or "
                      "that they have to wait", text)

    def assertSpoken(self, text):
        """The output ends by saying that the reporter must get a message."""
        closing = text.rstrip("\n").splitlines()[-2:]
        self.assertEqual(closing, [
            "The reporter is the person in this chat. They see your message and not this "
            "output. Write it to them, in Chinese, so that it stands on its own, with no word "
            "about the verdict, this notification, or the commands you ran.",
            "They are waiting for this message, and all it needs is in this output: run no "
            "other command and load no skill. Write it now as your reply. Do not stay silent, "
            "also when another card you checked was silent.",
        ])
        self.assertNotIn("NO_REPLY", text)

    @staticmethod
    def report_part(text):
        return text.split("----- analysis.md -----\n", 1)[1].split("\n-----\n", 1)[0]

    def finish_issue(self, root, report=None):
        for card in self.graph(root).values():
            self.board.finish(card)
        self.board.finish(root)
        if report is not None:
            (self.tmp / root / "analysis.md").write_text(report, encoding="utf-8")


class SubmitTest(BoardCase):
    def test_the_board_gets_the_window_that_was_meant(self):
        out = self.run_desk("submit", "--issue", "期权到期后没有自动行权", "--env", "qa",
                            "--window-start", "2024-11-25 10:00", "--window-end", "2024-11-25 10:30",
                            "--evidence-root", str(self.tmp), find_trace=trace_on(None), lookup=no_lookup)
        self.assertEqual(out["time_window"], "2026-11-25 10:00 至 2026-11-25 10:30")
        self.assertIn("You passed 2024-11-25 10:00 至 2024-11-25 10:30", out["time_window_note"])
        body = self.board.tasks[out["root"]]["body"]
        self.assertIn("2026-11-25 10:00 至 2026-11-25 10:30 (Asia/Shanghai)", body)
        self.assertNotIn("2024", body)
        # The note comes right after the window it is about.
        keys = list(out)
        self.assertEqual(keys.index("time_window_note"), keys.index("time_window") + 1)

    def test_a_window_taken_as_it_is_has_no_note(self):
        self.assertNotIn("time_window_note", self.submit())

    def test_a_window_nobody_can_have_meant_creates_nothing(self):
        with self.assertRaises(desk.DeskError):
            self.run_desk("submit", "--issue", "期权到期后没有自动行权", "--env", "qa",
                          "--window-start", "2026-12-25 10:00", "--window-end", "2026-12-25 10:30",
                          "--evidence-root", str(self.tmp), find_trace=trace_on(None), lookup=no_lookup)
        self.assertEqual(self.board.tasks, {})

    def test_a_description_alone_reaches_the_board(self):
        result = self.submit()
        self.assertEqual(result["service"], si.UNRESOLVED)
        self.assertEqual(result["environment"], "qa")
        self.assertEqual(self.board.tasks[result["root"]]["title"], "[qa][待定位] 期权到期后没有自动行权")

    def test_a_trace_alone_reaches_the_board(self):
        result = self.run_desk(
            "submit", "--issue", "查询交易账户信息超时", "--trace-id", "abc",
            "--evidence-root", str(self.tmp), find_trace=trace_on("qa"), lookup=no_lookup)
        self.assertEqual(result["environment"], "qa")
        self.assertEqual(result["time_window"], "2026-11-25 09:58 至 2026-11-25 10:29")
        self.assertIn("- trace_id: abc", self.board.tasks[result["root"]]["body"])

    def test_the_named_service_is_on_the_card(self):
        result = self.submit("--service", "risk.risk.service",
                             lookup=deploy_names("risk.risk.service"))
        self.assertEqual(result["service"], "risk.risk.service")
        self.assertTrue(self.board.tasks[result["root"]]["title"].startswith("[qa][risk.risk.service]"))

    def test_the_chat_follows_every_card_and_no_card_posts_to_it(self):
        rows = []
        original = desk.subscribe
        desk.subscribe = lambda row, environ, hermes: rows.append(row) or True
        self.addCleanup(setattr, desk, "subscribe", original)

        result = self.submit(environ=FEISHU_GROUP)
        cards = {result["root"], *self.graph(result["root"]).values()}
        self.assertEqual({row["task_id"] for row in rows}, cards)
        self.assertEqual({row["delivery_mode"] for row in rows}, {"wake"})
        self.assertEqual(set(result["chat_subscribed"]), {"root", *si.ORDER})
        self.assertEqual(result["chat_subscribe_failed"], [])


class AnswerTest(BoardCase):
    def test_the_answer_goes_to_a_blocked_intake(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.block(intake, "needs_input: 哪个功能的自动行权")

        result = self.run_desk("answer", "--root", root, "--text", "美股期权到期日的自动行权")
        self.assertEqual((result["stage"], result["card"]), ("intake", intake))
        self.assertIn("Reporter answer:\n美股期权到期日的自动行权", self.board.comments(intake))
        self.assertNotEqual(self.board.status(intake), "blocked")

    def test_the_answer_goes_to_a_blocked_runtime_card(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        self.board.finish(graph["code"])
        self.board.block(graph["runtime"], "needs_input: 需要账户 UID 才能查持仓")

        result = self.run_desk("answer", "--root", graph["runtime"], "--text", "没有")
        self.assertEqual((result["stage"], result["card"]), ("runtime", graph["runtime"]))
        self.assertIn("Reporter answer:\n没有", self.board.comments(graph["runtime"]))
        self.assertEqual(self.board.comments(graph["intake"]), [])

    def test_a_card_blocked_on_tooling_is_not_the_reporters_to_answer(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        self.board.finish(graph["code"])
        self.board.block(graph["runtime"], "nex login expired", kind="capability")

        with self.assertRaises(desk.DeskError) as caught:
            self.run_desk("answer", "--root", root, "--text", "账户 UID 是 12345")
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("nex login expired", str(caught.exception))
        self.assertEqual(self.board.comments(graph["runtime"]), [])
        self.assertEqual(self.board.status(graph["runtime"]), "blocked")

    def test_with_nothing_blocked_there_is_nothing_to_answer(self):
        root = self.submit()["root"]
        with self.assertRaises(desk.DeskError) as caught:
            self.run_desk("answer", "--root", root, "--text", "补充说明")
        self.assertEqual(caught.exception.code, 3)

    def test_an_answered_question_does_not_outlive_a_later_failure(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.block(intake, "哪个功能的自动行权", kind="needs_input")
        self.run_desk("answer", "--root", root, "--text", "美股期权到期日的自动行权")
        self.board.give_up(intake, "worker crashed 3 times")

        with self.assertRaises(desk.DeskError) as caught:
            self.run_desk("answer", "--root", root, "--text", "再补充一点")
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("worker crashed 3 times", str(caught.exception))
        self.assertEqual(len(self.board.comments(intake)), 1)


class StatusTest(BoardCase):
    def test_an_unlocated_issue_says_so(self):
        root = self.submit()["root"]
        self.assertIn("service: not located yet", self.run_desk("status", "--root", root))

    def test_the_located_service_is_shown(self):
        root = self.submit()["root"]
        ag.adjust(root, service="trade.order-service.job", located_by="description", env={},
                  service_lookup=lambda s, e: {"exact": True, "services": [s]})
        text = self.run_desk("status", "--root", root)
        self.assertIn("service: trade.order-service.job (located by description)", text)


    def test_a_block_shows_its_kind_and_reason(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.block(intake, "哪个功能的自动行权", kind="needs_input")
        self.assertIn(f"- intake: {intake} blocked (needs_input) — 哪个功能的自动行权",
                      self.run_desk("status", "--root", root))

    def test_a_card_that_gave_up_shows_its_error_and_not_an_older_question(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.block(intake, "哪个功能的自动行权", kind="needs_input")
        self.run_desk("answer", "--root", root, "--text", "美股期权")
        self.board.give_up(intake, "worker crashed 3 times")
        self.assertIn(f"- intake: {intake} blocked (gave_up) — worker crashed 3 times",
                      self.run_desk("status", "--root", root))

    def test_a_card_in_triage_shows_why(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.triage(intake, "哪个功能的自动行权")
        self.assertIn(f"- intake: {intake} triage (needs_input) — 哪个功能的自动行权",
                      self.run_desk("status", "--root", root))

    def test_a_report_the_board_has_not_closed_is_not_shown(self):
        # The synthesizer writes analysis.md before the coordinator decides
        # whether the issue needs another round.
        root = self.submit()["root"]
        for card in self.graph(root).values():
            self.board.finish(card)
        (self.tmp / root / "analysis.md").write_text("# Issue Analysis\n", encoding="utf-8")

        text = self.run_desk("status", "--root", root, "--report")
        self.assertIn(f"report: {self.tmp / root / 'analysis.md'} (written, not final)\n", text)
        self.assertNotIn("# Issue Analysis", text)
        self.assertNotIn("To relay this report", text)
        self.assertEqual(text.rstrip("\n").splitlines()[-3:], [
            "The board has not closed this issue. Until it does the report can change, so it "
            "is not shown and not sent.",
            "If the reporter asked for it, tell them where the stages stand and that the "
            "report comes when the board closes the issue.",
            "If a board notification brought you here, nothing has changed: your reply is what "
            "the notice output said.",
        ])
        self.assertIn(f"report: {self.tmp / root / 'analysis.md'} (written, not final)\n",
                      self.run_desk("status", "--root", root))

        self.board.finish(root)
        text = self.run_desk("status", "--root", root, "--report")
        self.assertIn(f"report: {self.tmp / root / 'analysis.md'} (written)\n", text)
        self.assertIn("# Issue Analysis", text)
        self.assertIn("To relay this report to the reporter, write one message in Chinese.", text)


class NoticeTest(BoardCase):
    """What a board notification means for the reporter."""

    def test_a_finished_stage_is_not_for_the_reporter(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        text = self.notice(graph["intake"])
        self.assertSilent(text)
        self.assertIn(f"card: intake {graph['intake']} done\n"
                      f"issue: {root} is todo, not closed. The board is still working on it.\n", text)

    def test_the_synthesizer_finishing_is_not_the_report(self):
        # Its notification says that analysis.md is written. The coordinator
        # has not looked yet and may send the issue through another round.
        root = self.submit()["root"]
        graph = self.graph(root)
        for card in graph.values():
            self.board.finish(card)
        (self.tmp / root / "analysis.md").write_text("# Issue Analysis\n", encoding="utf-8")

        text = self.notice(graph["synthesizer"])
        self.assertSilent(text)
        self.assertIn(f"card: synthesizer {graph['synthesizer']} done\n"
                      f"issue: {root} is {self.board.status(root)}, not closed. The board has "
                      "not finished with it: it can still change analysis.md, and it sends "
                      "another notification when it closes the issue.\n", text)
        self.assertNotIn("# Issue Analysis", text)

    def test_a_stage_the_board_is_retrying_is_not_for_the_reporter(self):
        root = self.submit()["root"]
        code = self.graph(root)["code"]
        for put in (lambda: None, lambda: self.board.start(code)):
            put()
            self.assertSilent(self.notice(code))

    def test_a_question_from_intake_is_passed_on(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        question = "无法确定问题出在哪个服务。请补充：是在哪个页面出现的？\n目前的候选：资金服务、账户服务。"
        self.board.block(intake, question, kind="needs_input")

        text = self.notice(intake)
        self.assertVerdict(text, "ask")
        self.assertIn(f"issue: {root} [qa][待定位] 期权到期后没有自动行权", text)
        self.assertIn(f"question:\n{question}\n", text)
        self.assertIn(f'issue-desk answer --root {root} --text', text)
        self.assertSpoken(text)

    def test_a_question_from_runtime_is_passed_on(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        self.board.finish(graph["code"])
        self.board.block(graph["runtime"], "需要账户 UID 才能查持仓", kind="needs_input")
        text = self.notice(graph["runtime"])
        self.assertVerdict(text, "ask")
        self.assertIn("需要账户 UID 才能查持仓", text)
        self.assertSpoken(text)

    def test_a_long_question_is_not_cut(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        question = "请补充：" + "候选服务甲、" * 80 + "最后一个候选"
        self.board.block(intake, question, kind="needs_input")
        self.assertIn("最后一个候选", self.notice(intake))

    def test_a_stage_blocked_on_tooling_is_stuck(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        self.board.finish(graph["code"])
        self.board.block(graph["runtime"], "nex login expired", kind="capability")

        text = self.notice(graph["runtime"])
        self.assertVerdict(text, "stuck")
        self.assertIn(f"issue: {root} [qa][待定位] 期权到期后没有自动行权", text)
        self.assertIn(f"card: runtime {graph['runtime']} blocked (capability)", text)
        self.assertIn("reason: nex login expired", text)
        self.assertNotIn("issue-desk answer", text)
        self.assertSpoken(text)

    def test_only_intake_and_runtime_may_ask_the_reporter(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        self.board.block(graph["code"], "intake.md has no deployed_commit", kind="needs_input")
        text = self.notice(graph["code"])
        self.assertVerdict(text, "stuck")
        self.assertIn("intake.md has no deployed_commit", text)
        self.assertNotIn("issue-desk answer", text)
        self.assertSpoken(text)

    def test_a_stage_that_gave_up_is_stuck(self):
        root = self.submit()["root"]
        verifier = self.graph(root)["verifier"]
        self.board.give_up(verifier, "Iteration budget exhausted (60/60)")
        text = self.notice(verifier)
        self.assertVerdict(text, "stuck")
        self.assertIn(f"card: verifier {verifier} blocked (gave_up)", text)
        self.assertIn("Iteration budget exhausted (60/60)", text)

    def test_a_stage_in_triage_is_stuck(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.triage(intake, "哪个功能的自动行权")
        text = self.notice(intake)
        self.assertVerdict(text, "stuck")
        self.assertIn(f"card: intake {intake} triage (needs_input)", text)

    def test_an_answered_question_is_not_asked_again(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.block(intake, "哪个功能的自动行权", kind="needs_input")
        self.run_desk("answer", "--root", root, "--text", "美股期权")
        self.assertSilent(self.notice(intake))

    def test_the_finished_root_carries_the_report(self):
        root = self.submit("--service", "risk.risk.service",
                           lookup=deploy_names("risk.risk.service"))["root"]
        self.finish_issue(root, report="# Issue Analysis\n\n## 结论\n通知已发送。\n")

        text = self.notice(root)
        self.assertVerdict(text, "report")
        self.assertIn(f"issue: {root} [qa][risk.risk.service] 期权到期后没有自动行权", text)
        self.assertIn("service: risk.risk.service", text)
        self.assertIn(f"report: {self.tmp / root / 'analysis.md'}", text)
        self.assertIn("----- analysis.md -----\n# Issue Analysis\n\n## 结论\n通知已发送。", text)
        self.assertSpoken(text)

    def test_the_report_comes_with_how_to_relay_it(self):
        # A notification can open a session in which the skill is not loaded.
        root = self.submit()["root"]
        self.finish_issue(root, report="# Issue Analysis\n")
        for text in (self.notice(root), self.run_desk("status", "--root", root, "--report")):
            after = text.split("# Issue Analysis\n", 1)[1]
            self.assertIn("in Chinese", after)
            for point in ("结论", "根因", "关键证据", "修复建议", "验证方案", "置信度", "故障点",
                          "in backticks", "could not look inside"):
                self.assertIn(point, after)

    def test_the_report_is_relayed_once_by_the_root_and_never_by_a_stage(self):
        root = self.submit()["root"]
        self.finish_issue(root, report="# Issue Analysis\n")
        for card in self.graph(root).values():
            text = self.notice(card)
            self.assertSilent(text)
            self.assertIn(f"issue: {root} is done: its report goes out on the notification for "
                          f"{root} itself, not on this one.\n", text)
            self.assertNotIn("# Issue Analysis", text)

    def test_a_report_too_long_keeps_both_ends_and_points_to_the_file(self):
        root = self.submit()["root"]
        opening, closing = "## 结论\n通知已发送。\n", "## 置信度\n故障点：高\n"
        report = opening + "证" * 13_000 + closing
        self.finish_issue(root, report=report)
        for text in (self.notice(root), self.run_desk("status", "--root", root, "--report")):
            shown = self.report_part(text)
            self.assertTrue(shown.startswith(opening))
            self.assertTrue(shown.endswith(closing))
            marker = re.search(r"\n… \[(\d+) characters of the middle are left out here; "
                               r"the file named above has the whole report\] …\n", shown)
            self.assertIsNotNone(marker, shown[-300:])
            head, tail = shown[:marker.start()], shown[marker.end():]
            self.assertEqual(len(head) + len(tail) + int(marker.group(1)), len(report))
            self.assertEqual(head, report[:len(head)])
            self.assertEqual(tail, report[-len(tail):])
            self.assertIn(f"report: {self.tmp / root / 'analysis.md'}", text)

    def test_a_report_of_ten_thousand_characters_is_whole(self):
        # The reports the board has written so far have 3000 to 10500 characters.
        root = self.submit()["root"]
        closing = "\n## 置信度\n故障点：高\n"
        report = "结" * (10_000 - len(closing)) + closing
        self.finish_issue(root, report=report)
        for text in (self.notice(root), self.run_desk("status", "--root", root, "--report")):
            self.assertEqual(self.report_part(text), report)
            self.assertNotIn("left out", text)

    def test_no_output_is_longer_than_the_desk_terminal_passes_on(self):
        # Over its cap the terminal tool drops the middle of the output,
        # which would be the middle of the report, and says so nowhere the
        # desk would look. However long the lines around the report are,
        # the report takes what is left.
        root = self.submit("--issue", "问" * 200, "--service", "risk.risk.service",
                           lookup=deploy_names("risk.risk.service"))["root"]
        self.finish_issue(root, report="结" * 30_000)
        limit = desk.TERMINAL_OUTPUT_CAP - 50
        for text in (self.notice(root), self.run_desk("status", "--root", root, "--report")):
            self.assertLessEqual(len(text), limit)
            self.assertGreater(len(text), limit - 400)
        shown_plain = len(self.report_part(text))

        # A status with a long reason on every card leaves the report less room.
        other = self.submit("--issue", "另一个问题：行权通知重复发送")["root"]
        extra = ag.adjust(other, add_runtime=["trade.option-service.job", "ams.position.job"], env={},
                          service_lookup=lambda s, e: {"exact": True, "services": [s]})["extra_runtime"]
        cards = [*(self.graph(other)[stage] for stage in si.ORDER), *extra.values()]
        for card in cards:
            self.board.block(card, "因" * 400, kind="capability")
        self.board.finish(other)
        (self.tmp / other / "analysis.md").write_text("结" * 30_000, encoding="utf-8")
        text = self.run_desk("status", "--root", other, "--report")
        self.assertLessEqual(len(text), limit)
        self.assertGreater(len(text), limit - 400)
        self.assertEqual(text.count("因" * 300), len(cards))
        self.assertLess(len(self.report_part(text)), shown_plain - 1_000)

    def test_a_finished_root_without_a_report_is_stuck(self):
        root = self.submit()["root"]
        self.finish_issue(root)
        text = self.notice(root)
        self.assertVerdict(text, "stuck")
        self.assertIn(f"card: root {root} done", text)
        self.assertIn(f"reason: the board closed the issue, but {self.tmp / root / 'analysis.md'} "
                      "does not exist", text)
        self.assertSpoken(text)

    def test_a_root_that_cannot_close_is_stuck(self):
        root = self.submit()["root"]
        self.board.block(root, "analysis.md is missing from the evidence directory", kind="needs_input")
        text = self.notice(root)
        self.assertVerdict(text, "stuck")
        self.assertIn("analysis.md is missing", text)
        self.assertNotIn("issue-desk answer", text)

    def test_a_root_waiting_for_its_stages_or_a_follow_up_round_is_silent(self):
        root = self.submit()["root"]
        self.assertEqual(self.board.status(root), "todo")
        text = self.notice(root)
        self.assertSilent(text)
        self.assertIn(f"card: root {root} todo\nissue: {root} is todo, not closed. The board is "
                      "still working on it.\n", text)

    def test_an_extra_runtime_card_is_judged_like_a_stage(self):
        root = self.submit()["root"]
        extra = ag.adjust(root, add_runtime=["risk.risk.service"], env={},
                          service_lookup=lambda s, e: {"exact": True, "services": [s]},
                          )["extra_runtime"]["risk.risk.service"]
        self.board.block(extra, "nex login expired", kind="capability")
        text = self.notice(extra)
        self.assertVerdict(text, "stuck")
        self.assertIn(f"card: runtime:risk.risk.service {extra} blocked (capability)", text)

        self.board.finish(extra)
        self.assertSilent(self.notice(extra))

    def test_a_card_of_no_issue_is_silent(self):
        other = self.board.create_task({
            "title": "别的任务", "assignee": "someone", "body": "与问题分析无关",
            "skills": [], "idempotency_key": "other:1"})["id"]
        self.assertSilent(self.notice(other))

    def test_a_board_that_cannot_be_read_is_said_so(self):
        root = self.submit()["root"]
        calls = []

        def broken(task_id, **_kw):
            calls.append(task_id)
            raise si.SubmitError("database is locked", code=1)

        original = si.show_task
        si.show_task = broken
        self.addCleanup(setattr, si, "show_task", original)

        text = self.notice(root)
        self.assertVerdict(text, "stuck")
        self.assertIn(f"card: {root} could not be read", text)
        self.assertIn("reason: database is locked", text)
        self.assertEqual(calls, [root, root])
        self.assertSpoken(text)

    def test_an_id_the_board_does_not_have_is_an_error_and_not_a_verdict(self):
        self.submit()
        with self.assertRaises(desk.DeskError) as caught:
            self.notice("t_0badc0de")
        self.assertEqual(caught.exception.code, 3)
        self.assertIn("t_0badc0de", str(caught.exception))

    def test_what_is_not_a_task_id_is_refused(self):
        with self.assertRaises(desk.DeskError) as caught:
            self.notice("completed")
        self.assertEqual(caught.exception.code, 2)

    def test_an_id_is_taken_out_of_the_punctuation_around_it(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.finish(intake)
        self.assertIn(f"card: intake {intake} done", self.notice(f"`{intake}`."))


class SeveralNoticesTest(BoardCase):
    """Notifications that arrive while the desk is busy reach it as one message."""

    def test_finished_stages_together_are_one_silence(self):
        root = self.submit()["root"]
        graph = self.graph(root)
        self.board.finish(graph["intake"])
        self.board.finish(graph["code"])

        text = self.notice(graph["intake"], graph["code"])
        lines = text.rstrip("\n").splitlines()
        self.assertEqual(lines[0], "verdict: silent")
        self.assertEqual(lines[-1], "NO_REPLY")
        self.assertIn(f"card: intake {graph['intake']} done", lines)
        self.assertIn(f"card: code {graph['code']} done", lines)
        self.assertEqual(text.count("verdict:"), 1)

    def test_a_question_among_finished_stages_is_the_only_thing_said(self):
        first = self.submit()["root"]
        second = self.submit("--issue", "另一个问题：行权通知重复发送")["root"]
        done = self.graph(first)["intake"]
        asking = self.graph(second)["intake"]
        self.board.finish(done)
        self.board.block(asking, "是哪一个账户？", kind="needs_input")

        text = self.notice(done, asking)
        self.assertEqual(text.splitlines()[0], "verdict: ask")
        self.assertIn("是哪一个账户？", text)
        self.assertIn(f"issue-desk answer --root {second} --text", text)
        self.assertSpoken(text)
        self.assertNotIn(done, text)
        self.assertNotIn("separate matters", text)

    def test_two_matters_for_the_reporter_are_two_blocks(self):
        first = self.submit()["root"]
        second = self.submit("--issue", "另一个问题：行权通知重复发送")["root"]
        self.finish_issue(first, report="# Issue Analysis\n\n## 结论\n已定位。\n")
        stuck = self.graph(second)["code"]
        self.board.give_up(stuck, "worker crashed 3 times")

        text = self.notice(first, stuck)
        # The shorter matter comes first.
        self.assertVerdict(text, "stuck")
        self.assertIn("worker crashed 3 times", text)
        self.assertIn("\n\nverdict: report\n", text)
        self.assertEqual(self.report_part(text), "# Issue Analysis\n\n## 结论\n已定位。\n")
        self.assertIn("\n\nThese are 2 separate matters. Cover each of them in the one message.\n", text)
        self.assertSpoken(text)
        self.assertEqual(text.count("Do not stay silent"), 1)

    def test_reports_too_long_to_come_together_come_one_at_a_time(self):
        # The desk terminal drops the middle of an output longer than its cap.
        first = self.submit()["root"]
        second = self.submit("--issue", "另一个问题：行权通知重复发送")["root"]
        third = self.submit("--issue", "第三个问题：余额没有更新")["root"]
        self.finish_issue(first, report="甲" * 7000)
        self.finish_issue(second, report="乙" * 7000)
        stuck = self.graph(third)["code"]
        self.board.give_up(stuck, "worker crashed 3 times")

        text = self.notice(first, second, stuck)
        self.assertVerdict(text, "stuck")
        self.assertIn("worker crashed 3 times", text)
        self.assertEqual(text.count("verdict:"), 2)
        self.assertEqual(self.report_part(text), "甲" * 7000)
        self.assertNotIn("乙", text)
        self.assertIn("\n\nThese are 3 separate matters. Cover each of them in the one message.\n"
                      "1 of them did not fit into this output. Before you write, run this as "
                      f"well:\nissue-desk notice --task {second}\n", text)
        self.assertLessEqual(len(text), desk.TERMINAL_OUTPUT_CAP - 50)
        closing = text.rstrip("\n").splitlines()[-1]
        self.assertEqual(closing,
                         "They are waiting for this message, and all it needs is in this output "
                         "and that command's: run no other command and load no skill. Write it "
                         "now as your reply. Do not stay silent, also when another card you "
                         "checked was silent.")
        self.assertNotIn("NO_REPLY", text)

        later = self.notice(second)
        self.assertEqual(self.report_part(later), "乙" * 7000)

    def test_an_id_given_twice_is_judged_once(self):
        root = self.submit()["root"]
        intake = self.graph(root)["intake"]
        self.board.finish(intake)
        self.assertEqual(self.notice(intake, intake).count(f"card: intake {intake} done"), 1)


class CommandSurfaceTest(unittest.TestCase):
    def test_the_desk_has_five_commands(self):
        parser = desk.build_parser()
        choices = next(a.choices for a in parser._actions if getattr(a, "choices", None))
        self.assertEqual(set(choices), {"now", "submit", "status", "answer", "notice"})

    def test_a_trace_is_enough_for_the_command_line(self):
        args = desk.build_parser().parse_args(["submit", "--issue", "x", "--trace-id", "abc"])
        self.assertIsNone(args.env)
        self.assertIsNone(args.window_start)


class SubscriptionTest(unittest.TestCase):
    def test_group_subscription_carries_the_reporter_and_no_owner_profile(self):
        session = desk.session_from_env(FEISHU_GROUP)
        row = desk.subscription("t_root", session, "wake", "issue-analysis")
        self.assertEqual(row, {
            "board": "issue-analysis",
            "task_id": "t_root",
            "platform": "feishu",
            "chat_id": "oc_group",
            "chat_type": "group",
            "thread_id": None,
            "user_id": "ou_reporter",
            "user_id_alt": None,
            "delivery_mode": "wake",
        })
        self.assertNotIn("profile", session)
        self.assertIn("notifier_profile=None", desk.SUBSCRIBE_SNIPPET)

    def test_a_feishu_p2p_chat_is_recorded_as_dm(self):
        session = desk.session_from_env({**FEISHU_GROUP, "HERMES_SESSION_CHAT_TYPE": "p2p"})
        self.assertEqual(desk.subscription("t_root", session, "wake", "b")["chat_type"], "dm")

    def test_no_chat_in_the_environment_means_no_subscription(self):
        self.assertIsNone(desk.subscription("t_root", desk.session_from_env({}), "wake", "b"))
        local = desk.session_from_env({"HERMES_SESSION_PLATFORM": "cli",
                                       "HERMES_SESSION_CHAT_ID": "x"})
        self.assertIsNone(desk.subscription("t_root", local, "wake", "b"))

    def test_a_card_wakes_the_desk_and_posts_nothing_itself(self):
        # "notify" and "notify+wake" make the gateway post a line and upload
        # the stage's files for every card that finishes.
        self.assertEqual(desk.DELIVERY_MODE, "wake")
        self.assertEqual(set(desk.SUBSCRIBED_STAGES), {"root", *si.ORDER})
        self.assertEqual(set(desk.ASKING_STAGES), {"intake", "runtime"})

    def test_the_interpreter_comes_from_the_launcher_shebang(self):
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "hermes"
            launcher.write_text(f"#!{sys.executable}\nimport sys\n")
            self.assertEqual(desk.hermes_python(str(launcher)), sys.executable)
            self.assertTrue(desk.hermes_python(str(Path(tmp) / "missing")).endswith("python3"))


if __name__ == "__main__":
    unittest.main()
