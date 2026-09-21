---
id: T-029

title: Make PR-mode derived project state post-merge consistent

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

# T-029: Make PR-Mode Derived Project State Post-Merge Consistent

## Goal

Give PR-mode completion one coherent source-of-truth model so a merged task is
interpreted as complete without any post-merge lifecycle command, sync commit,
or cleanup pull request, and without leaving committed generated Markdown in a
state that validation must call stale.

## Context

PR mode derives A1/A2 completion from Git provenance: the persisted task record
stays `review`/`pending` and the record's presence on the base branch is the
completion evidence. Generated Markdown (`README.md` status block,
`project/index.md`, `project/board.md`) previously persisted that derived result,
which is impossible to keep correct: the pull request must render the task as
awaiting merge, and the human merge cannot rewrite the committed snapshot.

Real evidence on `main` after PR #15 merged:

- `project/tasks/T-027-*.md` is still `review`/`pending` and correctly derives as
  done through `task_merge_completed()`.
- `project/board.md` and the README status block still said "awaiting human
  GitHub merge" for T-027.
- `make validate-project` failed with four stale-block errors and asked for
  `make sync-project-docs`, i.e. the lifecycle-only reconciliation commit that
  issue #9 removed.

The model therefore separates canonical state, derived runtime presentation, and
committed deterministic documentation instead of treating a committed dashboard
as a second lifecycle database.

## Scope

- Classify artifacts as canonical (`project/tasks/*.md`, `project/state.yaml`,
  Git provenance), derived at read time (effective status, waiting state,
  dependency completion, next action, live board), and committed generated
  documentation (deterministic subset only).
- In `workflow_mode: pr`, stop persisting Git-relative status rows in
  `README.md`, `project/index.md`, and `project/board.md`, and render the live
  merge-aware status, board, and next action at read time with
  `make project-status`.
- Keep `effective_status()`, `task_merge_completed()`, and `dependencies_done()`
  as the single canonical derivation path used by dependencies, validation,
  dashboards, and the agent CLI.
- Keep drift validation exact for persisted deterministic content and reject
  re-introduced Git-relative rows in committed blocks.
- Update generated templates, canonical lifecycle documentation, the
  documentation skill, upgrade guidance, and the changelog.
- Replace the previous post-merge test that synced first with clean-repository
  before/after-merge regression coverage.

## Out of Scope

- Issue #17 / open PR #20 implementation, issue #19 `project.py` refactor, #18
  multi-agent support, #11/#12/#13 architecture work, and any GitHub
  synchronization service, bot commit, webhook, API state, or state cache.
- Broad `project.py` refactoring; only the small extraction needed to separate
  persisted from runtime rendering.
- Deleting `project/board.md`, `project/index.md`, or the README status block,
  and changing `local`/`branch` offline completion semantics.

## Acceptance Criteria

- [x] Before a merge, an A1 review task in `workflow_mode: pr` keeps persisted
      status `review`, derives effective status `review`, reports
      `Awaiting human GitHub merge`, and keeps dependent tasks blocked.
- [x] After the human merge, the same unmodified task record derives effective
      status `done`, unblocks dependents for `task-ready`/`task-start`, and is
      reported truthfully by `make project-status` without editing any file.
- [x] Normal status/validation commands after merge require no modification of
      tracked files, and `make sync-project-docs` is a no-op.
- [x] Committed generated blocks still fail drift validation when genuinely
      stale, and merge-derived status cannot be persisted in `pr` mode.
- [x] Merge commit, squash, and fast-forward/rebase histories behave
      identically, and `local`/`branch` keep the explicit human
      `task-approve` + `task-complete` persisted completion path.
- [x] A2 keeps human approval before start plus the human merge as completion
      boundary; agents still cannot manufacture A1 approval.
- [x] The T-027 case is interpreted as completed on `main` through the general
      model, with no T-027-specific code or task-record rewrite.
- [x] Focused and full checks pass and documentation explains the ownership
      model.

## Verification

- Defect reproduced before the fix on a branch cut from `main` at `5a182b6`:
  `make validate-project` exited 2 with `README.md`, `project/index.md`, and
  `project/board.md` "generated block is stale" errors plus a stale README
  dashboard error, although `project/tasks/T-027-*.md` was already merged.
- After the fix the same `main`-based checkout validates cleanly with T-027
  still persisted as `review`/`pending`: `make project-status` reports
  `Last completed task | [T-027]` and lists T-027 under Done as
  `completed by merged Git provenance`, while the committed board keeps only
  persisted records and points at the live view.
- `tests/test_project_state_validation_golden_path.py` focused run:
  before/after-merge coverage, deterministic-only drift, and merge-strategy
  independence pass (`test_github_pr_a1_merge_lifecycle_needs_no_cleanup`,
  `test_pr_mode_committed_blocks_stay_deterministic`,
  `test_task_merge_completed_is_merge_strategy_independent`).
- `tests/test_template_static.py` focused run:
  `test_pr_mode_generated_project_commits_deterministic_status_only` proves a
  freshly rendered `pr` project validates and that `make sync-project-docs` is a
  no-op, and `test_github_merge_approval_lifecycle_is_rendered_consistently`
  proves the maintainer repository no longer commits Git-relative rows.
- `make agent-pre-review TASK=T-029` (diff safety plus the canonical `make check`
  gate) result is recorded in the pull request.

## Documentation Impact

Implemented. Generated lifecycle docs (`.agents/skills/update-documentation`,
`docs/workflow`, `AGENTS.md`, `README.md`), the root agent/workflow guidance,
`UPGRADING.md`, `CHANGELOG.md`, and `docs/template-development.md` now state
which artifact is canonical, which is derived at read time, and why
merge-derived completion is never persisted.

## Completion Notes

Implementation is review-ready. This task record stays at `review` with
`approval_status: pending` by design; the human GitHub merge of its pull request
is the completion boundary and no post-merge lifecycle or synchronization commit
is required.
