---
id: T-027

title: Simplify GitHub-backed A1 approval to the human PR merge

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

# T-027: Simplify GitHub-Backed A1 Approval to the Human PR Merge

## Goal

Redesign managed governance so a normal GitHub-backed A1 task requires exactly
one human approval action: the merge of the task's pull request. Remove the
repository-local `task-approve`/`task-complete`/sync/cleanup-PR lifecycle that
currently duplicates that GitHub authority decision.

## Context

Managed governance currently duplicates human approval: GitHub PR review/merge
plus repository-local task approval. A normal A1 change ends with
`task-review -> PR -> human approves -> task-approve -> task-complete ->
sync-project-docs -> lifecycle commit -> merge`, and this has caused repository
state to diverge from GitHub reality. GitHub should be the primary human
approval boundary for normal A1 work, while agents must still never approve
their own governed work.

## Scope

- Make `workflow_mode: pr` (GitHub-backed managed projects) treat the human
  GitHub merge of a task's pull request as the A1 approval/completion boundary,
  and as A2's completion boundary while A2 keeps its explicit pre-start human
  approval.
- Keep the repository task record deterministic without post-merge mutations:
  A1/A2 implementation ends at `review`, `approval_status: pending` is
  documented as local pre-merge state only, and boards/dashboards derive the
  completed post-merge view so no cleanup commit or pull request is required.
- Reject A1 `task-approve` and A1/A2 `task-complete` in `workflow_mode: pr` so
  agents cannot manufacture approval or use completion as a loophole.
- Add a deterministic PR-to-task association (exactly one `T-###` across branch
  name, title, and body) plus pre-merge structural validation
  (`make pr-validate`) run by CI on governed pull requests.
- Preserve the `local`/`branch` offline fallback (`make task-approve` then
  `make task-complete`, humans only) and keep historical `done` approval
  metadata valid without rewriting task history.
- Update canonical agent guidance (`.agents/`, `AGENTS.md`, generated docs),
  migration guidance, and focused regression tests.

## Out of Scope

- Cline adapter implementation, Python/frontend engineering contracts, or
  documentation-architecture redesign.
- Agent Efficiency redesign, broad CI performance redesign, or release-workflow
  redesign unrelated to approvals.
- A GitHub synchronization service, persistent GitHub state cache, webhook
  server, workflow engine, database, or event-sourcing subsystem.
- Rewriting historical task files or weakening the one-active-task invariant.

## Acceptance Criteria

- [x] A normal GitHub-backed A1 task has exactly one human approval boundary:
      the human GitHub PR merge.
- [x] `make task-approve` and `make task-complete` are not required (and are
      rejected) for A1/A2 in `workflow_mode: pr`; no lifecycle-only cleanup PR
      is required after merge.
- [x] Agents still cannot self-approve A1/A2 or manufacture approval evidence.
- [x] Task/PR association is deterministic (one `T-###` in branch/title/body)
      and `make pr-validate` passes only for structurally ready pull requests.
- [x] Merge commit, squash, and rebase/fast-forward strategies do not change
      lifecycle semantics.
- [x] `local`/`branch` projects keep the explicit human offline fallback.
- [x] A2 keeps its stronger pre-start human approval in `pr` mode.
- [x] Historical `done` tasks using old approval metadata remain valid; no task
      history is rewritten.
- [x] Project dashboards/reconciliation cannot remain misleading after a valid
      merge and require no lifecycle-only follow-up PR.
- [x] Lightweight governance is unaffected and focused regression tests pass.

## Verification

Before the human merge, this task intentionally stays on the PR branch as
`status: review` / `approval_status: pending`; no local `task-approve` or
`task-complete` was run and none may be run in `workflow_mode: pr`.

- Effective status is derived from Git base provenance, never from `review`
  alone: `template/tools/project.py` implements one canonical helper that asks
  whether the review-ready A1/A2 task record is present in the authoritative
  base tree (`HEAD` on `main`/`master`, else `origin/main`/`origin/master`,
  else local `main`/`master`). Merge commits, squash merges, and
  rebase/fast-forward merges all behave identically because the helper does not
  inspect merge commits or commit messages.
- Pre-merge regression coverage: an A1 task in `review` is rendered as
  `awaiting human GitHub merge` on the board/dashboard, `waiting_text` and the
  recommended next action report the merge wait (no `make task-approve`
  recommendation), `last_completed_task` stays on the previous task, and a
  dependent task (`T-003` depending on `T-002`) remains blocked for both
  `task-ready` and `task-start`.
- Post-merge regression coverage: after the review-ready record is merged onto
  `main`, the derived view moves the task to Done, the dependent task becomes
  ready/startable, and `make sync-project-docs` plus `make validate-project`
  remain no-ops with a clean worktree. No post-merge lifecycle commit or
  cleanup pull request is produced.
- Merge-strategy coverage proves the same derivation for `--no-ff` merge,
  squash, and `--ff-only` histories.
- The `_ai_project_template` maintainer state now explicitly sets
  `project.workflow_mode: pr` (static regression test), so this repository
  dogfoods the reviewed lifecycle; already-merged historical review records
  (T-016/T-017/T-018) derive as Done from main provenance without rewriting
  their task metadata.
- Focused regression suites pass: `make check` (32 passed: template static 19,
  project-state lifecycle 13 including the GitHub PR lifecycle,
  before/after-merge dependency blocking, merge-strategy independence,
  self-approval rejection, A2 pre-start approval, deterministic PR
  association, historical metadata, and offline fallback), plus the branch-mode
  agent one-task workflow golden path (4 passed).
- `make release-check` (full pytest) result and the latest complete GitHub
  Actions run are recorded in the pull request once green.

## Documentation Impact

Update the durable managed lifecycle, human-vs-agent authority, pr-mode flow,
offline fallback, A2 distinction, project-state semantics, and upgrade
guidance.

## Completion Notes

Implementation is review-ready and opened as the issue #9 pull request.
Completion remains pending the human GitHub merge; this task record stays at
`review` / `approval_status: pending` by design and requires no post-merge
lifecycle mutation.
