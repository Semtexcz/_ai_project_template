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

In managed projects, `make agent-handoff TASK=<id>` renders the compact,
deterministic state of the task this worktree owns. Use it when a large task must
continue in a fresh session: the task, branch, worktree, claim, and pull request
persist, while the conversation does not.

When a large branch is resumed in a fresh session, `make agent-context TASK=<id>
MODE=resume FOCUS="<path> ..."` optionally eagerly loads only that small working
set. `FOCUS` is ephemeral request input (never persisted) and never changes the
complete branch scope, recommended checks, ownership, or governance.

Run the focused checks that `make agent-context` recommends for the changed
surface while iterating. In a governed project the single canonical local gate is
`make agent-pre-review TASK=<id>` (it runs the project's `make check` once); do
not run `make check` immediately before it. Exhaustive validation is CI's job:
once the task is in review and the branch is pushed, the implementation session
ends and does not wait for or poll CI. A CI failure starts a fresh session that
resumes from durable state - the task, branch, worktree, claim, and pull request
persist while the conversation does not.
