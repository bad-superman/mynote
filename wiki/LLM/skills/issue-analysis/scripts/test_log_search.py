import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout

import deployed_version as dv
import log_search as ls

SERVICE = "trade.order-service.job"
TRACE = "68d380ddca0e946fda37a15025f8ba88"
OTHER_TRACE = "0123456789abcdef0123456789abcdef"


def line(time, msg, *, level="info", caller="biz/order.go:10", trace_id=""):
    return {
        "_logtime": time,
        "level": level,
        "caller": caller,
        "msg": msg,
        "message": json.dumps({"level": level, "caller": caller, "msg": msg}),
        "trace_id": trace_id,
    }


LINES = [
    line("2026-11-25 09:00:01.000", "job started"),
    line("2026-11-25 09:10:00.000", "grpc request operation=GetTradeConfig", trace_id=TRACE),
    line("2026-11-25 09:10:00.200", "driver.Query: query=SELECT 1", trace_id=TRACE),
    line("2026-11-25 09:20:00.000", "grpc request operation=ListOrders", trace_id=OTHER_TRACE),
    line("2026-11-25 09:30:00.000", "grpc request operation=GetTradeConfig", trace_id=OTHER_TRACE),
    line("2026-11-25 09:40:00.000", "place order failed: rpc timeout", level="error", trace_id=TRACE),
    line("2026-11-25 09:59:59.000", "job finished"),
]


def flag(cmd, name):
    return cmd[cmd.index(name) + 1] if name in cmd else None


class Platform:
    """Answers `nex logs platform search` the way the log platform was seen to."""

    def __init__(self, lines=LINES, known=(SERVICE,)):
        self.lines = lines
        self.known = known
        self.calls = []
        self.failures = []

    def __call__(self, cmd, timeout):
        self.calls.append(cmd)
        if self.failures:
            return subprocess.CompletedProcess(cmd, 1, b"", self.failures.pop(0))
        if flag(cmd, "--service-name") not in self.known:
            return subprocess.CompletedProcess(
                cmd, 6, b"",
                b'{"error":{"code":"NOT_FOUND","message":"no exact log config","retryable":false}}')
        query, trace_id = flag(cmd, "--query"), flag(cmd, "--trace-id")
        if trace_id:
            # The platform drops --query when a trace id is given.
            found = [item for item in self.lines if item["trace_id"] == trace_id]
        elif query is None:
            found = list(self.lines)
        elif query.startswith('"') and query.endswith('"'):
            found = [item for item in self.lines if query[1:-1] in item["message"]]
        elif " " in query:
            return subprocess.CompletedProcess(
                cmd, 1, b"",
                b'{"error":{"code":"REMOTE_ERROR","message":"downstream returned error","retryable":false}}')
        else:
            found = [item for item in self.lines if query in item["message"]]
        if flag(cmd, "--sort-order") == "desc":
            found = found[::-1]
        rows = int(flag(cmd, "--rows") or 100)
        out = json.dumps({"hits": found[:rows], "total": len(found), "took": 1, "highlight": {}})
        return subprocess.CompletedProcess(cmd, 0, out.encode(), b"")


def run(platform=None, **overrides):
    args = dict(service=SERVICE, env="qa", start="2026-11-25 09:00", end="2026-11-25 10:00")
    args.update(overrides)
    return ls.search(runner=platform or Platform(), **args)


class TextTest(unittest.TestCase):
    def test_counts_the_lines_that_contain_the_text(self):
        platform = Platform()
        result = run(platform, text="grpc request")
        self.assertEqual(result["hits"], 3)
        self.assertEqual(result["first"], "2026-11-25 09:10:00.000")
        self.assertEqual(result["last"], "2026-11-25 09:30:00.000")
        self.assertEqual([s["time"] for s in result["samples"]], [
            "2026-11-25 09:10:00.000", "2026-11-25 09:20:00.000", "2026-11-25 09:30:00.000"])
        self.assertEqual(result["samples"][0]["line"], "grpc request operation=GetTradeConfig")
        self.assertEqual(result["samples"][0]["caller"], "biz/order.go:10")

    def test_the_text_is_sent_as_one_quoted_phrase(self):
        # A bare phrase with a space is rejected by the platform.
        platform = Platform()
        run(platform, text="grpc request")
        self.assertEqual(flag(platform.calls[0], "--query"), '"grpc request"')

    def test_the_match_is_exact_and_case_sensitive(self):
        self.assertEqual(run(text="GRPC request")["hits"], 0)

    def test_the_last_time_is_asked_for_when_more_lines_match_than_are_shown(self):
        platform = Platform()
        result = run(platform, text="grpc request", samples=1)
        self.assertEqual(result["hits"], 3)
        self.assertEqual(len(result["samples"]), 1)
        self.assertEqual(result["first"], "2026-11-25 09:10:00.000")
        self.assertEqual(result["last"], "2026-11-25 09:30:00.000")
        self.assertEqual(len(platform.calls), 2)
        self.assertEqual(flag(platform.calls[1], "--sort-order"), "desc")
        self.assertEqual(flag(platform.calls[1], "--rows"), "1")

    def test_one_call_is_enough_when_every_match_is_shown(self):
        platform = Platform()
        run(platform, text="grpc request")
        self.assertEqual(len(platform.calls), 1)

    def test_no_text_and_no_trace_counts_every_line(self):
        result = run()
        self.assertEqual(result["hits"], 7)
        self.assertNotIn("lines_in_window", result)

    def test_a_text_with_a_double_quote_is_refused_before_asking(self):
        platform = Platform()
        with self.assertRaises(dv.ResolveError) as ctx:
            run(platform, text='msg="x"')
        self.assertEqual(ctx.exception.code, ls.EXIT_USAGE)
        self.assertEqual(platform.calls, [])

    def test_an_empty_text_is_refused(self):
        with self.assertRaises(dv.ResolveError) as ctx:
            run(text="   ")
        self.assertEqual(ctx.exception.code, ls.EXIT_USAGE)


class NothingFoundTest(unittest.TestCase):
    def test_no_match_says_how_much_the_service_logged(self):
        platform = Platform()
        result = run(platform, text="option auto expiration")
        self.assertEqual(result["hits"], 0)
        self.assertEqual(result["lines_in_window"], 7)
        self.assertEqual(result["samples"], [])
        self.assertNotIn("first", result)
        # The count of all lines comes from a search without a filter.
        self.assertIsNone(flag(platform.calls[-1], "--query"))
        self.assertIsNone(flag(platform.calls[-1], "--trace-id"))

    def test_a_window_without_any_line_cannot_decide(self):
        result = run(Platform(lines=[]), text="option auto expiration")
        self.assertEqual(result["hits"], 0)
        self.assertEqual(result["lines_in_window"], 0)
        self.assertIn("cannot decide", result["note"])

    def test_a_service_that_logged_gets_no_warning(self):
        self.assertNotIn("note", run(text="option auto expiration"))


class TraceTest(unittest.TestCase):
    def test_a_trace_id_is_searched_with_its_own_flag(self):
        platform = Platform()
        result = run(platform, trace_id=TRACE)
        self.assertEqual(result["hits"], 3)
        self.assertEqual(flag(platform.calls[0], "--trace-id"), TRACE)
        self.assertIsNone(flag(platform.calls[0], "--query"))

    def test_a_text_inside_a_trace_is_matched_here(self):
        # The platform ignores the text when a trace id is given, so the
        # trace's lines are fetched and filtered by this script.
        platform = Platform()
        result = run(platform, trace_id=TRACE, text="place order failed")
        self.assertEqual(result["hits"], 1)
        self.assertEqual(result["trace_lines"], 3)
        self.assertEqual(result["first"], "2026-11-25 09:40:00.000")
        self.assertEqual(result["samples"][0]["level"], "error")
        self.assertEqual(flag(platform.calls[0], "--rows"), str(ls.MAX_ROWS))
        self.assertIsNone(flag(platform.calls[0], "--query"))

    def test_a_trace_with_lines_but_none_with_the_text(self):
        result = run(trace_id=TRACE, text="no such text")
        self.assertEqual(result["hits"], 0)
        self.assertEqual(result["trace_lines"], 3)
        self.assertNotIn("lines_in_window", result)

    def test_a_trace_the_service_never_logged_says_how_much_it_logged(self):
        result = run(trace_id="f" * 32)
        self.assertEqual(result["hits"], 0)
        self.assertEqual(result["lines_in_window"], 7)

    def test_a_trace_longer_than_one_page_is_said_to_be_cut(self):
        many = [line(f"2026-11-25 09:00:{i % 60:02d}.{i:03d}", f"step {i}", trace_id=TRACE)
                for i in range(ls.MAX_ROWS + 20)]
        result = run(Platform(lines=many), trace_id=TRACE, text="step 7")
        self.assertEqual(result["trace_lines"], ls.MAX_ROWS + 20)
        self.assertIn(f"first {ls.MAX_ROWS}", result["note"])

    def test_a_malformed_trace_id_is_refused(self):
        with self.assertRaises(dv.ResolveError) as ctx:
            run(trace_id="not-a-trace")
        self.assertEqual(ctx.exception.code, ls.EXIT_USAGE)


class ScopeTest(unittest.TestCase):
    def test_the_environment_picks_the_log_cluster(self):
        for env, cluster in (("qa", "tx-sg-youfi-qa"), ("test", "tx-sg-youfi-test"),
                             ("prod", "aws-hk-youfi-prod")):
            platform = Platform()
            result = run(platform, env=env)
            self.assertEqual(flag(platform.calls[0], "--cluster"), cluster)
            self.assertEqual(result["log_cluster"], cluster)

    def test_the_log_source_is_derived_from_the_service_name(self):
        platform = Platform()
        run(platform)
        self.assertEqual(flag(platform.calls[0], "--service-name"), SERVICE)
        self.assertEqual(flag(platform.calls[0], "--log-source"), "youfi-" + SERVICE)
        self.assertEqual(flag(platform.calls[0], "--appkey"), "youfi")

    def test_the_window_is_shanghai_time_in_milliseconds(self):
        platform = Platform()
        result = run(platform, start="2026-11-25 09:00", end="2026-11-25 10:00:30")
        # 2026-11-25 09:00:00 +08:00
        self.assertEqual(flag(platform.calls[0], "--from"), "1795568400000")
        self.assertEqual(flag(platform.calls[0], "--to"), "1795572030000")
        self.assertEqual(result["window_start"], "2026-11-25 09:00:00")
        self.assertEqual(result["window_end"], "2026-11-25 10:00:30")

    def test_an_end_that_is_not_after_the_start_is_refused(self):
        platform = Platform()
        with self.assertRaises(dv.ResolveError) as ctx:
            run(platform, start="2026-11-25 10:00", end="2026-11-25 10:00")
        self.assertEqual(ctx.exception.code, ls.EXIT_USAGE)
        self.assertEqual(platform.calls, [])

    def test_the_number_of_samples_is_limited(self):
        platform = Platform()
        result = run(platform, samples=50)
        self.assertEqual(flag(platform.calls[0], "--rows"), str(ls.MAX_SAMPLES))
        self.assertEqual(len(result["samples"]), 7)

    def test_a_long_line_is_cut(self):
        long = [line("2026-11-25 09:00:01.000", "x" * 1000)]
        sample = run(Platform(lines=long))["samples"][0]
        self.assertEqual(len(sample["line"]), ls.LINE_WIDTH + 1)
        self.assertTrue(sample["line"].endswith("…"))

    def test_a_line_without_msg_shows_the_raw_message(self):
        raw = [{"_logtime": "2026-11-25 09:00:01.000", "message": "panic: nil map"}]
        sample = run(Platform(lines=raw))["samples"][0]
        self.assertEqual(sample["line"], "panic: nil map")
        self.assertEqual(sample["level"], "")


class FailureTest(unittest.TestCase):
    def test_a_service_the_log_platform_does_not_know_is_not_found(self):
        with self.assertRaises(dv.ResolveError) as ctx:
            run(service="trade.no-such.job")
        self.assertEqual(ctx.exception.code, ls.EXIT_NOT_FOUND)
        self.assertEqual(ctx.exception.payload["error"], "no_log_config")
        self.assertEqual(ctx.exception.payload["service"], "trade.no-such.job")

    def test_a_search_the_platform_rejects_is_a_tool_error(self):
        platform = Platform()
        platform.failures = [
            b'{"error":{"code":"REMOTE_ERROR","message":"downstream returned error","retryable":false}}']
        with self.assertRaises(dv.ResolveError) as ctx:
            run(platform, text="grpc request")
        self.assertEqual(ctx.exception.code, ls.EXIT_TOOL)
        self.assertEqual(ctx.exception.payload["nex_error"], "REMOTE_ERROR")
        # Asking again would get the same answer.
        self.assertEqual(len(platform.calls), 1)

    def test_a_request_that_timed_out_is_tried_once_more(self):
        platform = Platform()
        platform.failures = [b'{"error":{"code":"INTERNAL","message":"request timeout"}}']
        result = run(platform, text="grpc request")
        self.assertEqual(result["hits"], 3)
        self.assertEqual(len(platform.calls), 2)

    def test_two_timeouts_in_a_row_are_reported(self):
        platform = Platform()
        platform.failures = [b'{"error":{"code":"INTERNAL","message":"request timeout"}}'] * 2
        with self.assertRaises(dv.ResolveError) as ctx:
            run(platform, text="grpc request")
        self.assertEqual(ctx.exception.code, ls.EXIT_TOOL)

    def test_a_command_that_hangs_is_a_tool_error(self):
        def hangs(cmd, timeout):
            raise subprocess.TimeoutExpired(cmd, timeout)

        with self.assertRaises(dv.ResolveError) as ctx:
            ls.search(service=SERVICE, env="qa", start="2026-11-25 09:00",
                      end="2026-11-25 10:00", runner=hangs)
        self.assertEqual(ctx.exception.code, ls.EXIT_TOOL)

    def test_raw_control_characters_in_a_line_do_not_break_the_answer(self):
        def runner(cmd, timeout):
            out = (b'{"hits":[{"_logtime":"2026-11-25 09:00:01.000","level":"error",'
                   b'"msg":"panic\nstack\tline"}],"total":1}')
            return subprocess.CompletedProcess(cmd, 0, out, b"")

        result = ls.search(service=SERVICE, env="qa", start="2026-11-25 09:00",
                           end="2026-11-25 10:00", runner=runner)
        self.assertEqual(result["samples"][0]["line"], "panic stack line")


class CommandLineTest(unittest.TestCase):
    def call(self, *argv, platform=None):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ls.main(list(argv), runner=platform or Platform())
        return code, out.getvalue()

    BASE = ("--env", "qa", "--service", SERVICE,
            "--start", "2026-11-25 09:00", "--end", "2026-11-25 10:00")

    def test_prints_the_count_the_times_and_the_samples(self):
        code, out = self.call(*self.BASE, "--text", "grpc request")
        self.assertEqual(code, 0)
        self.assertIn("service: trade.order-service.job (qa, log cluster tx-sg-youfi-qa)", out)
        self.assertIn("window: 2026-11-25 09:00:00 to 2026-11-25 10:00:00 Asia/Shanghai", out)
        self.assertIn('text: "grpc request"', out)
        self.assertIn("hits: 3", out)
        self.assertIn("first: 2026-11-25 09:10:00.000", out)
        self.assertIn("last: 2026-11-25 09:30:00.000", out)
        self.assertIn("2026-11-25 09:10:00.000 info biz/order.go:10 grpc request operation=GetTradeConfig", out)

    def test_no_match_is_exit_zero_with_the_line_count(self):
        code, out = self.call(*self.BASE, "--text", "option auto expiration")
        self.assertEqual(code, 0)
        self.assertIn("hits: 0", out)
        self.assertIn("lines_in_window: 7", out)
        self.assertNotIn("first:", out)

    def test_a_trace_search_names_the_trace(self):
        code, out = self.call(*self.BASE, "--trace-id", TRACE, "--text", "place order failed")
        self.assertEqual(code, 0)
        self.assertIn(f"trace_id: {TRACE}", out)
        self.assertIn("trace_lines: 3", out)
        self.assertIn("hits: 1", out)

    def test_an_unknown_service_prints_the_error_and_exits_4(self):
        code, out = self.call("--env", "qa", "--service", "trade.no-such.job",
                              "--start", "2026-11-25 09:00", "--end", "2026-11-25 10:00")
        self.assertEqual(code, ls.EXIT_NOT_FOUND)
        self.assertEqual(json.loads(out)["error"], "no_log_config")

    def test_an_unsupported_environment_is_refused(self):
        code, out = self.call("--env", "staging", "--service", SERVICE,
                              "--start", "2026-11-25 09:00", "--end", "2026-11-25 10:00")
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "unsupported_environment")


if __name__ == "__main__":
    unittest.main()
