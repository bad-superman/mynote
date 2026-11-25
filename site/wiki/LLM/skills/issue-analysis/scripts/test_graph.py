import json
import shutil
import tempfile
import unittest
from pathlib import Path

import adjust_graph as ag
import submit_issue as si
from fake_board import FakeBoard, issue_body


def exact(names):
    """A service lookup that knows these deploy names and nothing else."""
    def lookup(service, environment):
        return {"exact": service in names, "services": sorted(names)}
    return lookup


class GraphCase(unittest.TestCase):
    def setUp(self):
        self.board = FakeBoard().install(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="issue-graph-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def submit(self, **body_kw):
        return si.submit(
            issue_body(**body_kw), key="case-1", title=None, deployed_commit=None,
            board="issue-analysis", workspace=si.WORKSPACE, evidence_root=self.tmp,
            env={}, verify_service=True,
            service_lookup=exact({"ams.account.job", "trade.order-service.job"}),
        )

    def adjust(self, root, **kw):
        kw.setdefault("route", None)
        kw.setdefault("add_runtime", [])
        return ag.adjust(root, env={}, service_lookup=exact({
            "ams.account.job", "trade.order-service.job", "risk.risk.service",
            "trade.asset-service.job"}), **kw)


class SubmitOrderTest(GraphCase):
    def test_runtime_waits_for_the_code_stage(self):
        ids = self.submit()
        runtime = self.board.tasks[ids["runtime"]]
        self.assertEqual(runtime["parents"], [ids["intake"], ids["code"]])

        self.board.finish(ids["intake"])
        self.assertEqual(self.board.status(ids["code"]), "ready")
        self.assertEqual(self.board.status(ids["runtime"]), "todo")

        self.board.finish(ids["code"])
        self.assertEqual(self.board.status(ids["runtime"]), "ready")

    def test_code_card_is_told_to_hand_runtime_a_list(self):
        ids = self.submit()
        self.assertIn("待验证", self.board.tasks[ids["code"]]["body"])
        self.assertIn("待验证", self.board.tasks[ids["runtime"]]["body"])


class UnresolvedServiceTest(GraphCase):
    def test_an_issue_without_a_service_is_accepted(self):
        ids = self.submit(service="unresolved")
        root = self.board.tasks[ids["root"]]
        self.assertEqual(root["title"], "[qa][待定位] 查询交易账户信息接口超时")
        self.assertEqual(root["status"], "todo")

    def test_a_named_service_must_still_be_a_deploy_name(self):
        with self.assertRaises(si.SubmitError) as caught:
            self.submit(service="OrderService.grpc")
        self.assertEqual(caught.exception.code, 3)

    def test_later_stages_are_told_where_the_service_will_be(self):
        ids = self.submit(service="unresolved")
        self.assertIn("unresolved", self.board.tasks[ids["intake"]]["body"])
        self.assertIn("intake.md", self.board.tasks[ids["code"]]["body"].split("## Original Issue")[0])


class LocateServiceTest(GraphCase):
    def test_intake_records_the_service_it_located(self):
        ids = self.submit(service="unresolved")
        result = self.adjust(ids["root"], service="trade.order-service.job", located_by="description")

        self.assertEqual(result["service"], "trade.order-service.job")
        state = json.loads((self.tmp / ids["root"] / "route.json").read_text())
        self.assertEqual(state["service"], "trade.order-service.job")
        self.assertEqual(state["located_by"], "description")
        for stage in ("code", "runtime", "verifier", "synthesizer", "root"):
            notes = "\n".join(self.board.comments(ids[stage]))
            self.assertIn("## Service\ntrade.order-service.job", notes, stage)

    def test_a_name_that_is_not_deployed_is_refused(self):
        ids = self.submit(service="unresolved")
        with self.assertRaises(ag.AdjustError) as caught:
            self.adjust(ids["root"], service="trade.order.service", located_by="description")
        self.assertEqual(caught.exception.code, 3)
        self.assertFalse((self.tmp / ids["root"] / "route.json").exists())

    def test_an_issue_that_names_its_service_keeps_it(self):
        ids = self.submit()
        with self.assertRaises(ag.AdjustError):
            self.adjust(ids["root"], service="trade.order-service.job", located_by="trace")

    def test_repeating_the_call_changes_nothing(self):
        ids = self.submit(service="unresolved")
        self.adjust(ids["root"], service="trade.order-service.job", located_by="trace")
        before = self.board.comments(ids["code"])
        self.adjust(ids["root"], service="trade.order-service.job", located_by="trace")
        self.assertEqual(self.board.comments(ids["code"]), before)

    def test_the_service_cannot_change_once_code_has_started(self):
        ids = self.submit(service="unresolved")
        self.adjust(ids["root"], service="trade.order-service.job", located_by="trace")
        self.board.finish(ids["intake"])
        self.board.start(ids["code"])
        with self.assertRaises(ag.AdjustError):
            self.adjust(ids["root"], service="risk.risk.service", located_by="trace")


class NextHopTest(GraphCase):
    def test_code_stage_adds_a_runtime_card_for_the_next_hop(self):
        ids = self.submit()
        self.board.finish(ids["intake"])
        self.board.start(ids["code"])

        result = self.adjust(ids["root"], add_runtime=["trade.asset-service.job"],
                             reason="ListAccounts 超时，确认下游在窗口内是否收到请求")
        card = result["extra_runtime"]["trade.asset-service.job"]
        task = self.board.tasks[card]
        self.assertEqual(task["parents"], [ids["intake"], ids["code"]])
        self.assertEqual(task["status"], "todo")
        self.assertIn("ListAccounts 超时", task["body"])
        self.assertIn(card, self.board.tasks[ids["verifier"]]["parents"])

        self.board.finish(ids["code"])
        self.assertEqual(self.board.status(card), "ready")

    def test_the_located_service_is_not_added_as_an_extra(self):
        ids = self.submit(service="unresolved")
        self.adjust(ids["root"], service="trade.order-service.job", located_by="trace")
        result = self.adjust(ids["root"], add_runtime=["trade.order-service.job"])
        self.assertEqual(result["extra_runtime"], {})

    def test_at_most_two_extra_services(self):
        ids = self.submit()
        self.adjust(ids["root"], add_runtime=["trade.order-service.job", "risk.risk.service"])
        with self.assertRaises(ag.AdjustError):
            self.adjust(ids["root"], add_runtime=["trade.asset-service.job"])


class FactRouteTest(GraphCase):
    def test_runtime_runs_after_intake_when_the_code_card_is_archived(self):
        ids = self.submit()
        self.adjust(ids["root"], route="fact")
        self.assertEqual(self.board.status(ids["code"]), "archived")

        self.board.finish(ids["intake"])
        self.assertEqual(self.board.status(ids["runtime"]), "ready")


if __name__ == "__main__":
    unittest.main()
