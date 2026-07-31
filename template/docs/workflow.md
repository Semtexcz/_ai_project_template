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

Select a ready task -> load minimal context -> verify scope -> design the smallest coherent change -> implement -> test -> self-review -> human review when required -> merge -> release when relevant -> observe -> update project state.

## Task Lifecycle

Use the deterministic commands instead of editing task status by hand:

```bash
make project-status
make task-ready TASK=T-001
make task-start TASK=T-001
make task-review TASK=T-001
make task-complete TASK=T-001
make task-block TASK=T-001 REASON="..." UNBLOCK="..."
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

- Load `AGENTS.md`, `project/state.yaml`, `project/index.md`, and the active task first.
- Use `.agents/context-map.yaml` for additional context.
- Do not run `make task-approve`; approval commands are for humans only.
- Do not bypass task transitions by silently editing status.
- Prefer the smallest reversible change.

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

## Blocked Tasks

Blocked tasks require `blocked_reason` and `unblock_action`. A blocked task
cannot be the active task and is never selected as the next startable task.

## Release and Post-Release

Local projects may stop at verified checks. Shared and production projects need release notes, rollback notes, and post-release verification appropriate to their runtime level.
