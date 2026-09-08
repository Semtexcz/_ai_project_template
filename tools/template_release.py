from __future__ import annotations

# ruff: noqa: E501
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnnecessaryIsInstance=false
"""Template-maintainer release workflow (repository-root only, not rendered).

This tool intentionally does not live under ``template/``, so generated
projects never receive template-maintainer release commands. Shared project
lifecycle code stays in ``template/tools/project.py`` and is loaded here.

Local release vs publication
----------------------------

``make template-release`` prepares and validates a LOCAL release:

1. validate bump, branch, worktree, tag, and Git identity guards;
2. run ``make release-check``;
3. validate the candidate project state;
4. create the release commit and its annotated tag (both local).

The commit/tag become visible to Copier and GitHub only after an explicit
publish step (``git push origin main --follow-tags``).

Transaction order
-----------------

The annotated tag is created BEFORE the branch moves. The version commit is
prepared as an object first (``git commit-tree``). A failure never leaves a
version commit on the branch without the intended tag:

* state/commit-object failure: restore state file and index; no tag exists;
* tag-creation failure: restore state file and index; HEAD and tags untouched;
* branch-move failure: delete only the tag created by this run, restore state
  file and index; HEAD is untouched.

No unrelated user commit is reset and no existing tag is overwritten. The
branch advances only with ``git update-ref <branch> <commit> <old-head>`` so a
concurrent branch commit aborts the release instead of being clobbered.

Test-only fault injection mirrors the ``PROJECT_TOOL_FAIL_*`` seams:

* ``TEMPLATE_RELEASE_FAIL_COMMIT=1``: fail while creating the release commit;
* ``TEMPLATE_RELEASE_FAIL_TAG=1``: fail while creating the tag after the
  version commit would otherwise succeed;
* ``TEMPLATE_RELEASE_FAIL_BRANCH=1``: fail while moving the branch after the
  tag was created.
"""

import argparse
import copy
import importlib.util
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

VERSION_RE = re.compile(r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
BUMP_TYPES = {"major", "minor", "patch"}
PROJECT_TOOL_MODULE = "_template_release_project_tool"


class ReleaseError(Exception):
    pass


def discover_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "project" / "state.yaml").exists():
        return cwd
    return Path(__file__).resolve().parents[1]


ROOT = discover_root()
STATE_REL = Path("project") / "state.yaml"
STATE_PATH = ROOT / STATE_REL
PROJECT_TOOL_PATH = ROOT / "template" / "tools" / "project.py"


def load_project_tool() -> Any:
    """Load the shared project lifecycle tool from the template repository."""
    if PROJECT_TOOL_MODULE in sys.modules:
        return sys.modules[PROJECT_TOOL_MODULE]
    spec = importlib.util.spec_from_file_location(PROJECT_TOOL_MODULE, PROJECT_TOOL_PATH)
    if spec is None or spec.loader is None:
        raise ReleaseError("Could not load template/tools/project.py.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[PROJECT_TOOL_MODULE] = module
    spec.loader.exec_module(module)
    return module


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, check=False)
    if check and result.returncode != 0:
        raise ReleaseError(f"Command failed: {' '.join(command)}")
    return result


def command_output(command: list[str], *, check: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        suffix = f": {output}" if output else ""
        raise ReleaseError(f"Command failed: {' '.join(command)}{suffix}")
    return result.stdout.strip()


def inject_failure(env_name: str, description: str) -> None:
    if os.environ.get(env_name) == "1":
        raise ReleaseError(f"Injected {description} failure.")


def parse_template_version(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(version)
    if not match:
        raise ReleaseError(
            f"Invalid template version '{version}'. Use SemVer tags in vX.Y.Z format."
        )
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )


def bump_template_version(version: str, bump: str) -> str:
    if bump not in BUMP_TYPES:
        raise ReleaseError("BUMP must be one of: major, minor, patch.")
    major, minor, patch = parse_template_version(version)
    if bump == "major":
        return f"v{major + 1}.0.0"
    if bump == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def git_worktree_dirty() -> bool:
    return bool(command_output(["git", "status", "--porcelain"]))


def git_current_branch() -> str:
    return command_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def git_head_sha() -> str:
    return command_output(["git", "rev-parse", "HEAD"])


def git_tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--quiet", "--verify", f"refs/tags/{tag}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def git_config_value(name: str) -> str:
    return command_output(["git", "config", "--get", name], check=False)


def validate_release_state(
    state: dict[str, Any],
    *,
    bump: str,
    allow_non_main: bool,
) -> tuple[str, str, str]:
    if state.get("project", {}).get("type") != "template":
        raise ReleaseError(
            "Template releases are only supported in the template repository "
            "(project.type=template)."
        )
    current_version = str(state.get("template", {}).get("version", ""))
    next_version = bump_template_version(current_version, bump)
    if git_tag_exists(next_version):
        raise ReleaseError(f"Git tag {next_version} already exists.")
    if git_worktree_dirty():
        raise ReleaseError("Git worktree must be clean before creating a template release.")
    branch = git_current_branch()
    if branch == "HEAD":
        raise ReleaseError("Template releases cannot run from a detached HEAD.")
    if branch != "main" and not allow_non_main:
        raise ReleaseError(
            f"Template releases must run on main, not {branch}. Set ALLOW_NON_MAIN=1 only "
            "for tests or controlled dry runs."
        )
    if not git_config_value("user.email") or not git_config_value("user.name"):
        raise ReleaseError("Git user.name and user.email must be configured before release.")
    return current_version, next_version, branch


def state_file_mode() -> int:
    try:
        return stat.S_IMODE(STATE_PATH.stat().st_mode)
    except OSError:
        return 0o644


def write_state_preserving_mode(project: Any, state: dict[str, Any], mode: int) -> None:
    """Write project state and keep the file mode stable across the release."""
    project.write_state(state)
    try:
        os.chmod(STATE_PATH, mode)
    except OSError as exc:
        raise ReleaseError(f"Could not preserve state file mode: {exc}") from exc


def restore_release_mutation(
    project: Any,
    original_state: dict[str, Any],
    mode: int,
) -> list[str]:
    """Restore state file and index after an aborted release mutation.

    Never touches branch refs or tags; callers delete tags created by this run.
    The original file mode is restored too, so an aborted release cannot leave a
    mode-only working-tree change behind.
    """
    problems: list[str] = []
    try:
        write_state_preserving_mode(project, original_state, mode)
    except Exception as exc:  # pragma: no cover - defensive cleanup reporting
        problems.append(f"state file restore failed: {exc}")
    try:
        run_command(["git", "restore", "--staged", str(STATE_REL)], check=False)
    except ReleaseError as exc:
        problems.append(f"index restore failed: {exc}")
    return problems


def perform_release_mutation(
    *,
    project: Any,
    state: dict[str, Any],
    next_version: str,
    branch: str,
    head_sha: str,
) -> None:
    """Create the release commit and tag transactionally.

    Order: write+stage state -> create commit object -> create annotated tag ->
    advance branch with a guarded fast-forward. Tag creation failure therefore
    leaves no release commit on the branch, and branch advancement failure
    removes only the tag created by this run.
    """
    commit_message = f"chore(release): {next_version}"
    tag_message = f"Template release {next_version}"
    original_state = copy.deepcopy(state)
    candidate = copy.deepcopy(state)
    candidate["template"]["version"] = next_version
    tag_created = False
    phase = "write candidate version state"
    state_mode = state_file_mode()
    try:
        write_state_preserving_mode(project, candidate, state_mode)
        run_command(["git", "add", str(STATE_REL)])
        phase = "create release commit object"
        inject_failure("TEMPLATE_RELEASE_FAIL_COMMIT", phase)
        tree_sha = command_output(["git", "write-tree"])
        commit_sha = command_output(
            ["git", "commit-tree", tree_sha, "-p", head_sha, "-m", commit_message]
        )
        phase = "create release tag"
        inject_failure("TEMPLATE_RELEASE_FAIL_TAG", phase)
        run_command(["git", "tag", "-a", next_version, "-m", tag_message, commit_sha])
        tag_created = True
        phase = "advance branch to the release commit"
        inject_failure("TEMPLATE_RELEASE_FAIL_BRANCH", phase)
        run_command(["git", "update-ref", f"refs/heads/{branch}", commit_sha, head_sha])
    except ReleaseError as exc:
        problems = restore_release_mutation(project, original_state, state_mode)
        if tag_created:
            try:
                run_command(["git", "tag", "-d", next_version])
            except ReleaseError as tag_exc:
                problems.append(
                    f"could not delete tag {next_version}; remove it manually with: "
                    f"git tag -d {next_version} ({tag_exc})"
                )
        cleanup = ""
        if problems:
            cleanup = " Cleanup problems: " + " ".join(problems)
        raise ReleaseError(
            f"{phase} failed: {exc}. The release was aborted before publishing a version. "
            f"Branch {branch} still points to {head_sha[:12]}, no version commit was "
            f"left on the branch, and the working tree was restored to the pre-release "
            f"state.{cleanup}"
        ) from exc


def release_template(*, bump: str, dry_run: bool, allow_non_main: bool) -> None:
    project = load_project_tool()
    state = project.read_state()
    current_version, next_version, branch = validate_release_state(
        state,
        bump=bump,
        allow_non_main=allow_non_main,
    )
    print(f"Template release: {current_version} -> {next_version} ({bump})")
    run_command(["make", "release-check"])
    if git_worktree_dirty():
        raise ReleaseError(
            "Git worktree changed during release-check; inspect the diff before release."
        )
    if dry_run:
        print(f"Dry run only. No state, commit, or tag was created for {next_version}.")
        return

    candidate = copy.deepcopy(state)
    candidate["template"]["version"] = next_version
    errors = project.validate_candidate(candidate, project.load_tasks())
    if errors:
        raise ReleaseError("Candidate release state is invalid:\n" + "\n".join(errors))

    head_sha = git_head_sha()
    perform_release_mutation(
        project=project,
        state=state,
        next_version=next_version,
        branch=branch,
        head_sha=head_sha,
    )
    print(f"Created template release {next_version}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a local template release commit and annotated tag."
    )
    parser.add_argument("--bump", choices=sorted(BUMP_TYPES), default="patch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-non-main", action="store_true")
    args = parser.parse_args()
    try:
        release_template(
            bump=args.bump,
            dry_run=args.dry_run,
            allow_non_main=args.allow_non_main,
        )
    except ReleaseError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
