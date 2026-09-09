from __future__ import annotations

# ruff: noqa: E501
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnnecessaryIsInstance=false
import argparse
import copy
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def discover_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "project" / "state.yaml").exists():
        return cwd
    return Path(__file__).resolve().parents[1]


ROOT = discover_root()
STATE_PATH = ROOT / "project" / "state.yaml"
TASKS_DIR = ROOT / "project" / "tasks"

STATE_START = "<!-- project-status:start -->"
STATE_END = "<!-- project-status:end -->"
INDEX_START = "<!-- project-index:start -->"
INDEX_END = "<!-- project-index:end -->"
KANBAN_START = "<!-- kanban:start -->"
KANBAN_END = "<!-- kanban:end -->"

TASK_ID_RE = re.compile(r"^T-\d{3}$")
TASK_TOKEN_RE = re.compile(r"T-\d{3}")
TASK_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CHECKBOX_RE = re.compile(r"^\s*-\s+\[( |x|X)\]\s+(.+)$")
MAKE_COMMAND_RE = re.compile(r"\bmake\s+([A-Za-z0-9_-]+)")
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s|$)", re.MULTILINE)
UNRENDERED_JINJA_RE = re.compile(r"({[{%#].*?[}%]})")
PERSONAL_PATH_RE = re.compile(
    "|".join(
        re.escape(marker)
        for marker in [
            "/" + "mnt" + "/" + "Data" + "/",
            "/" + "home" + "/" + "semtex" + "/",
            "C:\\Users\\",
        ]
    )
)

PROJECT_TYPES = {"script", "library", "backend", "frontend", "fullstack", "template"}
RUNTIME_LEVELS = {"local", "shared", "production"}
GOVERNANCE_MODES = {"lightweight", "managed"}
WORKFLOW_MODES = {"local", "branch", "pr"}
RISKS = {"low", "medium", "high"}
PROJECT_STATUSES = {"active", "paused", "done", "retired"}
LIFECYCLE_PHASES = {
    "inception",
    "discovery",
    "definition",
    "architecture",
    "bootstrap",
    "delivery",
    "production-readiness",
    "operation",
    "evolution",
    "retirement",
}
TASK_STATUSES = {
    "backlog",
    "ready",
    "in-progress",
    "review",
    "blocked",
    "done",
    "cancelled",
}
APPROVAL_LEVELS = {"A0", "A1", "A2"}
APPROVAL_STATUSES = {"not-required", "pending", "approved", "rejected"}
COLUMNS = [
    ("Backlog", "backlog"),
    ("Ready", "ready"),
    ("In Progress", "in-progress"),
    ("Review", "review"),
    ("Blocked", "blocked"),
    ("Done", "done"),
    ("Cancelled", "cancelled"),
]
DOR_SECTIONS = [
    "Goal",
    "Context",
    "Scope",
    "Out of Scope",
    "Acceptance Criteria",
    "Verification",
    "Documentation Impact",
]
DOD_SECTIONS = ["Verification", "Completion Notes", "Documentation Impact"]
TRANSITIONS = {
    "backlog": {"ready", "cancelled"},
    "ready": {"in-progress", "cancelled"},
    "in-progress": {"review", "blocked", "cancelled"},
    "review": {"in-progress", "done", "cancelled"},
    "blocked": {"ready", "in-progress", "cancelled"},
}
# Levels whose A1/A2 approval boundary is the human GitHub merge when the
# project runs the `pr` workflow mode.
GITHUB_MERGE_LEVELS = {"A1", "A2"}


def state_workflow_mode(state: dict[str, Any]) -> str:
    """Return the project workflow mode, defaulting to local for legacy state."""
    return str(state.get("project", {}).get("workflow_mode", "local"))


def is_github_pr_mode(state: dict[str, Any]) -> bool:
    return state_workflow_mode(state) == "pr"


def git_stdout(args: list[str]) -> str | None:
    """Return stdout from a read-only Git command, or None when it cannot run."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def git_authoritative_base_ref() -> str | None:
    """Resolve the branch whose history is authoritative for PR completion.

    A checkout of main/master is itself the authoritative post-merge view. On a
    feature branch, prefer the remote-tracking base and retain Agent Efficiency's
    local main/master fallbacks for repositories without a configured remote.
    """
    current = (git_stdout(["branch", "--show-current"]) or "").strip()
    if current in {"main", "master"}:
        return "HEAD"
    for ref in ["origin/main", "origin/master", "main", "master"]:
        if git_stdout(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]) is not None:
            return ref
    return None


def task_merge_completed(state: dict[str, Any] | None, task: Task) -> bool:
    """Whether this review-ready A1/A2 record has landed on the base branch.

    The persisted record remains ``review``/``pending``. Completion is derived
    only when the same task record is present in the authoritative base tree, so
    merge commits, squash merges, and rebase/fast-forward merges behave alike.
    """
    if (
        state is None
        or not is_github_pr_mode(state)
        or task.status != "review"
        or task.approval_level not in GITHUB_MERGE_LEVELS
    ):
        return False
    base_ref = git_authoritative_base_ref()
    if base_ref is None:
        return False
    task_path = relative(task.path)
    base_text = git_stdout(["show", f"{base_ref}:{task_path}"])
    if base_text is None:
        return False
    return base_text == task.path.read_text(encoding="utf-8")


def github_merge_completes(state: dict[str, Any] | None, task: Task) -> bool:
    """Compatibility name for the canonical Git-provenance completion check."""
    return task_merge_completed(state, task)


def effective_status(state: dict[str, Any], task: Task) -> str:
    """Status used for dashboards, planning, and dependency resolution."""
    if github_merge_completes(state, task):
        return "done"
    return task.status


class ProjectError(Exception):
    pass


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: str
    priority: int
    milestone: str
    depends_on: tuple[str, ...]
    approval_level: str
    approval_status: str
    approved_by: str | None
    approved_at: str | None
    blocked_reason: str | None
    unblock_action: str | None
    path: Path
    body: str


def parse_scalar(value: str) -> Any:
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
    def scalar(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, list):
            return "[" + ", ".join(str(item) for item in value) + "]"
        return str(value)

    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for child_key, child_value in value.items():
                lines.append(f"  {child_key}: {scalar(child_value)}".rstrip())
            lines.append("")
        else:
            lines.append(f"{key}: {scalar(value)}".rstrip())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def read_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        raise ProjectError(
            "project/state.yaml does not exist. Create project state before validating."
        )
    data = parse_simple_yaml(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProjectError("project/state.yaml must be a mapping.")
    return data


def split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    return split_frontmatter_text(path.read_text(encoding="utf-8"), path)


def split_frontmatter_text(text: str, path: Path) -> tuple[dict[str, Any], str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ProjectError(f"{relative(path)} is missing YAML frontmatter. Add task metadata.")
    return parse_simple_yaml(match.group(1)), match.group(2)


def normalize_task_data(data: dict[str, Any], path: Path, body: str) -> Task:
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
    priority_raw = data.get("priority")
    priority = int(priority_raw) if str(priority_raw).isdigit() else 999
    return Task(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        status=str(data.get("status", "")),
        priority=priority,
        milestone=str(data.get("milestone", "")),
        depends_on=tuple(str(item) for item in depends),
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
    if not TASKS_DIR.exists():
        return []
    tasks = []
    for path in sorted(TASKS_DIR.glob("*.md")):
        data, body = split_frontmatter(path)
        tasks.append(normalize_task_data(data, path, body))
    return sorted(tasks, key=task_sort_key)


def load_tasks_with_overrides(overrides: dict[Path, str]) -> list[Task]:
    if not TASKS_DIR.exists():
        return []
    tasks = []
    for path in sorted(TASKS_DIR.glob("*.md")):
        data, body = split_frontmatter_text(
            overrides.get(path, path.read_text(encoding="utf-8")),
            path,
        )
        tasks.append(normalize_task_data(data, path, body))
    return sorted(tasks, key=task_sort_key)


def task_sort_key(task: Task) -> tuple[int, int, str]:
    number = int(task.id.split("-")[1]) if TASK_ID_RE.match(task.id) else 999999
    return (task.priority, number, task.title)


def relative(path: Path, base: Path = ROOT) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def nonempty(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict) and not value:
        return None
    if isinstance(value, list) and not value:
        return None
    text = str(value).strip()
    return text or None


def task_by_id(tasks: list[Task]) -> dict[str, Task]:
    return {task.id: task for task in tasks}


def section_content(body: str, title: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(title)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", body[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(body)
    return body[start:end].strip()


def has_real_content(body: str, title: str) -> bool:
    content = section_content(body, title)
    meaningful = [line.strip() for line in content.splitlines() if line.strip()]
    return any(not line.startswith("<!--") for line in meaningful)


def acceptance_checkboxes(task: Task) -> list[tuple[bool, str]]:
    content = section_content(task.body, "Acceptance Criteria")
    boxes = []
    for line in content.splitlines():
        match = CHECKBOX_RE.match(line)
        if match:
            boxes.append((match.group(1).lower() == "x", match.group(2)))
    return boxes


def definition_of_ready(task: Task) -> list[str]:
    return [section for section in DOR_SECTIONS if not has_real_content(task.body, section)]


def definition_of_done(task: Task) -> list[str]:
    missing = [section for section in DOD_SECTIONS if not has_real_content(task.body, section)]
    boxes = acceptance_checkboxes(task)
    if boxes and any(not checked for checked, _ in boxes):
        missing.append("all Acceptance Criteria checkboxes checked")
    if "TBD" in section_content(task.body, "Documentation Impact").upper():
        missing.append("Documentation Impact resolved")
    return missing


def valid_datetime(value: str | None) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def dependency_cycle(tasks: list[Task]) -> list[str] | None:
    graph = {task.id: list(task.depends_on) for task in tasks}
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = visiting.index(node)
            return visiting[start:] + [node]
        if node in visited:
            return None
        visiting.append(node)
        for dep in graph.get(node, []):
            cycle = visit(dep)
            if cycle:
                return cycle
        visiting.pop()
        visited.add(node)
        return None

    for task in tasks:
        cycle = visit(task.id)
        if cycle:
            return cycle
    return None


def dependencies_done(
    task: Task,
    tasks_by_id: dict[str, Task],
    *,
    state: dict[str, Any] | None = None,
) -> bool:
    def is_complete(dep: str) -> bool:
        dependency = tasks_by_id[dep]
        if dependency.status in {"done", "cancelled"}:
            return True
        return effective_status(state, dependency) in {"done", "cancelled"}

    return all(is_complete(dep) for dep in task.depends_on if dep in tasks_by_id)


def validate_all(*, check_drift: bool = True) -> list[str]:
    errors: list[str] = []
    try:
        state = read_state()
        tasks = load_tasks()
    except ProjectError as exc:
        return [str(exc)]
    tasks_by = task_by_id(tasks)

    errors.extend(validate_state_schema(state, tasks_by))
    errors.extend(validate_tasks(tasks, state))
    errors.extend(validate_task_graph(tasks, tasks_by, state))
    errors.extend(validate_active_task(state, tasks, tasks_by))
    if check_drift:
        errors.extend(validate_drift(state, tasks))
    errors.extend(validate_markdown_links())
    errors.extend(validate_docs(state, tasks, check_drift=check_drift))
    return errors


def validate_candidate(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    errors: list[str] = []
    tasks_by = task_by_id(tasks)
    errors.extend(validate_state_schema(state, tasks_by))
    errors.extend(validate_tasks(tasks, state))
    errors.extend(validate_task_graph(tasks, tasks_by, state))
    errors.extend(validate_active_task(state, tasks, tasks_by))
    errors.extend(validate_markdown_links())
    errors.extend(validate_docs(state, tasks, check_drift=False))
    return errors


def markdown_files() -> list[Path]:
    roots = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "project", ROOT / "docs"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.exists():
            files.extend(sorted(root.rglob("*.md")))
    return files


def make_targets() -> set[str]:
    makefile = ROOT / "Makefile"
    if not makefile.exists():
        return set()
    return set(MAKE_TARGET_RE.findall(makefile.read_text(encoding="utf-8")))


def documented_make_commands() -> list[tuple[Path, int, str]]:
    commands: list[tuple[Path, int, str]] = []
    for path in markdown_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in MAKE_COMMAND_RE.finditer(line):
                commands.append((path, lineno, match.group(1)))
    return commands


def validate_docs(
    state: dict[str, Any],
    tasks: list[Task],
    *,
    check_drift: bool = True,
) -> list[str]:
    errors: list[str] = []
    if state.get("project", {}).get("type") == "template":
        errors.extend(validate_required_docs())
        if check_drift:
            errors.extend(validate_readme_dashboard(state, tasks))
            errors.extend(validate_doc_drift(state, tasks))
        return errors
    errors.extend(validate_required_docs())
    errors.extend(validate_documented_make_commands())
    errors.extend(validate_doc_text_hygiene())
    errors.extend(validate_profile_documentation(state))
    if check_drift:
        errors.extend(validate_readme_dashboard(state, tasks))
        errors.extend(validate_doc_drift(state, tasks))
    return errors


def validate_required_docs() -> list[str]:
    state = read_state()
    is_template = state.get("project", {}).get("type") == "template"
    required = [
        ROOT / "README.md",
        ROOT / "project" / "index.md",
        ROOT / "project" / "roadmap.md",
        ROOT / "project" / "board.md",
    ]
    if is_template:
        required.extend(
            [
                ROOT / "docs" / "template-architecture.md",
                ROOT / "docs" / "profile-matrix.md",
                ROOT / "docs" / "template-development.md",
            ]
        )
    else:
        required.extend(
            [
                ROOT / "docs" / "architecture.md",
                ROOT / "docs" / "product.md",
                ROOT / "docs" / "workflow.md",
                ROOT / "docs" / "quality.md",
            ]
        )
    errors = [
        f"{relative(path)} is required documentation. Add it."
        for path in required
        if not path.exists()
    ]
    if errors:
        return errors
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required_links = ["project/roadmap.md", "project/board.md"]
    if is_template:
        required_links.extend(
            [
                "docs/template-architecture.md",
                "docs/profile-matrix.md",
                "docs/template-development.md",
            ]
        )
    else:
        required_links.extend(
            [
                "docs/product.md",
                "docs/architecture.md",
                "docs/workflow.md",
            ]
        )
    for link in required_links:
        if f"]({link})" not in readme and f"]({link}#" not in readme:
            errors.append(f"README.md must link to {link}. Add it to the navigation table.")
    return errors


def validate_documented_make_commands() -> list[str]:
    targets = make_targets()
    errors: list[str] = []
    for path, lineno, target in documented_make_commands():
        if target not in targets:
            errors.append(
                f"{relative(path)}:{lineno}: documented command 'make {target}' has no Makefile target."
            )
    return errors


def validate_doc_text_hygiene() -> list[str]:
    errors: list[str] = []
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        if UNRENDERED_JINJA_RE.search(text):
            errors.append(f"{relative(path)} contains an unrendered Jinja placeholder.")
        if PERSONAL_PATH_RE.search(text):
            errors.append(f"{relative(path)} contains a personal absolute path.")
        if "../my-project" in text or "../my-fullstack" in text:
            errors.append(f"{relative(path)} contains stale template example output paths.")
    return errors


def validate_readme_dashboard(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    errors: list[str] = []
    expected_rows = {
        "Project type",
        "Runtime level",
        "Phase",
        "Milestone",
        "Last completed task",
        "Active task",
        "Waiting",
        "Blocker",
        "Next gate",
        "Recommended next action",
        "Next action command",
    }
    try:
        dashboard = extract_block(ROOT / "README.md", STATE_START, STATE_END)
    except ProjectError as exc:
        return [str(exc)]
    for row in expected_rows:
        if f"| {row} |" not in dashboard:
            errors.append(f"README.md dashboard is missing '{row}'. Run: make sync-project-docs")
    command_line = next(
        (line for line in dashboard.splitlines() if line.startswith("| Next action command |")),
        "",
    )
    commands = MAKE_COMMAND_RE.findall(command_line)
    if len(commands) != 1:
        errors.append("README.md dashboard must contain exactly one next action make command.")
    return errors


def validate_profile_documentation(state: dict[str, Any]) -> list[str]:
    project_type = str(state.get("project", {}).get("type", ""))
    runtime_level = str(state.get("project", {}).get("runtime_level", ""))
    docs = {ROOT / "README.md": (ROOT / "README.md").read_text(encoding="utf-8")}
    architecture_path = ROOT / "docs" / "architecture.md"
    if architecture_path.exists():
        docs[architecture_path] = architecture_path.read_text(encoding="utf-8")
    joined = "\n".join(docs.values())
    errors: list[str] = []
    if project_type not in {"backend", "fullstack"} and "FastAPI" in joined:
        errors.append("Project documentation mentions FastAPI for a profile without a backend.")
    if project_type not in {"frontend", "fullstack"} and "Nuxt" in joined:
        errors.append("Project documentation mentions Nuxt for a profile without a frontend.")
    if project_type != "fullstack" and "generated OpenAPI client" in joined:
        errors.append("Project documentation mentions generated OpenAPI client outside fullstack.")
    if runtime_level != "production" and "OCI image" in joined:
        errors.append(
            "Project documentation mentions production OCI images for a non-production runtime."
        )
    required_by_type = {
        "script": "Python CLI package",
        "library": "Python library package",
        "backend": "FastAPI service",
        "frontend": "Nuxt application",
        "fullstack": "FastAPI backend and Nuxt frontend",
        "template": "Copier template",
    }
    marker = required_by_type.get(project_type)
    if marker and marker not in joined:
        errors.append(f"Project documentation must describe the selected profile as: {marker}.")
    return errors


def validate_doc_drift(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    expected = {
        ROOT / "README.md": (STATE_START, STATE_END, dashboard_block(state, tasks)),
    }
    errors: list[str] = []
    for path, (start, end, content) in expected.items():
        try:
            current = extract_block(path, start, end)
        except ProjectError as exc:
            errors.append(str(exc))
            continue
        if normalize_block(current) != normalize_block(content):
            errors.append(
                f"{relative(path)} documentation dashboard is stale. Run: make sync-project-docs"
            )
    return errors


def validate_state_schema(state: dict[str, Any], tasks_by: dict[str, Task]) -> list[str]:
    errors: list[str] = []
    if state.get("schema_version") != 1:
        errors.append("project/state.yaml schema_version must be 1. Fix schema_version.")
    project = state.get("project")
    lifecycle = state.get("lifecycle")
    work = state.get("work")
    template = state.get("template")
    for key, section in [
        ("project", project),
        ("lifecycle", lifecycle),
        ("work", work),
        ("template", template),
    ]:
        if not isinstance(section, dict):
            errors.append(f"project/state.yaml is missing mapping '{key}'. Add the {key} section.")
    if errors:
        return errors
    assert isinstance(project, dict)
    assert isinstance(lifecycle, dict)
    assert isinstance(work, dict)
    assert isinstance(template, dict)
    if project.get("type") not in PROJECT_TYPES:
        errors.append(
            f"project.type '{project.get('type')}' is invalid. Use one of: {', '.join(sorted(PROJECT_TYPES))}."
        )
    if project.get("runtime_level") not in RUNTIME_LEVELS:
        errors.append("project.runtime_level is invalid. Use local, shared, or production.")
    if "governance" in project and project.get("governance") not in GOVERNANCE_MODES:
        errors.append("project.governance is invalid. Use lightweight or managed.")
    if "workflow_mode" in project and project.get("workflow_mode") not in WORKFLOW_MODES:
        errors.append("project.workflow_mode is invalid. Use local, branch, or pr.")
    if project.get("risk") not in RISKS:
        errors.append("project.risk is invalid. Use low, medium, or high.")
    if project.get("status") not in PROJECT_STATUSES:
        errors.append("project.status is invalid. Use active, paused, done, or retired.")
    if lifecycle.get("phase") not in LIFECYCLE_PHASES:
        errors.append("lifecycle.phase is invalid. Use a documented lifecycle phase.")
    if project.get("status") == "active":
        if not nonempty(lifecycle.get("milestone")):
            errors.append("Active project requires lifecycle.milestone. Set the current milestone.")
        if not nonempty(lifecycle.get("next_gate")):
            errors.append("Active project requires lifecycle.next_gate. Set the next gate.")
    active = nonempty(work.get("active_task"))
    if active and not TASK_ID_RE.match(active):
        errors.append(
            f"work.active_task '{active}' is invalid. Use format T-001 or leave it empty."
        )
    if active and active not in tasks_by:
        errors.append(
            f"work.active_task '{active}' does not exist. Create the task or clear active_task."
        )
    if not nonempty(template.get("version")):
        errors.append("template.version is required. Set the template version.")
    return errors


def validate_tasks(tasks: list[Task], state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    current_milestone = str(state.get("lifecycle", {}).get("milestone", ""))
    for task in tasks:
        prefix = f"{task.id or relative(task.path)}:"
        if not TASK_ID_RE.match(task.id):
            errors.append(f"{prefix} invalid task id. Use format T-001.")
        if task.id in seen:
            errors.append(f"Duplicate task id {task.id}. Keep task IDs unique.")
        seen.add(task.id)
        if not task.title:
            errors.append(f"{prefix} title is required.")
        if task.status not in TASK_STATUSES:
            errors.append(
                f"{prefix} invalid status '{task.status}'. Use one of: {', '.join(sorted(TASK_STATUSES))}."
            )
        if not isinstance(task.priority, int) or task.priority < 1:
            errors.append(f"{prefix} priority must be a positive integer.")
        if not task.milestone:
            errors.append(f"{prefix} milestone is required.")
        if (
            effective_status(state, task) in {"ready", "in-progress", "review"}
            and task.milestone != current_milestone
        ):
            errors.append(
                f"{prefix} milestone '{task.milestone}' is not the current milestone '{current_milestone}'. Move it or update project/state.yaml."
            )
        if task.approval_level not in APPROVAL_LEVELS:
            errors.append(
                f"{prefix} invalid approval_level '{task.approval_level}'. Use A0, A1, or A2."
            )
        if task.approval_status not in APPROVAL_STATUSES:
            errors.append(
                f"{prefix} invalid approval_status '{task.approval_status}'. Use not-required, pending, approved, or rejected."
            )
        errors.extend(validate_approval(task, state))
        errors.extend(validate_blocker(task))
        if effective_status(state, task) in {"ready", "in-progress", "review"}:
            missing = definition_of_ready(task)
            if missing:
                errors.append(
                    f"{prefix} Definition of Ready is incomplete: {', '.join(missing)}. Fill the required sections before ready/start."
                )
        if task.status == "done":
            missing = definition_of_done(task)
            if missing:
                errors.append(
                    f"{prefix} Definition of Done is incomplete: {', '.join(missing)}. Complete verification, notes, docs impact, and checked criteria."
                )
    return errors


def validate_approval(task: Task, state: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    prefix = f"{task.id}:"
    pr_mode = state is not None and is_github_pr_mode(state)
    merged = bool(state) and task_merge_completed(state, task)
    if task.approval_level == "A0":
        if task.approval_status != "not-required":
            errors.append(f"{prefix} A0 tasks must use approval_status not-required.")
        if task.approved_by or task.approved_at:
            errors.append(f"{prefix} A0 tasks must not carry human approval metadata.")
    if task.approval_level in {"A1", "A2"}:
        if task.approval_status == "approved":
            if not task.approved_by:
                errors.append(
                    f"{prefix} approved task requires approved_by. Record the human approver."
                )
            if not valid_datetime(task.approved_at):
                errors.append(
                    f"{prefix} approved_at is invalid. Use ISO datetime, for example 2026-07-31T10:00:00+02:00."
                )
        if task.approval_status != "approved" and (task.approved_by or task.approved_at):
            errors.append(
                f"{prefix} approval metadata is present but approval_status is not approved. Clear it or approve explicitly."
            )
    if pr_mode and not merged and task.approval_level == "A1" and task.status != "done":
        if task.approval_status == "approved" or task.approved_by or task.approved_at:
            errors.append(
                f"{prefix} A1 approval cannot be recorded locally in workflow_mode=pr. "
                "The human GitHub merge is the only A1 approval boundary. Clear the local approval fields."
            )
        if task.status == "review" and task.approval_status != "pending":
            errors.append(
                f"{prefix} A1 review tasks in workflow_mode=pr must keep approval_status pending. "
                "Completion is derived from the human GitHub merge, never recorded by the agent."
            )
    if task.approval_level == "A1" and task.status == "done" and task.approval_status != "approved":
        if pr_mode:
            errors.append(
                f"{prefix} A1 task cannot be done without approval. In workflow_mode=pr the human GitHub merge of the review pull request is the only A1 approval."
            )
        else:
            errors.append(
                f'{prefix} A1 task cannot be done without human approval. Run: make task-approve TASK={task.id} APPROVED_BY="<human>".'
            )
    if (
        task.approval_level == "A2"
        and task.status in {"in-progress", "review", "done"}
        and task.approval_status != "approved"
    ):
        errors.append(
            f'{prefix} A2 task cannot start or finish without prior human approval. Human must run: make task-approve TASK={task.id} APPROVED_BY="<human>".'
        )
    return errors


def validate_blocker(task: Task) -> list[str]:
    errors: list[str] = []
    prefix = f"{task.id}:"
    if task.status == "blocked":
        if not task.blocked_reason:
            errors.append(
                f'{prefix} blocked task requires blocked_reason. Use make task-block TASK={task.id} REASON="..." UNBLOCK="...".'
            )
        if not task.unblock_action:
            errors.append(
                f'{prefix} blocked task requires unblock_action. Use make task-block TASK={task.id} REASON="..." UNBLOCK="...".'
            )
    elif task.blocked_reason or task.unblock_action:
        errors.append(
            f"{prefix} blocker metadata is only allowed when status is blocked. Clear blocked_reason and unblock_action."
        )
    return errors


def validate_task_graph(
    tasks: list[Task], tasks_by: dict[str, Task], state: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    for task in tasks:
        if len(set(task.depends_on)) != len(task.depends_on):
            errors.append(
                f"{task.id}: duplicate dependencies are not allowed. Remove duplicates from depends_on."
            )
        if task.id in task.depends_on:
            errors.append(
                f"{task.id}: task cannot depend on itself. Remove {task.id} from depends_on."
            )
        for dep in task.depends_on:
            if dep not in tasks_by:
                errors.append(
                    f"{task.id}: dependency {dep} does not exist. Create it or remove the dependency."
                )
    cycle = dependency_cycle(tasks)
    if cycle:
        errors.append(
            f"Task dependency cycle detected: {' -> '.join(cycle)}. Break the cycle before continuing."
        )
    for task in tasks:
        if task.status in {"ready", "in-progress"} and not dependencies_done(
            task, tasks_by, state=state
        ):
            missing = [
                dep
                for dep in task.depends_on
                if dep in tasks_by
                and effective_status(state, tasks_by[dep]) not in {"done", "cancelled"}
            ]
            errors.append(
                f"{task.id}: cannot be {task.status}; dependencies are not done: {', '.join(missing)}. Complete dependencies first."
            )
    return errors


def validate_active_task(
    state: dict[str, Any], tasks: list[Task], tasks_by: dict[str, Task]
) -> list[str]:
    errors: list[str] = []
    active = nonempty(state.get("work", {}).get("active_task"))
    in_progress = [task for task in tasks if task.status == "in-progress"]
    blocked_flag = bool(state.get("work", {}).get("blocked"))
    any_blocked = any(task.status == "blocked" for task in tasks)
    if len(in_progress) > 1:
        errors.append(
            "More than one task is in-progress. Finish, review, block, or cancel one task."
        )
    if len(in_progress) == 1 and active != in_progress[0].id:
        errors.append(
            f"work.active_task must be {in_progress[0].id}. Run the controlled task transition or update state consistently."
        )
    if not in_progress and active:
        errors.append(
            "work.active_task is set but no task is in-progress. Clear work.active_task or start the task through make task-start."
        )
    if active and active in tasks_by and tasks_by[active].status == "blocked":
        errors.append(
            f"Active task {active} is blocked. Active task cannot be blocked; unblock it or clear active_task."
        )
    if blocked_flag != any_blocked:
        errors.append(
            "work.blocked does not match blocked tasks. Run: make sync-project-docs after fixing blocker state."
        )
    return errors


def validate_drift(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    errors: list[str] = []
    expected = {
        ROOT / "README.md": (STATE_START, STATE_END, dashboard_block(state, tasks)),
        ROOT / "project" / "index.md": (
            INDEX_START,
            INDEX_END,
            project_index_block(state, tasks),
        ),
        ROOT / "project" / "board.md": (KANBAN_START, KANBAN_END, kanban_block(tasks, state)),
    }
    for path, (start, end, content) in expected.items():
        try:
            current = extract_block(path, start, end)
        except ProjectError as exc:
            errors.append(str(exc))
            continue
        if normalize_block(current) != normalize_block(content):
            errors.append(f"{relative(path)} generated block is stale. Run: make sync-project-docs")
    return errors


def validate_markdown_links() -> list[str]:
    errors: list[str] = []
    for path in markdown_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in TASK_LINK_RE.finditer(line):
                target = match.group(2).strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                resolved = (path.parent / target_path).resolve()
                if not resolved.exists():
                    errors.append(
                        f"{relative(path)}:{lineno}: broken internal Markdown link target '{target_path}'. Fix the relative path."
                    )
    return errors


def extract_block(path: Path, start: str, end: str) -> str:
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
    return text.strip().replace("\r\n", "\n")


def find_active(tasks: list[Task], state: dict[str, Any]) -> Task | None:
    active = nonempty(state.get("work", {}).get("active_task"))
    return task_by_id(tasks).get(active) if active else None


def task_link(task: Task, base: Path) -> str:
    return f"[{task.id}]({relative(task.path, base)})"


def approval_text(task: Task | None) -> str:
    if not task:
        return "None"
    return f"{task.approval_level} / {task.approval_status}"


def last_completed_task(tasks: list[Task], base: Path, state: dict[str, Any] | None = None) -> str:
    done = sorted(
        (task for task in tasks if effective_status(state, task) == "done"),
        key=task_sort_key,
    )
    if not done:
        return "None"
    return task_link(done[-1], base)


def waiting_text(tasks: list[Task], state: dict[str, Any] | None = None) -> str:
    pr_mode = state is not None and is_github_pr_mode(state)
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if blocked:
        return f"Blocked: {blocked[0].id}"
    review_waiting = sorted(
        (
            task
            for task in tasks
            if task.status == "review"
            and task.approval_level in {"A1", "A2"}
            and not github_merge_completes(state, task)
            and (pr_mode or task.approval_status != "approved")
        ),
        key=task_sort_key,
    )
    if review_waiting:
        task = review_waiting[0]
        if pr_mode:
            return f"Awaiting human GitHub merge: {task.id}"
        return f"{task.approval_level} approval pending: {task.id}"
    pending_a2 = sorted(
        (
            task
            for task in tasks
            if task.status == "ready"
            and task.approval_level == "A2"
            and task.approval_status != "approved"
        ),
        key=task_sort_key,
    )
    if pending_a2:
        return f"A2 approval required before start: {pending_a2[0].id}"
    return "None"


def blocker_text(tasks: list[Task]) -> str:
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if not blocked:
        return "None"
    task = blocked[0]
    return f"{task.id}: {task.blocked_reason or 'blocked'}"


def recommended_next_action(
    state: dict[str, Any], tasks: list[Task], *, invalid: bool = False
) -> str:
    if invalid:
        return "Fix project validation errors, then run: make validate-project."
    tasks_by = task_by_id(tasks)
    pr_mode = is_github_pr_mode(state)
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if blocked:
        task = blocked[0]
        return f"Unblock {task.id} by {task.unblock_action}."
    pending_a2 = sorted(
        (
            task
            for task in tasks
            if task.approval_level == "A2"
            and task.approval_status != "approved"
            and task.status == "ready"
        ),
        key=task_sort_key,
    )
    if pending_a2:
        return f"Human A2 approval is required for {pending_a2[0].id} before work starts."
    in_progress = [task for task in tasks if task.status == "in-progress"]
    if in_progress:
        return f"Complete {in_progress[0].id}."
    review_waiting = sorted(
        (
            task
            for task in tasks
            if task.status == "review"
            and task.approval_level in {"A1", "A2"}
            and not github_merge_completes(state, task)
            and (pr_mode or task.approval_status != "approved")
        ),
        key=task_sort_key,
    )
    if review_waiting:
        task = review_waiting[0]
        if pr_mode:
            return f"Await human GitHub merge for {task.id}; merge is the completion boundary."
        return f"Human {task.approval_level} approval is required for {task.id} before completion."
    ready = sorted(
        (
            task
            for task in tasks
            if task.status == "ready" and dependencies_done(task, tasks_by, state=state)
        ),
        key=task_sort_key,
    )
    if ready:
        return f"Start {ready[0].id}."
    gate = state.get("lifecycle", {}).get("next_gate", "current-gate")
    return f"No ready task exists. Create one task addressing gate {gate}."


def recommended_next_command(
    state: dict[str, Any], tasks: list[Task], *, invalid: bool = False
) -> str:
    if invalid:
        return "`make validate-project`"
    tasks_by = task_by_id(tasks)
    pr_mode = is_github_pr_mode(state)
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if blocked:
        return f"`make task-unblock TASK={blocked[0].id}`"
    pending_a2 = sorted(
        (
            task
            for task in tasks
            if task.approval_level == "A2"
            and task.approval_status != "approved"
            and task.status == "ready"
        ),
        key=task_sort_key,
    )
    if pending_a2:
        return f'`make task-approve TASK={pending_a2[0].id} APPROVED_BY="<human>"`'
    in_progress = [task for task in tasks if task.status == "in-progress"]
    if in_progress:
        return f"`make task-review TASK={in_progress[0].id}`"
    review_waiting = sorted(
        (
            task
            for task in tasks
            if task.status == "review"
            and task.approval_level in {"A1", "A2"}
            and not github_merge_completes(state, task)
            and (pr_mode or task.approval_status != "approved")
        ),
        key=task_sort_key,
    )
    if review_waiting:
        task = review_waiting[0]
        if pr_mode:
            return f"`make project-status` (await human GitHub merge of {task.id})."
        return f'`make task-approve TASK={task.id} APPROVED_BY="<human>"`'
    ready = sorted(
        (
            task
            for task in tasks
            if task.status == "ready" and dependencies_done(task, tasks_by, state=state)
        ),
        key=task_sort_key,
    )
    if ready:
        return f"`make task-start TASK={ready[0].id}`"
    return "`make task-ready TASK=<new-task-id>`"


def dashboard_block(state: dict[str, Any], tasks: list[Task]) -> str:
    project = state["project"]
    lifecycle = state["lifecycle"]
    active = find_active(tasks, state)
    active_value = task_link(active, ROOT) if active else "None"
    return "\n".join(
        [
            "| Item | Value |",
            "|---|---|",
            f"| Project type | {project['type']} |",
            f"| Runtime level | {project['runtime_level']} |",
            f"| Phase | {lifecycle['phase']} |",
            f"| Milestone | {lifecycle['milestone']} |",
            f"| Last completed task | {last_completed_task(tasks, ROOT, state)} |",
            f"| Active task | {active_value} |",
            f"| Approval | {approval_text(active)} |",
            f"| Waiting | {waiting_text(tasks, state)} |",
            f"| Blocker | {blocker_text(tasks)} |",
            f"| Next gate | {lifecycle['next_gate']} |",
            f"| Recommended next action | {recommended_next_action(state, tasks)} |",
            f"| Next action command | {recommended_next_command(state, tasks)} |",
        ]
    )


def project_index_block(state: dict[str, Any], tasks: list[Task]) -> str:
    project = state["project"]
    lifecycle = state["lifecycle"]
    active = find_active(tasks, state)
    blocker = active.blocked_reason if active and active.blocked_reason else "None"
    active_value = task_link(active, ROOT / "project") if active else "None"
    return "\n".join(
        [
            "| Item | Value |",
            "|---|---|",
            f"| Project | {project.get('name', project.get('type', 'project'))} |",
            f"| Phase | {lifecycle['phase']} |",
            f"| Milestone | {lifecycle['milestone']} |",
            f"| Next gate | {lifecycle['next_gate']} |",
            f"| Active task | {active_value} |",
            f"| Approval | {approval_text(active)} |",
            f"| Blocker | {blocker} |",
            f"| Recommended next action | {recommended_next_action(state, tasks)} |",
            "",
            "Links: [Board](board.md) | [Roadmap](roadmap.md)",
        ]
    )


def kanban_block(tasks: list[Task], state: dict[str, Any] | None = None) -> str:
    lines: list[str] = []
    for title, status in COLUMNS:
        lines.extend([f"## {title}", ""])
        matching = sorted(
            (task for task in tasks if effective_status(state, task) == status),
            key=task_sort_key,
        )
        if matching:
            for task in matching:
                rel = relative(task.path, ROOT / "project")
                if status == "blocked" and task.blocked_reason:
                    suffix = f" - blocked: {task.blocked_reason}"
                elif task_merge_completed(state, task):
                    suffix = " - completed by merged Git provenance"
                elif (
                    is_github_pr_mode(state)
                    and task.status == "review"
                    and task.approval_level in GITHUB_MERGE_LEVELS
                ):
                    suffix = " - awaiting human GitHub merge"
                else:
                    suffix = ""
                lines.append(f"- [{task.id}]({rel}) - P{task.priority} - {task.title}{suffix}")
        else:
            lines.append("_None_")
        lines.append("")
    return "\n".join(lines).rstrip()


def replace_block_text(text: str, start: str, end: str, content: str, path: Path) -> str:
    pattern = re.compile(rf"({re.escape(start)}\n)(.*?)(\n{re.escape(end)})", re.DOTALL)
    updated, count = pattern.subn(rf"\1{content}\3", text)
    if count != 1:
        raise ProjectError(f"{relative(path)} does not contain exactly one {start} block.")
    return updated


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def rendered_dashboard_texts(state: dict[str, Any], tasks: list[Task]) -> dict[Path, str]:
    if os.environ.get("PROJECT_TOOL_FAIL_RENDER") == "1":
        raise ProjectError("Injected dashboard rendering failure.")
    replacements = {
        ROOT / "README.md": (STATE_START, STATE_END, dashboard_block(state, tasks)),
        ROOT / "project" / "index.md": (
            INDEX_START,
            INDEX_END,
            project_index_block(state, tasks),
        ),
        ROOT / "project" / "board.md": (KANBAN_START, KANBAN_END, kanban_block(tasks, state)),
    }
    rendered: dict[Path, str] = {}
    for path, (start, end, content) in replacements.items():
        rendered[path] = replace_block_text(
            path.read_text(encoding="utf-8"), start, end, content, path
        )
    return rendered


def sync() -> None:
    state = read_state()
    tasks = load_tasks()
    errors = validate_all(check_drift=False)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    for path, updated in rendered_dashboard_texts(state, tasks).items():
        write_if_changed(path, updated)
    print("Project docs synchronized.")


def dump_task_text(data: dict[str, Any], body: str) -> str:
    if "approval" in data:
        data.pop("approval")
    return "---\n" + dump_simple_yaml(data).strip() + "\n---\n" + body


def project_control_paths(task_file: Path) -> list[Path]:
    return [
        task_file,
        STATE_PATH,
        ROOT / "README.md",
        ROOT / "project" / "index.md",
        ROOT / "project" / "board.md",
    ]


def assert_no_tmp_files(paths: list[Path]) -> None:
    leftovers: list[Path] = []
    for path in paths:
        leftovers.extend(path.parent.glob(path.name + ".tmp-*"))
    if leftovers:
        raise ProjectError(
            "Temporary mutation files remain: "
            + ", ".join(relative(path) for path in sorted(leftovers))
        )


def commit_files_atomically(files: dict[Path, str]) -> None:
    paths = list(files)
    snapshots = {path: path.read_bytes() if path.exists() else None for path in paths}
    tmp_paths: list[Path] = []
    try:
        for path, content in files.items():
            tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
            tmp.write_text(content, encoding="utf-8")
            tmp_paths.append(tmp)
        if os.environ.get("PROJECT_TOOL_FAIL_WRITE") == "1":
            raise ProjectError("Injected write failure.")
        for tmp, path in zip(tmp_paths, paths, strict=True):
            tmp.replace(path)
        if os.environ.get("PROJECT_TOOL_FAIL_FINAL_VALIDATE") == "1":
            raise ProjectError("Injected final validation failure.")
        errors = validate_all(check_drift=True)
        if errors:
            raise ProjectError("\n".join(errors))
    except Exception:
        for path, content in snapshots.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        for tmp in tmp_paths:
            tmp.unlink(missing_ok=True)
        assert_no_tmp_files(paths)
        raise
    assert_no_tmp_files(paths)


def transactional_task_mutation(
    task_id: str,
    task_updates: dict[str, Any],
    state: dict[str, Any],
) -> None:
    path = task_path(task_id)
    data, body = split_frontmatter(path)
    data.update(task_updates)
    task_text = dump_task_text(data, body)
    task_overrides = {path: task_text}
    candidate_tasks = load_tasks_with_overrides(task_overrides)
    if os.environ.get("PROJECT_TOOL_FAIL_VALIDATION") == "1":
        candidate_tasks = [
            task
            if task.id != task_id
            else normalize_task_data(
                {**data, "status": "__invalid_candidate_status__"},
                path,
                body,
            )
            for task in candidate_tasks
        ]
    errors = validate_candidate(state, candidate_tasks)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    rendered = rendered_dashboard_texts(state, candidate_tasks)
    files = {
        path: task_text,
        STATE_PATH: dump_simple_yaml(state),
        **rendered,
    }
    try:
        commit_files_atomically(files)
    except ProjectError as exc:
        print_errors([str(exc)])
        raise SystemExit(1) from exc


def print_errors(errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR: {error}")
    print("Recommended fix: apply the specific correction above, then run: make validate-project")


def validate() -> None:
    errors = validate_all(check_drift=True)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    print("Project state is valid.")


def validate_docs_command() -> None:
    state = read_state()
    tasks = load_tasks()
    errors: list[str] = []
    errors.extend(validate_markdown_links())
    errors.extend(validate_docs(state, tasks, check_drift=True))
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    print("Project documentation is valid.")


def status() -> None:
    state = read_state()
    tasks = load_tasks()
    errors = validate_all(check_drift=False)
    print(dashboard_block(state, tasks))
    print()
    print(f"Next action: {recommended_next_action(state, tasks, invalid=bool(errors))}")
    if errors:
        print()
        print_errors(errors)


def task_path(task_id: str) -> Path:
    matches = sorted(TASKS_DIR.glob(f"{task_id}-*.md"))
    if not matches:
        raise ProjectError(
            f"Task {task_id} does not exist. Create project/tasks/{task_id}-...md first."
        )
    if len(matches) > 1:
        raise ProjectError(f"Task {task_id} has multiple files. Keep one task file per id.")
    return matches[0]


def update_task_frontmatter(task_id: str, updates: dict[str, Any]) -> None:
    path = task_path(task_id)
    data, body = split_frontmatter(path)
    data.update(updates)
    text = dump_task_text(data, body)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_state(state: dict[str, Any]) -> None:
    tmp = STATE_PATH.with_suffix(".yaml.tmp")
    tmp.write_text(dump_simple_yaml(state), encoding="utf-8")
    tmp.replace(STATE_PATH)


def controlled_transition(
    task_id: str,
    new_status: str,
    *,
    reason: str | None = None,
    unblock: str | None = None,
) -> None:
    state = read_state()
    candidate_state = copy.deepcopy(state)
    tasks = load_tasks()
    tasks_by = task_by_id(tasks)
    pr_mode = is_github_pr_mode(state)
    task = tasks_by.get(task_id)
    if task is None:
        raise ProjectError(f"Task {task_id} does not exist. Create it before transitioning.")
    if new_status not in TASK_STATUSES:
        raise ProjectError(f"Invalid target status {new_status}. Use a supported task status.")
    if new_status not in TRANSITIONS.get(task.status, set()) and not (
        task.approval_level == "A0" and task.status == "in-progress" and new_status == "done"
    ):
        raise ProjectError(
            f"Invalid transition: {task.status} -> {new_status}. Task must pass through the allowed lifecycle."
        )
    candidate = dict(status=new_status)
    if new_status == "blocked":
        if not reason or not unblock:
            raise ProjectError(
                'Blocking requires REASON and UNBLOCK. Run: make task-block TASK=... REASON="..." UNBLOCK="..."'
            )
        candidate.update(blocked_reason=reason, unblock_action=unblock)
    else:
        candidate.update(blocked_reason=None, unblock_action=None)
    if new_status == "in-progress":
        if task.approval_level == "A2" and task.approval_status != "approved":
            raise ProjectError(f"Human A2 approval is required for {task.id} before work starts.")
        if any(other.status == "in-progress" and other.id != task.id for other in tasks):
            raise ProjectError(
                "Another task is already in-progress. Move it to review, blocked, done, or cancelled first."
            )
        missing = definition_of_ready(task)
        if missing:
            raise ProjectError(f"{task.id} is not ready: {', '.join(missing)}.")
        if not dependencies_done(task, tasks_by, state=state):
            raise ProjectError(f"{task.id} cannot start until all dependencies are done.")
        candidate_state["work"]["active_task"] = task.id
    if new_status == "ready":
        missing = definition_of_ready(task)
        if missing:
            raise ProjectError(f"{task.id} is not ready: {', '.join(missing)}.")
        if not dependencies_done(task, tasks_by, state=state):
            raise ProjectError(f"{task.id} cannot become ready until dependencies are done.")
    if new_status == "done":
        if pr_mode and task.approval_level in {"A1", "A2"}:
            raise ProjectError(
                f"Task {task.id} is {task.approval_level} in workflow_mode=pr. "
                "The human GitHub merge of its pull request is the completion boundary; "
                "make task-complete is not used for A1/A2 tasks in pr mode."
            )
        if task.approval_level in {"A1", "A2"} and task.approval_status != "approved":
            raise ProjectError(
                f"Human {task.approval_level} approval is required for {task.id} before done."
            )
        missing = definition_of_done(task)
        if missing:
            raise ProjectError(f"{task.id} cannot be done: {', '.join(missing)}.")
    if task.status == "in-progress" and new_status != "in-progress":
        candidate_state["work"]["active_task"] = None
    if new_status == "blocked":
        candidate_state["work"]["active_task"] = None
    path = task_path(task_id)
    data, body = split_frontmatter(path)
    data.update(candidate)
    refreshed = load_tasks_with_overrides({path: dump_task_text(data, body)})
    candidate_state["work"]["blocked"] = any(item.status == "blocked" for item in refreshed)
    if not any(item.status == "in-progress" for item in refreshed):
        candidate_state["work"]["active_task"] = None
    transactional_task_mutation(task_id, candidate, candidate_state)
    print(f"Task {task_id} moved to {new_status}.")


def approve(task_id: str, approved_by: str) -> None:
    if not approved_by.strip():
        raise ProjectError("APPROVED_BY is required and must be a human identity.")
    task = task_by_id(load_tasks()).get(task_id)
    if task is None:
        raise ProjectError(f"Task {task_id} does not exist.")
    if task.approval_level == "A0":
        raise ProjectError(f"{task_id} is A0 and does not require approval.")
    state = read_state()
    if is_github_pr_mode(state) and task.approval_level == "A1":
        raise ProjectError(
            f"{task_id} is A1 in workflow_mode=pr. The human GitHub merge is the only A1 "
            "approval boundary; do not record a local A1 approval."
        )
    transactional_task_mutation(
        task_id,
        {
            "approval_status": "approved",
            "approved_by": approved_by.strip(),
            "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        state,
    )
    print(f"Task {task_id} approved by {approved_by.strip()}.")


def pr_validate() -> None:
    """Pre-merge structural validation for a governed GitHub pull request.

    Deterministic association: exactly one task id (T-###) must appear across
    the PR branch name, title, and body. The task must already be in review
    (A1/A2) or done (A0) so that merging the pull request is a pure human
    decision. A1 tasks must not carry locally recorded approval: the human
    GitHub merge is the only A1 approval boundary.
    """
    state = read_state()
    if not is_github_pr_mode(state):
        raise ProjectError(
            "pr-validate is only meaningful for managed projects with project.workflow_mode: pr."
        )
    tasks = load_tasks()
    tasks_by = task_by_id(tasks)
    sources = [
        os.environ.get("PR_HEAD_REF", ""),
        os.environ.get("PR_TITLE", ""),
        os.environ.get("PR_BODY", ""),
    ]
    referenced = {match for source in sources for match in TASK_TOKEN_RE.findall(source or "")}
    if not referenced:
        raise ProjectError(
            "PR association is missing. Put exactly one task id (T-###) in the PR branch "
            "name or the PR title, for example feat/T-002-... or 'T-002: title'."
        )
    if len(referenced) > 1:
        ordered = ", ".join(sorted(referenced))
        raise ProjectError(
            f"PR references multiple task ids: {ordered}. Open one pull request per task."
        )
    task_id = next(iter(referenced))
    task = tasks_by.get(task_id)
    if task is None:
        raise ProjectError(f"PR references {task_id} but no such task exists.")
    if task.approval_level == "A0":
        if task.status != "done":
            raise ProjectError(
                f"{task_id} is A0 and must be done before its pull request is merged. "
                "Run: make task-complete TASK={task_id}"
            )
    elif task.status != "review":
        raise ProjectError(
            f"{task_id} must be in review before its pull request is merged. "
            "Move it there first: make task-review TASK={task_id}"
        )
    elif task.approval_level == "A1":
        if task.approval_status != "pending" or task.approved_by or task.approved_at:
            raise ProjectError(
                f"{task_id} must not record local A1 approval. In workflow_mode=pr the human "
                "GitHub merge is the only A1 approval boundary."
            )
    elif task.approval_level == "A2":
        if task.approval_status != "approved" or not task.approved_by:
            raise ProjectError(
                f"{task_id} is A2 and requires a human-recorded approval before work starts. "
                "A2 keeps its stronger pre-start approval boundary in workflow_mode=pr."
            )
    errors = validate_all(check_drift=True)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    print(f"Pull request for {task_id} is structurally valid for a human GitHub merge.")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sync")
    sub.add_parser("validate")
    sub.add_parser("validate-docs")
    sub.add_parser("pr-validate")
    for name in ["ready", "start", "review", "complete", "unblock", "cancel"]:
        command = sub.add_parser(name)
        command.add_argument("task")
    block = sub.add_parser("block")
    block.add_argument("task")
    block.add_argument("--reason", required=True)
    block.add_argument("--unblock", required=True)
    approve_cmd = sub.add_parser("approve")
    approve_cmd.add_argument("task")
    approve_cmd.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    try:
        if args.command == "status":
            status()
        elif args.command == "sync":
            sync()
        elif args.command == "validate":
            validate()
        elif args.command == "validate-docs":
            validate_docs_command()
        elif args.command == "pr-validate":
            pr_validate()
        elif args.command == "ready":
            controlled_transition(args.task, "ready")
        elif args.command == "start":
            controlled_transition(args.task, "in-progress")
        elif args.command == "review":
            controlled_transition(args.task, "review")
        elif args.command == "complete":
            controlled_transition(args.task, "done")
        elif args.command == "unblock":
            controlled_transition(args.task, "ready")
        elif args.command == "cancel":
            controlled_transition(args.task, "cancelled")
        elif args.command == "block":
            controlled_transition(args.task, "blocked", reason=args.reason, unblock=args.unblock)
        elif args.command == "approve":
            approve(args.task, args.approved_by)
    except ProjectError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
