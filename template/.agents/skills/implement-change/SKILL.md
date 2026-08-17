---
name: implement-change
version: 1
purpose: Implement a requested change with the smallest coherent repository diff.
triggers: [implement change, make change, code task, implement task]
inputs:
  required:
    - requested_change
reads:
  - AGENTS.md
  - .agents/context-map.yaml
  - project/brief.md
  - docs/architecture.md
  - docs/workflow.md
  - docs/quality.md
  - docs/decisions/
commands:
  - make validate-docs
  - make validate-agent-skills
  - make check
outputs:
  - scoped code or documentation change
  - verification results
approval_boundary:
  may_approve: false
stop_conditions:
  - requested change is ambiguous
  - scope requires higher approval
  - context map is invalid
  - focused checks fail
---

# Implement Change

Use durable project context first, then inspect only the files needed for the
requested change. In managed projects, include active-task context when it is
available, but do not make implementation depend on a task id.

Choose the smallest coherent implementation that preserves architecture
invariants. Prefer existing patterns and helpers over new abstractions. Run
focused checks while working, then finish with the relevant repository checks.
Do not mutate task state from this skill.

Before extending an existing Python module, perform a module-responsibility
check:

- Identify the module's current primary responsibility.
- Decide whether the requested behavior belongs to that responsibility.
- Inspect the module's approximate size.
- Prefer extracting a cohesive module when the change introduces a new
  responsibility.
- Explicitly consider decomposition when the resulting module would exceed 300
  LOC.
- Refuse artificial abstractions whose only purpose is reducing LOC.

Keep the change as small as possible, but make it the smallest coherent change:
cohesion and meaningful boundaries outrank raw line count.
