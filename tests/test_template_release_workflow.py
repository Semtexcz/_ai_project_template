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

CURRENT_VERSION = "v1.1.1"


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


def output_of(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


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


def add_origin(repo: Path, tmp_path: Path) -> Path:
    """Create a temporary bare origin and publish main to it."""
    origin = tmp_path / "origin.git"
    run(["git", "init", "--bare", "-q", str(origin)], tmp_path)
    run(["git", "remote", "add", "origin", str(origin)], repo)
    run(["git", "push", "-q", "-u", "origin", "main"], repo)
    return origin


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
    assert_snapshot_equal(repo, before)
    assert "chore(release)" not in before["log"]


def assert_snapshot_equal(repo: Path, before: dict[str, str]) -> None:
    after = git_snapshot(repo)
    assert after == before, f"Release failure changed the repository:\n{before}\n!=\n{after}"


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


def release_branch(tmp_path: Path, version: str = "v1.1.2") -> Path:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    run(["git", "checkout", "-q", "-b", f"release/{version}"], repo)
    return repo


@pytest.mark.parametrize(
    ("bump", "expected_version"),
    [
        ("patch", "v1.1.2"),
        ("minor", "v1.2.0"),
        ("major", "v2.0.0"),
    ],
)
def test_template_release_prepare_success_for_each_bump(
    tmp_path: Path,
    bump: str,
    expected_version: str,
) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    main_head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    run(["git", "checkout", "-q", "-b", f"release/{expected_version}"], repo)

    result = run(["make", "template-release-prepare", f"BUMP={bump}"], repo)

    assert f"Prepared template release {expected_version}" in result.stdout
    assert f"version: {expected_version}" in state_text(repo)
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()
    assert branch == f"release/{expected_version}"
    subject = run(["git", "log", "-1", "--pretty=%s"], repo).stdout.strip()
    assert subject == f"chore(release): {expected_version}"
    head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    assert head != main_head
    assert run(["git", "rev-parse", "HEAD^"], repo).stdout.strip() == main_head
    assert run(["git", "tag", "--list"], repo).stdout.strip() == ""
    assert run(["git", "status", "--porcelain"], repo).stdout.strip() == ""


def test_template_release_prepare_rejects_main(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare", "BUMP=patch"], repo, expect_success=False)

    output = output_of(result)
    assert "must run on a release branch" in output
    assert "not on 'main'" in output
    assert "git switch -c release/" in output
    assert_release_unchanged(repo, before)


def test_template_release_prepare_dirty_worktree_fails(tmp_path: Path) -> None:
    repo = release_branch(tmp_path)
    (repo / "docs" / "template-development.md").write_text("dirty\n", encoding="utf-8")
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare"], repo, expect_success=False)

    assert "Git worktree must be clean" in output_of(result)
    assert_release_unchanged(repo, before)


def test_template_release_prepare_invalid_bump_fails(tmp_path: Path) -> None:
    repo = release_branch(tmp_path)
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare", "BUMP=weekly"], repo, expect_success=False)

    assert "invalid choice" in output_of(result)
    assert_release_unchanged(repo, before)


def test_template_release_prepare_invalid_version_fails(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    state = repo / "project" / "state.yaml"
    state.write_text(state.read_text(encoding="utf-8").replace("v1.1.1", "banana"), encoding="utf-8")
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-q", "-m", "set an invalid template version"], repo)
    run(["git", "checkout", "-q", "-b", "release/v1.1.2"], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare", "BUMP=patch"], repo, expect_success=False)

    assert "Invalid template version" in output_of(result)
    assert_release_unchanged(repo, before)


def test_template_release_prepare_existing_tag_fails_before_mutation(tmp_path: Path) -> None:
    repo = release_branch(tmp_path)
    run(["git", "tag", "v1.1.2"], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare", "BUMP=patch"], repo, expect_success=False)

    assert "Git tag v1.1.2 already exists" in output_of(result)
    assert_release_unchanged(repo, before)


def test_template_release_prepare_dry_run_does_not_mutate(tmp_path: Path) -> None:
    repo = release_branch(tmp_path)
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare", "DRY_RUN=1"], repo)

    assert f"Preparing template release {CURRENT_VERSION} -> v1.1.2 (patch) on branch release/v1.1.2." in result.stdout
    assert "Dry run only" in result.stdout
    assert_release_unchanged(repo, before)


def test_template_release_prepare_check_failure_aborts_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo, release_check_fails=True)
    init_release_repo(repo)
    run(["git", "checkout", "-q", "-b", "release/v1.1.2"], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-prepare", "BUMP=patch"], repo, expect_success=False)

    assert "ERROR:" in output_of(result)
    assert_release_unchanged(repo, before)


@pytest.mark.parametrize(
    ("env_name", "expected_phase"),
    [
        ("TEMPLATE_RELEASE_PREPARE_FAIL_STATE", "update project/state.yaml.template.version failed"),
        ("TEMPLATE_RELEASE_PREPARE_FAIL_COMMIT", "create the release commit failed"),
    ],
)
def test_template_release_prepare_failure_leaves_no_partial_state(
    tmp_path: Path,
    env_name: str,
    expected_phase: str,
) -> None:
    """A prepare failure must restore state and index and leave no release commit."""
    repo = release_branch(tmp_path)
    before = git_snapshot(repo)

    result = run(
        ["make", "template-release-prepare", "BUMP=patch"],
        repo,
        env={env_name: "1"},
        expect_success=False,
    )

    output = output_of(result)
    assert expected_phase in output
    assert "The prepare was aborted" in output
    assert_release_unchanged(repo, before)


def prepare_and_publish_release(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """Run the full phase-1 flow and simulate a PR merge to origin main.

    Returns (repo, origin, release_sha, version). The merge is simulated with a
    normal git fast-forward merge followed by a push to the bare origin, which
    is what a GitHub PR merge performs on origin/main.
    """
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    origin = add_origin(repo, tmp_path)
    expected_version = "v1.1.2"

    run(["git", "checkout", "-q", "-b", f"release/{expected_version}"], repo)
    result = run(["make", "template-release-prepare", "BUMP=patch"], repo)
    assert f"Prepared template release {expected_version}" in result.stdout
    assert run(["git", "tag", "--list"], repo).stdout.strip() == ""
    release_sha = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    run(["git", "push", "-q", "-u", "origin", f"release/{expected_version}"], repo)
    run(["git", "checkout", "-q", "main"], repo)
    run(["git", "merge", "-q", "--ff-only", f"release/{expected_version}"], repo)
    run(["git", "push", "-q", "origin", "main"], repo)
    return repo, origin, release_sha, expected_version


def remote_main_sha(repo: Path) -> str:
    return run(["git", "ls-remote", "origin", "refs/heads/main"], repo).stdout.split()[0]


def test_template_release_tag_rejects_non_main(tmp_path: Path) -> None:
    repo, _origin, _sha, _version = prepare_and_publish_release(tmp_path)
    run(["git", "checkout", "-q", "-b", "feature/not-main"], repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    output = output_of(result)
    assert "must run on 'main'" in output
    assert "never creates commits" in output


def test_template_release_tag_rejects_dirty_worktree(tmp_path: Path) -> None:
    repo, _origin, _sha, _version = prepare_and_publish_release(tmp_path)
    (repo / "docs" / "template-development.md").write_text("dirty\n", encoding="utf-8")
    before = git_snapshot(repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    assert "Git worktree must be clean" in output_of(result)
    assert_snapshot_equal(repo, before)


def test_template_release_tag_rejects_unexpected_head_subject(tmp_path: Path) -> None:
    repo, _origin, _sha, version = prepare_and_publish_release(tmp_path)
    readme = repo / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\npost-release note\n", encoding="utf-8")
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-q", "-m", "docs: post-release note"], repo)
    run(["git", "push", "-q", "origin", "main"], repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    output = output_of(result)
    assert "HEAD subject is 'docs: post-release note'" in output
    assert f"expected 'chore(release): {version}'" in output


def test_template_release_tag_rejects_fake_release_subject_without_state_change(tmp_path: Path) -> None:
    """A matching subject is not enough: HEAD must actually change template.version."""
    repo, _origin, _sha, version = prepare_and_publish_release(tmp_path)
    readme = repo / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nfake release\n", encoding="utf-8")
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-q", "-m", f"chore(release): {version}"], repo)
    run(["git", "push", "-q", "origin", "main"], repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    output = output_of(result)
    assert "HEAD does not change template.version" in output
    assert f"already records {version}" in output


def test_template_release_tag_rejects_mismatched_state_version(tmp_path: Path) -> None:
    repo, _origin, _sha, _version = prepare_and_publish_release(tmp_path)
    state = repo / "project" / "state.yaml"
    state.write_text(
        state.read_text(encoding="utf-8").replace("version: v1.1.2", "version: v1.1.3"),
        encoding="utf-8",
    )
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-q", "-m", "chore(release): v1.1.2"], repo)
    run(["git", "push", "-q", "origin", "main"], repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    output = output_of(result)
    assert "expected 'chore(release): v1.1.3'" in output


def test_template_release_tag_rejects_existing_local_tag(tmp_path: Path) -> None:
    repo, _origin, release_sha, version = prepare_and_publish_release(tmp_path)
    run(["git", "tag", version, release_sha], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    assert f"Git tag {version} already exists locally" in output_of(result)
    assert git_snapshot(repo) == before


def test_template_release_tag_rejects_existing_remote_tag(tmp_path: Path) -> None:
    repo, _origin, release_sha, version = prepare_and_publish_release(tmp_path)
    run(["git", "tag", "-a", version, "-m", "pre-existing release", release_sha], repo)
    run(["git", "push", "-q", "origin", version], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    assert f"Tag {version} already exists on origin" in output_of(result)
    assert git_snapshot(repo) == before


def test_template_release_tag_rejects_stale_local_main(tmp_path: Path) -> None:
    repo, origin, _sha, _version = prepare_and_publish_release(tmp_path)
    clone = tmp_path / "fresh-clone"
    run(["git", "clone", "-q", str(origin), str(clone)], tmp_path)
    run(["git", "config", "user.email", "release-test@example.invalid"], clone)
    run(["git", "config", "user.name", "Release Test"], clone)
    readme = clone / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nmerged after release\n", encoding="utf-8")
    run(["git", "add", "-A"], clone)
    run(["git", "commit", "-q", "-m", "docs: merged after the release"], clone)
    run(["git", "push", "-q", "origin", "main"], clone)
    before = git_snapshot(repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    output = output_of(result)
    assert "does not match origin/main" in output
    assert "local main is behind origin/main" in output
    assert_snapshot_equal(repo, before)


def test_template_release_tag_rejects_diverged_main(tmp_path: Path) -> None:
    repo, origin, _sha, _version = prepare_and_publish_release(tmp_path)
    clone = tmp_path / "fresh-clone"
    run(["git", "clone", "-q", str(origin), str(clone)], tmp_path)
    run(["git", "config", "user.email", "release-test@example.invalid"], clone)
    run(["git", "config", "user.name", "Release Test"], clone)
    readme = clone / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nremote divergence\n", encoding="utf-8")
    run(["git", "add", "-A"], clone)
    run(["git", "commit", "-q", "-m", "docs: remote divergence"], clone)
    run(["git", "push", "-q", "origin", "main"], clone)

    readme = repo / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nlocal divergence\n", encoding="utf-8")
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-q", "-m", "docs: local divergence"], repo)
    before = git_snapshot(repo)

    result = run(["make", "template-release-tag"], repo, expect_success=False)

    assert "have diverged" in output_of(result)
    assert_snapshot_equal(repo, before)


def test_template_release_tag_creates_annotated_tag_on_exact_release_commit(tmp_path: Path) -> None:
    repo, _origin, release_sha, version = prepare_and_publish_release(tmp_path)
    head_before = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    log_before = run(["git", "log", "--oneline"], repo).stdout
    state_before = state_text(repo)

    result = run(["make", "template-release-tag"], repo)

    assert f"Created annotated tag {version}" in result.stdout
    assert f"git push origin {version}" in result.stdout
    assert run(["git", "cat-file", "-t", f"refs/tags/{version}"], repo).stdout.strip() == "tag"
    peeled = run(["git", "rev-parse", f"{version}^{{}}"], repo).stdout.strip()
    assert peeled == release_sha
    assert peeled == run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    assert run(["git", "rev-parse", "HEAD"], repo).stdout.strip() == head_before
    assert run(["git", "log", "--oneline"], repo).stdout == log_before
    assert state_text(repo) == state_before
    assert run(["git", "status", "--porcelain"], repo).stdout.strip() == ""


def test_template_release_tag_failure_leaves_repository_unchanged(tmp_path: Path) -> None:
    repo, _origin, _sha, _version = prepare_and_publish_release(tmp_path)
    before = git_snapshot(repo)

    result = run(
        ["make", "template-release-tag"],
        repo,
        env={"TEMPLATE_RELEASE_FAIL_TAG": "1"},
        expect_success=False,
    )

    output = output_of(result)
    assert "Injected create the annotated release tag failure" in output
    assert_snapshot_equal(repo, before)


def test_publication_pushes_only_the_intended_tag(tmp_path: Path) -> None:
    repo, origin, release_sha, version = prepare_and_publish_release(tmp_path)
    main_before_push = remote_main_sha(repo)
    assert main_before_push == release_sha

    run(["git", "tag", "-a", "experimental", "-m", "unrelated local tag", "HEAD"], repo)
    run(["make", "template-release-tag"], repo)
    # Publication pushes ONLY the release tag; main was already published by the
    # simulated PR merge and no direct release-commit push to main is needed.
    run(["git", "push", "-q", "origin", version], repo)

    assert remote_main_sha(repo) == release_sha
    remote_tags = run(["git", "ls-remote", "--tags", "origin"], repo).stdout
    assert f"refs/tags/{version}" in remote_tags
    assert "refs/tags/experimental" not in remote_tags
    local_tags = run(["git", "tag", "--list"], repo).stdout
    assert version in local_tags
    assert "experimental" in local_tags
    peeled_remote_tag_line = [
        line
        for line in remote_tags.splitlines()
        if line.endswith(f"refs/tags/{version}^{{}}")
    ][0]
    assert peeled_remote_tag_line.startswith(release_sha)


def test_publication_does_not_republish_main_through_follow_tags(tmp_path: Path) -> None:
    """The obsolete --follow-tags publication mechanism is removed everywhere."""
    release_tool_doc = (ROOT / "tools" / "template_release.py").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for text in (release_tool_doc, makefile, readme):
        assert "--follow-tags" not in text
    development_doc = (ROOT / "docs" / "template-development.md").read_text(encoding="utf-8")
    if "--follow-tags" in development_doc:
        assert "not recommended" in development_doc or "never" in development_doc
    assert "git push origin vX.Y.Z" in development_doc or "git push origin v1.2.0" in development_doc


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
    assert "template-release-prepare:" in maintainer_makefile
    assert "template-release-tag:" in maintainer_makefile
    assert "template-release:" not in maintainer_makefile
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
