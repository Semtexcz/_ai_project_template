---
name: orient-project
version: 1
purpose: Establish enough project context to work safely without loading the whole repository.
triggers: [orient project, understand repo, start work, resume work]
inputs:
  required: []
reads:
  - AGENTS.md
  - project/brief.md
  - docs/architecture.md
  - .agents/context-map.yaml
commands:
  - make validate-docs
  - make validate-agent-skills
outputs:
  - concise orientation
  - likely affected areas
  - validation commands
  - important unknowns
approval_boundary:
  may_approve: false
stop_conditions:
  - durable project context is missing
  - context map is invalid
  - requested work needs undisclosed credentials or secrets
---

# Orient Project

Read the durable project context before inspecting broad source trees. Produce a
concise orientation that covers the project goal, architecture, constraints,
applicable ADRs, likely affected areas, available validation commands, and
important unknowns.

Do not modify files. In managed projects, active-task context may enrich the
orientation when available, but orientation must still work without task state.
