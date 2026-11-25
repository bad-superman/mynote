import json
import subprocess
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import deployed_version as dv

SH = ZoneInfo("Asia/Shanghai")


def item(commit, when, status="done", current="False"):
    return {
        "commit": commit,
        "deploy_time": when,
        "status": status,
        "type": "deploy",
        "current": current,
    }


class SelectionTest(unittest.TestCase):
    def test_env_and_job_selection_use_the_verified_clusters(self):
        self.assertEqual(dv.normalize_env("production"), "prod")
        services = [
            {"service_name": "risk.risk.service", "cluster": "tx-youfi-qa-sg", "job_name": "job-qa"},
            {"service_name": "risk.risk.service", "cluster": "aws-youfi-prod-hk", "job_name": "job-prod"},
            {"service_name": "risk.risk.extra", "cluster": "tx-youfi-qa-sg", "job_name": "other"},
        ]
        self.assertEqual(dv.select_job(services, "risk.risk.service", "qa")["job_name"], "job-qa")
        with self.assertRaises(dv.ResolveError) as caught:
            dv.select_job(services, "risk.risk.service", "test")
        self.assertEqual(caught.exception.code, dv.EXIT_NO_JOB)

    def test_incident_commit_is_the_last_success_at_or_before_the_window(self):
        history = [
            item("new1111", "20261022104800", current="True"),
            item("mid2222", "20261022034000"),
            item("old3333", "20261021163600"),
            item("nope444", "20261021100000", status="cancel"),
        ]
        start = datetime(2026, 10, 22, 3, 31, 8, tzinfo=SH)
        end = datetime(2026, 10, 22, 3, 45, 0, tzinfo=SH)
        selected = dv.select_deploys(history, start, end)
        self.assertEqual(selected["incident"]["commit"], "old3333")
        self.assertEqual(selected["during_window"][0]["commit"], "mid2222")
        self.assertEqual(selected["after_window"][0]["commit"], "new1111")
        self.assertEqual(selected["current"]["commit"], "new1111")

    def test_history_that_starts_after_the_incident_is_an_error(self):
        history = [item("only555", "20261022100000")]
        start = datetime(2026, 10, 21, 3, 0, 0, tzinfo=SH)
        with self.assertRaises(dv.ResolveError) as caught:
            dv.select_deploys(history, start, None)
        self.assertEqual(caught.exception.payload["error"], "history_does_not_cover_window")

    def test_deploy_time_is_shanghai_local(self):
        when = dv.parse_deploy_time("20261116111128")
        self.assertEqual(when.strftime("%Y-%m-%d %H:%M:%S %z"), "2026-11-16 11:11:28 +0800")

    def test_checkout_path_and_branch_parsing(self):
        path = dv.repo_checkout_path("git@code.youfi.com:risk/riskservice.git", "/work")
        self.assertEqual(str(path), "/work/code.youfi.com/risk/riskservice")
        branches = dv.parse_branches("  origin/HEAD -> origin/qa\n  origin/qa\n  origin/release/test\n")
        self.assertEqual(branches, ["origin/qa", "origin/release/test"])


class ExpectPathTest(unittest.TestCase):
    """Intake locates a service in production code, then checks that the
    deploy name it picked really serves that code in the environment."""

    def resolve(self, present):
        def runner(cmd, timeout):
            if cmd[1:3] == ["deploy", "services"]:
                body = {"services": [{"service_name": "trade.order-service.job",
                                      "cluster": "tx-youfi-qa-sg", "job_name": "job-qa"}]}
            elif cmd[1:3] == ["deploy", "info"]:
                body = {"git_addr": "git@code.youfi.com:link1/OrderService.git"}
            elif cmd[1:3] == ["deploy", "history"]:
                body = {"history": [item("abcdef1", "20261021163600", current="True")]}
            else:
                body = None
            if body is not None:
                return subprocess.CompletedProcess(cmd, 0, json.dumps(body).encode(), b"")
            if "rev-parse" in cmd:
                return subprocess.CompletedProcess(cmd, 0, b"abcdef1234567890\n", b"")
            if "branch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, b"  origin/qa\n", b"")
            if "cat-file" in cmd:
                self.assertEqual(cmd[-1], "abcdef1234567890:internal/biz/option_expiration")
                return subprocess.CompletedProcess(cmd, 0 if present else 128, b"", b"")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        original = dv._ensure_checkout
        dv._ensure_checkout = lambda checkout, git_addr, runner: None
        self.addCleanup(setattr, dv, "_ensure_checkout", original)
        return dv.resolve(service="trade.order-service.job", env="qa",
                          window_start="2026-10-22 03:31:08", runner=runner,
                          expect_path="/internal/biz/option_expiration/")

    def test_reports_a_path_the_deployed_commit_contains(self):
        self.assertEqual(self.resolve(present=True)["expect_path"], {
            "path": "internal/biz/option_expiration", "in_deployed_commit": True})

    def test_reports_a_path_the_deployed_commit_lacks(self):
        self.assertFalse(self.resolve(present=False)["expect_path"]["in_deployed_commit"])


class ResolveTest(unittest.TestCase):
    def test_resolve_uses_nex_then_git_without_checkout(self):
        calls = []

        def runner(cmd, timeout):
            calls.append(cmd)
            if cmd[1:3] == ["deploy", "services"]:
                body = {"services": [{
                    "service_name": "risk.risk.service",
                    "cluster": "tx-youfi-qa-sg",
                    "job_name": "job-qa",
                }]}
            elif cmd[1:3] == ["deploy", "info"]:
                body = {"git_addr": "git@code.youfi.com:risk/riskservice.git"}
            elif cmd[1:3] == ["deploy", "history"]:
                body = {"history": [item("abcdef1", "20261021163600", current="True")]}
            else:
                body = None
            if body is not None:
                return subprocess.CompletedProcess(cmd, 0, json.dumps(body).encode(), b"")
            if cmd[:2] == ["git", "clone"]:
                raise AssertionError("clone was not expected")
            if "fetch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if "rev-parse" in cmd:
                return subprocess.CompletedProcess(cmd, 0, b"abcdef1234567890\n", b"")
            if "branch" in cmd:
                return subprocess.CompletedProcess(cmd, 0, b"  origin/qa\n", b"")
            raise AssertionError(cmd)

        # Pretend the checkout already exists by patching the check.
        original = dv._ensure_checkout
        dv._ensure_checkout = lambda checkout, git_addr, runner: None
        try:
            result = dv.resolve(
                service="risk.risk.service",
                env="qa",
                window_start="2026-10-22 03:31:08",
                fetch=True,
                runner=runner,
            )
        finally:
            dv._ensure_checkout = original
        self.assertTrue(result["ok"])
        self.assertEqual(result["deployed_commit"], "abcdef1")
        self.assertEqual(result["analyzed_commit"], "abcdef1234567890")
        self.assertEqual(result["branches"], ["origin/qa"])
        self.assertNotIn("checkout", " ".join(" ".join(cmd) for cmd in calls if "checkout" in cmd))
        self.assertFalse(any("checkout" in part for cmd in calls for part in cmd))


if __name__ == "__main__":
    unittest.main()
