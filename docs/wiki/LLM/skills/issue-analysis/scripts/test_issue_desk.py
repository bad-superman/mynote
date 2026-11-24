import sys
import tempfile
import unittest
from pathlib import Path

import issue_desk as desk
import submit_issue as si

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
    service_source="identifier",
)

FEISHU_GROUP = {
    "HERMES_SESSION_PLATFORM": "feishu",
    "HERMES_SESSION_CHAT_ID": "oc_group",
    "HERMES_SESSION_CHAT_TYPE": "group",
    "HERMES_SESSION_THREAD_ID": "",
    "HERMES_SESSION_USER_ID": "ou_reporter",
    "HERMES_SESSION_PROFILE": "issue-desk",
}


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
        self.assertIn("- service located by: identifier", sections["Evidence"])

    def test_trace_id_is_written_where_intake_looks_for_it(self):
        body = desk.build_body(**{**BASE, "trace_id": "abc123", "identifier": None, "evidence": None})
        self.assertIn("- trace_id: abc123", si.parse_sections(body)["Evidence"])

    def test_a_known_service_needs_no_trace_and_no_account(self):
        body = desk.build_body(**{**BASE, "identifier": None, "evidence": "  ",
                                  "service_source": "reporter"})
        evidence = si.parse_sections(body)["Evidence"]
        self.assertIn("- no trace id or account identifier", evidence)
        self.assertIn("- service located by: reporter", evidence)

    def test_a_vague_time_is_rejected(self):
        with self.assertRaises(desk.DeskError):
            desk.build_body(**{**BASE, "window_start": "今天上午"})


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


class CatalogSourceTest(unittest.TestCase):
    def test_a_catalog_pick_is_refused_until_the_reporter_agrees(self):
        args = desk.build_parser().parse_args([
            "submit", "--issue", "x", "--service", "ca.corporate-action.job", "--env", "qa",
            "--window-start", "2026-11-24 14:00", "--window-end", "2026-11-24 14:30",
            "--service-source", "catalog"])
        with self.assertRaises(desk.DeskError) as ctx:
            desk.cmd_submit(args, environ={})
        self.assertEqual(ctx.exception.code, 3)
        self.assertIn("--reporter-confirmed", str(ctx.exception))


class SubscriptionTest(unittest.TestCase):
    def test_group_subscription_carries_the_reporter_and_no_owner_profile(self):
        session = desk.session_from_env(FEISHU_GROUP)
        row = desk.subscription("t_root", session, "notify+wake", "issue-analysis")
        self.assertEqual(row, {
            "board": "issue-analysis",
            "task_id": "t_root",
            "platform": "feishu",
            "chat_id": "oc_group",
            "chat_type": "group",
            "thread_id": None,
            "user_id": "ou_reporter",
            "user_id_alt": None,
            "delivery_mode": "notify+wake",
        })
        self.assertNotIn("profile", session)
        self.assertIn("notifier_profile=None", desk.SUBSCRIBE_SNIPPET)

    def test_a_feishu_p2p_chat_is_recorded_as_dm(self):
        session = desk.session_from_env({**FEISHU_GROUP, "HERMES_SESSION_CHAT_TYPE": "p2p"})
        self.assertEqual(desk.subscription("t_root", session, "notify", "b")["chat_type"], "dm")

    def test_no_chat_in_the_environment_means_no_subscription(self):
        self.assertIsNone(desk.subscription("t_root", desk.session_from_env({}), "notify", "b"))
        local = desk.session_from_env({"HERMES_SESSION_PLATFORM": "cli",
                                       "HERMES_SESSION_CHAT_ID": "x"})
        self.assertIsNone(desk.subscription("t_root", local, "notify", "b"))

    def test_the_interpreter_comes_from_the_launcher_shebang(self):
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "hermes"
            launcher.write_text(f"#!{sys.executable}\nimport sys\n")
            self.assertEqual(desk.hermes_python(str(launcher)), sys.executable)
            self.assertTrue(desk.hermes_python(str(Path(tmp) / "missing")).endswith("python3"))


if __name__ == "__main__":
    unittest.main()
