from __future__ import annotations

import argparse
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
CHANGELOG_FIRST_LINE = "# Changelog"
CHANGELOG_RELEASE_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"\s+-\s+(?P<date>\d{4}-\d{2}-\d{2})$"
)
CHANGELOG_UNRELEASED_RE = re.compile(r"^\[?unreleased\]?:?$", re.IGNORECASE)
SEMVER_RE = re.compile(r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
SEMVER_BUMPS = ("major", "minor", "patch")


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


def template_state_version() -> str | None:
    state_path = ROOT / "project" / "state.yaml"
    if not state_path.exists():
        return None
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    template = data.get("template")
    if not isinstance(template, dict):
        return None
    version = template.get("version")
    return str(version) if version else None


def parse_semver(version: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.match(version.strip())
    if not match:
        return None
    return (int(match.group("major")), int(match.group("minor")), int(match.group("patch")))


def semver_bump(version: str, bump: str) -> str:
    parsed = parse_semver(version)
    if parsed is None:
        raise ValueError(f"Invalid version '{version}'.")
    major, minor, patch = parsed
    if bump == "major":
        return f"v{major + 1}.0.0"
    if bump == "minor":
        return f"v{major}.{minor + 1}.0"
    if bump == "patch":
        return f"v{major}.{minor}.{patch + 1}"
    raise ValueError(f"Invalid bump '{bump}'.")


def parse_changelog(text: str) -> tuple[list[str], list[tuple[str, int]]]:
    """Parse a changelog into structural errors and released sections.

    The structural rules are shared by every validation mode - the
    ``# Changelog`` heading, no ``Unreleased`` section, dated SemVer release
    headings in descending order, and a non-empty newest release section - so the
    parser is single-sourced. Version-window rules differ per mode and stay in the
    mode-specific validators.
    """
    errors: list[str] = []
    lines = text.splitlines()
    first_line = next((line.strip() for line in lines if line.strip()), "")
    if first_line != CHANGELOG_FIRST_LINE:
        errors.append(f"CHANGELOG.md must start with '{CHANGELOG_FIRST_LINE}'.")

    sections: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^##\s+(?P<body>.+?)\s*$", line)
        if not match:
            continue
        body = match.group("body")
        if CHANGELOG_UNRELEASED_RE.match(body):
            errors.append(
                "CHANGELOG.md must not contain an Unreleased section; every template "
                "change is released with its own version and changelog entry."
            )
            continue
        release = CHANGELOG_RELEASE_RE.match(body)
        if not release:
            errors.append(
                f"CHANGELOG.md section '## {body}' must be a released version heading "
                "of the form '## vX.Y.Z - YYYY-MM-DD'."
            )
            continue
        sections.append((f"v{release.group('major')}.{release.group('minor')}.{release.group('patch')}", index))

    if not sections:
        errors.append("CHANGELOG.md must contain at least one '## vX.Y.Z - YYYY-MM-DD' release section.")
        return errors, sections

    versions = [version for version, _index in sections]
    parsed = [parse_semver(version) for version in versions]
    for previous, current in zip(parsed, parsed[1:]):
        if previous is None or current is None:
            continue
        if current >= previous:
            errors.append(
                f"CHANGELOG.md releases must be in descending order; {versions} is not."
            )
            break

    newest, newest_index = sections[0]
    next_index = sections[1][1] if len(sections) > 1 else len(lines)
    newest_body = "\n".join(lines[newest_index + 1 : next_index])
    if not any(line.lstrip().startswith("- ") for line in newest_body.splitlines()):
        errors.append(f"CHANGELOG.md section '## {newest}' must contain at least one entry.")

    return errors, sections


def validate_changelog_text(text: str, state_version: str | None) -> list[str]:
    """Validate the changelog while a release may still be prepared.

    This ordinary, permissive mode accepts a newest release that is either the
    current ``template.version`` or exactly one ``patch``/``minor``/``major`` bump
    ahead of it, so ``make template-release-prepare`` can run before the version
    commit exists. The strict final boundary is ``validate_release_ready_text``.
    """
    errors, sections = parse_changelog(text)
    if not sections:
        return errors
    newest = sections[0][0]
    if state_version:
        allowed = {state_version} | {semver_bump(state_version, bump) for bump in SEMVER_BUMPS}
        if newest not in allowed:
            errors.append(
                f"CHANGELOG.md newest release {newest} must match the current template "
                f"version {state_version} or its next patch/minor/major release."
            )
    return errors


def validate_release_ready_text(text: str, state_version: str | None) -> list[str]:
    """Validate the strict final boundary: changelog version == template version.

    Ordinary changelog validation permits one pending SemVer bump so a release can
    be prepared before the version commit exists. That gap must be closed at the
    final PR/CI boundary: without this strict check a change could ship a newer
    changelog version, skip ``make template-release-prepare``, and still pass
    ordinary documentation validation, violating the per-change release policy
    that every template change is a release.
    """
    errors, sections = parse_changelog(text)
    if not sections:
        return errors
    newest = sections[0][0]
    if not state_version:
        errors.append(
            "project/state.yaml must define template.version for release-ready validation."
        )
    elif newest != state_version:
        errors.append(
            f"CHANGELOG.md newest release {newest} must exactly match the released "
            f"template version {state_version} at the final release boundary; run "
            "`make template-release-prepare BUMP=<major|minor|patch>` to record the version."
        )
    return errors


def changelog_text() -> str | None:
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        return None
    return changelog.read_text(encoding="utf-8")


def validate_changelog() -> list[str]:
    text = changelog_text()
    if text is None:
        return ["CHANGELOG.md is required."]
    return validate_changelog_text(text, template_state_version())


def validate_release_ready() -> list[str]:
    text = changelog_text()
    if text is None:
        return ["CHANGELOG.md is required."]
    return validate_release_ready_text(text, template_state_version())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate template documentation and the release contract.",
    )
    parser.add_argument(
        "--release-ready",
        action="store_true",
        help=(
            "Require the strict final release boundary: the newest changelog release "
            "must exactly equal project/state.yaml template.version."
        ),
    )
    args = parser.parse_args(argv)

    if args.release_ready:
        errors = validate_release_ready()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)
        print("Template release is ready: changelog and template version match.")
        return

    errors: list[str] = []
    errors.extend(validate_required_docs())
    errors.extend(validate_internal_links())
    errors.extend(validate_make_commands())
    errors.extend(validate_profile_matrix())
    errors.extend(validate_text_hygiene())
    errors.extend(validate_diagrams())
    errors.extend(validate_changelog())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Template documentation is valid.")


if __name__ == "__main__":
    main()
