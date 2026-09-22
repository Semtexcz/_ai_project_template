"""Persistence and parsing for canonical governance records.

Owns the intentionally simple YAML codec, task/state loading, generated-block
text mechanics, and single-file writes. It never makes lifecycle decisions and
never renders dashboards: those live above this layer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from project_tool.model import (
    STATE_PATH,
    TASKS_DIR,
    ProjectError,
    Task,
    nonempty,
    relative,
    task_sort_key,
)

STATE_START = "<!-- project-status:start -->"
STATE_END = "<!-- project-status:end -->"
INDEX_START = "<!-- project-index:start -->"
INDEX_END = "<!-- project-index:end -->"
KANBAN_START = "<!-- kanban:start -->"
KANBAN_END = "<!-- kanban:end -->"


def parse_scalar(value: str) -> Any:
    """Parse a single scalar value from the supported YAML subset."""
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    if value.isdigit():
        return int(value)
    return value.strip('"').strip("'")


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the mapping/list subset used by canonical governance files."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    current_list_key: dict[int, str] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            key = current_list_key.get(indent)
            if key is None:
                raise ProjectError(f"Invalid YAML list item: {raw}")
            parent.setdefault(key, []).append(parse_scalar(stripped[2:]))
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            raise ProjectError(f"Invalid YAML line: {raw}")
        value = value.strip()
        if value:
            parent[key] = parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            current_list_key[indent + 2] = key
            stack.append((indent, child))
    return root


def dump_simple_yaml(data: dict[str, Any]) -> str:
    """Serialize a mapping to the supported YAML subset."""

    def scalar(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, list):
            items = cast("list[Any]", value)
            return "[" + ", ".join(str(item) for item in items) + "]"
        return str(value)

    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            nested = cast("dict[str, Any]", value)
            lines.append(f"{key}:")
            for child_key, child_value in nested.items():
                lines.append(f"  {child_key}: {scalar(child_value)}".rstrip())
            lines.append("")
        else:
            lines.append(f"{key}: {scalar(value)}".rstrip())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Split a Markdown record into its YAML frontmatter mapping and body."""
    return split_frontmatter_text(path.read_text(encoding="utf-8"), path)


def split_frontmatter_text(text: str, path: Path) -> tuple[dict[str, Any], str]:
    """Split record text into its YAML frontmatter mapping and body."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ProjectError(f"{relative(path)} is missing YAML frontmatter. Add task metadata.")
    return parse_simple_yaml(match.group(1)), match.group(2)


def normalize_task_data(data: dict[str, Any], path: Path, body: str) -> Task:
    """Build a :class:`Task` from parsed frontmatter and body text."""
    approval_level = str(data.get("approval_level", data.get("approval", "")))
    approval_status = str(
        data.get(
            "approval_status",
            "not-required" if approval_level == "A0" else "pending",
        )
    )
    depends = data.get("depends_on", [])
    if depends is None:
        depends = []
    if not isinstance(depends, list):
        depends = [depends]
    depends_list = cast("list[Any]", depends)
    priority_text = str(data.get("priority"))
    priority = int(priority_text) if priority_text.isdigit() else 999
    return Task(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        status=str(data.get("status", "")),
        priority=priority,
        milestone=str(data.get("milestone", "")),
        depends_on=tuple(str(item) for item in depends_list),
        approval_level=approval_level,
        approval_status=approval_status,
        approved_by=nonempty(data.get("approved_by")),
        approved_at=nonempty(data.get("approved_at")),
        blocked_reason=nonempty(data.get("blocked_reason")),
        unblock_action=nonempty(data.get("unblock_action")),
        path=path,
        body=body,
    )


def load_tasks() -> list[Task]:
    """Load every task record in the managed project, ordered for planning."""
    if not TASKS_DIR.exists():
        return []
    tasks: list[Task] = []
    for path in sorted(TASKS_DIR.glob("*.md")):
        data, body = split_frontmatter(path)
        tasks.append(normalize_task_data(data, path, body))
    return sorted(tasks, key=task_sort_key)


def load_tasks_with_overrides(overrides: dict[Path, str]) -> list[Task]:
    """Load task records, substituting candidate text for given paths."""
    if not TASKS_DIR.exists():
        return []
    tasks: list[Task] = []
    for path in sorted(TASKS_DIR.glob("*.md")):
        data, body = split_frontmatter_text(
            overrides.get(path, path.read_text(encoding="utf-8")),
            path,
        )
        tasks.append(normalize_task_data(data, path, body))
    return sorted(tasks, key=task_sort_key)


def dump_task_text(data: dict[str, Any], body: str) -> str:
    """Serialize task frontmatter plus body back to Markdown."""
    if "approval" in data:
        data.pop("approval")
    return "---\n" + dump_simple_yaml(data).strip() + "\n---\n" + body


def task_path(task_id: str) -> Path:
    """Resolve the unique task record path for ``task_id``."""
    matches = sorted(TASKS_DIR.glob(f"{task_id}-*.md"))
    if not matches:
        raise ProjectError(
            f"Task {task_id} does not exist. Create project/tasks/{task_id}-...md first."
        )
    if len(matches) > 1:
        raise ProjectError(f"Task {task_id} has multiple files. Keep one task file per id.")
    return matches[0]


def write_if_changed(path: Path, content: str) -> None:
    """Write ``content`` only when it differs from the current file text."""
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def write_state(state: dict[str, Any]) -> None:
    """Persist project state, replacing the file atomically."""
    tmp = STATE_PATH.with_suffix(".yaml.tmp")
    tmp.write_text(dump_simple_yaml(state), encoding="utf-8")
    tmp.replace(STATE_PATH)


def update_task_frontmatter(task_id: str, updates: dict[str, Any]) -> None:
    """Persist frontmatter updates for one task record atomically."""
    path = task_path(task_id)
    data, body = split_frontmatter(path)
    data.update(updates)
    text = dump_task_text(data, body)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def extract_block(path: Path, start: str, end: str) -> str:
    """Return the single generated block between ``start`` and ``end``."""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"{re.escape(start)}\n(.*?)\n{re.escape(end)}", re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise ProjectError(
            f"{relative(path)} must contain exactly one generated block {start} ... {end}."
        )
    if len(pattern.findall(text)) != 1:
        raise ProjectError(f"{relative(path)} contains more than one generated block {start}.")
    return match.group(1)


def normalize_block(text: str) -> str:
    """Normalize block text so drift comparison ignores line endings."""
    return text.strip().replace("\r\n", "\n")


def replace_block_text(text: str, start: str, end: str, content: str, path: Path) -> str:
    """Return ``text`` with its single generated block replaced by ``content``."""
    pattern = re.compile(rf"({re.escape(start)}\n)(.*?)(\n{re.escape(end)})", re.DOTALL)
    updated, count = pattern.subn(rf"\1{content}\3", text)
    if count != 1:
        raise ProjectError(f"{relative(path)} does not contain exactly one {start} block.")
    return updated


def read_state() -> dict[str, Any]:
    """Load ``project/state.yaml`` as a mapping."""
    if not STATE_PATH.exists():
        raise ProjectError(
            "project/state.yaml does not exist. Create project state before validating."
        )
    data = parse_simple_yaml(STATE_PATH.read_text(encoding="utf-8"))
    # Defensive guard for the untyped YAML entry point; parse_simple_yaml is
    # annotated to return a mapping, so pyright cannot see this as reachable.
    if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ProjectError("project/state.yaml must be a mapping.")
    return data
