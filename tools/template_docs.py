from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
TASK_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MAKE_COMMAND_RE = re.compile(r"\bmake\s+([A-Za-z0-9_-]+)")
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s|$)", re.MULTILINE)
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


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def markdown_files() -> list[Path]:
    roots = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "docs",
        ROOT / "project" / "index.md",
        ROOT / "project" / "board.md",
        ROOT / "project" / "roadmap.md",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.exists():
            files.extend(sorted(root.rglob("*.md")))
    return files


def make_targets() -> set[str]:
    targets = set(MAKE_TARGET_RE.findall((ROOT / "Makefile").read_text(encoding="utf-8")))
    generated_makefile = ROOT / "template" / "Makefile.jinja"
    targets.update(MAKE_TARGET_RE.findall(generated_makefile.read_text(encoding="utf-8")))
    return targets


def copier_config() -> dict[str, Any]:
    data = yaml.safe_load((ROOT / "copier.yml").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("copier.yml must be a mapping.")
    return data


def validate_required_docs() -> list[str]:
    required = [
        ROOT / "README.md",
        ROOT / "docs" / "template-architecture.md",
        ROOT / "docs" / "profile-matrix.md",
        ROOT / "docs" / "template-development.md",
        ROOT / "docs" / "diagrams" / "template-flow.d2",
        ROOT / "docs" / "diagrams" / "generated-project-workflow.d2",
        ROOT / "docs" / "diagrams" / "runtime-profiles.d2",
    ]
    errors = [f"{relative(path)} is required." for path in required if not path.exists()]
    if errors:
        return errors
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in [
        "docs/template-architecture.md",
        "docs/profile-matrix.md",
        "docs/template-development.md",
        "project/index.md",
        "project/board.md",
        "project/roadmap.md",
    ]:
        if f"]({target})" not in readme and f"]({target}#" not in readme:
            errors.append(f"README.md must link to {target}.")
    return errors


def validate_internal_links() -> list[str]:
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
                        f"{relative(path)}:{lineno}: broken internal link '{target_path}'."
                    )
    return errors


def validate_make_commands() -> list[str]:
    targets = make_targets()
    errors: list[str] = []
    for path in markdown_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in MAKE_COMMAND_RE.finditer(line):
                target = match.group(1)
                if target not in targets:
                    errors.append(
                        f"{relative(path)}:{lineno}: documented command 'make {target}' has no target."
                    )
    return errors


def validate_profile_matrix() -> list[str]:
    config = copier_config()
    project_types = set(config["project_type"]["choices"].values())
    runtime_levels = set(config["runtime_level"]["choices"].values())
    matrix = (ROOT / "docs" / "profile-matrix.md").read_text(encoding="utf-8")
    errors: list[str] = []
    for project_type in sorted(project_types):
        if f"`{project_type}`" not in matrix:
            errors.append(f"docs/profile-matrix.md is missing project_type `{project_type}`.")
    for runtime_level in sorted(runtime_levels):
        if f"`{runtime_level}`" not in matrix:
            errors.append(f"docs/profile-matrix.md is missing runtime_level `{runtime_level}`.")
    invalid_profile_markers = re.findall(r"`(script|library|backend|frontend|fullstack)-([a-z]+)`", matrix)
    for project_type, runtime_level in invalid_profile_markers:
        if project_type not in project_types or runtime_level not in runtime_levels:
            errors.append(
                f"docs/profile-matrix.md documents unknown profile `{project_type}-{runtime_level}`."
            )
    return errors


def validate_text_hygiene() -> list[str]:
    errors: list[str] = []
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        if "{{" in text or "{%" in text or "{#" in text:
            errors.append(f"{relative(path)} contains an unrendered Jinja placeholder.")
        if PERSONAL_PATH_RE.search(text):
            errors.append(f"{relative(path)} contains a personal absolute path.")
        if "../my-project" in text or "../my-fullstack" in text:
            errors.append(f"{relative(path)} contains stale example output paths.")
    return errors


def validate_diagrams() -> list[str]:
    errors: list[str] = []
    for path in sorted((ROOT / "docs" / "diagrams").glob("*.d2")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            errors.append(f"{relative(path)} is empty.")
        if len(text.splitlines()) > 80:
            errors.append(f"{relative(path)} should stay small enough to scan.")
    return errors


def main() -> None:
    errors: list[str] = []
    errors.extend(validate_required_docs())
    errors.extend(validate_internal_links())
    errors.extend(validate_make_commands())
    errors.extend(validate_profile_matrix())
    errors.extend(validate_text_hygiene())
    errors.extend(validate_diagrams())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Template documentation is valid.")


if __name__ == "__main__":
    main()
