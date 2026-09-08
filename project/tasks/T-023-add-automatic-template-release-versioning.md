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

Add an explicit post-merge template release workflow that bumps the template
version and creates the matching Git tag required by Copier.

## Context

Generated projects rely on Copier tags for updates. The template currently has
release validation, but no controlled command that updates
`project/state.yaml.template.version` and creates the matching release tag.

## Scope

- Add a `make template-release` workflow backed by a template-maintainer-only
  tool (`tools/template_release.py`) outside the rendered template directory.
- Support explicit `BUMP=major|minor|patch`, defaulting to `patch`.
- Support `DRY_RUN=1` for validation and preview without mutation.
- Reject invalid versions, existing tags, dirty worktrees, and accidental
  non-main releases unless explicitly overridden.
- Run the existing release gate before mutating release state.
- Make release creation transactional so a tag-creation failure cannot leave a
  version commit without its intended tag.
- Keep template-maintainer release commands out of generated projects.
- Document the local-release vs publication boundary, release timing, and how
  agents choose the semantic version bump.
- Keep `make release-check`, task review, and task completion validation-only.

## Out of Scope

- Publishing packages or images.
- Adding external release infrastructure.
- Changing Copier ownership or generated project update semantics.

## Acceptance Criteria

- [x] `make template-release` prepares a local release: it validates, updates
  state, and creates the version commit and annotated Git tag only on `main`.
- [x] Dry-run mode previews the release without modifying tracked files or tags.
- [x] Release creation is transactional: tag-creation failure or branch-move
  failure leaves HEAD, tags, state, and the working tree unchanged, and no
  version commit remains without its intended tag.
- [x] A regression test simulates tag-creation failure after the version commit
  would otherwise succeed, using a temporary real Git repository.
- [x] Release tooling is maintainer-only (`tools/template_release.py`); generated
  projects do not expose `template-release` commands.
- [x] Documentation separates local release from publication and defines the
  post-merge/human authority boundary.
- [x] Copier update tests use the release workflow for the new template tag.
- [x] Documentation explains the agent bump policy and release timing.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_template_release_workflow.py`
  passed: 17 tests (bump matrix, invalid version, dirty worktree, existing tag,
  wrong branch, dry run, successful local release for patch/minor/major,
  release-check failure, injected commit/tag/branch failures, no partial state
  after failure, and generated-project isolation).
- `make validate-project` passed.
- `make validate-agent-skills` passed.
- `make validate-template-docs` passed.
- `UV_CACHE_DIR=/tmp/uv-cache make check` passed: 23 tests in 78.62s.
- The full `tests/test_copier_update_golden_path.py` Copier update golden path
  still cannot complete in this environment: it reaches the Copier update
  assertions and then fails in generated `make setup` because `corepack` is not
  installed. The release workflow portion (stubbed `release-check`) used by that
  test is covered by the release workflow tests above.

## Documentation Impact

Update template development and architecture documentation with the release
workflow, local-release vs publication semantics, and the bump policy.

## Completion Notes

`make template-release` is now backed by a maintainer-only
`tools/template_release.py` (outside the rendered template directory) and
prepares a local release: SemVer bumping, dry-run preview, Git release guards,
`make release-check`, candidate-state validation, then a transactional version
commit plus annotated tag. The tag is created before the branch ref moves, so a
tag-creation or branch-move failure restores HEAD, tags, state, and the working
tree and can never leave a version commit without its intended tag. The command
never pushes; documentation separates local release from the human
`git push origin main --follow-tags` publication step and defines releases as a
post-merge `main` operation. Release tooling no longer leaks into generated
projects. The template repository agent context map repair is retained.
