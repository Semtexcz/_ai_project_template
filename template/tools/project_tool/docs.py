"""Documentation validation: required docs, links, commands, hygiene, drift.

Kept separate from project/task lifecycle validation because these checks are
about the Markdown surface (entry documents, navigation, documented `make`
targets, text hygiene, profile wording, and persisted dashboard drift).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_tool.model import ROOT, ProjectError, Task, relative
from project_tool.rendering import (
    PERSISTED_STATUS_ROWS,
    TASK_DERIVED_STATUS_ROWS,
    persisted_status_block,
)
from project_tool.storage import (
    STATE_END,
    STATE_START,
    extract_block,
    normalize_block,
    read_state,
)

TASK_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
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


def markdown_files() -> list[Path]:
    """Markdown files that participate in documentation validation."""
    roots = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "project", ROOT / "docs"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.exists():
            files.extend(sorted(root.rglob("*.md")))
    return files


def make_targets() -> set[str]:
    """Targets declared by the project Makefile."""
    makefile = ROOT / "Makefile"
    if not makefile.exists():
        return set()
    return set(MAKE_TARGET_RE.findall(makefile.read_text(encoding="utf-8")))


def documented_make_commands() -> list[tuple[Path, int, str]]:
    """Documented ``make <target>`` usages with file and line provenance."""
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
    """Validate the documentation surface appropriate to this project type."""
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
    """Check that required entry documents exist and are linked from README."""
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
    """Check that every documented `make <target>` exists in the Makefile."""
    targets = make_targets()
    errors: list[str] = []
    for path, lineno, target in documented_make_commands():
        if target not in targets:
            errors.append(
                f"{relative(path)}:{lineno}: documented command 'make {target}' "
                "has no Makefile target."
            )
    return errors


def validate_doc_text_hygiene() -> list[str]:
    """Reject unrendered Jinja, personal paths, and stale example paths."""
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


def validate_profile_documentation(state: dict[str, Any]) -> list[str]:
    """Check that documentation describes the selected project profile only."""
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


def validate_readme_dashboard(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    """Check that the committed README status block is the project-global view."""
    errors: list[str] = []
    try:
        dashboard = extract_block(ROOT / "README.md", STATE_START, STATE_END)
    except ProjectError as exc:
        return [str(exc)]
    for row in PERSISTED_STATUS_ROWS:
        if f"| {row} |" not in dashboard:
            errors.append(f"README.md dashboard is missing '{row}'. Run: make sync-project-docs")
    # Committed status may contain only project-global facts. Task-derived rows
    # change on every transition, so committing them would make parallel task
    # branches conflict; they are rendered at read time by `make project-status`.
    for row in TASK_DERIVED_STATUS_ROWS:
        if f"| {row} |" in dashboard:
            errors.append(
                f"README.md dashboard must not persist the task-derived row '{row}'. "
                "Run: make sync-project-docs; live status is rendered by make project-status."
            )
    return errors


def validate_doc_drift(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    """Check that the README persisted status block is not stale."""
    expected = {
        ROOT / "README.md": (STATE_START, STATE_END, persisted_status_block(state)),
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


def validate_markdown_links() -> list[str]:
    """Reject broken relative Markdown links in validated documentation."""
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
                        f"{relative(path)}:{lineno}: broken internal Markdown link target "
                        f"'{target_path}'. Fix the relative path."
                    )
    return errors
