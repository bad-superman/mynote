import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import check_list as cl
import deployed_version as dv


def statements(source):
    return cl.log_statements(source)


def texts(source):
    found = statements(source)
    return found[0].texts if found else None


class LogStatementTest(unittest.TestCase):
    def test_finds_the_fixed_part_before_the_first_verb(self):
        found = statements('package a\n\nfunc f() {\n\tlogger.Infof("order created, id=%d", id)\n}\n')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 4)
        self.assertEqual(found[0].method, "Infof")
        self.assertEqual(found[0].texts, ("order created, id=",))
        self.assertFalse(found[0].debug)

    def test_keeps_every_fixed_part_between_verbs(self):
        self.assertEqual(
            texts('gologger.Infof(ctx, "gRPC调用耗时拆解: 服务=%s 方法=%s 耗时ms=%d", a, b, c)'),
            ("gRPC调用耗时拆解: 服务=", " 方法=", " 耗时ms="))

    def test_a_call_over_several_lines_ends_at_its_closing_parenthesis(self):
        found = statements('x := 1\nu.log.WithContext(ctx).Infof("execute expiry: order created, id=%d",\n\tposition.ID,\n\tresult.No)\ny := 2\n')
        self.assertEqual((found[0].line, found[0].end_line), (2, 4))

    def test_reads_a_logger_reached_through_calls(self):
        for call in ('klog.NewHelper(logger).Warnf("rate limited %s", k)',
                     's.Logger().WithContext(ctx).Errorf("rate limited %s", k)',
                     'uc.exchangeAssetLogger.WithContext(ctx).Warnf("rate limited %s", k)',
                     'youfilogger.Infof(ctx, "rate limited %s", k)',
                     'helper.Error("rate limited ", k)',
                     'log.Printf("rate limited %s", k)'):
            with self.subTest(call=call):
                self.assertEqual(texts(call)[0].strip(), "rate limited")

    def test_building_an_error_is_not_writing_a_log(self):
        for call in ('return fmt.Errorf("create order failed: %w", err)',
                     'return errors.New("create order failed")',
                     'return status.Errorf(codes.Internal, "create order failed")',
                     't.Fatalf("create order failed: %v", err)',
                     'msg := err.Error()',
                     'return u.serverError(ctx, "create order failed", err)'):
            with self.subTest(call=call):
                self.assertEqual(statements(call), [])

    def test_a_commented_out_statement_writes_nothing(self):
        source = ('// logger.Infof("task registered %s", name)\n'
                  '/*\nlogger.Infof("task started %s", name)\n*/\n'
                  'logger.Infof("task skipped %s", name)\n')
        found = statements(source)
        self.assertEqual([item.texts for item in found], [("task skipped ",)])
        self.assertEqual(found[0].line, 5)

    def test_slashes_inside_a_string_do_not_start_a_comment(self):
        self.assertEqual(texts('logger.Infof("see http://host/path for %s", id)'),
                         ("see http://host/path for ",))

    def test_a_quote_rune_does_not_start_a_string(self):
        found = statements("if c == '\"' {\n\tlogger.Info(\"quote seen\")\n}\n")
        self.assertEqual([item.texts for item in found], [("quote seen",)])

    def test_reads_a_raw_string(self):
        self.assertEqual(texts('logger.Infof(`raw text %s`, x)'), ("raw text ",))

    def test_a_message_built_with_sprintf_is_logged_text(self):
        self.assertEqual(texts('logger.Info(fmt.Sprintf("order %s created", id))'),
                         ("order ", " created"))

    def test_a_string_passed_to_another_function_is_not_logged_text(self):
        self.assertEqual(texts('logger.Errorf("load failed: %v", wrap(err, "inner detail"))'),
                         ("load failed: ",))

    def test_strings_inside_a_composite_literal_are_not_logged_text(self):
        self.assertEqual(texts('logger.Infow("msg", "sync done", "tags", []string{"alpha", "beta"})'),
                         ("msg", "sync done", "tags"))

    def test_concatenated_strings_are_separate_parts(self):
        self.assertEqual(texts('logger.Info("sync done for " + name + ", took " + cost)'),
                         ("sync done for ", ", took "))

    def test_an_escape_ends_a_part(self):
        self.assertEqual(texts('logger.Infof("line one\\nline two %s", x)'),
                         ("line one", "line two "))

    def test_a_doubled_percent_ends_a_part(self):
        self.assertEqual(texts('logger.Infof("progress 50%% of %d", n)'),
                         ("progress 50", " of "))

    def test_a_percent_sign_stays_when_the_method_does_not_format(self):
        self.assertEqual(texts('logger.Info("rate 5% reached")'), ("rate 5% reached",))

    def test_characters_a_json_log_may_escape_end_a_part(self):
        self.assertEqual(texts('logger.Infof("resp <%s> ok & done", r)'),
                         ("resp ", " ok ", " done"))

    def test_a_part_without_a_letter_or_digit_is_dropped(self):
        self.assertEqual(texts('logger.Infof("%s: %s", a, b)'), ())

    def test_debug_statements_are_marked(self):
        self.assertTrue(statements('logger.Debugf("cache hit %s", k)')[0].debug)
        self.assertTrue(statements('logger.Log(log.LevelDebug, "msg", "cache hit")')[0].debug)
        self.assertFalse(statements('logger.Log(log.LevelInfo, "msg", "cache hit")')[0].debug)

    def test_statements_come_in_source_order(self):
        source = 'logger.Info("first")\nlogger.Warn("second")\nlogger.Error("third")\n'
        self.assertEqual([(item.line, item.method) for item in statements(source)],
                         [(1, "Info"), (2, "Warn"), (3, "Error")])

    def test_an_unclosed_call_is_ignored(self):
        self.assertEqual(statements('logger.Infof("never closed %s", x'), [])


CODE_MD = """# Code Investigation Report

## 结论
风控校验失败后直接返回。

## 待验证
1. 要确认：该笔请求走到了风控校验失败的分支
   - 服务：trade.order-service.job
   - 去哪查：日志 "risk check failed"（internal/biz/order.go:42）
   - 成立时会看到：窗口内有这条日志
   - 不成立时会看到：窗口内没有这条日志

2. 要确认：订单没有落库
   - 服务：trade.order-service.job
   - 去哪查：数据库（看板查不了）：orders 表，order_no = 该订单号
   - 成立时会看到：没有这一行
   - 不成立时会看到：有这一行

## 下一跳
- 无
"""


class ParseListTest(unittest.TestCase):
    def test_reads_each_item_and_its_fields(self):
        items = cl.parse_list(CODE_MD)
        self.assertEqual([item.number for item in items], [1, 2])
        first = items[0]
        self.assertEqual(first.statement, "该笔请求走到了风控校验失败的分支")
        self.assertEqual(first.service, "trade.order-service.job")
        self.assertEqual(first.where, '日志 "risk check failed"（internal/biz/order.go:42）')
        self.assertEqual(first.holds, "窗口内有这条日志")
        self.assertEqual(first.fails, "窗口内没有这条日志")

    def test_stops_at_the_next_heading(self):
        items = cl.parse_list(CODE_MD)
        self.assertEqual(items[-1].fails, "有这一行")

    def test_accepts_bold_labels_and_ascii_colons(self):
        text = ("## 待验证\n"
                "1. **要确认**: 走到了失败分支\n"
                "   - **服务**: ams.account.job\n"
                "   * 去哪查: 指标 order_fail_total\n"
                "   - 成立时会看到: 计数增加\n"
                "   - 不成立时会看到: 计数不变\n")
        item = cl.parse_list(text)[0]
        self.assertEqual(item.statement, "走到了失败分支")
        self.assertEqual(item.service, "ams.account.job")
        self.assertEqual(item.where, "指标 order_fail_total")
        self.assertEqual((item.holds, item.fails), ("计数增加", "计数不变"))

    def test_a_field_may_continue_on_the_next_line(self):
        text = ("## 待验证\n"
                "1. 要确认：走到了失败分支\n"
                "   - 服务：ams.account.job\n"
                "   - 去哪查：日志 \"risk check failed\"\n"
                "     （internal/biz/order.go:42）\n"
                "   - 成立时会看到：有\n"
                "   - 不成立时会看到：没有\n")
        self.assertEqual(cl.parse_list(text)[0].where,
                         '日志 "risk check failed" （internal/biz/order.go:42）')

    def test_a_missing_field_is_empty(self):
        text = "## 待验证\n1. 要确认：走到了失败分支\n   - 去哪查：指标 order_fail_total\n"
        item = cl.parse_list(text)[0]
        self.assertEqual((item.service, item.holds, item.fails), ("", "", ""))

    def test_a_list_that_says_none_is_empty(self):
        for body in ("- 无\n", "无\n", "\n"):
            with self.subTest(body=body):
                self.assertEqual(cl.parse_list("## 结论\nx\n\n## 待验证\n" + body + "\n## 下一跳\n- 无\n"), [])

    def test_a_report_without_the_section_is_an_error(self):
        with self.assertRaises(cl.ListError):
            cl.parse_list("# Code Investigation Report\n\n## 结论\n没有清单\n")

    def test_a_list_rewritten_on_a_retry_replaces_the_earlier_one(self):
        text = ("## 待验证\n1. 要确认：第一次写的\n\n## 下一跳\n- 无\n\n"
                "## 待验证\n1. 要确认：重试后写的\n\n## 下一跳\n- 无\n")
        self.assertEqual([item.statement for item in cl.parse_list(text)], ["重试后写的"])

    def test_a_decimal_at_the_start_of_a_line_is_not_a_new_item(self):
        text = ("## 待验证\n"
                "1. 要确认：调用等满了超时时间\n"
                "   - 成立时会看到：耗时接近\n"
                "     5.0 秒\n")
        items = cl.parse_list(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].holds, "耗时接近 5.0 秒")


MAIN = "trade.order-service.job"

ORDER_GO = """package biz

func (u *UseCase) Place(ctx context.Context, req *Req) error {
	if err := u.risk.Check(ctx, req); err != nil {
		u.log.WithContext(ctx).Errorf("risk check failed, order_no=%s err=%v", req.OrderNo, err)
		return err
	}
	u.log.WithContext(ctx).Debugf("risk check passed, order_no=%s", req.OrderNo)
	// u.log.Infof("order task registered %s", name)
	return u.repo.Save(ctx, req)
}

func (u *UseCase) Cancel(ctx context.Context, req *Req) error {
	u.log.WithContext(ctx).Infof("cancel accepted, order_no=%s",
		req.OrderNo,
	)
	return nil
}
"""

FILES = {
    "internal/biz/order.go": ORDER_GO,
    "internal/biz/risk.go": 'package biz\n\nfunc (r *Risk) Check() {\n\tlogger.Warnf("risk limit reached, account=%d", id)\n}\n',
    "internal/biz/quiet.go": 'package biz\n\nfunc Quiet() error {\n\treturn fmt.Errorf("quiet failure")\n}\n',
    "internal/data/order.go": "package data\n",
    "scripts/sync.py": 'logger.info("sync started")\n',
}


class Source:
    """The files of a commit, held in memory."""

    def __init__(self, files=FILES):
        self._files = files

    def files(self):
        return sorted(self._files)

    def read(self, path):
        return self._files[path]


def entry(where, *, number=1, service=MAIN, statement="走到了失败分支", holds="有", fails="没有"):
    return cl.Item(number, statement=statement, service=service, where=where, holds=holds, fails=fails)


def check_one(where, **fields):
    return cl.check([entry(where, **fields)], service=MAIN, source=Source())[0]


class ConfirmedTest(unittest.TestCase):
    def test_a_text_from_the_cited_log_statement_is_confirmed(self):
        result = check_one('日志 "risk check failed"（internal/biz/order.go:5）')
        self.assertEqual(result.number, 1)
        self.assertEqual(result.status, "已确认")
        self.assertIn('"risk check failed"', result.detail)
        self.assertIn("internal/biz/order.go:5", result.detail)
        self.assertIn("Errorf", result.detail)

    def test_a_file_name_is_enough_when_only_one_file_has_it(self):
        result = check_one('日志 "risk limit reached"（risk.go:4）')
        self.assertEqual(result.status, "已确认")
        self.assertIn("internal/biz/risk.go:4", result.detail)

    def test_a_path_inside_a_worktree_is_read_from_the_commit(self):
        result = check_one(
            '日志 "risk limit reached"（/home/roy/dev/.hermes-issue-analysis/t_1/code-worktree/internal/biz/risk.go:4）')
        self.assertEqual(result.status, "已确认")
        self.assertIn("internal/biz/risk.go:4", result.detail)

    def test_the_line_may_be_three_lines_off(self):
        self.assertEqual(check_one('日志 "risk check failed"（internal/biz/order.go:2）').status, "已确认")
        self.assertIn("internal/biz/order.go:5",
                      check_one('日志 "risk check failed"（internal/biz/order.go:2）').detail)

    def test_a_long_call_counts_from_its_last_line(self):
        # The statement is on lines 14 to 16.
        self.assertEqual(check_one('日志 "cancel accepted"（internal/biz/order.go:19）').status, "已确认")
        self.assertEqual(check_one('日志 "cancel accepted"（internal/biz/order.go:20）').status, "要改")

    def test_other_quote_marks_and_ascii_parentheses_are_read(self):
        for where in ('日志 “risk check failed”(internal/biz/order.go:5)',
                      '日志 `risk check failed`（internal/biz/order.go:5）',
                      '日志："risk check failed"（internal/biz/order.go：5）',
                      '日志 "risk check failed"（internal/biz/order.go:5-6），按 trace 查'):
            with self.subTest(where=where):
                self.assertEqual(check_one(where).status, "已确认")

    def test_metric_and_database_entries_pass(self):
        self.assertEqual(check_one("指标 order_fail_total").status, "通过")
        self.assertEqual(check_one("数据库（看板查不了）：orders 表，order_no = 该订单号").status, "通过")


class NotConfirmedTest(unittest.TestCase):
    def test_a_debug_statement_cannot_refute(self):
        result = check_one('日志 "risk check passed"（internal/biz/order.go:8）')
        self.assertEqual(result.status, "未确认")
        self.assertIn("Debugf", result.detail)

    def test_a_statement_outside_the_repository_cannot_refute(self):
        result = check_one('日志 "xxl-job executor run error"（不在本仓库：XXL-Job 执行器库）')
        self.assertEqual(result.status, "未确认")
        self.assertIn("XXL-Job 执行器库", result.detail)

    def test_another_service_was_not_resolved(self):
        result = check_one('日志 "ListAccounts"（internal/service/account.go:10）',
                           service="trade.asset-service.job")
        self.assertEqual(result.status, "未确认")
        self.assertIn("trade.asset-service.job", result.detail)
        self.assertIn(MAIN, result.detail)

    def test_a_service_written_with_a_remark_is_still_the_main_one(self):
        result = check_one('日志 "risk check failed"（internal/biz/order.go:5）',
                           service=f"{MAIN}（qa）")
        self.assertEqual(result.status, "已确认")

    def test_only_go_sources_are_read(self):
        result = check_one('日志 "sync started"（scripts/sync.py:1）')
        self.assertEqual(result.status, "未确认")
        self.assertIn("Go", result.detail)


class NeedsFixingTest(unittest.TestCase):
    def assert_fix(self, where, *fragments, **fields):
        result = check_one(where, **fields)
        self.assertEqual(result.status, "要改", result.detail)
        for fragment in fragments:
            self.assertIn(fragment, result.detail)
        return result

    def test_a_text_without_a_source_location(self):
        self.assert_fix('日志 "risk check failed"', "<文件>:<行号>", "不在本仓库")

    def test_a_search_instruction_instead_of_a_text(self):
        self.assert_fix("该服务在时间窗口内的请求日志", "日志", "指标", "数据库")

    def test_a_log_entry_without_a_quoted_text(self):
        self.assert_fix("日志 风控校验失败的那一条（internal/biz/order.go:5）", "引号")

    def test_two_texts_in_one_entry(self):
        self.assert_fix('日志 "risk check failed" 或 "risk limit reached"（internal/biz/order.go:5）',
                        "一个")
        self.assert_fix('日志 "risk check failed"（internal/biz/order.go:5）或 "risk limit reached"（risk.go:4）',
                        "一个")

    def test_a_text_that_runs_across_a_value_filled_in_at_run_time(self):
        self.assert_fix('日志 "risk check failed, order_no=%s err=%v"（internal/biz/order.go:5）',
                        '"risk check failed, order_no="')

    def test_a_function_name_where_the_statement_is_commented_out(self):
        self.assert_fix('日志 "order task registered"（internal/biz/order.go:9）', "internal/biz/order.go")

    def test_a_text_no_statement_there_writes(self):
        self.assert_fix('日志 "RegTask("（internal/biz/order.go:5）', '"risk check failed, order_no="')

    def test_the_right_text_at_the_wrong_line(self):
        self.assert_fix('日志 "cancel accepted"（internal/biz/order.go:5）', "14")

    def test_a_place_without_a_log_statement(self):
        self.assert_fix('日志 "save order"（internal/biz/order.go:40）',
                        "logs --file internal/biz/order.go --around 40")

    def test_a_file_that_writes_no_log(self):
        self.assert_fix('日志 "quiet failure"（internal/biz/quiet.go:4）', "没有日志语句")

    def test_a_file_the_commit_does_not_have(self):
        self.assert_fix('日志 "risk check failed"（internal/biz/missing.go:5）', "internal/biz/missing.go")

    def test_a_file_name_shared_by_two_files(self):
        self.assert_fix('日志 "risk check failed"（order.go:5）',
                        "internal/biz/order.go", "internal/data/order.go")

    def test_an_empty_text(self):
        self.assert_fix('日志 ""（internal/biz/order.go:5）', "引号")

    def test_a_text_the_log_search_cannot_take(self):
        self.assert_fix('日志 "risk check failed\\n"（internal/biz/order.go:5）', "反斜杠")

    def test_missing_fields_are_named(self):
        result = cl.check([cl.Item(1, statement="走到了失败分支", where="指标 order_fail_total")],
                          service=MAIN, source=Source())[0]
        self.assertEqual(result.status, "要改")
        for name in ("服务", "成立时会看到", "不成立时会看到"):
            self.assertIn(name, result.detail)
        self.assertNotIn("去哪查", result.detail)


class WholeListTest(unittest.TestCase):
    def test_results_keep_the_order_and_numbers_of_the_list(self):
        results = cl.check(
            [entry('日志 "risk check failed"（internal/biz/order.go:5）', number=1),
             entry("指标 order_fail_total", number=2),
             entry("数据库（看板查不了）：orders 表", number=3)],
            service=MAIN, source=Source())
        self.assertEqual([(r.number, r.status) for r in results],
                         [(1, "已确认"), (2, "通过"), (3, "通过")])

    def test_a_database_entry_must_be_the_last_one(self):
        results = cl.check(
            [entry("数据库（看板查不了）：orders 表", number=1),
             entry("指标 order_fail_total", number=2)],
            service=MAIN, source=Source())
        self.assertEqual([r.status for r in results], ["要改", "通过"])
        self.assertIn("最后", results[0].detail)

    def test_only_one_database_entry(self):
        results = cl.check(
            [entry("数据库（看板查不了）：orders 表", number=1),
             entry("数据库（看板查不了）：positions 表", number=2)],
            service=MAIN, source=Source())
        self.assertEqual([r.status for r in results], ["要改", "要改"])

    def test_more_than_five_entries_is_reported_for_the_list(self):
        results = cl.check([entry("指标 order_fail_total", number=n) for n in range(1, 7)],
                           service=MAIN, source=Source())
        self.assertEqual(len(results), 7)
        self.assertIsNone(results[-1].number)
        self.assertEqual(results[-1].status, "要改")
        self.assertIn("6", results[-1].detail)

    def test_an_empty_list_has_no_results(self):
        self.assertEqual(cl.check([], service=MAIN, source=Source()), [])


def many_statements(count):
    return "package biz\n" + "".join(f'logger.Infof("step {n} done %d", n)\n' for n in range(1, count + 1))


class ListLogsTest(unittest.TestCase):
    def test_lists_each_statement_with_its_line_and_searchable_text(self):
        result = cl.list_logs(Source(), "internal/biz/order.go")
        self.assertEqual(result["file"], "internal/biz/order.go")
        self.assertEqual(result["total"], 3)
        self.assertEqual(
            [(row["line"], row["method"], row["text"], row["debug"]) for row in result["shown"]],
            [(5, "Errorf", "risk check failed, order_no=", False),
             (8, "Debugf", "risk check passed, order_no=", True),
             (14, "Infof", "cancel accepted, order_no=", False)])

    def test_the_text_is_the_longest_fixed_part_without_outer_spaces(self):
        source = Source({"a.go": 'logger.Infof("id=%d  the order was rejected by risk  %s", id, why)\n'})
        self.assertEqual(cl.list_logs(source, "a.go")["shown"][0]["text"], "the order was rejected by risk")

    def test_a_very_long_text_is_cut(self):
        source = Source({"a.go": 'logger.Info("' + "long message " * 30 + '")\n'})
        text = cl.list_logs(source, "a.go")["shown"][0]["text"]
        self.assertEqual(len(text), 120)
        self.assertTrue(("long message " * 30).startswith(text))

    def test_a_file_name_is_resolved_like_a_citation(self):
        self.assertEqual(cl.list_logs(Source(), "risk.go")["file"], "internal/biz/risk.go")

    def test_around_keeps_the_statements_within_forty_lines(self):
        source = Source({"big.go": many_statements(200)})
        result = cl.list_logs(source, "big.go", around=100)
        lines = [row["line"] for row in result["shown"]]
        self.assertEqual((min(lines), max(lines)), (60, 140))
        self.assertEqual(result["total"], 200)

    def test_around_falls_back_to_the_nearest_statements(self):
        result = cl.list_logs(Source(), "internal/biz/order.go", around=500)
        self.assertEqual([row["line"] for row in result["shown"]], [5, 8, 14])

    def test_a_long_file_is_cut_at_forty_statements(self):
        result = cl.list_logs(Source({"big.go": many_statements(200)}), "big.go")
        self.assertEqual(len(result["shown"]), 40)
        self.assertEqual(result["total"], 200)

    def test_an_unknown_file_is_an_error(self):
        with self.assertRaises(dv.ResolveError) as caught:
            cl.list_logs(Source(), "internal/biz/missing.go")
        self.assertEqual(caught.exception.code, 4)

    def test_a_shared_file_name_is_an_error_that_lists_the_files(self):
        with self.assertRaises(dv.ResolveError) as caught:
            cl.list_logs(Source(), "order.go")
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(caught.exception.payload["candidates"],
                         ["internal/biz/order.go", "internal/data/order.go"])

    def test_only_go_sources_are_listed(self):
        with self.assertRaises(dv.ResolveError) as caught:
            cl.list_logs(Source(), "scripts/sync.py")
        self.assertEqual(caught.exception.code, 2)


class RenderTest(unittest.TestCase):
    def test_logs_are_shown_one_statement_per_line(self):
        text = cl.render_logs(cl.list_logs(Source(), "internal/biz/order.go"))
        self.assertIn("file: internal/biz/order.go", text)
        self.assertIn("log statements: 3", text)
        self.assertRegex(text, r'(?m)^\s+5\s+Errorf\s+"risk check failed, order_no="$')
        self.assertRegex(text, r'(?m)^\s+8\s+Debugf\s+"risk check passed, order_no="\s+\(debug')
        self.assertIn("（internal/biz/order.go:<line>）", text)

    def test_a_filtered_listing_says_how_many_there_are(self):
        text = cl.render_logs(cl.list_logs(Source({"big.go": many_statements(200)}), "big.go", around=100))
        self.assertIn("log statements: 200, showing 81 within 40 lines of 100", text)

    def test_a_cut_listing_points_to_around(self):
        text = cl.render_logs(cl.list_logs(Source({"big.go": many_statements(200)}), "big.go"))
        self.assertIn("log statements: 200, showing the first 40", text)
        self.assertIn("--around", text)

    def test_a_file_without_log_statements_is_called_silent(self):
        text = cl.render_logs(cl.list_logs(Source(), "internal/biz/quiet.go"))
        self.assertIn("log statements: 0", text)
        self.assertIn("writes nothing to the log", text)

    def test_a_statement_that_logs_only_values_has_no_text(self):
        text = cl.render_logs(cl.list_logs(Source({"a.go": "logger.Error(err)\n"}), "a.go"))
        self.assertRegex(text, r"(?m)^\s+1\s+Error\s+\(no fixed text")

    def test_the_check_has_one_line_per_item_and_the_totals(self):
        results = cl.check(
            [entry('日志 "risk check failed"（internal/biz/order.go:5）', number=1),
             entry('日志 "RegTask("（internal/biz/order.go:5）', number=2),
             entry('日志 "xxl-job executor run error"（不在本仓库：XXL-Job 执行器库）', number=3),
             entry("数据库（看板查不了）：orders 表", number=4)],
            service=MAIN, source=Source())
        text = cl.render_check(results, service=MAIN, commit="b9a01162e7b2e1585245791d66247582605891f0")
        lines = text.splitlines()
        self.assertEqual(lines[0], f"待验证清单检查：{MAIN}，提交 b9a01162")
        self.assertTrue(lines[1].startswith('1. 已确认 — 日志 "risk check failed" internal/biz/order.go:5'))
        self.assertTrue(lines[2].startswith("2. 要改 — "))
        self.assertTrue(lines[3].startswith("3. 未确认 — "))
        self.assertTrue(lines[4].startswith("4. 通过 — "))
        self.assertIn("合计：已确认 1，未确认 1，通过 1，要改 1", text)

    def test_a_problem_of_the_whole_list_has_no_number(self):
        results = cl.check([entry("指标 order_fail_total", number=n) for n in range(1, 7)],
                           service=MAIN, source=Source())
        text = cl.render_check(results, service=MAIN, commit="b9a01162")
        self.assertRegex(text, r"(?m)^清单：要改 — 最多 5 条")
        self.assertIn("合计：已确认 0，未确认 0，通过 6，要改 1", text)

    def test_the_check_explains_what_each_status_allows(self):
        text = cl.render_check(cl.check([entry("指标 order_fail_total")], service=MAIN, source=Source()),
                               service=MAIN, commit="b9a01162")
        self.assertIn("已确认：", text)
        self.assertIn("零命中", text)
        self.assertIn("未确认：", text)
        self.assertIn("要改：", text)

    def test_an_empty_list_is_said_to_be_empty(self):
        text = cl.render_check([], service=MAIN, commit="b9a01162")
        self.assertIn("清单为空", text)
        self.assertNotIn("合计", text)


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return done.stdout.strip()


class EvidenceCase(unittest.TestCase):
    """An evidence directory, and a repository whose first commit is the deployed one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="check-list-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        (self.repo / "internal/biz").mkdir(parents=True)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        (self.repo / "internal/biz/order.go").write_text(ORDER_GO)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "deployed")
        self.deployed = git(self.repo, "rev-parse", "HEAD")
        # Later work that was not deployed: one commit, and one uncommitted edit.
        (self.repo / "internal/biz/order.go").write_text(ORDER_GO.replace("risk check failed", "risk rejected"))
        (self.repo / "internal/biz/later.go").write_text('package biz\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "later")
        (self.repo / "internal/biz/order.go").write_text("package biz\n")

        self.evidence = self.tmp / "evidence"
        self.evidence.mkdir()
        self.write_deployed()
        (self.evidence / "code.md").write_text(CODE_MD.replace("order.go:42", "order.go:5"))

    def write_deployed(self, **changes):
        doc = {"ok": True, "service": MAIN, "checkout": str(self.repo),
               "deployed_commit": self.deployed[:8], "analyzed_commit": self.deployed}
        doc.update(changes)
        (self.evidence / "deployed.json").write_text(json.dumps({k: v for k, v in doc.items() if v is not None}))

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cl.main([*argv, "--evidence-dir", str(self.evidence)])
        return code, out.getvalue()


class GitSourceTest(EvidenceCase):
    def test_reads_the_deployed_commit_not_the_checkout(self):
        source = cl.GitSource(self.repo, self.deployed)
        self.assertEqual(source.files(), ["internal/biz/order.go"])
        self.assertEqual(source.read("internal/biz/order.go"), ORDER_GO)

    def test_an_unknown_commit_is_a_tool_error(self):
        with self.assertRaises(dv.ResolveError) as caught:
            cl.GitSource(self.repo, "0" * 40).files()
        self.assertEqual(caught.exception.code, 6)


class CommandLineTest(EvidenceCase):
    def test_check_reads_code_md_and_the_deployed_commit(self):
        code, out = self.run_main("check")
        self.assertEqual(code, 0)
        self.assertIn(f"待验证清单检查：{MAIN}，提交 {self.deployed[:8]}", out)
        self.assertIn('1. 已确认 — 日志 "risk check failed" internal/biz/order.go:5 Errorf', out)
        self.assertIn("2. 通过 — ", out)

    def test_check_still_exits_zero_when_items_need_fixing(self):
        (self.evidence / "code.md").write_text(CODE_MD)      # cites line 42
        code, out = self.run_main("check")
        self.assertEqual(code, 0)
        self.assertIn("1. 要改 — ", out)

    def test_check_without_code_md(self):
        (self.evidence / "code.md").unlink()
        code, out = self.run_main("check")
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["error"], "no_code_md")

    def test_check_without_the_list(self):
        (self.evidence / "code.md").write_text("# Code Investigation Report\n\n## 结论\n没有清单\n")
        code, out = self.run_main("check")
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["error"], "no_list_in_code_md")

    def test_no_deployed_json(self):
        (self.evidence / "deployed.json").unlink()
        for command in (("check",), ("logs", "--file", "internal/biz/order.go")):
            with self.subTest(command=command):
                code, out = self.run_main(*command)
                self.assertEqual(code, 4)
                self.assertEqual(json.loads(out)["error"], "no_deployed_json")

    def test_a_deployed_json_without_a_commit(self):
        self.write_deployed(analyzed_commit=None, deployed_commit=None)
        code, out = self.run_main("check")
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["error"], "deployed_json_has_no_commit")

    def test_the_short_commit_is_used_when_the_full_one_is_missing(self):
        self.write_deployed(analyzed_commit=None)
        code, out = self.run_main("check")
        self.assertEqual(code, 0)
        self.assertIn("1. 已确认", out)

    def test_logs_lists_the_statements_of_the_deployed_file(self):
        code, out = self.run_main("logs", "--file", "order.go", "--around", "5")
        self.assertEqual(code, 0)
        self.assertIn("file: internal/biz/order.go", out)
        self.assertIn('"risk check failed, order_no="', out)
        self.assertNotIn("risk rejected", out)

    def test_logs_for_a_file_the_commit_does_not_have(self):
        code, out = self.run_main("logs", "--file", "internal/biz/later.go")
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(out)["error"], "no_such_file_in_commit")

    def test_a_git_failure_is_reported(self):
        self.write_deployed(checkout=str(self.tmp / "not-a-repo"))
        code, out = self.run_main("check")
        self.assertEqual(code, 6)
        self.assertEqual(json.loads(out)["error"], "git_failed")


if __name__ == "__main__":
    unittest.main()
