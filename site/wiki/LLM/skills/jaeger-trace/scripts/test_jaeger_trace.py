import json
import unittest
from pathlib import Path

import jaeger_trace as jt


def _span(span_id, op, start, duration, process, tags=None, parent=None):
    refs = []
    if parent:
        refs.append({"refType": "CHILD_OF", "traceID": "abc", "spanID": parent})
    return {
        "traceID": "abc",
        "spanID": span_id,
        "operationName": op,
        "startTime": start,
        "duration": duration,
        "processID": process,
        "references": refs,
        "tags": [{"key": k, "value": v} for k, v in (tags or {}).items()],
    }


TRACE = {
    "traceID": "abc",
    "processes": {
        "p1": {"serviceName": "gateway"},
        "p2": {"serviceName": "risk.risk.service"},
    },
    "spans": [
        _span("s1", "GET /orders", 1_700_000_000_000_000, 20_000, "p1", {
            "http.method": "GET",
            "http.status_code": "500",
            "http.url": "https://example.test/orders?token=SECRET",
            "customer_id": "CUST-SECRET",
        }),
        _span("s2", "Query", 1_700_000_000_005_000, 4_000, "p2", {
            "db.system": "mysql",
            "sql": "select * from accounts where id=SECRET",
            "sql.args": "SECRET",
            "error": True,
        }, parent="s1"),
    ],
}


class SummarizeTest(unittest.TestCase):
    def test_summary_hides_payloads_and_keeps_the_call_tree(self):
        text = jt.summarize(TRACE, env="qa")
        self.assertIn("found: yes", text)
        self.assertIn("duration_ms: 20.0", text)
        self.assertIn("gateway GET /orders 20.0ms", text)
        self.assertIn("services: gateway, risk.risk.service", text)
        self.assertIn("error_spans: 2", text)
        self.assertIn("http.method=GET", text)
        self.assertIn("http.status_code=500", text)
        self.assertIn("db.system=mysql", text)
        self.assertIn("gateway GET /orders", text)
        self.assertIn("  risk.risk.service Query", text)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("http.url", text)
        self.assertNotIn("customer_id", text)
        self.assertNotIn("sql=", text)
        self.assertIn("Asia/Shanghai", text)

    def test_not_found_detects_status_and_error_body(self):
        self.assertTrue(jt.is_not_found(404, None))
        self.assertTrue(jt.is_not_found(200, {"errors": [{"code": 404, "msg": "trace not found"}]}))
        self.assertFalse(jt.is_not_found(200, TRACE))

    def test_unwraps_the_api_envelope(self):
        self.assertEqual(jt.unwrap_trace({"data": [TRACE]})["traceID"], "abc")
        self.assertIsNone(jt.unwrap_trace({"data": [], "errors": [{"code": 404}]}))


# A gateway call into one service, which then calls a second backend that
# never answers: the last span is a failed client call with nothing under it.
CHAIN = {
    "traceID": "abc",
    "processes": {
        "p1": {"serviceName": "open-gateway.http"},
        "p2": {"serviceName": "ams.account.job.grpc"},
    },
    "spans": [
        _span("g1", "GET /info", 1_700_000_000_000_000, 5_000_000, "p1", {
            "http.status_code": "500", "span.kind": "server"}),
        _span("g2", "/ams.Account/Get", 1_700_000_000_001_000, 4_999_000, "p1", {
            "error": True, "span.kind": "client"}, parent="g1"),
        _span("a1", "/ams.Account/Get", 1_700_000_000_002_000, 4_998_000, "p2", {
            "error": True, "span.kind": "server"}, parent="g2"),
        _span("a2", "/customer.Customer/Get", 1_700_000_000_003_000, 5_000, "p2", {
            "span.kind": "client"}, parent="a1"),
        _span("a3", "/trs.AccountService/ListAccounts", 1_700_000_000_009_000, 4_990_000, "p2", {
            "error": True, "span.kind": "client"}, parent="a1"),
    ],
}


class FailurePointTest(unittest.TestCase):
    def test_names_the_error_span_deepest_in_the_tree(self):
        text = jt.summarize(CHAIN, env="qa")
        self.assertIn(
            "deepest_error: ams.account.job.grpc /trs.AccountService/ListAccounts", text)

    def test_lists_a_failed_outgoing_call_that_no_service_answered(self):
        text = jt.summarize(CHAIN, env="qa")
        self.assertIn("unanswered_calls: 1", text)
        self.assertIn(
            "- ams.account.job.grpc -> /trs.AccountService/ListAccounts 4990.0ms", text)

    def test_a_failed_call_with_a_server_span_under_it_is_answered(self):
        facts = jt.analyze(CHAIN)
        self.assertEqual([s["spanID"] for s in facts["unanswered"]], ["a3"])

    def test_a_trace_without_error_spans_has_no_failure_point(self):
        healthy = {
            "traceID": "abc",
            "processes": {"p1": {"serviceName": "gateway"}},
            "spans": [_span("s1", "GET /ok", 1_700_000_000_000_000, 1_000, "p1",
                            {"http.status_code": "200"})],
        }
        text = jt.summarize(healthy, env="qa")
        self.assertIn("error_spans: 0", text)
        self.assertIn("deepest_error: none", text)
        self.assertIn("unanswered_calls: 0", text)

    def test_analyze_reports_bounds_and_services(self):
        facts = jt.analyze(CHAIN)
        self.assertEqual(facts["services"], ["open-gateway.http", "ams.account.job.grpc"])
        self.assertEqual(facts["start_us"], 1_700_000_000_000_000)
        self.assertEqual(facts["end_us"], 1_700_000_000_000_000 + 5_000_000)
        self.assertEqual(jt.service_of(facts["deepest_error"], facts), "ams.account.job.grpc")


def _one_error_span(tags):
    return {
        "traceID": "abc",
        "processes": {"p1": {"serviceName": "open-gateway.http"}},
        "spans": [_span("s1", "/ams.Account/Get", 1_700_000_000_000_000, 5_000_000, "p1",
                        {"error": True, "span.kind": "client", **tags})],
    }


class GrpcErrorTest(unittest.TestCase):
    """A reader who sees a bare 13 guesses its meaning, and guesses wrong."""

    def error_line(self, tags):
        text = jt.summarize(_one_error_span(tags), env="qa")
        return next(line for line in text.splitlines() if line.startswith("- open-gateway.http"))

    def test_a_grpc_status_code_is_printed_with_its_name(self):
        self.assertIn("rpc.grpc.status_code=13(Internal)",
                      self.error_line({"rpc.grpc.status_code": 13}))
        self.assertIn("rpc.grpc.status_code=4(DeadlineExceeded)",
                      self.error_line({"rpc.grpc.status_code": "4"}))

    def test_a_code_outside_the_grpc_range_is_printed_as_it_is(self):
        self.assertIn("rpc.grpc.status_code=99 ", self.error_line({"rpc.grpc.status_code": 99}) + " ")

    def test_the_grpc_errors_named_in_the_description_are_listed_outermost_first(self):
        line = self.error_line({"otel.status_description": (
            "rpc error: code = Internal desc = rpc error: code = DeadlineExceeded "
            "desc = context deadline exceeded for account SECRET")})
        self.assertIn("grpc_error=Internal>DeadlineExceeded", line)

    def test_nothing_else_of_the_description_is_printed(self):
        line = self.error_line({"otel.status_description": (
            "rpc error: code = DeadlineExceeded desc = context deadline exceeded for account SECRET")})
        self.assertIn("grpc_error=DeadlineExceeded", line)
        self.assertNotIn("SECRET", line)
        self.assertNotIn("context deadline", line)
        self.assertNotIn("otel.status_description", line)

    def test_a_description_without_a_grpc_code_adds_nothing(self):
        line = self.error_line({"otel.status_description": "account SECRET not found, code = Whatever"})
        self.assertNotIn("grpc_error", line)
        self.assertNotIn("SECRET", line)
        self.assertNotIn("Whatever", line)


class FindEnvTest(unittest.TestCase):
    def _with_fetch(self, fake):
        original = jt.fetch_trace
        jt.fetch_trace = fake
        self.addCleanup(lambda: setattr(jt, "fetch_trace", original))

    def test_returns_the_environment_that_holds_the_trace(self):
        asked = []

        def fake_fetch(base, trace_id, timeout):
            asked.append(base)
            if base == jt.ENV_BASES["qa"]:
                return 200, {"data": [CHAIN]}
            return 404, {"data": None, "errors": [{"code": 404}]}

        self._with_fetch(fake_fetch)
        found = jt.find_env("abc", envs=("prod", "qa", "test"))
        self.assertEqual(found["env"], "qa")
        self.assertEqual(found["trace"]["traceID"], "abc")
        self.assertEqual(found["unreachable"], [])
        # The search stops at the first server that has the trace.
        self.assertEqual(asked, [jt.ENV_BASES["prod"], jt.ENV_BASES["qa"]])

    def test_reports_a_server_that_could_not_be_asked(self):
        import urllib.error

        def fake_fetch(base, trace_id, timeout):
            if base == jt.ENV_BASES["prod"]:
                raise urllib.error.URLError("timed out")
            return 404, None

        self._with_fetch(fake_fetch)
        found = jt.find_env("abc", envs=("prod", "qa"))
        self.assertIsNone(found["env"])
        self.assertEqual(found["unreachable"], ["prod"])

    def test_a_server_that_stops_answering_midway_does_not_end_the_search(self):
        def fake_fetch(base, trace_id, timeout):
            if base == jt.ENV_BASES["prod"]:
                raise TimeoutError("The read operation timed out")
            return 200, {"data": [CHAIN]}

        self._with_fetch(fake_fetch)
        found = jt.find_env("abc", envs=("prod", "qa"))
        self.assertEqual(found["env"], "qa")
        self.assertEqual(found["unreachable"], ["prod"])


class MainTest(unittest.TestCase):
    def test_not_found_exit_code_prints_no_raw_body(self):
        def fake_fetch(base, trace_id, timeout):
            return 404, {"data": None, "errors": [{"code": 404, "msg": "trace not found"}]}

        original = jt.fetch_trace
        jt.fetch_trace = fake_fetch
        try:
            code = jt.main(["--env", "qa", "--trace-id", "deadbeef"])
        finally:
            jt.fetch_trace = original
        self.assertEqual(code, jt.EXIT_NOT_FOUND)

    def test_raw_out_keeps_the_unredacted_document(self):
        def fake_fetch(base, trace_id, timeout):
            return 200, {"data": [TRACE]}

        original = jt.fetch_trace
        jt.fetch_trace = fake_fetch
        path = Path("/tmp/jaeger-trace-test-raw.json")
        try:
            code = jt.main([
                "--env", "qa", "--trace-id", "abc", "--raw-out", str(path),
            ])
        finally:
            jt.fetch_trace = original
        self.assertEqual(code, 0)
        saved = json.loads(path.read_text())
        self.assertIn("CUST-SECRET", json.dumps(saved))
        path.unlink()


if __name__ == "__main__":
    unittest.main()
