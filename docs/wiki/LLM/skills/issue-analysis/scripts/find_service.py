#!/usr/bin/env python3
"""List the deployable service names that contain a keyword in one environment.

The board keys every stage on the Nex deploy service name. Jaeger names
(`OrderService.grpc`) and source-catalog names (`trade.order.service`) can
differ from it (`trade.order-service.job`), so a candidate from either
source must be converged to a name printed here before a card is created.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import deployed_version as dv

EXIT_USAGE = 2
EXIT_NOT_FOUND = 4
EXIT_TOOL = 6


def names_in_cluster(services: list[dict], cluster: str) -> list[str]:
    names = {
        str(item.get("service_name"))
        for item in services
        if isinstance(item, dict)
        and item.get("service_name")
        and item.get("job_name")
        and item.get("cluster") == cluster
    }
    return sorted(names)


def find(keyword: str, env: str, *, runner=None) -> dict:
    """Return the service names in env's deploy cluster that contain keyword."""
    runner = runner or _default_runner
    environment = dv.normalize_env(env)
    word = keyword.strip()
    if len(word) < 2 or any(ch.isspace() for ch in word):
        raise dv.ResolveError(EXIT_USAGE, "keyword_must_be_one_token_of_2_or_more_chars")
    command = [
        dv.NEX, "deploy", "services",
        "--pdl", dv.PDL, "--class", "k8s",
        "--service-name", word, "--page-size", "50", "-o", "json",
    ]
    # Nex now and then answers "request timeout" to a query it serves a
    # moment later. One more try costs less than a card blocked on tooling.
    for _ in range(2):
        completed = runner(command, timeout=60)
        if completed.returncode == 0 and completed.stdout.strip():
            break
    else:
        detail = (completed.stderr or b"").decode("utf-8", errors="replace").strip()[:300]
        raise dv.ResolveError(EXIT_TOOL, "nex_services_failed", detail=detail)
    doc = dv._load_json(completed.stdout)
    cluster = dv.DEPLOY_CLUSTERS[environment]
    names = names_in_cluster(doc.get("services") or [], cluster)
    return {
        "ok": bool(names),
        "environment": environment,
        "deploy_cluster": cluster,
        "keyword": word,
        "exact": word in names,
        "services": names,
    }


def is_deployable(service: str, env: str, *, runner=None) -> bool:
    """True when service is an exact deploy service name in env."""
    return find(service, env, runner=runner)["exact"]


def _default_runner(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List deployable service names containing a keyword.")
    parser.add_argument("--env", required=True)
    parser.add_argument("--keyword", required=True,
                        help="Part of a service name, e.g. order, account, quote.market")
    args = parser.parse_args(argv)
    try:
        result = find(args.keyword, args.env)
    except dv.ResolveError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return exc.code
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": "nex_services_timeout"}, indent=2))
        return EXIT_TOOL
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["services"] else EXIT_NOT_FOUND


if __name__ == "__main__":
    sys.exit(main())
