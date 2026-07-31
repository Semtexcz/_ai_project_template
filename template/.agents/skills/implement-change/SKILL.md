---
name: implement-change
version: 1
purpose: Implement the active task with the smallest coherent change.
triggers: [implement task, make change, code task]
inputs:
  required:
    - task_id
reads:
  - AGENTS.md
  - .agents/context-map.yaml
  - project/state.yaml
  - project/tasks/{{ task_id }}*.md
commands:
  - make agent-context
  - make agent-pre-task
  - make check
outputs:
  - scoped code or documentation change
  - verification results
approval_boundary:
  may_approve: false
stop_conditions:
  - task is not active
  - scope requires higher approval
  - context map is invalid
  - focused checks fail
---

# Implement Change

Agent judgment chooses the smallest implementation that satisfies the task.
Deterministic commands provide context, status, and checks. Do not change task
status except through the project CLI.
