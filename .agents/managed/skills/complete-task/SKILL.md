---
name: complete-task
version: 1
purpose: Complete one managed task when the project CLI allows completion.
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

Check `project/state.yaml` first. In `workflow_mode: pr`, A1 and A2
implementation ends at `review`; the human GitHub merge of the pull request is
the completion boundary and `make task-complete` is not used for those tasks.
In `local`/`branch` mode, or for A0 tasks, use `make task-complete TASK=<id>`
when the project CLI allows it. For A1 and A2 in offline mode, stop until a
human records approval. Run post-task checks only where the CLI accepted the
completion.
