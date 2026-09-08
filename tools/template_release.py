from __future__ import annotations

# ruff: noqa: E501
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnnecessaryIsInstance=false
"""Template-maintainer release workflow (repository-root only, not rendered).

This tool intentionally does not live under ``template/``, so generated
projects never receive template-maintainer release commands. Shared project
lifecycle code stays in ``template/tools/project.py`` and is loaded here.

Two-phase, PR-only release model
--------------------------------

``make template-release-prepare BUMP=<major|minor|patch>`` (Phase 1) prepares
an ordinary, reviewable release version commit on a NON-``main`` release
branch:

1. validate the current template version and the requested SemVer bump;
2. require a non-``main`` branch and a clean worktree;
3. run ``make release-check``;
4. validate the candidate project state;
5. update ``project/state.yaml.template.version``;
6. create a normal Git commit ``chore(release): vX.Y.Z`` on the branch.

It creates no tag and pushes nothing. The version bump is a normal repository
change and must reach ``main`` through the standard branch -> push -> pull
request -> human merge workflow. Running prepare on ``main`` fails with
instructions to create a release branch.

``make template-release-tag`` (Phase 2) runs AFTER that release commit has
been merged to ``main`` by a human. It is the only post-merge release
mutation and it creates only an annotated tag:

1. require checked-out ``main`` and a clean worktree;
2. refuse an existing remote tag before any fetch;
3. fetch ``origin main`` (updates ``refs/remotes/origin/main`` only);
4. require local ``main`` == ``origin/main`` (no stale/diverged main);
5. verify ``HEAD`` is the exact release commit: its subject is
   ``chore(release): vX.Y.Z`` matching ``project/state.yaml.template.version``
   and the version was actually changed by that commit;
6. refuse an existing local tag;
7. create an annotated ``vX.Y.Z`` tag pointing at ``HEAD``.

Tagging creates no commit and never rewrites history. Publication stays an
explicit human action that pushes ONLY the intended tag:

``git push origin vX.Y.Z``

A tag-following push of ``main`` is deliberately not recommended: ``main`` was
already published by the PR merge and a tag-following push can publish
unrelated annotated tags.

Failure semantics
-----------------

Prepare: a state-write or commit failure restores ``project/state.yaml`` and
the index to the pre-command state. HEAD never moves and no tag is created.

Tag: annotated-tag creation happens only after every validation passed. A
failure leaves HEAD, ``project/state.yaml``, the worktree, and the tag list
unchanged.

Test-only fault injection mirrors the ``PROJECT_TOOL_FAIL_*`` seams:

* ``TEMPLATE_RELEASE_PREPARE_FAIL_STATE=1``: fail while writing the candidate
  state during prepare;
* ``TEMPLATE_RELEASE_PREPARE_FAIL_COMMIT=1``: fail while creating the release
  commit during prepare;
* ``TEMPLATE_RELEASE_FAIL_TAG=1``: fail while creating the annotated tag
  during tag.
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


def git_head_subject() -> str:
    return command_output(["git", "log", "-1", "--pretty=%s"])


def git_has_parent() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD^"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def git_tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--quiet", "--verify", f"refs/tags/{tag}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def git_origin_tag_exists(tag: str) -> bool:
    """Return whether origin already has refs/tags/<tag>.

    Raises when the remote cannot be queried: tagging must never proceed
    without remote collision safety.
    """
    result = subprocess.run(
        ["git", "ls-remote", "origin", f"refs/tags/{tag}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip()
        raise ReleaseError(
            f"Could not query origin for tag {tag}; refusing to tag without remote "
            f"collision safety. Fix the origin remote and retry. ({output})"
        )
    return bool(result.stdout.strip())


def fetch_origin_main() -> None:
    """Fetch origin main into refs/remotes/origin/main only.

    Never merges, rebases, or mutates local branches.
    """
    print("Fetching origin main (remote-tracking ref only; local main is not mutated).")
    try:
        run_command(["git", "fetch", "origin", "main"])
    except ReleaseError as exc:
        raise ReleaseError(
            "Could not fetch origin/main to verify freshness. Check the origin remote "
            "and network, then retry. " + str(exc)
        ) from exc


def git_remote_tracking_sha() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_is_ancestor(ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


def git_config_value(name: str) -> str:
    return command_output(["git", "config", "--get", name], check=False)


def git_file_version(project: Any, rev: str) -> str | None:
    """Return template.version recorded in project/state.yaml at Git rev, if any."""
    result = subprocess.run(
        ["git", "show", f"{rev}:project/state.yaml"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        data = project.parse_simple_yaml(result.stdout)
    except Exception:
        return None
    version = data.get("template", {}).get("version", "")
    return str(version) if version else None


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
    """Restore state file content and index after an aborted prepare mutation.

    Never touches branch refs or tags. The original file mode is restored too,
    so an aborted prepare cannot leave a mode-only working-tree change behind.
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


def perform_prepare_mutation(
    project: Any,
    state: dict[str, Any],
    next_version: str,
) -> None:
    """Create the normal release commit on the current (non-main) branch.

    Order: write+stage state -> create the release commit with plain ``git
    commit``. No tag is created and no ref is moved except the release branch's
    own commit. A failure restores state and index to the pre-command state.
    """
    commit_message = f"chore(release): {next_version}"
    original_state = copy.deepcopy(state)
    candidate = copy.deepcopy(state)
    candidate["template"]["version"] = next_version
    branch = git_current_branch()
    head_before = git_head_sha()
    phase = "update project/state.yaml.template.version"
    state_mode = state_file_mode()
    try:
        write_state_preserving_mode(project, candidate, state_mode)
        inject_failure("TEMPLATE_RELEASE_PREPARE_FAIL_STATE", "update project state")
        run_command(["git", "add", str(STATE_REL)])
        phase = "create the release commit"
        inject_failure("TEMPLATE_RELEASE_PREPARE_FAIL_COMMIT", "create the release commit")
        run_command(["git", "commit", "-q", "-m", commit_message])
        if git_head_sha() == head_before:
            raise ReleaseError("release commit was not created on the branch")
    except ReleaseError as exc:
        problems = restore_release_mutation(project, original_state, state_mode)
        cleanup = ""
        if problems:
            cleanup = " Cleanup problems: " + " ".join(problems)
        raise ReleaseError(
            f"{phase} failed: {exc}. The prepare was aborted: branch {branch} still "
            f"points to {head_before[:12]}, the index was restored, and "
            f"project/state.yaml was restored to its pre-command content. No tag "
            f"was created.{cleanup}"
        ) from exc


def require_clean_worktree() -> None:
    if git_worktree_dirty():
        raise ReleaseError(
            "Git worktree must be clean before a template release step. Commit or "
            "stash the pending changes first."
        )


def require_git_identity() -> None:
    if not git_config_value("user.email") or not git_config_value("user.name"):
        raise ReleaseError("Git user.name and user.email must be configured before release.")


def prepare_template_release(*, bump: str, dry_run: bool) -> None:
    project = load_project_tool()
    state = project.read_state()
    if state.get("project", {}).get("type") != "template":
        raise ReleaseError(
            "Template releases are only supported in the template repository "
            "(project.type=template)."
        )
    current_version = str(state.get("template", {}).get("version", ""))
    next_version = bump_template_version(current_version, bump)

    branch = git_current_branch()
    if branch == "HEAD":
        raise ReleaseError(
            "template-release-prepare cannot run from a detached HEAD. Check out a "
            "release branch first."
        )
    if branch == "main":
        raise ReleaseError(
            "template-release-prepare must run on a release branch, not on 'main'. "
            "A version bump is a normal reviewed repository change and may never be "
            "committed directly to main. Create a release branch first, for example "
            f"'git switch -c release/{next_version}', then run "
            "'make template-release-prepare' again."
        )
    if git_tag_exists(next_version):
        raise ReleaseError(f"Git tag {next_version} already exists.")
    require_clean_worktree()
    require_git_identity()

    print(f"Preparing template release {current_version} -> {next_version} ({bump}) on branch {branch}.")
    run_command(["make", "release-check"])
    require_clean_worktree()
    if dry_run:
        print(f"Dry run only. No state change, commit, or tag was created for {next_version}.")
        return

    candidate = copy.deepcopy(state)
    candidate["template"]["version"] = next_version
    errors = project.validate_candidate(candidate, project.load_tasks())
    if errors:
        raise ReleaseError("Candidate release state is invalid:\n" + "\n".join(errors))

    perform_prepare_mutation(project=project, state=state, next_version=next_version)
    print(
        f"Prepared template release {next_version} on branch {branch}. "
        f"Commit 'chore(release): {next_version}' was created; no tag was created "
        "and nothing was pushed. Push this branch, open a pull request, and let "
        "CI and human review merge it to main. After the merge, update local main "
        "and run 'make template-release-tag'."
    )


def tag_template_release() -> None:
    project = load_project_tool()
    state = project.read_state()
    if state.get("project", {}).get("type") != "template":
        raise ReleaseError(
            "Template releases are only supported in the template repository "
            "(project.type=template)."
        )

    branch = git_current_branch()
    if branch == "HEAD":
        raise ReleaseError(
            "template-release-tag cannot run from a detached HEAD. Check out main first."
        )
    if branch != "main":
        raise ReleaseError(
            f"template-release-tag must run on 'main' after the release PR is merged, "
            f"not on branch '{branch}'. Tagging is a post-merge release step; it never "
            "creates commits and grants no exception to the PR-only main rule."
        )
    require_clean_worktree()
    require_git_identity()

    current_version = str(state.get("template", {}).get("version", ""))
    parse_template_version(current_version)
    expected_subject = f"chore(release): {current_version}"

    # Remote collision safety runs first: a later fetch would auto-follow an
    # existing remote tag into the local tag list and hide the remote check.
    if git_origin_tag_exists(current_version):
        raise ReleaseError(
            f"Tag {current_version} already exists on origin. A release tag is never "
            "overwritten; delete or rename the remote tag only with explicit human intent."
        )

    fetch_origin_main()
    head = git_head_sha()
    remote_main = git_remote_tracking_sha()
    if remote_main is None:
        raise ReleaseError(
            "Could not verify refs/remotes/origin/main after fetch. Local main must "
            "equal origin/main before the release can be tagged."
        )
    if head != remote_main:
        if git_is_ancestor(head, remote_main):
            detail = "local main is behind origin/main; update it first (git fetch origin main, then git merge --ff-only origin/main or git pull --ff-only)"
        elif git_is_ancestor(remote_main, head):
            detail = "local main is ahead of origin/main (it contains commits not on origin); the release commit must first reach origin/main through a pull request merge"
        else:
            detail = "local main and origin/main have diverged; reconcile them before tagging"
        raise ReleaseError(
            f"Refusing to tag: local main ({head[:12]}) does not match origin/main "
            f"({remote_main[:12]}). {detail}. The tag command never fetches-and-merges "
            "or rewrites branches; update local main explicitly and retry."
        )

    head_version = git_file_version(project, "HEAD")
    if head_version != current_version:
        raise ReleaseError(
            f"project/state.yaml at HEAD does not record version {current_version}. "
            "Refusing to tag an unexpected release state."
        )
    subject = git_head_subject()
    if subject != expected_subject:
        raise ReleaseError(
            f"Refusing to tag: HEAD subject is '{subject}', expected "
            f"'{expected_subject}'. The release tag must point to the exact release "
            "commit that the release PR merged to main."
        )
    if not git_has_parent():
        raise ReleaseError(
            "Refusing to tag: HEAD has no parent, so the version change cannot be "
            "verified as a committed release change."
        )
    parent_version = git_file_version(project, "HEAD^")
    try:
        parse_template_version(parent_version or "")
    except ReleaseError as exc:
        raise ReleaseError(
            "Refusing to tag: could not read a valid previous template version from "
            "HEAD^. The version change must be an ordinary committed change. " + str(exc)
        ) from exc
    if parent_version == current_version:
        raise ReleaseError(
            "Refusing to tag: HEAD does not change template.version (its parent already "
            f"records {current_version}). The release tag must point to the commit that "
            "performed the version bump."
        )
    if parse_template_version(current_version) <= parse_template_version(str(parent_version)):
        raise ReleaseError(
            f"Refusing to tag: version did not advance ({parent_version} -> "
            f"{current_version})."
        )
    if git_tag_exists(current_version):
        raise ReleaseError(f"Git tag {current_version} already exists locally.")

    inject_failure("TEMPLATE_RELEASE_FAIL_TAG", "create the annotated release tag")
    tag_message = f"Template release {current_version}"
    run_command(["git", "tag", "-a", current_version, "-m", tag_message, "HEAD"])
    print(
        f"Created annotated tag {current_version} at {head[:12]} on main. "
        "No commit was created and project state was not modified. Publish ONLY "
        f"this tag with: git push origin {current_version}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Template-maintainer release workflow (two-phase, PR-only main)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Phase 1: create the reviewable release version commit on a non-main branch.",
    )
    prepare_parser.add_argument("--bump", choices=sorted(BUMP_TYPES), default="patch")
    prepare_parser.add_argument("--dry-run", action="store_true")
    subparsers.add_parser(
        "tag",
        help="Phase 2: create the annotated release tag on the merged main release commit.",
    )
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare_template_release(bump=args.bump, dry_run=args.dry_run)
        else:
            tag_template_release()
    except ReleaseError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
