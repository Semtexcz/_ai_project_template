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

- Add a `make template-release` workflow backed by the project tool.
- Support explicit `BUMP=major|minor|patch`, defaulting to `patch`.
- Support `DRY_RUN=1` for validation and preview without mutation.
- Reject invalid versions, existing tags, dirty worktrees, and accidental
  non-main releases unless explicitly overridden.
- Run the existing release gate before mutating release state.
- Document how agents choose the semantic version bump.
- Keep `make release-check`, task review, and task completion validation-only.

## Out of Scope

- Publishing packages or images.
- Adding external release infrastructure.
- Changing Copier ownership or generated project update semantics.

## Acceptance Criteria

- [x] `make template-release` computes the next template version, updates state,
  commits the release, and creates an annotated Git tag.
- [x] Dry-run mode previews the release without modifying tracked files or tags.
- [x] Failure cases leave state and tags unchanged.
- [x] Copier update tests use the release workflow for the new template tag.
- [x] Documentation explains the agent bump policy and release timing.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_template_release_workflow.py` passed.
- `make validate-agent-skills` passed.
- `make validate-project` passed.
- `make validate-template-docs` passed.
- `UV_CACHE_DIR=/tmp/uv-cache make check` passed after approved network access:
  23 tests in 440.72 seconds.
- `UV_CACHE_DIR=/tmp/uv-cache UV_LINK_MODE=copy uv run pytest
  tests/test_copier_update_golden_path.py::test_copier_update_golden_path`
  reached the Copier update assertions after approved network access, then
  failed in generated `make setup` because `corepack` is not installed in this
  environment.

## Documentation Impact

Update template development and architecture documentation with the release
workflow and bump policy.

## Completion Notes

Implemented `make template-release` and `project.py release-template` with
SemVer bumping, dry-run preview, Git release guards, release-check execution,
state commit, and annotated tag creation. Documented post-merge release timing
and the agent bump policy. Repaired the template repository agent context map
so required context paths exist.
