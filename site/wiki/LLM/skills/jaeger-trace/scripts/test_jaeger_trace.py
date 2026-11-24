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
