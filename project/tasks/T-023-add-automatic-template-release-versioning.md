---
id: T-023

title: Add automatic template release versioning

status: review

priority: 1

milestone: M-08

depends_on: []

approval_level: A1

approval_status: pending

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-023: Add Automatic Template Release Versioning

## Goal

Add a two-phase template release workflow that bumps the template version and
creates the matching annotated Git tag required by Copier, while preserving the
repository's PR-only `main` governance.

## Context

Generated projects rely on Copier tags for updates. The template currently has
release validation, but no controlled workflow that updates
`project/state.yaml.template.version` and creates the matching release tag
without bypassing the pull-request rule for commits to `main`. CI's
`require-pr-for-main` guard requires every commit reaching `main` to come from
a pull request, so a release version bump must be an ordinary reviewed
repository change; only the release tag is created after the merge.

## Scope

- Phase 1 `make template-release-prepare BUMP=major|minor|patch` (default
  `patch`): on a non-`main` release branch, run the release gate, update
  `project/state.yaml.template.version`, and create an ordinary
  `chore(release): vX.Y.Z` commit. Create no tag, push nothing, and refuse to
  run on `main`.
- Phase 2 `make template-release-tag`: after the release PR is merged, run on
  clean `main`, fetch `origin main` (remote-tracking ref only), require local
  `main` == `origin/main`, verify `HEAD` is the exact release commit, refuse
  existing local and remote tags, and create an annotated `vX.Y.Z` tag at
  `HEAD`. Tagging creates no commit and never rewrites history.
- Remove direct-main release behavior: no version commit created directly on
  `main`, no `git update-ref` ref advancement by release tooling, and no
  `--follow-tags` publication recommendation. Publication is the explicit
  `git push origin vX.Y.Z`.
- Keep the transaction safety properties: prepare failures restore
  `project/state.yaml` and the index; tag failures happen before any mutation.
- Keep template-maintainer release commands out of generated projects.
- Document the PR-only release lifecycle, release-state validation, and
  exact-tag publication.
- Keep `make release-check`, task review, and task completion validation-only.
- Keep CI's `require-pr-for-main` guard unchanged and exception-free.

## Out of Scope

- Publishing packages or images.
- Adding external release infrastructure.
- Changing Copier ownership or generated project update semantics.

## Acceptance Criteria

- [x] `make template-release-prepare` refuses `main`, creates the reviewable
  `chore(release): vX.Y.Z` commit on a non-`main` release branch, creates no
  tag, and pushes nothing.
- [x] Prepare supports `patch`/`minor`/`major` and `DRY_RUN=1` and fails
  cleanly on invalid versions, invalid bumps, dirty worktrees, existing target
  tags, and release-gate failure; a prepare failure restores state and index
  with no partial release commit.
- [x] `make template-release-tag` requires clean `main`, fetches `origin main`,
  requires local `main` == `origin/main`, verifies the exact release commit via
  subject and state transition, refuses existing local and remote tags, and
  creates an annotated tag on the merged release commit without creating
  commits or touching project state.
- [x] Tag phase rejects non-`main`, dirty worktrees, unexpected or missing
  release commits, mismatched state versions, existing local/remote tags, and
  stale, ahead, or diverged local `main`.
- [x] Direct release commits to `main`, `git update-ref` ref advancement by
  release tooling, and the `git push origin main --follow-tags` recommendation
  are removed.
- [x] CI `require-pr-for-main` remains unchanged with no release exception.
- [x] Real-Git tests use a temporary bare remote to exercise prepare -> PR
  merge -> tag -> publish only the intended tag.
- [x] Release tooling is maintainer-only (`tools/template_release.py`);
  generated projects do not expose template-release commands.
- [x] Documentation explains the PR-only two-phase lifecycle, release-state
  validation, failure behavior, and exact-tag publication.

## Verification

- `tests/test_template_release_workflow.py` passes: 30 tests with real temporary
  Git repositories and a bare remote. Prepare coverage includes patch/minor/major
  bumps, invalid version, invalid bump, dirty worktree, rejection on `main`,
  dry run, existing tag, release-check failure, injected state/commit failures,
  and generated-project isolation. Tag coverage includes rejection off `main`,
  dirty worktree, unexpected/missing release commit, mismatched state version,
  existing local tag, existing remote tag, stale and diverged local `main`,
  exact annotated tag creation, no new commit, unchanged state, injected tag
  failure, and publication of only the intended tag with unrelated local tags
  left unpushed.
- `make validate-project`, `make validate-agent-skills`,
  `make validate-template-docs`, and `make check` pass.
- The full `tests/test_copier_update_golden_path.py` Copier update golden path
  still cannot complete in this environment: it reaches the Copier update
  assertions and then fails in generated `make setup` because `corepack` is not
  installed. Its release portion now exercises the two-phase flow (prepare on a
  release branch, simulated PR merge through a bare origin, tag on main).
- Generated lightweight and managed projects contain no maintainer release
  tooling.

## Documentation Impact

Update the root README, AGENTS, agent-layer readme, template development and
architecture docs, changelog, and this task with the two-phase release
workflow, release-state validation, publication, and bump policy.

## Completion Notes

Template releases now use a PR-only, two-phase flow backed by a maintainer-only
`tools/template_release.py` (outside the rendered template directory).
`make template-release-prepare` prepares an ordinary, reviewable version commit
on a release branch (no tag, no push, refuses `main`); the commit reaches
`main` through the normal pull request and human merge. After the merge,
`make template-release-tag` verifies clean, up-to-date `main`, confirms `HEAD`
is the exact `chore(release): vX.Y.Z` commit whose state changed from its
parent, refuses existing local/remote tags, and creates an annotated tag.
Tagging creates no commit; publication pushes only the intended tag. Release
tooling no longer leaks into generated projects. The template repository agent
context map repair is retained.
