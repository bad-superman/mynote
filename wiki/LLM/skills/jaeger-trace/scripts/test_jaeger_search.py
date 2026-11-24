import contextlib
import io
import json
import unittest
import urllib.parse

import jaeger_search as js
from test_jaeger_trace import _span


def _trace(trace_id, start, *, fail):
    spans = [
        _span("g1", "/api/v1/orders", start, 30_000, "p1", {
            "http.method": "POST",
            "http.status_code": "500" if fail else "200",
            "http.url": "https://example.test/orders?token=SECRET",
            "uid": "UID-SECRET",
        }),
        _span("o1", "OrderService/Place", start + 2_000, 20_000, "p2", {
            "rpc.system": "grpc",
            "rpc.grpc.status_code": "13" if fail else "0",
            "account": "ACCOUNT-SECRET",
        }, parent="g1"),
    ]
    for span in spans:
        span["traceID"] = trace_id
    return {
        "traceID": trace_id,
        "processes": {
            "p1": {"serviceName": "open-gateway.http"},
            "p2": {"serviceName": "trade.order.service"},
        },
        "spans": spans,
    }


BASE_US = 1_700_000_000_000_000


class DescribeTest(unittest.TestCase):
    def test_failing_trace_names_the_services_that_errored(self):
        row = js.describe(_trace("t1", BASE_US, fail=True), entry_service="open-gateway.http")
        self.assertEqual(row["trace_id"], "t1")
        self.assertEqual(row["method"], "POST")
        self.assertEqual(row["operation"], "/api/v1/orders")
        self.assertEqual(row["http_status"], "500")
        self.assertEqual(row["services"], ["open-gateway.http", "trade.order.service"])
        self.assertEqual(row["error_services"], ["open-gateway.http", "trade.order.service"])
        self.assertEqual(row["duration_ms"], 30.0)

    def test_healthy_trace_has_no_error_services(self):
        row = js.describe(_trace("t2", BASE_US, fail=False), entry_service="open-gateway.http")
        self.assertEqual(row["error_services"], [])


class RenderTest(unittest.TestCase):
    def test_failing_traces_come_first_and_no_tag_value_is_printed(self):
        rows = [
            js.describe(_trace("ok-new", BASE_US + 60_000_000, fail=False),
                        entry_service="open-gateway.http"),
            js.describe(_trace("bad-old", BASE_US, fail=True),
                        entry_service="open-gateway.http"),
        ]
        text = js.render(rows, env="qa", entry_service="open-gateway.http", matched_key="uid",
                         start_us=BASE_US, end_us=BASE_US + 120_000_000, max_lines=10)
        self.assertIn("trace_count: 2", text)
        self.assertIn("traces_with_errors: 1", text)
        self.assertIn("matched_key: uid", text)
        self.assertLess(text.index("bad-old"), text.index("ok-new"))
        self.assertIn("error_services=open-gateway.http,trade.order.service", text)
        self.assertIn("error_services=- services=", text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("http.url", text)

    def test_long_lists_are_cut_at_max_lines(self):
        rows = [
            js.describe(_trace(f"t{i}", BASE_US + i, fail=False), entry_service="open-gateway.http")
            for i in range(5)
        ]
        text = js.render(rows, env="qa", entry_service="open-gateway.http", matched_key="uid",
                         start_us=BASE_US, end_us=BASE_US + 10, max_lines=2)
        self.assertEqual(sum(1 for line in text.splitlines() if line.startswith("- ")), 2)
        self.assertIn("3 more traces omitted", text)


class MainTest(unittest.TestCase):
    def _run(self, argv, responder):
        calls = []

        def fake_fetch(url, timeout):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            calls.append(query)
            return responder(query)

        original = js.fetch_json
        js.fetch_json = fake_fetch
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = js.main(argv)
        finally:
            js.fetch_json = original
        return code, out.getvalue(), err.getvalue(), calls

    ARGS = ["--env", "qa", "--identifier", "12345",
            "--start", "2026-11-23 14:00", "--end", "2026-11-23 15:00"]

    def test_tries_each_identifier_tag_until_one_matches(self):
        def responder(query):
            key = next(iter(json.loads(query["tags"][0])))
            if key == "customer_id":
                return 200, {"data": [_trace("hit", BASE_US, fail=True)]}
            return 200, {"data": []}

        code, out, _, calls = self._run(self.ARGS, responder)
        self.assertEqual(code, 0)
        self.assertIn("matched_key: customer_id", out)
        self.assertIn("- hit ", out)
        self.assertEqual([next(iter(json.loads(c["tags"][0]))) for c in calls],
                         ["uid", "customer_id"])
        self.assertEqual(calls[0]["service"], ["open-gateway.http"])
        self.assertEqual(json.loads(calls[0]["tags"][0]), {"uid": "12345"})
        # 2026-11-23 14:00 Asia/Shanghai is 06:00 UTC.
        self.assertEqual(calls[0]["start"], ["1795413600000000"])

    def test_no_match_on_any_tag_exits_not_found(self):
        code, out, _, calls = self._run(self.ARGS, lambda query: (200, {"data": []}))
        self.assertEqual(code, js.EXIT_NOT_FOUND)
        self.assertIn("trace_count: 0", out)
        self.assertEqual(len(calls), len(js.IDENTIFIER_KEYS))

    def test_window_longer_than_a_day_is_rejected_before_any_request(self):
        argv = ["--env", "qa", "--identifier", "12345",
                "--start", "2026-11-21 14:00", "--end", "2026-11-23 15:00"]
        code, _, err, calls = self._run(argv, lambda query: (200, {"data": []}))
        self.assertEqual(code, js.EXIT_USAGE)
        self.assertIn("24 hours", err)
        self.assertEqual(calls, [])

    def test_server_error_is_reported_as_fetch_failure(self):
        code, _, err, _ = self._run(self.ARGS, lambda query: (500, None))
        self.assertEqual(code, js.EXIT_FETCH)
        self.assertIn("HTTP 500", err)


if __name__ == "__main__":
    unittest.main()
