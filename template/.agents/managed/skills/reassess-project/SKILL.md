---
name: reassess-project
version: 1
purpose: Reassess phase, milestone, risks, and next gate after assumptions change.
triggers: [reassess project, stale project, review roadmap]
inputs:
  required: []
reads:
  - README.md
  - project/state.yaml
  - project/roadmap.md
  - project/board.md
commands:
  - make agent-status
  - make validate-project
outputs:
  - reassessment summary
  - one recommended next step
approval_boundary:
  may_approve: false
stop_conditions:
  - active task in progress
  - lifecycle change requires approval
  - invalid project state
---

# Reassess Project

Use this only when assumptions materially changed or the project became stale.
Do not change lifecycle scope or approvals without the required human decision.
Project status already derives pr-mode reviewed A1/A2 tasks as completed by the
human GitHub merge; do not mark them pending or plan follow-up approval or
cleanup tasks for them.
