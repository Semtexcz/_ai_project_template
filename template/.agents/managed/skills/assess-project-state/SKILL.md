---
name: assess-project-state
version: 1
purpose: Summarize managed project state and return one next action.
triggers: [assess state, resume work, project status]
inputs:
  required: []
reads:
  - AGENTS.md
  - project/state.yaml
  - project/index.md
  - project/board.md
commands:
  - make agent-status
  - make validate-project
outputs:
  - state summary
  - one recommended next command
approval_boundary:
  may_approve: false
stop_conditions:
  - invalid project state
  - stale dashboards
  - blocked active task
---

# Assess Project State

Run `make agent-status`. It uses the project next-action algorithm, so do not
invent a second prioritization model. If validation fails, fix that before
choosing or starting work.
