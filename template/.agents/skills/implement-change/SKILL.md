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

Context routing stays with the tooling: `make agent-context` reads
`.agents/context-map.yaml`, resolves changed files and checks, and hands back the
result. An implementation session therefore does not eagerly load the routing
configuration or the Makefile just to re-interpret them; read them only when the
routing itself is what you are changing.

Choose the smallest coherent implementation that preserves architecture
invariants. Prefer existing patterns and helpers over new abstractions. Run
focused checks while working, then finish with the relevant repository checks.
Do not mutate task state from this skill.

When a managed project provides `make agent-handoff TASK=<id>`, use it only
when a large task must continue in a fresh session. Its task, branch, worktree,
and claim state persist while the conversation does not; a pull-request
association persists when the configured workflow uses one.

When a managed project provides focused resume input, use it only to narrow a
fresh session's working set; it must not change complete branch scope,
recommended checks, ownership, or governance.

Use focused checks while iterating. When the project provides a governed
pre-review gate, use that gate once instead of manually duplicating its full
check. After the local gate, follow the configured workflow boundary. In PR
workflows, CI is required but asynchronous; do not wait for or poll it from the
implementation session.
