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

- [x] `CHANGELOG.md` has no `Unreleased` section.
- [x] The top changelog release matches `project/state.yaml.template.version`.
- [x] Agent and maintainer documentation requires a SemVer bump and an English
      changelog entry for every template change.
- [x] Validation and focused tests reject invalid changelog/release contracts.

## Verification

- `make validate-template-docs` passes and rejects an `Unreleased` section,
  malformed or non-descending release headings, an empty newest release section,
  and a newest version that is neither the current `template.version` nor
  exactly one `patch`/`minor`/`major` bump ahead.
- `make validate-project`, `make validate-agent-skills`,
  `make validate-agent-layer`, and `make agent-pre-review TASK=T-036`
  (canonical `make check`) pass.
- `uv run pytest tests/test_template_release_workflow.py
  tests/test_template_changelog_policy.py` passes (35 + 12 tests).
- `make release-check` cannot pass in this environment:
  `tests/test_copier_update_golden_path.py` fails on the base commit too because
  `corepack` is unavailable. `make template-release-prepare` therefore could not
  run; the `v1.2.0` bump was applied as an equivalent `chore(release): v1.2.0`
  commit and CI must run the real release gate.
- Release tests now derive the current version from `project/state.yaml`, so
  future version bumps no longer break them.

## Documentation Impact

Root `AGENTS.md`, `README.md`, `docs/template-development.md`,
`docs/template-architecture.md`, `.agents/README.md`, and `CHANGELOG.md` now
state that every template change ships a version and a dated English changelog
entry with no `Unreleased` section.

## Completion Notes

`CHANGELOG.md` no longer has an `Unreleased` section; accumulated entries are
consolidated under `## v1.2.0 - 2026-10-03` and the template version is bumped to
`v1.2.0`. `make validate-template-docs` validates the changelog/version contract,
and `make template-release-prepare` refuses a release whose newest changelog
section is not the version being prepared.
