import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import service_catalog as sc


def fake_call(name, arguments):
    if name == "list_biz_lines":
        return {"biz_lines": [{"name": "风控", "service_count": 1},
                              {"name": "交易", "service_count": 2},
                              {"name": "调试", "service_count": 0}]}
    if name == "list_services":
        return {"services": {
            "风控": [{"repo_id": "risk.risk.service", "service_name": "risk.risk.service",
                     "description": "实时账户保证金风控服务", "branch": "main"}],
            "交易": [{"repo_id": "trade.order.service", "service_name": "trade.order.service",
                     "description": "订单服务"},
                    {"repo_id": "trade.market.service", "service_name": "trade.market.service",
                     "description": "交易行情"}],
        }[arguments["biz_line"]]}
    if name == "search":
        if arguments["repo_id"] == "no.such":
            raise sc.CatalogError("sourceinsight search: unknown repo_id: no.such", code=4)
        if arguments["repo_id"] == "risk.risk.service":
            return {"count": 3, "truncated": True, "hits": [
                {"path": "internal/poller/close.go", "line": 10, "snippet": "SECRET SOURCE LINE"},
                {"path": "internal/poller/close.go", "line": 22, "snippet": "SECRET SOURCE LINE"},
                {"path": "internal/alert/feishu.go", "line": 5, "snippet": "SECRET SOURCE LINE"}]}
        return {"count": 0, "truncated": False, "hits": []}
    raise AssertionError(name)


class CatalogTest(unittest.TestCase):
    def test_lists_every_line_that_has_services(self):
        result = sc.list_catalog(line=None, call=fake_call)
        self.assertEqual([b["biz_line"] for b in result["biz_lines"]], ["风控", "交易"])
        self.assertEqual(result["biz_lines"][0]["services"], [
            {"catalog_name": "risk.risk.service", "description": "实时账户保证金风控服务"}])

    def test_line_filter_and_unknown_line(self):
        result = sc.list_catalog(line="交易", call=fake_call)
        self.assertEqual(len(result["biz_lines"]), 1)
        with self.assertRaises(sc.CatalogError) as ctx:
            sc.list_catalog(line="清算", call=fake_call)
        self.assertEqual(ctx.exception.code, 4)

    def test_search_reports_counts_and_files_but_no_source(self):
        result = sc.search_text(text="get close price failed",
                                services=["risk.risk.service", "trade.order.service", "no.such"],
                                call=fake_call)
        self.assertEqual(result["results"][0], {
            "catalog_name": "risk.risk.service", "occurrences": 3, "more": True,
            "files": ["internal/poller/close.go", "internal/alert/feishu.go"]})
        self.assertEqual(result["results"][1]["occurrences"], 0)
        self.assertIn("unknown repo_id", result["results"][2]["error"])
        self.assertNotIn("SECRET SOURCE LINE", json.dumps(result))

    def test_search_limits(self):
        with self.assertRaises(sc.CatalogError):
            sc.search_text(text="ab", services=["a"], call=fake_call)
        with self.assertRaises(sc.CatalogError):
            sc.search_text(text="abcdef", services=["a", "b", "c", "d"], call=fake_call)
        with self.assertRaises(sc.CatalogError):
            sc.search_text(text="abcdef", services=[], call=fake_call)

    def test_main_prints_json_and_never_a_snippet(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sc.main(["--text", "close price", "--service", "risk.risk.service"],
                           call=fake_call)
        self.assertEqual(code, 0)
        self.assertNotIn("SECRET SOURCE LINE", out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["results"][0]["occurrences"], 3)

    def test_service_without_text_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(sc.main(["--service", "risk.risk.service"], call=fake_call), 2)


class TransportTest(unittest.TestCase):
    def test_parses_plain_json_and_server_sent_events(self):
        message = {"jsonrpc": "2.0", "id": 1, "result": {}}
        self.assertEqual(sc.parse_response(json.dumps(message)), message)
        self.assertEqual(sc.parse_response("event: message\ndata: " + json.dumps(message) + "\n"),
                         message)
        with self.assertRaises(sc.CatalogError):
            sc.parse_response("event: ping\n")

    def test_authorization_prefers_the_environment_then_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("OTHER=1\nSOURCEINSIGHT_AUTHORIZATION=Bearer from-file\n")
            self.assertEqual(sc.authorization({sc.AUTH_VAR: "Bearer from-env"}, env_file),
                             "Bearer from-env")
            self.assertEqual(sc.authorization({}, env_file), "Bearer from-file")
            with self.assertRaises(sc.CatalogError):
                sc.authorization({}, Path(tmp) / "missing")


if __name__ == "__main__":
    unittest.main()
