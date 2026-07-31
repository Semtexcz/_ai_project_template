from __future__ import annotations

# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportArgumentType=false
import argparse
import fnmatch
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised in generated projects without PyYAML
    yaml = None


REQUIRED_SKILLS = {
    "initialize-project",
    "assess-project-state",
    "choose-next-task",
    "prepare-task",
    "implement-change",
    "review-change",
    "complete-task",
    "create-adr",
    "reassess-project",
}
REQUIRED_SKILL_KEYS = {
    "name",
    "version",
    "purpose",
    "triggers",
    "inputs",
    "reads",
    "commands",
    "outputs",
    "approval_boundary",
    "stop_conditions",
}
SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "credentials*",
    "secrets*",
    "**/.env",
    "**/.env.*",
    "**/*.pem",
    "**/*.key",
    "**/credentials*",
    "**/secrets*",
]
DEFAULT_EXCLUDES = [
    ".git/**",
    "node_modules/**",
    ".venv/**",
    "dist/**",
    ".output/**",
    "coverage/**",
    "cache/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "__pycache__/**",
]
BUILD_ARTIFACT_PATTERNS = [
    "dist/**",
    "**/dist/**",
    ".output/**",
    "**/.output/**",
    "coverage/**",
    "**/coverage/**",
    "*.pyc",
    "**/*.pyc",
]


class AgentError(Exception):
    pass


@dataclass(frozen=True)
class CommandResult:
    command: str
    status: str
    output: str = ""


def discover_root() -> Path:
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "project" / "state.yaml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


ROOT = discover_root()
AGENTS_DIR = ROOT / ".agents"
CODEX_DIR = ROOT / ".codex"


def project_module() -> Any:
    candidates = [
        Path(__file__).with_name("project.py"),
        ROOT / "template" / "tools" / "project.py",
    ]
    for path in candidates:
        if path.exists():
            spec = importlib.util.spec_from_file_location("agent_project", path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module
    raise AgentError("Cannot find tools/project.py. Restore project tooling first.")


project = project_module()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AgentError(f"{rel(path)} does not exist.")
    data = yaml_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AgentError(f"{rel(path)} must be a YAML mapping.")
    return data


def yaml_load(text: str) -> Any:
    if yaml is not None:
        return yaml.safe_load(text)
    return parse_yaml_subset(text)


def parse_yaml_value(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_yaml_value(part.strip()) for part in inner.split(",")]
    return value.strip('"').strip("'")


def parse_yaml_subset(text: str) -> Any:
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    def block(start: int, indent: int) -> tuple[Any, int]:
        container: Any = [] if start < len(lines) and lines[start].lstrip().startswith("- ") else {}
        index = start
        while index < len(lines):
            raw = lines[index]
            current_indent = len(raw) - len(raw.lstrip(" "))
            if current_indent < indent:
                break
            if current_indent > indent:
                raise AgentError(f"Unsupported YAML indentation near: {raw}")
            stripped = raw.strip()
            if isinstance(container, list):
                if not stripped.startswith("- "):
                    break
                item = stripped[2:].strip()
                if not item:
                    value, index = block(index + 1, indent + 2)
                    container.append(value)
                elif ":" in item and not item.startswith(("http://", "https://")):
                    key, _, value_text = item.partition(":")
                    mapping: dict[str, Any] = {key.strip(): parse_yaml_value(value_text)}
                    index += 1
                    container.append(mapping)
                else:
                    container.append(parse_yaml_value(item))
                    index += 1
                continue
            key, sep, value_text = stripped.partition(":")
            if not sep:
                raise AgentError(f"Invalid YAML line: {raw}")
            if value_text.strip():
                container[key.strip()] = parse_yaml_value(value_text)
                index += 1
            else:
                value, index = block(index + 1, indent + 2)
                container[key.strip()] = value
        return container, index

    parsed, _ = block(0, 0)
    return parsed


def skill_paths() -> list[Path]:
    return sorted((AGENTS_DIR / "skills").glob("*/SKILL.md"))


def split_skill_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AgentError(f"{rel(path)} is missing YAML frontmatter.")
    _, rest = text.split("---\n", 1)
    front, marker, body = rest.partition("\n---\n")
    if not marker:
        raise AgentError(f"{rel(path)} is missing closing YAML frontmatter marker.")
    data = yaml_load(front)
    if not isinstance(data, dict):
        raise AgentError(f"{rel(path)} frontmatter must be a mapping.")
    return data, body


def make_targets() -> set[str]:
    path = ROOT / "Makefile"
    if not path.exists():
        return set()
    targets: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("\t") or ":" not in line:
            continue
        name = line.split(":", 1)[0].strip()
        if name and " " not in name and not name.startswith("."):
            targets.add(name)
    return targets


def validate_agent_skills() -> list[str]:
    errors: list[str] = []
    if not AGENTS_DIR.exists():
        return [".agents/ does not exist. Restore the canonical agent layer."]
    targets = make_targets()
    paths = skill_paths()
    names: list[str] = []
    for required in sorted(REQUIRED_SKILLS):
        expected = AGENTS_DIR / "skills" / required / "SKILL.md"
        if not expected.exists():
            errors.append(f"Missing required skill {required}: create {rel(expected)}.")
    for path in paths:
        try:
            meta, body = split_skill_frontmatter(path)
        except AgentError as exc:
            errors.append(str(exc))
            continue
        missing = sorted(REQUIRED_SKILL_KEYS - set(meta))
        if missing:
            errors.append(f"{rel(path)} metadata missing keys: {', '.join(missing)}.")
        name = str(meta.get("name", ""))
        names.append(name)
        if name != path.parent.name:
            errors.append(f"{rel(path)} name must match directory name {path.parent.name}.")
        if meta.get("version") != 1:
            errors.append(f"{rel(path)} version must be 1.")
        for key in ["purpose", "triggers", "reads", "commands", "outputs", "stop_conditions"]:
            value = meta.get(key)
            if not value:
                errors.append(f"{rel(path)} metadata field {key} must not be empty.")
        boundary = meta.get("approval_boundary")
        if not isinstance(boundary, dict):
            errors.append(f"{rel(path)} approval_boundary must be a mapping.")
        elif boundary.get("may_approve") is not False:
            errors.append(f"{rel(path)} must set approval_boundary.may_approve: false.")
        for command in meta.get("commands", []) or []:
            if not isinstance(command, str):
                errors.append(f"{rel(path)} command entries must be strings.")
                continue
            if "task-approve" in command:
                errors.append(f"{rel(path)} must not reference make task-approve.")
            if command.startswith("make "):
                target = command.split()[1]
                if target not in targets:
                    errors.append(f"{rel(path)} references missing Make target {target}.")
        lowered = body.lower()
        if "approval_status: approved" in lowered or "approved_by:" in lowered:
            errors.append(f"{rel(path)} must not instruct agents to write approval metadata.")
        if "project/board.md" in lowered and "direct" in lowered and "edit" in lowered:
            errors.append(f"{rel(path)} must not recommend direct generated dashboard edits.")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        errors.append(f"Duplicate skill name {name}. Keep skill names unique.")
    errors.extend(validate_context_map())
    errors.extend(validate_codex_adapter())
    return errors


def validate_context_map() -> list[str]:
    errors: list[str] = []
    path = AGENTS_DIR / "context-map.yaml"
    try:
        data = read_yaml(path)
    except AgentError as exc:
        return [str(exc)]
    if data.get("schema_version") != 1:
        errors.append(".agents/context-map.yaml schema_version must be 1.")
    always = data.get("always")
    if not isinstance(always, list) or not always:
        errors.append(".agents/context-map.yaml always must be a non-empty list.")
    for required in always or []:
        if not isinstance(required, str):
            errors.append(".agents/context-map.yaml always entries must be strings.")
            continue
        if any(token in required for token in ["..", "~"]):
            errors.append(f"Context path {required} cannot traverse outside the project.")
            continue
        if not (ROOT / required).exists():
            errors.append(f"Required context file {required} does not exist.")
    if not isinstance(data.get("task"), dict):
        errors.append(".agents/context-map.yaml task must be a mapping.")
    if not isinstance(data.get("exclude"), list):
        errors.append(".agents/context-map.yaml exclude must be a list.")
    return errors


def validate_codex_adapter() -> list[str]:
    errors: list[str] = []
    if not CODEX_DIR.exists():
        return errors
    for path in sorted((CODEX_DIR / "skills").glob("*/SKILL.md")):
        try:
            meta, body = split_skill_frontmatter(path)
        except AgentError as exc:
            errors.append(str(exc))
            continue
        canonical = str(meta.get("canonical_skill", ""))
        if not canonical:
            errors.append(f"{rel(path)} must declare canonical_skill.")
            continue
        target = AGENTS_DIR / "skills" / canonical / "SKILL.md"
        if not target.exists():
            errors.append(f"{rel(path)} references missing canonical skill {canonical}.")
        if len(body.splitlines()) > 40:
            errors.append(f"{rel(path)} is too large for a thin adapter.")
    return errors


def fail_if_errors(errors: list[str]) -> None:
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)


def get_task(task_id: str | None) -> Any:
    tasks = project.load_tasks()
    tasks_by = project.task_by_id(tasks)
    selected = task_id or project.nonempty(project.read_state().get("work", {}).get("active_task"))
    if not selected:
        raise AgentError("No task selected and no active task exists. Pass TASK=<id>.")
    task = tasks_by.get(selected)
    if task is None:
        raise AgentError(f"Task {selected} does not exist.")
    return task


def excluded(path: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)
        for pattern in patterns
    )


def safe_project_path(pattern: str) -> Path:
    if any(token in pattern for token in ["..", "~"]) or Path(pattern).is_absolute():
        raise AgentError(f"Context path {pattern} cannot traverse outside the project.")
    return ROOT / pattern


def add_existing_file(files: list[str], seen: set[str], path: Path, excludes: list[str]) -> None:
    resolved = path.resolve()
    try:
        rel_path = resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise AgentError(f"Context path {path} resolves outside the project root.") from exc
    if excluded(rel_path, excludes) or excluded(rel_path, SENSITIVE_PATTERNS):
        raise AgentError(f"Sensitive or excluded file {rel_path} cannot be included in context.")
    if path.is_symlink():
        target = path.resolve()
        try:
            target.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise AgentError(f"Symlink {rel_path} resolves outside the project root.") from exc
    if path.is_file() and rel_path not in seen:
        files.append(rel_path)
        seen.add(rel_path)


def expand_context_pattern(pattern: str, *, required: bool, excludes: list[str]) -> list[str]:
    if "{task_id}" in pattern:
        raise AgentError("Internal error: unresolved {task_id} in context pattern.")
    base = safe_project_path(pattern)
    matches = sorted(ROOT.glob(pattern)) if any(ch in pattern for ch in "*?[") else [base]
    files: list[str] = []
    seen: set[str] = set()
    for match in matches:
        if match.is_dir():
            for file in sorted(p for p in match.rglob("*") if p.is_file()):
                add_existing_file(files, seen, file, excludes)
        elif match.exists():
            add_existing_file(files, seen, match, excludes)
    if required and not files:
        raise AgentError(f"Required context path {pattern} did not match an existing file.")
    return files


def changed_files() -> list[str]:
    return [path for _, path in changed_file_entries()]


def changed_file_entries() -> list[tuple[str, str]]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        entries.append((status, path))
    return sorted(entries, key=lambda item: item[1])


def recommended_checks(config: dict[str, Any], changes: list[str]) -> list[str]:
    checks: list[str] = []
    seen: set[str] = set()
    mapping = config.get("checks", {}) or {}
    for changed in changes:
        for pattern, commands in mapping.items():
            if fnmatch.fnmatch(changed, pattern):
                for command in commands or []:
                    if command not in seen:
                        checks.append(command)
                        seen.add(command)
    if not checks:
        checks.append("make check")
    for command in ["make validate-agent-skills", "make validate-project"]:
        if command not in seen:
            checks.append(command)
            seen.add(command)
    return checks


def resolve_context(task_id: str | None) -> dict[str, Any]:
    task = get_task(task_id)
    config = read_yaml(AGENTS_DIR / "context-map.yaml")
    errors = validate_context_map()
    if errors:
        raise AgentError(errors[0])
    excludes = list(dict.fromkeys([*DEFAULT_EXCLUDES, *(config.get("exclude") or [])]))
    files: list[str] = []
    seen: set[str] = set()
    for pattern in config.get("always", []):
        for item in expand_context_pattern(pattern, required=True, excludes=excludes):
            if item not in seen:
                files.append(item)
                seen.add(item)
    task_section = config.get("task", {}) or {}
    for pattern in task_section.get("include", []) or []:
        resolved_pattern = pattern.format(task_id=task.id)
        for item in expand_context_pattern(resolved_pattern, required=True, excludes=excludes):
            if item not in seen:
                files.append(item)
                seen.add(item)
    state = project.read_state()
    project_type = state.get("project", {}).get("type")
    runtime_level = state.get("project", {}).get("runtime_level")
    profile_keys = [str(project_type), f"{project_type}-{runtime_level}"]
    project_type_map = config.get("project_type", {}) or {}
    for key in profile_keys:
        for pattern in project_type_map.get(key, []) or []:
            for item in expand_context_pattern(pattern, required=False, excludes=excludes):
                if item not in seen:
                    files.append(item)
                    seen.add(item)
    changes = changed_files()
    for changed in changes:
        for pattern, includes in (config.get("change_patterns", {}) or {}).items():
            if fnmatch.fnmatch(changed, pattern):
                for include in includes or []:
                    for item in expand_context_pattern(include, required=False, excludes=excludes):
                        if item not in seen:
                            files.append(item)
                            seen.add(item)
    files = sorted(files)
    return {
        "task": {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "approval_level": task.approval_level,
            "approval_status": task.approval_status,
        },
        "stop_conditions": [
            "missing task",
            "blocked task",
            "unmet dependencies",
            "missing required approval",
            "invalid context map",
        ],
        "files": files,
        "recommended_checks": recommended_checks(config, changes),
        "next_action": project.recommended_next_action(state, project.load_tasks()),
    }


def agent_status() -> str:
    state = project.read_state()
    tasks = project.load_tasks()
    errors = project.validate_all(check_drift=False)
    if errors:
        return "\n".join(
            ["ERROR: Project state is invalid.", *errors, "Next action: make validate-project"]
        )
    active = project.find_active(tasks, state)
    next_action = project.recommended_next_action(state, tasks)
    lines = [
        f"Project: {state['project'].get('name', state['project'].get('type'))}",
        f"Phase: {state['lifecycle']['phase']}",
        f"Milestone: {state['lifecycle']['milestone']}",
        f"Active task: {active.id + ' - ' + active.title if active else 'None'}",
        f"Task status: {active.status if active else 'None'}",
        f"Approval: {active.approval_level + ' ' + active.approval_status if active else 'None'}",
        f"Blocked: {'yes' if state.get('work', {}).get('blocked') else 'no'}",
        f"Next action: {next_action}",
    ]
    if active:
        lines.append(f"Context: make agent-context TASK={active.id}")
    return "\n".join(lines)


def run_command(command: str) -> CommandResult:
    result = subprocess.run(
        command.split(),
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    return CommandResult(command=command, status=status, output=result.stdout.strip())


def pre_task(task_id: str) -> None:
    fail_if_errors(project.validate_all(check_drift=True))
    task = get_task(task_id)
    tasks_by = project.task_by_id(project.load_tasks())
    if task.status not in {"ready", "in-progress"}:
        raise AgentError(f"{task.id} must be ready or in-progress before pre-task.")
    if task.status == "blocked":
        raise AgentError(f"{task.id} is blocked: {task.blocked_reason}.")
    missing = project.definition_of_ready(task)
    if missing:
        raise AgentError(f"{task.id} Definition of Ready is incomplete: {', '.join(missing)}.")
    if not project.dependencies_done(task, tasks_by):
        raise AgentError(f"{task.id} cannot start until all dependencies are done.")
    if task.approval_level == "A2" and task.approval_status != "approved":
        raise AgentError(f"Human A2 approval is required for {task.id} before work starts.")
    active = project.nonempty(project.read_state().get("work", {}).get("active_task"))
    if active and active != task.id:
        raise AgentError(f"Another task is active: {active}.")
    resolve_context(task.id)
    print(f"Task {task.id} is ready for implementation.")
    print(
        f"Next action: make task-start TASK={task.id}"
        if task.status == "ready"
        else "Next action: implement the scoped change."
    )


def diff_safety_errors() -> list[str]:
    errors: list[str] = []
    for status, path in changed_file_entries():
        if excluded(path, SENSITIVE_PATTERNS):
            errors.append(f"Sensitive file appears in Git diff: {path}.")
        if excluded(path, BUILD_ARTIFACT_PATTERNS) and "D" not in status:
            errors.append(f"Build artifact appears in Git diff: {path}.")
    return errors


def pre_review(task_id: str) -> None:
    task = get_task(task_id)
    active = project.nonempty(project.read_state().get("work", {}).get("active_task"))
    if active != task.id:
        raise AgentError(
            f"Pre-review requires active task {task.id}; current active task is {active or 'None'}."
        )
    if task.status != "in-progress":
        raise AgentError(f"{task.id} must be in-progress before review preparation.")
    fail_if_errors(diff_safety_errors())
    fail_if_errors(validate_agent_skills())
    checks = [run_command("make check"), run_command("make validate-project")]
    failed = [check for check in checks if check.status != "PASS"]
    if failed:
        for check in failed:
            print(f"ERROR: {check.command} failed.")
            if check.output:
                print(check.output)
        raise SystemExit(1)
    print(f"Task {task.id} is ready for review.")
    print(f"Next action: make task-review TASK={task.id}")


def post_task(task_id: str) -> None:
    task = get_task(task_id)
    if task.status != "done":
        raise AgentError(f"Post-task requires {task.id} to be done.")
    missing = project.definition_of_done(task)
    if missing:
        raise AgentError(f"{task.id} Definition of Done is incomplete: {', '.join(missing)}.")
    if task.approval_level in {"A1", "A2"} and task.approval_status != "approved":
        raise AgentError(f"Human {task.approval_level} approval is required before post-task.")
    sync = run_command("make sync-project-docs")
    if sync.status != "PASS":
        print(sync.output)
        raise SystemExit(1)
    fail_if_errors(project.validate_all(check_drift=True))
    if project.nonempty(project.read_state().get("work", {}).get("active_task")):
        raise AgentError("No task may remain active after post-task.")
    print(f"Task {task.id} post-task checks passed.")
    next_action = project.recommended_next_action(project.read_state(), project.load_tasks())
    print(f"Next action: {next_action}")


def print_context(data: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    task = data["task"]
    print(f"Task: {task['id']} - {task['title']}")
    print(f"Status: {task['status']}")
    print(f"Approval: {task['approval_level']} {task['approval_status']}")
    print("Stop conditions:")
    for item in data["stop_conditions"]:
        print(f"- {item}")
    print("Recommended files:")
    for item in data["files"]:
        print(f"- {item}")
    print("Recommended checks:")
    for item in data["recommended_checks"]:
        print(f"- {item}")
    print(f"Next action: {data['next_action']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    context = sub.add_parser("context")
    context.add_argument("--task")
    context.add_argument("--format", choices=["text", "json"], default="text")
    sub.add_parser("validate-skills")
    for name in ["pre-task", "pre-review", "post-task"]:
        command = sub.add_parser(name)
        command.add_argument("--task", required=True)
    args = parser.parse_args()
    try:
        if args.command == "status":
            print(agent_status())
        elif args.command == "context":
            print_context(resolve_context(args.task), args.format)
        elif args.command == "validate-skills":
            fail_if_errors(validate_agent_skills())
            print("Agent skills are valid.")
        elif args.command == "pre-task":
            pre_task(args.task)
        elif args.command == "pre-review":
            pre_review(args.task)
        elif args.command == "post-task":
            post_task(args.task)
    except AgentError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
