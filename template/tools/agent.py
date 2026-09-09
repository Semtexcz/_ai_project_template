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


CORE_SKILLS = {
    "capture-learning",
    "conventional-commit",
    "create-adr",
    "implement-change",
    "orient-project",
    "review-change",
    "update-documentation",
    "verify-change",
}
MANAGED_SKILLS = {
    "assess-project-state",
    "choose-next-task",
    "complete-task",
    "prepare-task",
    "reassess-project",
}
CAPABILITY_SKILLS = {
    "fullstack": {"change-api-contract"},
    "production": {"verify-production-artifact"},
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
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high"}
CHEAP_MODELS = {"gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini"}
CONTEXT_SCHEMA_VERSION = 2
DEFAULT_CONTEXT_BUDGET = {"max_files": 20, "max_bytes": 120000}
# Context loading order. Task and selected-skill material are protected from
# budget truncation; exploratory profile files are loaded last.
CONTEXT_CATEGORY_PRIORITY = {
    "task": 0,
    "skill": 1,
    "bootstrap": 2,
    "changed": 3,
    "managed": 4,
    "change": 5,
    "profile": 6,
}


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


project: Any | None = None


def require_project_module() -> Any:
    global project
    if project is None:
        project = project_module()
    return project


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


def project_metadata() -> dict[str, str]:
    answers_path = ROOT / ".copier-answers.yml"
    if answers_path.exists():
        data = yaml_load(answers_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                "project_type": str(data.get("project_type", "")),
                "runtime_level": str(data.get("runtime_level", "")),
                "governance": str(data.get("governance", "")),
            }
    state_path = ROOT / "project" / "state.yaml"
    if state_path.exists():
        data = yaml_load(state_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            project_data = data.get("project")
            template_data = data.get("template")
            if isinstance(project_data, dict):
                return {
                    "project_type": str(project_data.get("type", "")),
                    "runtime_level": str(project_data.get("runtime_level", "")),
                    "governance": str(
                        template_data.get("governance", "managed")
                        if isinstance(template_data, dict)
                        else "managed"
                    ),
                }
    return {"project_type": "", "runtime_level": "", "governance": "lightweight"}


def skill_roots() -> list[Path]:
    roots = [
        AGENTS_DIR / "skills",
        AGENTS_DIR / "managed" / "skills",
        AGENTS_DIR / "capabilities" / "skills",
    ]
    return [root for root in roots if root.exists()]


def skill_paths() -> list[Path]:
    paths: list[Path] = []
    for root in skill_roots():
        paths.extend(root.glob("*/SKILL.md"))
    return sorted(paths)


def canonical_skill_path(skill_name: str) -> Path | None:
    for root in skill_roots():
        candidate = root / skill_name / "SKILL.md"
        if candidate.exists():
            return candidate
    return None


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


def template_make_targets() -> set[str]:
    path = ROOT / "template" / "Makefile.jinja"
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


def context_source_exists(path_text: str) -> bool:
    path = ROOT / path_text
    template_path = ROOT / "template" / path_text
    return path.exists() or template_path.exists() or Path(f"{template_path}.jinja").exists()


def validate_agent_skills() -> list[str]:
    errors: list[str] = []
    if not AGENTS_DIR.exists():
        return [".agents/ does not exist. Restore the canonical agent layer."]
    metadata = project_metadata()
    governance = metadata["governance"]
    project_type = metadata["project_type"]
    runtime_level = metadata["runtime_level"]
    targets = make_targets() | template_make_targets()
    paths = skill_paths()
    names: list[str] = []
    required_skills = set(CORE_SKILLS)
    if governance == "managed":
        required_skills.update(MANAGED_SKILLS)
    required_skills.update(CAPABILITY_SKILLS.get(project_type, set()))
    required_skills.update(CAPABILITY_SKILLS.get(runtime_level, set()))
    for required in sorted(required_skills):
        expected = canonical_skill_path(required)
        if expected is None:
            expected_path = AGENTS_DIR / "skills" / required / "SKILL.md"
            errors.append(f"Missing required skill {required}: create {rel(expected_path)}.")
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
        for key in [
            "purpose",
            "triggers",
            "reads",
            "commands",
            "outputs",
            "stop_conditions",
        ]:
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
        errors.extend(validate_skill_bundle(path.parent, name))
    if governance != "managed":
        for managed in sorted(MANAGED_SKILLS):
            if canonical_skill_path(managed) is not None:
                errors.append(
                    f"Managed-only skill {managed} must not render in lightweight projects."
                )
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
    if data.get("schema_version") != CONTEXT_SCHEMA_VERSION:
        errors.append(
            f".agents/context-map.yaml schema_version must be {CONTEXT_SCHEMA_VERSION}. "
            "Schema v2 separates explicit files from search_roots and adds a budget."
        )
    if not isinstance(data.get("exclude"), list):
        errors.append(".agents/context-map.yaml exclude must be a list.")

    def validate_file_entries(section: str, entries: Any, *, required: bool) -> None:
        if not isinstance(entries, list):
            errors.append(f".agents/context-map.yaml {section} must be a list.")
            return
        if required and not entries:
            errors.append(f".agents/context-map.yaml {section} must be a non-empty list.")
        for entry in entries:
            if not isinstance(entry, str):
                errors.append(f".agents/context-map.yaml {section} entries must be strings.")
                continue
            if any(token in entry for token in ["..", "~"]):
                errors.append(f"Context path {entry} cannot traverse outside the project.")
                continue
            if any(ch in entry for ch in "*?["):
                continue  # wildcard entries are expanded deterministically later
            base = ROOT / entry
            if base.is_dir():
                errors.append(
                    f"Context path {entry} is a directory; directories belong under "
                    "search_roots and are never recursively loaded."
                )
                continue
            if required and not context_source_exists(entry):
                errors.append(f"Required context file {entry} does not exist.")

    bootstrap = data.get("bootstrap")
    if not isinstance(bootstrap, dict) or not isinstance(bootstrap.get("files"), list):
        errors.append(".agents/context-map.yaml bootstrap.files must be a list.")
    else:
        validate_file_entries("bootstrap.files", bootstrap.get("files"), required=True)
    if not isinstance(data.get("task"), dict):
        errors.append(".agents/context-map.yaml task must be a mapping.")
    else:
        validate_file_entries("task.files", data["task"].get("files"), required=True)
    managed = data.get("managed") or {}
    if isinstance(managed, dict):
        validate_file_entries("managed.files", managed.get("files"), required=False)
    budget = data.get("budget") or {}
    if isinstance(budget, dict):
        for key in ["max_files", "max_bytes"]:
            value = budget.get(key)
            if value is not None and (not isinstance(value, int) or value < 1):
                errors.append(f".agents/context-map.yaml budget.{key} must be a positive integer.")
    project_type = data.get("project_type") or {}
    if isinstance(project_type, dict):
        for profile, entry in project_type.items():
            if not isinstance(entry, dict):
                errors.append(f".agents/context-map.yaml project_type.{profile} must be a mapping.")
                continue
            validate_file_entries(
                f"project_type.{profile}.files", entry.get("files"), required=False
            )
    change_patterns = data.get("change_patterns") or {}
    if isinstance(change_patterns, dict):
        for pattern, entry in change_patterns.items():
            if not isinstance(entry, dict):
                errors.append(
                    f".agents/context-map.yaml change_patterns.{pattern} must be a mapping "
                    "with files and search_roots."
                )
                continue
            validate_file_entries(
                f"change_patterns.{pattern}.files", entry.get("files"), required=False
            )
    checks = data.get("checks") or {}
    if isinstance(checks, dict):
        for pattern, commands in checks.items():
            if not isinstance(commands, list) or not all(
                isinstance(command, str) for command in commands
            ):
                errors.append(
                    f".agents/context-map.yaml checks.{pattern} must be a list of commands."
                )
    return errors


def validate_openai_metadata(path: Path, skill_name: str) -> list[str]:
    errors: list[str] = []
    try:
        data = read_yaml(path)
    except AgentError as exc:
        return [str(exc)]
    interface = data.get("interface")
    if not isinstance(interface, dict):
        return [f"{rel(path)} interface must be a mapping."]
    for key in ["display_name", "short_description", "default_prompt"]:
        value = interface.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{rel(path)} interface.{key} must be a non-empty string.")
    short_description = interface.get("short_description")
    if isinstance(short_description, str) and not 25 <= len(short_description) <= 64:
        errors.append(f"{rel(path)} interface.short_description must be 25-64 characters.")
    default_prompt = interface.get("default_prompt")
    if isinstance(default_prompt, str) and f"${skill_name}" not in default_prompt:
        errors.append(f"{rel(path)} interface.default_prompt must mention ${skill_name}.")
    policy = data.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append(f"{rel(path)} policy must be a mapping when present.")
        elif "allow_implicit_invocation" in policy and not isinstance(
            policy["allow_implicit_invocation"], bool
        ):
            errors.append(f"{rel(path)} policy.allow_implicit_invocation must be boolean.")
    return errors


def validate_model_metadata(path: Path, skill_name: str) -> list[str]:
    errors: list[str] = []
    try:
        data = read_yaml(path)
    except AgentError as exc:
        return [str(exc)]
    model = data.get("model")
    if not isinstance(model, str) or not model.strip():
        errors.append(f"{rel(path)} model must be a non-empty string.")
    elif skill_name == "conventional-commit" and model not in CHEAP_MODELS:
        cheap_models = ", ".join(sorted(CHEAP_MODELS))
        errors.append(f"{rel(path)} must use a cheap model: {cheap_models}.")
    reasoning_effort = data.get("reasoning_effort")
    if reasoning_effort is not None and reasoning_effort not in ALLOWED_REASONING_EFFORTS:
        efforts = ", ".join(sorted(ALLOWED_REASONING_EFFORTS))
        errors.append(f"{rel(path)} reasoning_effort must be one of: {efforts}.")
    validator = data.get("deterministic_validator")
    if validator is None:
        errors.append(f"{rel(path)} deterministic_validator must be declared.")
    elif not isinstance(validator, str) or not validator.strip():
        errors.append(f"{rel(path)} deterministic_validator must be a non-empty string.")
    else:
        validator_path = path.parent.parent / validator
        if not validator_path.exists():
            errors.append(f"{rel(path)} references missing deterministic validator {validator}.")
    return errors


def validate_conventional_commit_validator(script_path: Path) -> list[str]:
    errors: list[str] = []
    valid = subprocess.run(
        [sys.executable, str(script_path), "--message", "feat(agent): add validator"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if valid.returncode != 0:
        output = f"{valid.stdout}{valid.stderr}".strip()
        errors.append(
            f"{rel(script_path)} must accept a valid conventional commit message. {output}"
        )
    invalid = subprocess.run(
        [sys.executable, str(script_path), "--message", "bad message"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if invalid.returncode == 0:
        errors.append(f"{rel(script_path)} must reject an invalid conventional commit message.")
    return errors


def validate_skill_bundle(skill_dir: Path, skill_name: str) -> list[str]:
    errors: list[str] = []
    agents_dir = skill_dir / "agents"
    scripts_dir = skill_dir / "scripts"
    openai_path = agents_dir / "openai.yaml"
    model_path = agents_dir / "model.yaml"
    if openai_path.exists():
        errors.extend(validate_openai_metadata(openai_path, skill_name))
    if model_path.exists():
        errors.extend(validate_model_metadata(model_path, skill_name))
    if skill_name == "conventional-commit":
        if not openai_path.exists():
            errors.append(f"Missing required skill metadata {rel(openai_path)}.")
        if not model_path.exists():
            errors.append(f"Missing required skill metadata {rel(model_path)}.")
        script_path = scripts_dir / "validate_commit_message.py"
        if not script_path.exists():
            errors.append(f"Missing required deterministic validator {rel(script_path)}.")
        else:
            errors.extend(validate_conventional_commit_validator(script_path))
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
        target = canonical_skill_path(canonical)
        if target is None:
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
    managed_project = require_project_module()
    tasks = managed_project.load_tasks()
    tasks_by = managed_project.task_by_id(tasks)
    selected = task_id or managed_project.nonempty(
        managed_project.read_state().get("work", {}).get("active_task")
    )
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


def expand_file_pattern(pattern: str, *, required: bool, excludes: list[str]) -> list[str]:
    """Expand one explicit context-map file entry to existing file paths.

    A literal directory is never recursively expanded: directories belong under
    ``search_roots`` and are reported as searchable instead of loaded. Wildcard
    matches that resolve to directories are skipped for the same reason.
    """
    if "{task_id}" in pattern:
        raise AgentError("Internal error: unresolved {task_id} in context pattern.")
    base = safe_project_path(pattern)
    is_glob = any(ch in pattern for ch in "*?[")
    if not is_glob:
        if base.is_dir():
            return []
        if not base.exists():
            if required:
                raise AgentError(f"Required context file {pattern} does not exist.")
            return []
        files: list[str] = []
        add_existing_file(files, set(), base, excludes)
        return files
    files = []
    seen: set[str] = set()
    for match in sorted(ROOT.glob(pattern)):
        if match.is_dir():
            continue
        if match.exists():
            add_existing_file(files, seen, match, excludes)
    if required and not files:
        raise AgentError(f"Required context path {pattern} did not match an existing file.")
    return files


def git_stdout_lines(args: list[str]) -> list[str]:
    """Run a read-only git command and return its stdout lines, or [] on any
    failure (including repositories without Git or without a configured remote)."""
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
        return []
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def git_base_commit() -> str | None:
    """Return the merge-base commit used for branch-aware diffs.

    Prefers a remote-tracking main; falls back to local main/master and then to
    the upstream of the current branch. Returns None when no base exists so the
    caller degrades to working-tree-only change detection.
    """
    for ref in ["origin/main", "origin/master", "main", "master"]:
        if not git_stdout_lines(["rev-parse", "--verify", "--quiet", ref]):
            continue
        merge_base = git_stdout_lines(["merge-base", "HEAD", ref])
        if merge_base and merge_base[0].strip():
            return merge_base[0].strip()
    upstream = git_stdout_lines(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    )
    if upstream and upstream[0].strip():
        base = git_stdout_lines(["merge-base", "HEAD", upstream[0].strip()])
        if base and base[0].strip():
            return base[0].strip()
    return None


def _parse_name_status(lines: list[str]) -> list[tuple[str, bool]]:
    """Parse ``git diff --name-status`` output into (path, deleted) entries."""
    entries: list[tuple[str, bool]] = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        path = parts[-1].strip()
        if path:
            entries.append((path, parts[0].startswith("D")))
    return entries


def changed_file_entries() -> list[tuple[str, str]]:
    """Return deterministic (source, path) entries for the complete branch/PR
    change set: committed branch changes + staged + unstaged + untracked.

    The union is stable after commits: a clean worktree on a feature branch
    still reports the branch's committed changes against the base.
    """
    base = git_base_commit()
    merged: dict[str, tuple[str, bool]] = {}

    def add(source: str, path: str, deleted: bool) -> None:
        if path not in merged:
            merged[path] = (source, deleted)

    if base is not None:
        for path, deleted in _parse_name_status(
            git_stdout_lines(["diff", "--name-status", base, "HEAD"])
        ):
            add("branch", path, deleted)
    for path, deleted in _parse_name_status(
        git_stdout_lines(["diff", "--cached", "--name-status"])
    ):
        add("staged", path, deleted)
    for path, deleted in _parse_name_status(git_stdout_lines(["diff", "--name-status"])):
        add("worktree", path, deleted)
    for path in git_stdout_lines(["ls-files", "--others", "--exclude-standard"]):
        if path.strip():
            add("untracked", path.strip(), False)
    return sorted(
        ((source, path) for path, (source, _deleted) in merged.items()),
        key=lambda item: item[1],
    )


def deleted_changed_files() -> set[str]:
    deleted: set[str] = set()
    base = git_base_commit()
    if base is not None:
        for path, is_deleted in _parse_name_status(
            git_stdout_lines(["diff", "--name-status", base, "HEAD"])
        ):
            if is_deleted:
                deleted.add(path)
    for path, is_deleted in _parse_name_status(
        git_stdout_lines(["diff", "--cached", "--name-status"])
    ):
        if is_deleted:
            deleted.add(path)
    for path, is_deleted in _parse_name_status(git_stdout_lines(["diff", "--name-status"])):
        if is_deleted:
            deleted.add(path)
    return deleted


def changed_files() -> list[str]:
    return [path for _, path in changed_file_entries()]


def _existing_make_commands(commands: list[str]) -> list[str]:
    """Keep commands whose Make target actually exists in this repository."""
    targets = make_targets() | template_make_targets()
    kept: list[str] = []
    for command in commands:
        if not command.startswith("make "):
            kept.append(command)
            continue
        parts = command.split()
        if len(parts) > 1 and parts[1] in targets:
            kept.append(command)
    return kept


def _change_categories(changes: list[str]) -> set[str]:
    """Small deterministic classifier used only when the context-map checks
    mapping does not match a changed path."""
    categories: set[str] = set()
    for path in changes:
        normalized = path.replace("\\", "/")
        if normalized.startswith(".agents/") or normalized.startswith(".codex/"):
            categories.add("skills")
        if normalized.startswith("project/"):
            categories.add("project")
        if (
            normalized.startswith("docs/")
            or normalized.endswith(".md")
            or normalized in {"README.md", "AGENTS.md"}
        ):
            categories.add("docs")
        if normalized.startswith("template/"):
            categories.add("template")
        if normalized.startswith("tests/"):
            categories.add("tests")
        if normalized.startswith("src/") or normalized.endswith(".py"):
            categories.add("python")
        if normalized.startswith("frontend/"):
            categories.add("frontend")
        if normalized.endswith("Dockerfile"):
            categories.add("docker")
        if normalized in {"Makefile", "copier.yml"} or normalized.startswith("tools/"):
            categories.add("tooling")
    return categories


def _focused_commands(categories: set[str]) -> list[str]:
    """Focused fallback checks; the rule set stays small on purpose."""
    commands: list[str] = []
    if "skills" in categories:
        commands.append("make validate-agent-skills")
    if categories == {"docs"}:
        for candidate in ["make validate-template-docs", "make validate-docs"]:
            commands.append(candidate)
    if categories == {"project"}:
        commands.append("make validate-project")
    if not commands and categories:
        commands.append("make check")
    return commands


def recommended_checks(config: dict[str, Any], changes: list[str]) -> list[str]:
    """Return focused validation commands for the actual changed-file set.

    ``make check`` is the canonical final full gate; an empty change set (no
    committed branch diff and no working-tree changes yet) simply defers to it.
    """
    if not changes:
        return _existing_make_commands(["make check"])
    mapping = config.get("checks", {}) or {}
    matched: list[str] = []
    seen: set[str] = set()
    for changed in changes:
        for pattern, commands in mapping.items():
            if fnmatch.fnmatch(changed, pattern):
                for command in commands or []:
                    if command not in seen:
                        matched.append(command)
                        seen.add(command)
    categories = _change_categories(changes)
    if not matched:
        matched = _focused_commands(categories)
    metadata = project_metadata()
    required: list[str] = []
    if "skills" in categories:
        required.append("make validate-agent-skills")
    if metadata.get("governance") == "managed" and "project" in categories:
        required.append("make validate-project")
    checks = [*matched, *[command for command in required if command not in seen]]
    if not checks:
        checks.append("make check")
    return _existing_make_commands(checks)


def resolve_context(
    task_id: str | None, skill: str | None = None, mode: str = "new"
) -> dict[str, Any]:
    """Resolve the deterministic context bundle for the selected task.

    ``mode="resume"`` keeps the bundle small for review/fix work on an existing
    PR: profile exploratory files are not eagerly loaded and the branch diff
    carries the affected-file context.
    """
    managed_project = require_project_module()
    task = get_task(task_id)
    config = read_yaml(AGENTS_DIR / "context-map.yaml")
    errors = validate_context_map()
    if errors:
        raise AgentError(errors[0])
    excludes = list(dict.fromkeys([*DEFAULT_EXCLUDES, *(config.get("exclude") or [])]))
    budget = config.get("budget") or {}
    max_files = int(budget.get("max_files", DEFAULT_CONTEXT_BUDGET["max_files"]))
    max_bytes = int(budget.get("max_bytes", DEFAULT_CONTEXT_BUDGET["max_bytes"]))
    selected_skill, skill_files, skill_roots = resolve_skill_context(skill)
    state = managed_project.read_state()
    project_type = str(state.get("project", {}).get("type", ""))
    runtime_level = str(state.get("project", {}).get("runtime_level", ""))
    changes = changed_files()
    deleted = deleted_changed_files()
    candidates, search_roots, changed_omitted = collect_context_candidates(
        task=task,
        config=config,
        excludes=excludes,
        skill_files=skill_files,
        skill_roots=skill_roots,
        mode=mode,
        changes=changes,
        deleted=deleted,
        project_type=project_type,
        runtime_level=runtime_level,
    )
    included, omitted, total_bytes = select_budgeted(candidates, max_files, max_bytes)
    omitted.extend(changed_omitted)
    reason = (
        "Tier 1 resume/fix context: task, skill, branch diff, and affected "
        "files without full project re-orientation"
        if mode == "resume"
        else "Tier 1 new-task context: task, skill reads, bootstrap, changed "
        "files, and narrow configuration"
    )
    return {
        "mode": mode,
        "reason": reason,
        "skill": selected_skill,
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
        "files": [item["path"] for item in included],
        "files_included": included,
        "search_roots": sorted(search_roots),
        "changed_files": sorted(changes),
        "deleted_files": sorted(deleted),
        "recommended_checks": recommended_checks(config, sorted(changes)),
        "budget": {"max_files": max_files, "max_bytes": max_bytes},
        "total_bytes": total_bytes,
        "omitted": omitted,
        "next_action": managed_project.recommended_next_action(state, managed_project.load_tasks()),
    }


def resolve_skill_context(
    skill_name: str | None,
) -> tuple[str | None, list[str], list[str]]:
    """Resolve a selected skill to (name, explicit read files, search roots).

    The skill's ``reads:`` metadata becomes deterministic routing information.
    Unknown skills fail clearly; missing read files degrade safely; directories
    become search roots and are never recursively loaded.
    """
    if not skill_name:
        return None, [], []
    path = canonical_skill_path(skill_name)
    if path is None:
        available = sorted(path.parent.name for path in skill_paths())
        raise AgentError(
            f"Skill {skill_name} does not exist. Available skills: {', '.join(available)}."
        )
    try:
        meta, _body = split_skill_frontmatter(path)
    except AgentError as exc:
        raise AgentError(f"Cannot load skill {skill_name}: {exc}") from exc
    reads = meta.get("reads")
    if not isinstance(reads, list):
        raise AgentError(f"Skill {skill_name} must declare reads as a list for context routing.")
    explicit: set[str] = set()
    roots: set[str] = set()
    for entry in reads:
        if not isinstance(entry, str) or not entry.strip() or "{{" in entry:
            continue  # templated/empty read entries cannot be resolved eagerly
        pattern = entry.strip()
        if any(token in pattern for token in ["..", "~"]) or Path(pattern).is_absolute():
            raise AgentError(f"Skill read {pattern} cannot traverse outside the project.")
        base = ROOT / pattern
        if any(ch in pattern for ch in "*?["):
            for match in sorted(ROOT.glob(pattern)):
                if match.is_dir():
                    roots.add(match.relative_to(ROOT).as_posix())
                elif match.is_file():
                    explicit.add(match.relative_to(ROOT).as_posix())
        elif base.is_dir():
            roots.add(pattern)
        elif base.exists():
            explicit.add(pattern)
    return skill_name, sorted(explicit), sorted(roots)


def collect_context_candidates(
    *,
    task: Any,
    config: dict[str, Any],
    excludes: list[str],
    skill_files: list[str],
    skill_roots: list[str],
    mode: str,
    changes: list[str],
    deleted: set[str],
    project_type: str,
    runtime_level: str,
) -> tuple[list[tuple[int, str, str, bool]], set[str], list[dict[str, str]]]:
    """Collect deterministic (priority, category, path, protected) candidates,
    available search roots, and changed files that were excluded from loading."""
    candidates: list[tuple[int, str, str, bool]] = []
    roots: set[str] = set()
    changed_omitted: list[dict[str, str]] = []

    def add_files(
        category: str,
        patterns: list[str],
        *,
        protected: bool = False,
        required: bool = False,
    ) -> None:
        priority = CONTEXT_CATEGORY_PRIORITY[category]
        for pattern in patterns or []:
            for path in expand_file_pattern(pattern, required=required, excludes=excludes):
                candidates.append((priority, category, path, protected))

    def add_roots(patterns: list[str]) -> None:
        for pattern in patterns or []:
            normalized = (pattern or "").rstrip("/")
            if normalized:
                roots.add(normalized)

    task_patterns = [
        pattern.format(task_id=task.id)
        for pattern in (config.get("task", {}) or {}).get("files", []) or []
    ]
    add_files("task", task_patterns, protected=True, required=True)
    add_files("skill", skill_files, protected=True)
    bootstrap = config.get("bootstrap", {}) or {}
    add_files("bootstrap", bootstrap.get("files", []) or [], protected=True, required=True)
    for changed in sorted(changes):
        if changed in deleted:
            continue
        resolved = (ROOT / changed).resolve()
        try:
            rel_path = resolved.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            continue
        if excluded(rel_path, excludes) or excluded(rel_path, SENSITIVE_PATTERNS):
            changed_omitted.append({"path": rel_path, "category": "changed", "reason": "excluded"})
            continue
        if resolved.is_file():
            candidates.append((CONTEXT_CATEGORY_PRIORITY["changed"], "changed", rel_path, False))
    managed = config.get("managed") or {}
    add_files("managed", managed.get("files", []) or [])
    change_patterns = config.get("change_patterns", {}) or {}
    for changed in changes:
        for pattern, mapping in change_patterns.items():
            if not isinstance(mapping, dict) or not fnmatch.fnmatch(changed, pattern):
                continue
            add_files("change", mapping.get("files", []) or [])
            add_roots(mapping.get("search_roots", []) or [])
    profile_map = config.get("project_type", {}) or {}
    for key in [project_type, f"{project_type}-{runtime_level}"]:
        entry = profile_map.get(key)
        if not isinstance(entry, dict):
            continue
        if mode != "resume":
            add_files("profile", entry.get("files", []) or [])
        add_roots(entry.get("search_roots", []) or [])
    add_roots(skill_roots)
    return candidates, roots, changed_omitted


def select_budgeted(
    candidates: list[tuple[int, str, str, bool]], max_files: int, max_bytes: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Apply deterministic file/byte budgets.

    Protected task/skill/bootstrap candidates are always included; if they do
    not fit, generation fails loudly instead of silently dropping them. Every
    other candidate is included in deterministic priority order until a budget
    is exhausted and is then reported as omitted.
    """
    by_path: dict[str, tuple[int, str, bool]] = {}
    for priority, category, path, protected in candidates:
        if path in by_path:
            old_priority, _old_category, old_protected = by_path[path]
            if priority < old_priority or (protected and not old_protected):
                by_path[path] = (priority, category, protected or old_protected)
            continue
        by_path[path] = (priority, category, protected)
    ordered = sorted(by_path.items(), key=lambda item: (item[1][0], item[0]))
    protected_paths = [
        (path, category) for path, (_priority, category, is_protected) in ordered if is_protected
    ]
    if len(protected_paths) > max_files:
        raise AgentError(
            f"Required task/skill/bootstrap context needs {len(protected_paths)} files "
            f"but budget.max_files is {max_files}. Raise the context budget."
        )
    core_bytes = sum((ROOT / path).stat().st_size for path, _category in protected_paths)
    if core_bytes > max_bytes:
        raise AgentError(
            f"Required task/skill/bootstrap context needs {core_bytes} bytes "
            f"but budget.max_bytes is {max_bytes}. Raise the context budget."
        )
    included: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    included_paths: set[str] = set()
    total_bytes = 0

    def include(path: str, category: str) -> None:
        nonlocal total_bytes
        size = (ROOT / path).stat().st_size
        included.append({"path": path, "category": category, "bytes": size})
        included_paths.add(path)
        total_bytes += size

    for path, category in protected_paths:
        include(path, category)
    for path, (_priority, category, is_protected) in ordered:
        if path in included_paths or is_protected:
            continue
        size = (ROOT / path).stat().st_size
        if len(included) >= max_files:
            omitted.append({"path": path, "category": category, "reason": "file budget"})
            continue
        if total_bytes + size > max_bytes:
            omitted.append({"path": path, "category": category, "reason": "byte budget"})
            continue
        include(path, category)
    return included, omitted, total_bytes


def agent_status() -> str:
    managed_project = require_project_module()
    state = managed_project.read_state()
    tasks = managed_project.load_tasks()
    errors = managed_project.validate_all(check_drift=False)
    if errors:
        return "\n".join(
            [
                "ERROR: Project state is invalid.",
                *errors,
                "Next action: make validate-project",
            ]
        )
    active = managed_project.find_active(tasks, state)
    next_action = managed_project.recommended_next_action(state, tasks)
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
    managed_project = require_project_module()
    fail_if_errors(managed_project.validate_all(check_drift=True))
    task = get_task(task_id)
    tasks_by = managed_project.task_by_id(managed_project.load_tasks())
    if task.status not in {"ready", "in-progress"}:
        raise AgentError(f"{task.id} must be ready or in-progress before pre-task.")
    if task.status == "blocked":
        raise AgentError(f"{task.id} is blocked: {task.blocked_reason}.")
    missing = managed_project.definition_of_ready(task)
    if missing:
        raise AgentError(f"{task.id} Definition of Ready is incomplete: {', '.join(missing)}.")
    if not managed_project.dependencies_done(task, tasks_by):
        raise AgentError(f"{task.id} cannot start until all dependencies are done.")
    if task.approval_level == "A2" and task.approval_status != "approved":
        raise AgentError(f"Human A2 approval is required for {task.id} before work starts.")
    active = managed_project.nonempty(
        managed_project.read_state().get("work", {}).get("active_task")
    )
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
    deleted = deleted_changed_files()
    for _status, path in changed_file_entries():
        if excluded(path, SENSITIVE_PATTERNS):
            errors.append(f"Sensitive file appears in Git diff: {path}.")
        if excluded(path, BUILD_ARTIFACT_PATTERNS) and path not in deleted:
            errors.append(f"Build artifact appears in Git diff: {path}.")
    return errors


def pre_review(task_id: str) -> None:
    managed_project = require_project_module()
    task = get_task(task_id)
    active = managed_project.nonempty(
        managed_project.read_state().get("work", {}).get("active_task")
    )
    if active != task.id:
        raise AgentError(
            f"Pre-review requires active task {task.id}; current active task is {active or 'None'}."
        )
    if task.status != "in-progress":
        raise AgentError(f"{task.id} must be in-progress before review preparation.")
    fail_if_errors(diff_safety_errors())
    checks = [run_command("make check")]
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
    managed_project = require_project_module()
    task = get_task(task_id)
    if task.status != "done":
        raise AgentError(f"Post-task requires {task.id} to be done.")
    missing = managed_project.definition_of_done(task)
    if missing:
        raise AgentError(f"{task.id} Definition of Done is incomplete: {', '.join(missing)}.")
    if task.approval_level in {"A1", "A2"} and task.approval_status != "approved":
        raise AgentError(f"Human {task.approval_level} approval is required before post-task.")
    sync = run_command("make sync-project-docs")
    if sync.status != "PASS":
        print(sync.output)
        raise SystemExit(1)
    fail_if_errors(managed_project.validate_all(check_drift=True))
    if managed_project.nonempty(managed_project.read_state().get("work", {}).get("active_task")):
        raise AgentError("No task may remain active after post-task.")
    print(f"Task {task.id} post-task checks passed.")
    next_action = managed_project.recommended_next_action(
        managed_project.read_state(), managed_project.load_tasks()
    )
    print(f"Next action: {next_action}")


def print_context(data: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    task = data["task"]
    budget = data.get("budget", {})
    included = data.get("files_included", [])
    omitted = data.get("omitted", [])
    print(f"Mode: {data.get('mode', 'new')}")
    print(f"Reason: {data.get('reason', '')}")
    print(f"Task: {task['id']} - {task['title']}")
    print(f"Status: {task['status']}")
    print(f"Approval: {task['approval_level']} {task['approval_status']}")
    print(f"Skill: {data.get('skill') or '(none)'}")
    if data.get("changed_files"):
        print(f"Changed files ({len(data['changed_files'])}):")
        for item in data["changed_files"]:
            print(f"- {item}")
    print(
        f"Files included ({len(included)}/{budget.get('max_files', '?')}, "
        f"{data.get('total_bytes', 0)}/{budget.get('max_bytes', '?')} bytes):"
    )
    for item in included:
        print(f"- ({item['category']}) {item['path']} ({item['bytes']} bytes)")
    if omitted:
        print(f"Omitted ({len(omitted)}):")
        for item in omitted:
            print(
                f"- ({item['category']}) {item['path']} [reason: {item.get('reason', 'unknown')}]"
            )
    if data.get("search_roots"):
        print(f"Search roots available ({len(data['search_roots'])}):")
        for item in data["search_roots"]:
            print(f"- {item}/")
    print("Recommended checks:")
    for item in data.get("recommended_checks", []):
        print(f"- {item}")
    print(f"Next action: {data['next_action']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    context = sub.add_parser("context")
    context.add_argument("--task")
    context.add_argument("--skill")
    context.add_argument("--mode", choices=["new", "resume"], default="new")
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
            print_context(
                resolve_context(args.task, skill=args.skill, mode=args.mode),
                args.format,
            )
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
