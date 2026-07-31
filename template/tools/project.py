from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "project" / "state.yaml"
TASKS_DIR = ROOT / "project" / "tasks"


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: str
    priority: int
    milestone: str
    approval: str
    path: Path


def load_state() -> dict[str, Any]:
    return parse_simple_yaml(STATE_PATH.read_text())


def parse_scalar(value: str) -> Any:
    if value in {"true", "false"}:
        return value == "true"
    if value == "[]":
        return []
    if value.isdigit():
        return int(value)
    return value.strip('"')


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        index += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, _, value = raw.strip().partition(":")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        value = value.strip()
        if value:
            parent[key] = parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def parse_task(path: Path) -> Task:
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError(f"{path} is missing YAML frontmatter")
    data = parse_simple_yaml(match.group(1))
    return Task(
        id=str(data["id"]),
        title=str(data["title"]),
        status=str(data["status"]),
        priority=int(data["priority"]),
        milestone=str(data["milestone"]),
        approval=str(data["approval"]),
        path=path,
    )


def load_tasks() -> list[Task]:
    return sorted(
        (parse_task(path) for path in TASKS_DIR.glob("*.md")),
        key=lambda task: (task.priority, task.id),
    )


def find_task(tasks: list[Task], task_id: str) -> Task | None:
    return next((task for task in tasks if task.id == task_id), None)


def dashboard_block(state: dict[str, Any], active: Task | None) -> str:
    project = state["project"]
    lifecycle = state["lifecycle"]
    work = state["work"]
    active_link = (
        f"[{active.id}]({active.path.relative_to(ROOT).as_posix()})"
        if active
        else str(work.get("active_task", "none"))
    )
    return "\n".join(
        [
            "## Project Status",
            "",
            "| Item | Current State |",
            "|---|---|",
            f"| Type | {project['type']} |",
            f"| Runtime level | {project['runtime_level']} |",
            f"| Phase | {lifecycle['phase']} |",
            f"| Milestone | {lifecycle['milestone']} |",
            f"| Active task | {work['active_task']} |",
            f"| Next gate | {lifecycle['next_gate']} |",
            "",
            f"> **Next step:** Complete the active task: {active_link}.",
            "",
            "Details: [Project Dashboard](project/index.md).",
        ]
    )


def project_index_block(state: dict[str, Any], active: Task | None) -> str:
    project = state["project"]
    lifecycle = state["lifecycle"]
    work = state["work"]
    active_link = (
        f"[{active.id}]({active.path.relative_to(ROOT / 'project').as_posix()})"
        if active
        else str(work.get("active_task", "none"))
    )
    return "\n".join(
        [
            "| Item | Current State |",
            "|---|---|",
            f"| Project | {project['name']} |",
            f"| Type | {project['type']} |",
            f"| Runtime level | {project['runtime_level']} |",
            f"| Phase | {lifecycle['phase']} |",
            f"| Milestone | {lifecycle['milestone']} |",
            f"| Active task | {work['active_task']} |",
            f"| Next gate | {lifecycle['next_gate']} |",
            "",
            f"Next step: {active_link}.",
        ]
    )


def kanban_block(tasks: list[Task]) -> str:
    sections = [
        ("In Progress", "in-progress"),
        ("Ready", "ready"),
        ("Backlog", "backlog"),
        ("Review", "review"),
        ("Blocked", "blocked"),
        ("Done", "done"),
    ]
    lines: list[str] = []
    for title, status in sections:
        lines.extend([f"## {title}", ""])
        matching = [task for task in tasks if task.status == status]
        if matching:
            for task in matching:
                rel = task.path.relative_to(ROOT / "project").as_posix()
                lines.append(f"- [{task.id}]({rel}) - {task.title}")
        else:
            lines.append("_None_")
        lines.append("")
    return "\n".join(lines).rstrip()


def replace_block(path: Path, start: str, end: str, content: str) -> None:
    text = path.read_text()
    pattern = re.compile(
        rf"({re.escape(start)}\n)(.*?)(\n{re.escape(end)})",
        re.DOTALL,
    )
    updated, count = pattern.subn(rf"\1{content}\3", text)
    if count != 1:
        raise ValueError(f"{path} does not contain exactly one {start} block")
    path.write_text(updated)


def sync() -> None:
    state = load_state()
    tasks = load_tasks()
    active = find_task(tasks, state["work"]["active_task"])
    replace_block(
        ROOT / "README.md",
        "<!-- project-dashboard:start -->",
        "<!-- project-dashboard:end -->",
        dashboard_block(state, active),
    )
    replace_block(
        ROOT / "project" / "index.md",
        "<!-- project-index:start -->",
        "<!-- project-index:end -->",
        project_index_block(state, active),
    )
    replace_block(
        ROOT / "project" / "board.md",
        "<!-- kanban:start -->",
        "<!-- kanban:end -->",
        kanban_block(tasks),
    )


def validate() -> None:
    state = load_state()
    tasks = load_tasks()
    errors: list[str] = []

    if state.get("schema_version") != 1:
        errors.append("project/state.yaml schema_version must be 1")
    if state["project"]["type"] not in {"script", "library", "backend", "frontend", "fullstack"}:
        errors.append("project.type is invalid")
    if state["project"]["runtime_level"] not in {"local", "shared", "production"}:
        errors.append("project.runtime_level is invalid")

    active_task_id = state["work"]["active_task"]
    active = find_task(tasks, active_task_id)
    if active is None:
        errors.append(f"active task {active_task_id} does not exist")

    active_main = [task for task in tasks if task.status == "in-progress"]
    if len(active_main) > 1:
        errors.append("more than one task is in-progress")
    if active and active.status not in {"ready", "in-progress", "review", "blocked"}:
        errors.append("active task must be ready, in-progress, review, or blocked")

    allowed_statuses = {"backlog", "ready", "in-progress", "review", "blocked", "done", "cancelled"}
    for task in tasks:
        if task.status not in allowed_statuses:
            errors.append(f"{task.id} has invalid status {task.status}")
        if task.approval not in {"A0", "A1", "A2"}:
            errors.append(f"{task.id} has invalid approval {task.approval}")

    if state["lifecycle"]["next_gate"] == "ready-for-development":
        required_docs = [
            ROOT / "project" / "brief.md",
            ROOT / "project" / "requirements.md",
            ROOT / "docs" / "architecture.md",
            ROOT / "docs" / "decisions" / "index.md",
        ]
        for path in required_docs:
            if not path.exists():
                errors.append(f"missing ready-for-development input: {path}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        recommended = next((task for task in tasks if task.status == "ready"), None)
        if recommended:
            print(f"Recommended next task: {recommended.id} - {recommended.title}")
        else:
            print("Recommended next task: refine T-001 until the ready gate inputs are complete.")
        raise SystemExit(1)

    print("Project state is valid.")


def status() -> None:
    state = load_state()
    active = find_task(load_tasks(), state["work"]["active_task"])
    print(dashboard_block(state, active))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "sync", "validate"])
    args = parser.parse_args()

    if args.command == "status":
        status()
    elif args.command == "sync":
        sync()
    elif args.command == "validate":
        validate()


if __name__ == "__main__":
    main()
