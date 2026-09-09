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
Project status derives pr-mode A1/A2 tasks in `review` as pending until their
human GitHub merge, and as completed by Git provenance after that merge; do not
plan follow-up approval or cleanup tasks for them.
