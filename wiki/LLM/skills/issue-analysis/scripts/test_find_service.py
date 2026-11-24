import json
import subprocess
import unittest

import deployed_version as dv
import find_service as fs

ROWS = [
    {"service_name": "trade.order-service.job", "cluster": "tx-youfi-qa-sg", "job_name": "j-qa"},
    {"service_name": "trade.order-service.job", "cluster": "aws-youfi-prod-hk", "job_name": "j-prod"},
    {"service_name": "trade.reorder.job", "cluster": "tx-youfi-qa-sg", "job_name": "j2"},
    {"service_name": "trade.order-preview.job", "cluster": "tx-youfi-test-sg", "job_name": "j3"},
    {"service_name": "trade.order-draft.job", "cluster": "tx-youfi-qa-sg", "job_name": ""},
]


def runner_for(rows, returncode=0, stderr=b""):
    calls = []

    def runner(cmd, timeout):
        calls.append(cmd)
        out = json.dumps({"services": rows, "total": len(rows)}).encode()
        return subprocess.CompletedProcess(cmd, returncode, out if returncode == 0 else b"", stderr)

    runner.calls = calls
    return runner


class FindTest(unittest.TestCase):
    def test_lists_only_names_deployed_in_the_requested_environment(self):
        runner = runner_for(ROWS)
        result = fs.find("order", "qa", runner=runner)
        self.assertEqual(result["services"], ["trade.order-service.job", "trade.reorder.job"])
        self.assertEqual(result["deploy_cluster"], "tx-youfi-qa-sg")
        self.assertFalse(result["exact"])
        self.assertIn("--service-name", runner.calls[0])
        self.assertEqual(runner.calls[0][runner.calls[0].index("--service-name") + 1], "order")

    def test_exact_is_true_only_for_a_full_name_in_that_environment(self):
        self.assertTrue(fs.is_deployable("trade.order-service.job", "qa", runner=runner_for(ROWS)))
        self.assertFalse(fs.is_deployable("trade.order-preview.job", "qa", runner=runner_for(ROWS)))
        # The source-catalog spelling is not the deploy name.
        self.assertFalse(fs.is_deployable("trade.order.service", "qa", runner=runner_for(ROWS)))

    def test_production_alias_maps_to_the_prod_cluster(self):
        result = fs.find("order", "production", runner=runner_for(ROWS))
        self.assertEqual(result["environment"], "prod")
        self.assertEqual(result["services"], ["trade.order-service.job"])

    def test_unsupported_environment_is_rejected_before_calling_nex(self):
        runner = runner_for(ROWS)
        with self.assertRaises(dv.ResolveError) as ctx:
            fs.find("order", "staging", runner=runner)
        self.assertEqual(ctx.exception.code, dv.EXIT_NO_JOB)
        self.assertEqual(runner.calls, [])

    def test_nex_failure_is_a_tool_error_not_an_empty_result(self):
        runner = runner_for(ROWS, returncode=1, stderr=b'{"error":{"code":"REMOTE_ERROR"}}')
        with self.assertRaises(dv.ResolveError) as ctx:
            fs.find("order", "qa", runner=runner)
        self.assertEqual(ctx.exception.code, fs.EXIT_TOOL)
        self.assertIn("REMOTE_ERROR", ctx.exception.payload["detail"])

    def test_one_character_keyword_is_rejected(self):
        with self.assertRaises(dv.ResolveError) as ctx:
            fs.find("o", "qa", runner=runner_for(ROWS))
        self.assertEqual(ctx.exception.code, fs.EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
