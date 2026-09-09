---
name: prepare-task
version: 1
purpose: Prepare one managed task for implementation.
triggers: [prepare task, make task ready, definition of ready]
inputs:
  required:
    - task_id
reads:
  - AGENTS.md
  - project/state.yaml
  - project/tasks/{{ task_id }}*.md
commands:
  - make validate-project
  - make task-ready
outputs:
  - prepared task
  - recommended next command
approval_boundary:
  may_approve: false
stop_conditions:
  - missing task
  - incomplete Definition of Ready
  - unmet dependencies
  - missing A2 approval before start
---

# Prepare Task

Fill Goal, Context, Scope, Out of Scope, Acceptance Criteria, Verification, and
Documentation Impact. Keep the record concise and durable: state the intent,
scope, and reproducible verification, then stop. Do not turn the task file into
an execution journal; transient detail belongs in commits and review
discussion. Use `make task-ready TASK=<id>` for the transition.
