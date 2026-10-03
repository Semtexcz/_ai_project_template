---
id: T-036

title: Enforce per-change template releases

status: in-progress

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

# T-036: Enforce Per-Change Template Releases

## Goal

Make every template change a versioned release with an English changelog entry,
instead of accumulating changes under an `Unreleased` heading.

## Context

The template changelog currently keeps a single `Unreleased` section that
collects unrelated changes until a maintainer starts a release. That model lets
template changes ship without a version or changelog entry and makes the
changelog drift from `project/state.yaml.template.version`.

## Scope

- Remove the `Unreleased` changelog model.
- Require a dated changelog section for the current template version.
- Require agents to prepare a SemVer release for every template change.
- Validate the changelog/version contract and cover it with focused tests.

## Out of Scope

- Changing the existing PR-only release/tagging boundary.
- Publishing a release tag from this task.

## Acceptance Criteria

- [ ] `CHANGELOG.md` has no `Unreleased` section.
- [ ] The top changelog release matches `project/state.yaml.template.version`.
- [ ] Agent and maintainer documentation requires a SemVer bump and an English
      changelog entry for every template change.
- [ ] Validation and focused tests reject invalid changelog/release contracts.

## Verification

- Pending.

## Documentation Impact

Document the mandatory per-change versioning and changelog policy.

## Completion Notes

Pending.
