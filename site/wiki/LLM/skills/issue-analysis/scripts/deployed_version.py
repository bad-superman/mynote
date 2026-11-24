#!/usr/bin/env python3
"""Resolve the commit that was deployed when an incident started.

Nex deploy history stores the commit and a local timestamp, but not the git
branch. This script selects the last successful deploy at or before the
incident, then asks git which remote branches contain that commit. It never
checks out or switches a branch.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NEX = "/home/roy/.nex/bin/nex"
PDL = "cop.youfi_owt.inno_pdl.youfi"
SHANGHAI = ZoneInfo("Asia/Shanghai")

# Verified against risk.risk.service and quote.market.service.
DEPLOY_CLUSTERS = {
    "qa": "tx-youfi-qa-sg",
    "test": "tx-youfi-test-sg",
    "prod": "aws-youfi-prod-hk",
}

ENV_ALIASES = {
    "qa": "qa",
    "test": "test",
    "prod": "prod",
    "production": "prod",
}

EXIT_USAGE = 2
EXIT_NO_JOB = 3
EXIT_HISTORY = 4
EXIT_COMMIT = 5
EXIT_TOOL = 6


class ResolveError(Exception):
    def __init__(self, code: int, error: str, **extra):
        super().__init__(error)
        self.code = code
        self.payload = {"ok": False, "error": error, **extra}


def normalize_env(env: str) -> str:
    key = (env or "").strip().lower()
    if key not in ENV_ALIASES:
        raise ResolveError(
            EXIT_NO_JOB,
            "unsupported_environment",
            environment=key,
            supported=sorted(ENV_ALIASES),
        )
    return ENV_ALIASES[key]


def parse_deploy_time(value: str) -> datetime:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{14}", text):
        raise ValueError(f"deploy_time {value!r} is not YYYYMMDDHHMMSS")
    return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=SHANGHAI)


def parse_window(value: str) -> datetime:
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=SHANGHAI)
        except ValueError:
            continue
    raise ResolveError(EXIT_USAGE, "bad_window_time", value=value)


def select_job(services: list[dict], service_name: str, env: str) -> dict:
    exact = [
        item for item in services
        if item.get("service_name") == service_name and item.get("job_name")
    ]
    cluster = DEPLOY_CLUSTERS[env]
    chosen = [item for item in exact if item.get("cluster") == cluster]
    if len(chosen) == 1:
        return chosen[0]
    candidates = [
        {"service_name": item.get("service_name"), "cluster": item.get("cluster"),
         "job_name": item.get("job_name")}
        for item in exact
    ]
    raise ResolveError(
        EXIT_NO_JOB,
        "deploy_job_not_unique",
        wanted_cluster=cluster,
        matches=len(chosen),
        candidates=candidates,
    )


def _is_done(item: dict) -> bool:
    return (
        str(item.get("status") or "").lower() == "done"
        and str(item.get("type") or "deploy").lower() == "deploy"
        and str(item.get("commit") or "").strip()
    )


def _current(item: dict) -> bool:
    return str(item.get("current")).lower() == "true"


def select_deploys(history: list[dict], window_start: datetime, window_end: datetime | None) -> dict:
    parsed = []
    for item in history:
        if not _is_done(item):
            continue
        try:
            when = parse_deploy_time(item.get("deploy_time"))
        except ValueError:
            continue
        parsed.append((when, item))
    parsed.sort(key=lambda pair: pair[0])
    if not parsed:
        raise ResolveError(EXIT_HISTORY, "no_successful_deploys")
    oldest = parsed[0][0]
    if oldest > window_start:
        raise ResolveError(
            EXIT_HISTORY,
            "history_does_not_cover_window",
            oldest_deploy_time=_fmt(oldest),
            window_start=_fmt(window_start),
        )
    before = [(when, item) for when, item in parsed if when <= window_start]
    incident_when, incident = before[-1]
    end = window_end or window_start
    during = [
        _public(when, item)
        for when, item in parsed
        if window_start < when <= end
    ]
    after = [
        _public(when, item)
        for when, item in parsed
        if when > end
    ]
    current = next((item for _, item in reversed(parsed) if _current(item)), None)
    return {
        "incident": _public(incident_when, incident),
        "during_window": during,
        "after_window": after,
        "current": _public(
            next(when for when, item in parsed if item is current),
            current,
        ) if current else None,
    }


def _fmt(when: datetime) -> str:
    return when.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S Asia/Shanghai")


def _public(when: datetime, item: dict) -> dict:
    return {
        "commit": str(item.get("commit")).strip(),
        "deploy_time": _fmt(when),
        "current": _current(item),
    }


def repo_checkout_path(git_addr: str, root: str | Path = "/home/roy/dev") -> Path:
    addr = git_addr.strip()
    if addr.startswith("git@"):
        host, _, path = addr[4:].partition(":")
    elif "://" in addr:
        rest = addr.split("://", 1)[1]
        host, _, path = rest.partition("/")
        host = host.split("@")[-1]
    else:
        raise ResolveError(EXIT_TOOL, "unrecognized_git_addr", git_addr=addr)
    if path.endswith(".git"):
        path = path[:-4]
    if not host or not path:
        raise ResolveError(EXIT_TOOL, "unrecognized_git_addr", git_addr=addr)
    return Path(root) / host / path


def parse_branches(text: str) -> list[str]:
    branches = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "->" in line:
            continue
        branches.append(line)
    return branches


def _load_json(raw: bytes) -> dict:
    clean = re.sub(rb"[\x00-\x1f]", b"", raw)
    doc = json.loads(clean.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ResolveError(EXIT_TOOL, "nex_returned_non_object")
    return doc


def resolve(
    *,
    service: str,
    env: str,
    window_start: str,
    window_end: str | None = None,
    commit_override: str | None = None,
    checkout_root: str = "/home/roy/dev",
    evidence_dir: str | None = None,
    fetch: bool = True,
    runner=None,
) -> dict:
    runner = runner or _default_runner
    environment = normalize_env(env)
    start = parse_window(window_start)
    end = parse_window(window_end) if window_end else None
    if end is not None and end < start:
        raise ResolveError(EXIT_USAGE, "window_end_before_start")

    services = _load_json(_capture(runner, [
        NEX, "deploy", "services",
        "--pdl", PDL, "--class", "k8s",
        "--service-name", service, "-o", "json",
    ], 60))
    job = select_job(services.get("services") or [], service, environment)
    info = _load_json(_capture(runner, [
        NEX, "deploy", "info", "-j", job["job_name"], "--class", "k8s", "-o", "json",
    ], 60))
    git_addr = str(info.get("git_addr") or "").strip()
    if not git_addr:
        raise ResolveError(EXIT_TOOL, "deploy_info_has_no_git_addr", job_name=job["job_name"])
    history = _load_json(_capture(runner, [
        NEX, "deploy", "history", "-j", job["job_name"], "--class", "k8s",
        "--limit", "100", "-o", "json",
    ], 60))
    selected = select_deploys(history.get("history") or [], start, end)
    checkout = repo_checkout_path(git_addr, checkout_root)
    _ensure_checkout(checkout, git_addr, runner)
    if fetch:
        # rev-parse below decides whether the commit is actually present.
        runner(["git", "-C", str(checkout), "fetch", "origin"], timeout=180)
    analyzed = commit_override or selected["incident"]["commit"]
    full, branches = _resolve_commit(checkout, analyzed, runner)
    result = {
        "ok": True,
        "service": service,
        "environment": environment,
        "deploy_cluster": DEPLOY_CLUSTERS[environment],
        "job_name": job["job_name"],
        "git_addr": git_addr,
        "checkout": str(checkout),
        "deployed_commit": selected["incident"]["commit"],
        "deployed_at": selected["incident"]["deploy_time"],
        "analyzed_commit": full,
        "commit_source": "override" if commit_override else "deploy_history",
        "branches": branches,
        "deploys_during_window": selected["during_window"],
        "deploys_after_window": selected["after_window"][:5],
        "current_deploy": selected["current"],
        "timezone": "Asia/Shanghai",
    }
    if commit_override and not full.startswith(commit_override):
        result["override_matches_deployed"] = selected["incident"]["commit"].startswith(commit_override)
    if evidence_dir:
        path = Path(evidence_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / "deployed.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result["report_path"] = str(path / "deployed.json")
    return result


def _capture(runner, cmd: list[str], timeout: int) -> bytes:
    completed = runner(cmd, timeout=timeout)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or b"").decode("utf-8", errors="replace")
        raise ResolveError(EXIT_TOOL, "command_failed", command=cmd[0:4], detail=detail[-500:])
    return completed.stdout


def _ensure_checkout(checkout: Path, git_addr: str, runner) -> None:
    if (checkout / ".git").exists():
        return
    if checkout.exists():
        raise ResolveError(EXIT_TOOL, "checkout_path_exists_but_is_not_a_repo", checkout=str(checkout))
    checkout.parent.mkdir(parents=True, exist_ok=True)
    completed = runner(
        ["git", "clone", "--quiet", git_addr, str(checkout)],
        timeout=300,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or b"").decode("utf-8", errors="replace")[-500:]
        raise ResolveError(EXIT_TOOL, "git_clone_failed", checkout=str(checkout), detail=detail)


def _resolve_commit(checkout: Path, commit: str, runner) -> tuple[str, list[str]]:
    rev = runner(
        ["git", "-C", str(checkout), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        timeout=30,
    )
    if rev.returncode != 0:
        raise ResolveError(
            EXIT_COMMIT,
            "commit_not_in_repo",
            commit=commit,
            checkout=str(checkout),
        )
    full = rev.stdout.decode().strip()
    listed = runner(
        ["git", "-C", str(checkout), "branch", "-r", "--contains", full],
        timeout=30,
    )
    branches = parse_branches(listed.stdout.decode("utf-8", errors="replace")) if listed.returncode == 0 else []
    return full, branches


def _default_runner(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve the deployed commit for an incident.")
    parser.add_argument("--service", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--window-start", required=True, help="Asia/Shanghai, YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--window-end")
    parser.add_argument("--commit", help="Use this commit instead of the deploy selected from history.")
    parser.add_argument("--checkout-root", default="/home/roy/dev")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args(argv)
    if args.commit and not re.fullmatch(r"[0-9a-fA-F]{7,40}", args.commit):
        print(json.dumps({"ok": False, "error": "bad_commit_override"}))
        return EXIT_USAGE
    try:
        result = resolve(
            service=args.service.strip(),
            env=args.env,
            window_start=args.window_start,
            window_end=args.window_end,
            commit_override=args.commit,
            checkout_root=args.checkout_root,
            evidence_dir=args.evidence_dir,
            fetch=not args.no_fetch,
        )
    except ResolveError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False))
        return exc.code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
