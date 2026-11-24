#!/usr/bin/env python3
"""Create the fixed issue-analysis graph.

The decomposer is not used. One root card waits until intake, code,
runtime, verification, and synthesis have all finished, which is also when
a Feishu subscription on the root fires.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BOARD = "issue-analysis"
WORKSPACE = "dir:/home/roy/dev"
EVIDENCE_ROOT = Path("/home/roy/dev/.hermes-issue-analysis")
SECTIONS = ("Issue", "Service", "Environment", "Time Window", "Evidence")

ASSIGNEE = {
    "root": "issue-coordinator",
    "intake": "issue-intake",
    "code": "code-investigator",
    "runtime": "runtime-investigator",
    "verifier": "evidence-verifier",
    "synthesizer": "issue-synthesizer",
}
SKILLS = {
    "root": ["issue-coordinator"],
    "intake": ["issue-intake", "jaeger-trace"],
    "code": ["code-investigator", "codegraph"],
    "runtime": ["runtime-investigator", "jaeger-trace", "nex-cli"],
    "verifier": ["evidence-verifier"],
    "synthesizer": ["issue-synthesizer"],
}
REPORT = {
    "root": "analysis.md",
    "intake": "intake.md",
    "code": "code.md",
    "runtime": "runtime.md",
    "verifier": "verification.md",
    "synthesizer": "analysis.md",
}
TITLES = {
    "intake": "规范化 issue 并确认事发时的部署提交",
    "code": "在部署提交上分析代码路径",
    "runtime": "收集该部署版本的运行时证据",
    "verifier": "复核代码与运行时证据",
    "synthesizer": "汇总根因报告",
}
ORDER = ("intake", "code", "runtime", "verifier", "synthesizer")


class SubmitError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def parse_sections(body: str) -> dict[str, str]:
    found: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match and match.group(1) in SECTIONS:
            current = match.group(1)
            found.setdefault(current, [])
            continue
        if current:
            found[current].append(line)
    missing = [name for name in SECTIONS if not "".join(found.get(name, [])).strip()]
    if missing:
        raise SubmitError("missing or empty sections: " + ", ".join(missing))
    return {name: "\n".join(lines).strip() for name, lines in found.items()}


def field_value(text: str) -> str:
    for line in text.splitlines():
        line = line.strip().strip("`")
        if line:
            return line.split()[0]
    raise SubmitError("empty field")


def check_service(service: str, environment: str, *, lookup=None) -> None:
    """Reject a service that is not an exact deploy name in the environment.

    Every stage looks the service up in Nex by exact name. A Jaeger or
    source-catalog spelling would only fail later, inside intake, after the
    reporter has stopped watching.
    """
    import deployed_version as dv
    import find_service

    lookup = lookup or find_service.find
    try:
        result = lookup(service, environment)
    except dv.ResolveError as exc:
        if exc.payload.get("error") == "unsupported_environment":
            raise SubmitError(
                f"environment {environment!r} is not supported; "
                "the board can investigate qa, test, and prod", code=3) from exc
        raise SubmitError(f"service lookup failed: {exc.payload}", code=6) from exc
    except subprocess.TimeoutExpired as exc:
        raise SubmitError("service lookup timed out", code=6) from exc
    if not result.get("exact"):
        near = ", ".join(result.get("services") or []) or "none"
        raise SubmitError(
            f"service {service!r} is not a deploy service name in {environment}; "
            f"names containing it: {near}. Look the name up by keyword "
            "(find_service.py, or 'issue_desk.py service') and use a name it prints.",
            code=3)


def stage_body(stage: str, root_id: str, evidence: Path, original: str, deployed_commit: str | None) -> str:
    commit_line = deployed_commit or (
        "intake must resolve the commit deployed at the incident time; "
        "do not analyze the latest code"
    )
    rules = {
        "intake": "Resolve the deployed commit before completing. Code and runtime wait on you.",
        "code": "Analyze that deployed commit, not the branch tip. Write code.md before you finish.",
        "runtime": "Use the deployed commit from intake.md. Do not look up a newer deploy and treat it as the incident.",
        "verifier": "Reject the evidence when the analyzed commit differs from the deployed commit. Do not create cards.",
        "synthesizer": "You are the only writer of analysis.md. Do not create cards and do not complete the root.",
        "root": "The graph already exists. Do not create another one. Complete only after synthesis, or after one follow-up round.",
    }[stage]
    return (
        f"## Stage\n{stage}\n\n"
        f"## Root Task\n{root_id}\n\n"
        f"## Evidence Directory\n{evidence}\n\n"
        f"## Report\n{REPORT[stage]}\n\n"
        f"## Deployed Commit\n{commit_line}\n\n"
        f"## Rules\n{rules}\n\n"
        f"## Original Issue\n{original.rstrip()}\n"
    )


def default_title(service: str, environment: str, issue: str) -> str:
    symptom = issue.splitlines()[0].strip()
    if len(symptom) > 60:
        symptom = symptom[:59] + "…"
    return f"[{environment}][{service}] {symptom}"


def _run(cmd: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, env=env)


def kanban_json(args: list[str], *, board: str, env: dict, hermes: str) -> dict:
    completed = _run([hermes, "kanban", "--board", board, *args, "--json"], env)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).decode("utf-8", errors="replace").strip()
        raise SubmitError(detail or f"kanban {' '.join(args)} failed", code=1)
    try:
        return json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmitError(f"kanban {' '.join(args)} returned non-JSON: {exc}", code=1) from exc


def create_task(spec: dict, *, board: str, env: dict, hermes: str) -> dict:
    args = [
        "create", spec["title"],
        "--assignee", spec["assignee"],
        "--workspace", spec["workspace"],
        "--idempotency-key", spec["idempotency_key"],
        "--body", spec["body"],
    ]
    for skill in spec["skills"]:
        args.extend(["--skill", skill])
    for parent in spec.get("parents") or []:
        args.extend(["--parent", parent])
    if spec.get("initial_status"):
        args.extend(["--initial-status", spec["initial_status"]])
    payload = kanban_json(args, board=board, env=env, hermes=hermes)
    if "id" not in payload:
        raise SubmitError(f"create returned no id: {payload}", code=1)
    return payload


def show_task(task_id: str, *, board: str, env: dict, hermes: str) -> dict:
    return kanban_json(["show", task_id], board=board, env=env, hermes=hermes)


def link_parent(parent: str, child: str, *, board: str, env: dict, hermes: str, existing: set[str]) -> None:
    if parent in existing:
        return
    completed = _run(
        [hermes, "kanban", "--board", board, "link", parent, child],
        env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).decode("utf-8", errors="replace").strip()
        raise SubmitError(detail or f"link {parent} -> {child} failed", code=1)


def submit(body: str, *, key: str, title: str | None, deployed_commit: str | None,
           board: str, workspace: str, evidence_root: Path, env: dict | None = None,
           hermes: str = "hermes", chat_id: str | None = None,
           chat_type: str = "dm", delivery_mode: str = "notify+wake",
           dry_run: bool = False, verify_service: bool = False,
           service_lookup=None) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{4,120}", key):
        raise SubmitError("idempotency key must be 4-120 chars of letters, digits, _ . : -")
    if deployed_commit and not re.fullmatch(r"[0-9a-fA-F]{7,40}", deployed_commit):
        raise SubmitError("--deployed-commit must be a 7-40 character hex git id")
    sections = parse_sections(body)
    service = field_value(sections["Service"])
    environment = field_value(sections["Environment"])
    if verify_service:
        check_service(service, environment, lookup=service_lookup)
    root_title = title or default_title(service, environment, sections["Issue"])
    env = dict(os.environ if env is None else env)
    if dry_run:
        return {
            "dry_run": True,
            "title": root_title,
            "service": service,
            "environment": environment,
            "key": key,
            "stages": list(ORDER),
        }

    root_key = f"issue:{key}:root"
    # The evidence directory is named by the root id, so the root card has to
    # exist before the other bodies can point at it. It stays blocked until
    # the five parents are linked, and then waits in todo.
    placeholder = stage_body("root", "(pending)", evidence_root / "(pending)", body, deployed_commit)
    root = create_task({
        "title": root_title,
        "assignee": ASSIGNEE["root"],
        "workspace": workspace,
        "idempotency_key": root_key,
        "body": placeholder,
        "skills": SKILLS["root"],
        "initial_status": "blocked",
    }, board=board, env=env, hermes=hermes)
    root_id = root["id"]
    evidence = evidence_root / root_id
    evidence.mkdir(parents=True, exist_ok=True)
    ids = {"root": root_id}

    def make(stage: str, parents: list[str]) -> str:
        created = create_task({
            "title": TITLES[stage],
            "assignee": ASSIGNEE[stage],
            "workspace": workspace,
            "idempotency_key": f"issue:{key}:{stage}",
            "body": stage_body(stage, root_id, evidence, body, deployed_commit),
            "skills": SKILLS[stage],
            "parents": parents,
        }, board=board, env=env, hermes=hermes)
        ids[stage] = created["id"]
        return created["id"]

    intake = make("intake", [])
    code = make("code", [intake])
    runtime = make("runtime", [intake])
    verifier = make("verifier", [intake, code, runtime])
    synthesizer = make("synthesizer", [intake, code, runtime, verifier])

    shown = show_task(root_id, board=board, env=env, hermes=hermes)
    existing_parents = set(shown.get("parents") or [])
    if shown["task"]["status"] not in {"done", "archived"}:
        for parent in (intake, code, runtime, verifier, synthesizer):
            link_parent(parent, root_id, board=board, env=env, hermes=hermes, existing=existing_parents)
        # Refresh after linking. A blocked root with open parents unblocks
        # into todo and the dispatcher will not run it early.
        shown = show_task(root_id, board=board, env=env, hermes=hermes)
        if shown["task"]["status"] == "blocked":
            completed = _run(
                [hermes, "kanban", "--board", board, "unblock", root_id,
                 "--reason", "graph linked; root waits for the five stages"],
                env,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).decode().strip()
                raise SubmitError(detail or "unblock root failed", code=1)
        # create is idempotent and will not refresh the placeholder body
        # written before the root id existed. One comment carries the real
        # evidence directory and the child ids.
        already = any(
            str(item.get("body") or "").startswith("## Stage\nroot\n")
            for item in shown.get("comments") or []
            if isinstance(item, dict)
        )
        if not already:
            # The root card body was stored before its id existed, so its
            # evidence path says "(pending)". This comment is the correction.
            final_body = (
                "## Stage\nroot\n\n"
                f"## Root Task\n{root_id}\n\n"
                f"## Evidence Directory\n{evidence}\n\n"
                "## Report\nanalysis.md\n\n"
                "## Graph\n"
                + "\n".join(f"- {stage}: {ids[stage]}" for stage in ORDER)
                + "\n"
            )
            comment = _run(
                [hermes, "kanban", "--board", board, "comment", root_id, final_body],
                env,
            )
            if comment.returncode != 0:
                detail = (comment.stderr or comment.stdout).decode().strip()
                raise SubmitError(detail or "comment root failed", code=1)

    if chat_id and shown["task"]["status"] not in {"done", "archived"}:
        sub = _run([
            hermes, "kanban", "--board", board, "notify-subscribe", root_id,
            "--platform", "feishu", "--chat-id", chat_id,
            "--chat-type", chat_type, "--delivery-mode", delivery_mode,
        ], env)
        if sub.returncode != 0:
            detail = (sub.stderr or sub.stdout).decode().strip()
            raise SubmitError(detail or "notify-subscribe failed", code=1)

    final = show_task(root_id, board=board, env=env, hermes=hermes)
    return {
        "root": root_id,
        "root_status": final["task"]["status"],
        "parents": final.get("parents") or [],
        "evidence_dir": str(evidence),
        **{stage: ids[stage] for stage in ORDER},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a fixed issue-analysis graph.")
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--title")
    parser.add_argument("--deployed-commit")
    parser.add_argument("--board", default=BOARD)
    parser.add_argument("--workspace", default=WORKSPACE)
    parser.add_argument("--evidence-root", default=str(EVIDENCE_ROOT))
    parser.add_argument("--chat-id")
    parser.add_argument("--chat-type", default="dm", choices=["dm", "group", "channel", "thread"])
    parser.add_argument("--delivery-mode", default="notify+wake", choices=["notify", "notify+wake", "wake"])
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-service", action="store_true",
                        help="Reject a Service that is not an exact deploy name in the Environment.")
    args = parser.parse_args(argv)
    body = Path(args.body_file).read_text(encoding="utf-8")
    try:
        result = submit(
            body,
            key=args.idempotency_key,
            title=args.title,
            deployed_commit=args.deployed_commit,
            board=args.board,
            workspace=args.workspace,
            evidence_root=Path(args.evidence_root),
            hermes=args.hermes,
            chat_id=args.chat_id,
            chat_type=args.chat_type,
            delivery_mode=args.delivery_mode,
            dry_run=args.dry_run,
            verify_service=args.verify_service,
        )
    except SubmitError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
