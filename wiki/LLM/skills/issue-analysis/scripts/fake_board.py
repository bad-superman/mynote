"""An in-memory stand-in for `hermes kanban`, for the script tests.

It replaces the four functions through which submit_issue.py,
adjust_graph.py, and issue_desk.py reach the board. Card statuses follow
the dispatcher's rule: a card is ready when every parent is done or
archived.
"""

from __future__ import annotations

import types

import submit_issue as si

CLOSED = {"done", "archived"}


class FakeBoard:
    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self.by_key: dict[str, str] = {}
        self.commands: list[list[str]] = []

    # -- the four entry points -------------------------------------------
    def create_task(self, spec: dict, **_kw) -> dict:
        key = spec["idempotency_key"]
        if key in self.by_key:
            return {"id": self.by_key[key]}
        task_id = f"t_{len(self.tasks) + 1:08x}"
        self.tasks[task_id] = {
            "id": task_id,
            "title": spec["title"],
            "assignee": spec["assignee"],
            "body": spec["body"],
            "skills": list(spec["skills"]),
            "parents": list(spec.get("parents") or []),
            "status": spec.get("initial_status") or "todo",
            "comments": [],
            "events": [],
            "workspace_kind": "dir",
        }
        self.by_key[key] = task_id
        self._settle()
        return {"id": task_id}

    def show_task(self, task_id: str, **_kw) -> dict:
        if task_id not in self.tasks:
            # What `hermes kanban show` prints before it exits with 1.
            raise si.SubmitError(f"no such task: {task_id}", code=1)
        task = self.tasks[task_id]
        return {
            "task": {k: task[k] for k in ("id", "title", "assignee", "body", "status",
                                          "workspace_kind")},
            "parents": list(task["parents"]),
            "comments": [{"body": body} for body in task["comments"]],
            "events": list(task["events"]),
        }

    def link_parent(self, parent: str, child: str, *, existing: set[str], **_kw) -> None:
        if parent in existing or parent in self.tasks[child]["parents"]:
            return
        self.tasks[child]["parents"].append(parent)
        self._settle()

    def run(self, cmd: list[str], _env: dict):
        """Handle `hermes kanban --board <b> <verb> ...` for the verbs the scripts use."""
        self.commands.append(list(cmd))
        verb, args = cmd[4], cmd[5:]
        if verb == "comment":
            self.tasks[args[0]]["comments"].append(args[1])
        elif verb == "unblock":
            self.tasks[args[0]]["status"] = "todo"
            self.tasks[args[0]]["events"].append({"kind": "unblocked", "payload": {}})
            self._settle()
        elif verb == "archive":
            self.tasks[args[0]]["status"] = "archived"
            self._settle()
        elif verb != "notify-subscribe":
            return types.SimpleNamespace(returncode=2, stdout=b"", stderr=f"unknown verb {verb}".encode())
        return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    # -- helpers for the tests -------------------------------------------
    def _settle(self) -> None:
        for task in self.tasks.values():
            if task["status"] == "todo" and all(
                    self.tasks[p]["status"] in CLOSED for p in task["parents"]):
                task["status"] = "ready"

    def finish(self, task_id: str) -> None:
        self.tasks[task_id]["status"] = "done"
        self._settle()

    def start(self, task_id: str) -> None:
        self.tasks[task_id]["status"] = "running"

    def block(self, task_id: str, reason: str, kind: str | None = None) -> None:
        task = self.tasks[task_id]
        task["status"] = "blocked"
        task["events"].append({"kind": "blocked", "payload": {"reason": reason, "kind": kind}})

    def give_up(self, task_id: str, error: str) -> None:
        """The dispatcher stops retrying: the card is blocked, the event is gave_up."""
        task = self.tasks[task_id]
        task["status"] = "blocked"
        task["events"].append({"kind": "gave_up", "payload": {"error": error, "failures": 3}})

    def triage(self, task_id: str, reason: str, kind: str = "needs_input") -> None:
        """A card blocked again and again for one cause is routed to triage."""
        task = self.tasks[task_id]
        task["status"] = "triage"
        task["events"].append({"kind": "block_loop_detected",
                               "payload": {"reason": reason, "kind": kind, "recurrences": 3}})

    def status(self, task_id: str) -> str:
        return self.tasks[task_id]["status"]

    def comments(self, task_id: str) -> list[str]:
        return list(self.tasks[task_id]["comments"])

    def install(self, case) -> "FakeBoard":
        """Route submit_issue's board calls here for the duration of one test."""
        for name, fake in (("create_task", self.create_task), ("show_task", self.show_task),
                           ("link_parent", self.link_parent), ("_run", self.run)):
            original = getattr(si, name)
            setattr(si, name, fake)
            case.addCleanup(setattr, si, name, original)
        return self


def issue_body(*, service: str = "ams.account.job", environment: str = "qa") -> str:
    return (
        "## Issue\n查询交易账户信息接口超时\n\n"
        f"## Service\n{service}\n\n"
        f"## Environment\n{environment}\n\n"
        "## Time Window\n2026-11-25 10:00 至 2026-11-25 10:30 (Asia/Shanghai)\n\n"
        "## Evidence\n- trace_id: abc123\n"
    )
