---
name: review-change
version: 1
purpose: Prepare a scoped change for review.
triggers: [review change, pre review, ready for review]
inputs:
  required:
    - task_id
reads:
  - project/state.yaml
  - project/tasks/{{ task_id }}*.md
  - .agents/context-map.yaml
commands:
  - make agent-pre-review
  - make task-review
outputs:
  - review readiness result
  - verification evidence
approval_boundary:
  may_approve: false
stop_conditions:
  - wrong active task
  - unsafe diff
  - failing checks
  - missing acceptance evidence
---

# Review Change

Inspect the diff against the task scope, run `make agent-pre-review TASK=<id>`,
then use `make task-review TASK=<id>` when ready. Human approval remains outside
the agent boundary.
