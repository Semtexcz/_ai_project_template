---
name: choose-next-task
version: 1
purpose: Select exactly one managed task without parallel main work.
triggers: [choose task, next task, select work]
inputs:
  required: []
reads:
  - project/state.yaml
  - project/board.md
  - project/tasks/*.md
commands:
  - make agent-status
  - make validate-project
outputs:
  - selected task or one task proposal
  - stop reason when no task can start
approval_boundary:
  may_approve: false
stop_conditions:
  - active task already exists
  - blocked project
  - A2 approval required before start
  - no ready task exists
---

# Choose Next Task

Use the recommendation from `make agent-status`. Prefer completing or unblocking
existing work before proposing one small task for the current gate. In
`workflow_mode: pr`, A1/A2 tasks already in `review` are completed by the human
GitHub merge and are not next-task candidates; do not create lifecycle-only
approval or cleanup tasks for them.
