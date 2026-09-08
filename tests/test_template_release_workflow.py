from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]

RELEASE_CHECK_STUB_OLD = (
    "release-check: validate-project validate-template-docs validate-agent-skills\n"
    "\tUV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} UV_LINK_MODE=$${UV_LINK_MODE:-copy} uv run pytest\n"
)
RELEASE_CHECK_STUB_NEW = "release-check:\n\t@echo release-check fixture\n"
RELEASE_CHECK_FAIL_MARKER = "\t@echo release-check fixture && exit 1\n"


def load_release_tool() -> Any:
    spec = importlib.util.spec_from_file_location(
        "template_release_tool",
        ROOT / "tools" / "template_release.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load template release tool module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["template_release_tool"] = module
    spec.loader.exec_module(module)
    return module


def run(
    command: list[str],
    cwd: Path,
    *,
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        command,
        cwd=cwd,
        env=full_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def copy_template_repo(target: Path, *, release_check_fails: bool = False) -> None:
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        ),
    )
    makefile = target / "Makefile"
    text = makefile.read_text(encoding="utf-8")
    text = text.replace(RELEASE_CHECK_STUB_OLD, RELEASE_CHECK_STUB_NEW)
    if release_check_fails:
        text = text.replace("\t@echo release-check fixture\n", RELEASE_CHECK_FAIL_MARKER)
    makefile.write_text(text)


def init_release_repo(path: Path) -> None:
    run(["git", "init", "-q"], path)
    run(["git", "checkout", "-q", "-b", "main"], path)
    run(["git", "config", "user.email", "release-test@example.invalid"], path)
    run(["git", "config", "user.name", "Release Test"], path)
    run(["git", "add", "-A"], path)
    run(["git", "commit", "-q", "-m", "initial template"], path)


def state_text(path: Path) -> str:
    return (path / "project" / "state.yaml").read_text(encoding="utf-8")


def git_snapshot(repo: Path) -> dict[str, str]:
    return {
        "head": run(["git", "rev-parse", "HEAD"], repo).stdout.strip(),
        "tags": run(["git", "tag", "--list"], repo).stdout.strip(),
        "porcelain": run(["git", "status", "--porcelain"], repo).stdout.strip(),
        "log": run(["git", "log", "--oneline"], repo).stdout,
        "state": state_text(repo),
    }


def assert_release_unchanged(repo: Path, before: dict[str, str]) -> None:
    after = git_snapshot(repo)
    assert after == before, f"Release failure changed the repository:\n{before}\n!=\n{after}"
    assert "chore(release)" not in after["log"]


def test_template_version_bumps() -> None:
    release_tool = load_release_tool()

    assert release_tool.bump_template_version("v1.1.1", "patch") == "v1.1.2"
    assert release_tool.bump_template_version("v1.1.1", "minor") == "v1.2.0"
    assert release_tool.bump_template_version("v1.1.1", "major") == "v2.0.0"


def test_invalid_template_version_fails_clearly() -> None:
    release_tool = load_release_tool()

    try:
        release_tool.bump_template_version("1.1.1", "patch")
    except release_tool.ReleaseError as exc:
        assert "vX.Y.Z" in str(exc)
    else:
        raise AssertionError("Invalid template version unexpectedly passed.")

    try:
        release_tool.bump_template_version("v1.1.1", "weekly")
    except release_tool.ReleaseError as exc:
        assert "BUMP must be one of: major, minor, patch" in str(exc)
    else:
        raise AssertionError("Invalid bump unexpectedly passed.")


@pytest.mark.parametrize(
    ("bump", "expected_version"),
    [
        ("patch", "v1.1.2"),
        ("minor", "v1.2.0"),
        ("major", "v2.0.0"),
    ],
)
def test_template_release_success_for_each_bump(
    tmp_path: Path,
    bump: str,
    expected_version: str,
) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before_head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    result = run(["make", "template-release", f"BUMP={bump}"], repo)

    assert f"Created template release {expected_version}" in result.stdout
    assert f"version: {expected_version}" in state_text(repo)
    subject = run(["git", "log", "-1", "--pretty=%s"], repo).stdout.strip()
    assert subject == f"chore(release): {expected_version}"
    assert run(["git", "tag", "--list", expected_version], repo).stdout.strip() == expected_version
    tag_type = run(["git", "cat-file", "-t", f"refs/tags/{expected_version}"], repo).stdout.strip()
    assert tag_type == "tag"
    peeled = run(["git", "rev-parse", f"{expected_version}^{{}}"], repo).stdout.strip()
    assert peeled == run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    assert peeled != before_head
    assert run(["git", "status", "--porcelain"], repo).stdout.strip() == ""


def test_template_release_dry_run_does_not_mutate(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release", "DRY_RUN=1"], repo)

    assert "Template release: v1.1.1 -> v1.1.2 (patch)" in result.stdout
    assert "Dry run only" in result.stdout
    assert_release_unchanged(repo, before)


def test_template_release_existing_tag_fails_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    run(["git", "tag", "v1.1.2"], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release"], repo, expect_success=False)

    assert "Git tag v1.1.2 already exists" in result.stdout
    assert_release_unchanged(repo, before)


def test_template_release_dirty_worktree_fails_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    (repo / "docs" / "template-development.md").write_text("dirty\n", encoding="utf-8")
    before = git_snapshot(repo)

    result = run(["make", "template-release"], repo, expect_success=False)

    assert "Git worktree must be clean" in result.stdout
    assert_release_unchanged(repo, before)


def test_template_release_wrong_branch_fails_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    run(["git", "checkout", "-q", "-b", "release-test"], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release"], repo, expect_success=False)

    assert "must run on main, not release-test" in result.stdout
    assert_release_unchanged(repo, before)


def test_template_release_check_failure_aborts_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo, release_check_fails=True)
    init_release_repo(repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release"], repo, expect_success=False)

    assert "ERROR:" in result.stdout
    assert_release_unchanged(repo, before)


@pytest.mark.parametrize(
    ("env_name", "expected_phase"),
    [
        ("TEMPLATE_RELEASE_FAIL_COMMIT", "create release commit object"),
        ("TEMPLATE_RELEASE_FAIL_TAG", "create release tag"),
        ("TEMPLATE_RELEASE_FAIL_BRANCH", "advance branch to the release commit"),
    ],
)
def test_template_release_failure_after_validation_leaves_no_partial_state(
    tmp_path: Path,
    env_name: str,
    expected_phase: str,
) -> None:
    """Regression: a failure after the version commit would otherwise succeed
    (especially tag creation) must leave HEAD, tags, state, and the working
    tree exactly as they were before the release."""
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before = git_snapshot(repo)

    result = run(
        ["make", "template-release"],
        repo,
        env={env_name: "1"},
        expect_success=False,
    )

    output = result.stdout + result.stderr
    assert expected_phase in output
    assert "failed" in output
    assert "no version commit was left on the branch" in output
    assert "working tree was restored" in output
    assert_release_unchanged(repo, before)


def test_template_release_branch_failure_removes_tag_created_by_run(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before = git_snapshot(repo)

    result = run(
        ["make", "template-release"],
        repo,
        env={"TEMPLATE_RELEASE_FAIL_BRANCH": "1"},
        expect_success=False,
    )

    assert "advance branch to the release commit failed" in result.stdout
    assert run(["git", "tag", "--list"], repo).stdout.strip() == ""
    assert_release_unchanged(repo, before)


def render_generated_project(tmp_path: Path, name: str, governance: str) -> Path:
    generated = tmp_path / name
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--skip-tasks",
            "--data",
            f"project_name={name}",
            "--data",
            "project_type=script",
            "--data",
            "runtime_level=local",
            "--data",
            f"governance={governance}",
            "--data",
            "workflow_mode=local",
            "--data",
            "include_reference_feature=false",
            "--trust",
            "--vcs-ref=HEAD",
            str(ROOT),
            str(generated),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return generated


def test_release_maintainer_tooling_lives_outside_rendered_template() -> None:
    maintainer_makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "template-release:" in maintainer_makefile
    assert (ROOT / "tools" / "template_release.py").exists()
    assert not (ROOT / "template" / "tools" / "template_release.py").exists()

    project_tool = (ROOT / "template" / "tools" / "project.py").read_text(encoding="utf-8")
    generated_makefile = (ROOT / "template" / "Makefile.jinja").read_text(encoding="utf-8")
    assert "release-template" not in project_tool
    assert "template-release" not in generated_makefile


@pytest.mark.parametrize("governance", ["lightweight", "managed"])
def test_generated_projects_do_not_expose_maintainer_release_commands(
    tmp_path: Path,
    governance: str,
) -> None:
    generated = render_generated_project(tmp_path, f"gen-{governance}", governance)

    makefile = (generated / "Makefile").read_text(encoding="utf-8")
    assert "template-release" not in makefile
    assert not (generated / "tools" / "template_release.py").exists()

    project_tool = generated / "tools" / "project.py"
    if project_tool.exists():
        assert "release-template" not in project_tool.read_text(encoding="utf-8")
