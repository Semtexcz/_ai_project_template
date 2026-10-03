---
id: T-036

title: Enforce per-change template releases

status: review

priority: 1

milestone: M-08

depends_on: [T-035]

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
- [x] A strict release-ready gate requires the newest changelog release to equal
      `template.version`, and Template CI runs it on every pull request.
- [x] A final read-only release-boundary gate proves `HEAD` itself introduces
      `template.version` relative to `HEAD^1`, and Template CI runs it after the
      release-ready gate.

## Verification

- `make validate-template-docs` passes and rejects an `Unreleased` section,
  malformed or non-descending release headings, an empty newest release section,
  and a newest version that is neither the current `template.version` nor
  exactly one `patch`/`minor`/`major` bump ahead.
- `make validate-template-release-ready` requires the newest changelog release to
  exactly equal `project/state.yaml.template.version`, and Template CI runs it
  after `make release-check`, so a change cannot ship a newer changelog version,
  skip `make template-release-prepare`, and still pass ordinary validation.
- `make validate-project`, `make validate-agent-skills`,
  `make validate-agent-layer`, and `make agent-pre-review TASK=T-036`
  (canonical `make check`) pass.
- `uv run pytest tests/test_template_release_workflow.py
  tests/test_template_changelog_policy.py` passes, covering both validation
  states: one pending bump passes ordinary validation, while the strict gate
  requires exact equality.
- `tests/test_copier_update_golden_path.py` now passes: its fixture regression
  was repaired, so no current `corepack` blocker is claimed.
- `make validate-template-release-boundary` is the final Git-history half of
  release readiness. It is read-only, works on the PR/task branch, requires
  `HEAD.template.version > HEAD^1.template.version`, rejects a version bump
  followed by another commit, and shares its core invariant with
  `make template-release-tag`.
- The `v1.2.0` version transition is the final commit of this release PR, so the
  branch tip itself introduces the release. Historically the bump was committed
  before later T-036 commits; that shape breaks rebase merges and is now
  machine-rejected.
- Release tests derive the current version from `project/state.yaml`, so future
  version bumps no longer break them.

## Documentation Impact

Root `AGENTS.md`, `README.md`, `docs/template-development.md`,
`docs/template-architecture.md`, `.agents/README.md`, and `CHANGELOG.md` now
state that every template change ships a version and a dated English changelog
entry with no `Unreleased` section. `docs/template-development.md` (and
`AGENTS.md`/`.agents/README.md`) also document the three validation boundaries:
the permissive ordinary changelog gate that allows one pending SemVer bump so
release preparation can run, the strict `make validate-template-release-ready`
state/content equality gate, and the final
`make validate-template-release-boundary` Git-history gate that requires the
branch tip itself to introduce the version transition. The release docs explain
that merge, squash, fast-forward, and rebase histories are supported only when
that transition commit is final, because a rebase replays PR commits in order.

## Completion Notes

`CHANGELOG.md` no longer has an `Unreleased` section; accumulated entries
(including the previously unrecorded T-035 role-based execution policy) are
consolidated under `## v1.2.0 - 2026-10-03` and the template version is bumped to
`v1.2.0`. `make validate-template-docs` validates the permissive changelog/version
contract, `make template-release-prepare` refuses a release whose newest
changelog section is not the version being prepared, and
`make validate-template-release-ready` (run by Template CI after
`make release-check`) proves final changelog/version equality, and
`make validate-template-release-boundary` proves the PR tip itself introduces
that version relative to `HEAD^1`, sharing its core invariant with
`make template-release-tag`. The `v1.2.0` transition is now the final commit of
this release PR. The Copier fixture regression was repaired;
`tests/test_copier_update_golden_path.py` passes locally.

This task was replayed onto the then-current `origin/main` after the original
branch was found to descend from a stale base. The replay reapplies only T-036
intent: it preserves T-031 through T-035 repository state, keeps the modern
`project/state.yaml` shape (no `work:` section), and changes only the intended
`template.version` field.
