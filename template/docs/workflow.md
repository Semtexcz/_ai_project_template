---
type: workflow
status: active
source_of_truth_for:
  - daily-change-loop
read_when:
  - implement-change
  - review-change
  - complete-task
update_when:
  - workflow-policy-change
---

# Workflow

## One Change Loop

Status -> select one task -> prepare -> start -> load minimal context -> verify
scope -> implement -> run checks -> pre-review -> human approval when required
-> complete -> post-task -> validate.

## Task Lifecycle

Use the deterministic commands instead of editing task status by hand:

```bash
make agent-status
make agent-context TASK=T-001
make agent-pre-task TASK=T-001
make project-status
make task-ready TASK=T-001
make task-start TASK=T-001
make agent-pre-review TASK=T-001
make task-review TASK=T-001
make task-complete TASK=T-001
make agent-post-task TASK=T-001
make task-block TASK=T-001 REASON="..." UNBLOCK="..."
make task-unblock TASK=T-001
make task-cancel TASK=T-001
make sync-project-docs
make validate-project
```

Allowed transitions are `backlog -> ready`, `ready -> in-progress`,
`in-progress -> review`, `in-progress -> blocked`, `review -> in-progress`,
`review -> done`, `blocked -> ready`, `blocked -> in-progress`, and cancellation
from any active state. A0 tasks may also move from `in-progress` directly to
`done` when Definition of Done is satisfied.

## Definition of Ready

- `Goal`, `Context`, `Scope`, `Out of Scope`, `Acceptance Criteria`,
  `Verification`, and `Documentation Impact` are non-empty.
- Dependencies exist and are done.
- The task is not blocked.
- A2 work has prior human approval before start.
- No other main task is `in-progress`.

## AI Agent Work

- Start with `make agent-status`.
- Work on a non-`main` branch before editing files.
- Use `make agent-context TASK=<id>` for the minimal context bundle.
- Use `.agents/context-map.yaml` for context routing.
- Use `.agents/skills/*/SKILL.md` for judgment and stop conditions.
- Do not run `make task-approve`; approval commands are for humans only.
- Do not bypass task transitions by silently editing status.
- Prefer the smallest reversible change.
- Run `make agent-pre-review TASK=<id>` before moving to review.
- Commit the agent's own changes, push the branch to `origin`, and open a ready
  GitHub pull request. Do not push directly to `main`.
- The CI guard for pushes to `main` is a signal; actual push blocking requires
  GitHub branch protection or a ruleset that marks the guard as a required
  check.

## Definition of Done

- Acceptance criteria use Markdown checkboxes and all are checked.
- Required tests pass.
- Documentation impact is handled.
- ADR impact is checked.
- Task, board, state, and README dashboard are synchronized.
- Completion Notes are filled in.
- A1 and A2 tasks have human approval before `done`.
- A deterministic next action is shown by `make project-status`.

## Approval Levels

- A0: no human approval required; use `approval_status: not-required`.
- A1: implementation can proceed, but `review -> done` requires human approval.
- A2: work cannot start until a human has explicitly approved it.

AI agents must not autonomously create human approvals. A human may record one
with:

```bash
make task-approve TASK=T-001 APPROVED_BY="Human Name"
```

All mutating task commands validate a candidate state, render dashboards, write
the control files together, and roll back if any step fails.

## Blocked Tasks

Blocked tasks require `blocked_reason` and `unblock_action`. A blocked task
cannot be the active task and is never selected as the next startable task. Use
`make task-unblock TASK=<id>` to return it to `ready` after the unblock action
is complete.

## Release and Post-Release

Local projects may stop at verified checks. Shared and production projects need release notes, rollback notes, and post-release verification appropriate to their runtime level.

For production full-stack projects, the minimum local release candidate check is:

```bash
make setup
make api-check
make check
make build
make image-build
make image-inspect
make prod-up
make prod-status
make prod-smoke
make e2e-production
make prod-down
```

Treat that as artifact readiness only. Actual deployment still needs a target
environment, secret handling, rollout and rollback ownership, and any required
A2 approval.
