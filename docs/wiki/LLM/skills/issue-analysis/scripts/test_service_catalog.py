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


REPO = {
    "": ["api/", "cmd/", "internal/", "third_party/", "go.mod", "README.md"],
    "api": ["order/"],
    "api/order": ["v1/"],
    "cmd": ["server/"],
    "internal": ["biz/", "crontab/", "data/"],
    "internal/biz": ["option_expiration/", "order/", "biz.go"],
    "internal/biz/option_expiration": ["usecase.go"],
    "internal/crontab": ["option_expiration_reminder.go", "order_sync.go"],
    "internal/data": ["order/"],
    "third_party": ["google/"],
    "third_party/google": ["api/"],
}


def tree_server(cap, calls=None):
    """A list_tree that walks REPO breadth-first and stops after `cap` entries."""
    def call(name, arguments):
        assert name == "list_tree", name
        if calls is not None:
            calls.append((arguments["path"], arguments["depth"]))
        start = "" if arguments["path"] == "." else arguments["path"]
        entries, level = [], [start]
        for _ in range(arguments["depth"]):
            following = []
            for directory in level:
                for child in REPO.get(directory, []):
                    path = f"{directory}/{child}".strip("/")
                    kind = "dir" if child.endswith("/") else "file"
                    entries.append({"path": path, "type": kind})
                    if kind == "dir":
                        following.append(path)
            level = following
        return {"path": arguments["path"], "entries": entries[:cap],
                "count": min(len(entries), cap), "truncated": len(entries) > cap}
    return call


class TreeTest(unittest.TestCase):
    def test_overview_lists_directories_three_levels_deep_and_no_files(self):
        result = sc.tree(service="trade.order.service", path=None, call=tree_server(cap=200))
        self.assertIn("internal/biz/option_expiration", result["directories"])
        self.assertIn("api/order/v1", result["directories"])
        self.assertNotIn("go.mod", result["directories"])
        self.assertNotIn("files", result)
        self.assertEqual(result["more"], [])

    def test_a_listing_the_server_cut_short_is_fetched_per_top_level_directory(self):
        calls = []
        # 20 entries in three levels, but no top-level directory holds more than 9.
        result = sc.tree(service="trade.order.service", path=None,
                         call=tree_server(cap=9, calls=calls))
        self.assertIn("internal/biz/option_expiration", result["directories"])
        self.assertIn("internal/data/order", result["directories"])
        self.assertEqual(result["more"], [])
        # Dependencies are listed but not walked.
        self.assertIn("third_party", result["directories"])
        self.assertNotIn("third_party/google", result["directories"])
        self.assertNotIn(("third_party", 2), calls)

    def test_a_directory_too_large_to_list_is_named(self):
        result = sc.tree(service="trade.order.service", path=None, call=tree_server(cap=3))
        self.assertIn("internal", result["more"])

    def test_a_path_lists_one_level_with_file_names(self):
        result = sc.tree(service="trade.order.service", path="internal/crontab/",
                         call=tree_server(cap=200))
        self.assertEqual(result["path"], "internal/crontab")
        self.assertEqual(result["directories"], [])
        self.assertEqual(result["files"], ["internal/crontab/option_expiration_reminder.go",
                                           "internal/crontab/order_sync.go"])

    def test_main_takes_one_service_for_a_tree(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(sc.main(["--tree", "--service", "trade.order.service"],
                                     call=tree_server(cap=200)), 0)
            self.assertEqual(sc.main(["--tree", "--service", "a", "--service", "b"],
                                     call=tree_server(cap=200)), 2)
            self.assertEqual(sc.main(["--path", "internal"], call=tree_server(cap=200)), 2)
        self.assertIn("internal/biz", json.loads(out.getvalue())["directories"])


class BudgetTest(unittest.TestCase):
    """Each card may look things up a fixed number of times."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []

    def lookup(self, *argv, task="t_intake"):
        def call(name, arguments):
            self.calls.append(name)
            return fake_call(name, arguments)
        out, err = io.StringIO(), io.StringIO()
        environ = {"HERMES_KANBAN_TASK": task} if task else {}
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sc.main(list(argv), call=call, environ=environ, budget_dir=Path(self.tmp.name))
        return code, out.getvalue(), err.getvalue()

    def test_a_lookup_by_a_card_is_counted(self):
        code, out, _ = self.lookup("--line", "风控")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["lookups_left"], sc.MAX_LOOKUPS_PER_CARD - 1)
        _, out, _ = self.lookup("--line", "风控")
        self.assertEqual(json.loads(out)["lookups_left"], sc.MAX_LOOKUPS_PER_CARD - 2)

    def test_past_the_limit_nothing_is_asked(self):
        for _ in range(sc.MAX_LOOKUPS_PER_CARD):
            self.assertEqual(self.lookup("--line", "风控")[0], 0)
        asked = len(self.calls)
        code, out, err = self.lookup("--line", "风控")
        self.assertEqual(code, sc.EXIT_BUDGET)
        self.assertEqual(out, "")
        self.assertIn(f"{sc.MAX_LOOKUPS_PER_CARD} lookups", err)
        self.assertEqual(len(self.calls), asked)

    def test_each_card_has_its_own_count(self):
        for _ in range(sc.MAX_LOOKUPS_PER_CARD):
            self.lookup("--line", "风控")
        self.assertEqual(self.lookup("--line", "风控", task="t_other")[0], 0)

    def test_a_usage_error_costs_nothing(self):
        self.assertEqual(self.lookup("--service", "risk.risk.service")[0], 2)
        _, out, _ = self.lookup("--line", "风控")
        self.assertEqual(json.loads(out)["lookups_left"], sc.MAX_LOOKUPS_PER_CARD - 1)

    def test_outside_a_card_there_is_no_count(self):
        code, out, _ = self.lookup("--line", "风控", task=None)
        self.assertEqual(code, 0)
        self.assertNotIn("lookups_left", json.loads(out))
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])


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
