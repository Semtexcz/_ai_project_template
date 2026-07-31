---
name: initialize-project
version: 1
purpose: Perform first project orientation after Copier generation.
triggers: [initialize project, first project setup]
inputs:
  required: []
reads:
  - AGENTS.md
  - project/state.yaml
  - project/index.md
  - project/brief.md
commands:
  - make agent-status
  - make sync-project-docs
  - make validate-project
outputs:
  - validated project orientation
  - one recommended next step
approval_boundary:
  may_approve: false
stop_conditions:
  - invalid project state
  - missing project brief
  - required A2 decision is not approved
---

# Initialize Project

Use the project status and generated project documents to orient the first task.
Keep long-term planning small and verifiable. Use `make sync-project-docs` and
`make validate-project` for deterministic updates and validation.
