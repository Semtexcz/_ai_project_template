---
name: complete-task
version: 1
purpose: Complete one task after DoD and approval requirements are met.
triggers: [complete task, close task, task done]
inputs:
  required:
    - task_id
reads:
  - project/state.yaml
  - project/tasks/{{ task_id }}*.md
commands:
  - make task-complete
  - make agent-post-task
  - make validate-project
outputs:
  - completed task
  - synchronized dashboards
  - deterministic next action
approval_boundary:
  may_approve: false
stop_conditions:
  - missing DoD evidence
  - missing A1 or A2 human approval
  - stale dashboards
  - invalid project state
---

# Complete Task

Use `make task-complete TASK=<id>` only when the project CLI allows it. For A1
and A2 tasks, stop until a human records approval. Run post-task checks after
completion.
