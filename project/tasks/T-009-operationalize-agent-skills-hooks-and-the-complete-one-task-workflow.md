---
id: T-009

title: Operationalize agent skills, hooks and the complete one-task workflow

status: done

priority: 1

milestone: M-07

depends_on: [T-008]

approval_level: A1

approval_status: approved

approved_by: Daniel Kopecký

approved_at: 2026-07-31T19:09:37+02:00

blocked_reason:

unblock_action:
---

# T-009: Operationalize Agent Skills, Hooks and the Complete One-Task Workflow

## Goal

Make the agent layer executable, deterministic, and test-covered for one task at
a time, using the existing project CLI as the source of truth.

## Context

The current project state, Kanban, approvals, profile golden paths, Copier
update path, and fullstack-production golden path are already in place. The
remaining gap is that agent guidance is mostly descriptive and cannot yet drive
a complete task workflow through validated skills, context routing, and hooks.

## Scope

- Add a canonical `.agents/` layer with metadata-bearing skills, context map,
  hook entry points, schemas, templates, and documentation.
- Add a thin `.codex/` adapter that points to canonical skills without copying
  them.
- Add deterministic agent commands for status, context, skill validation, and
  pre-task, pre-review, and post-task checks.
- Expose the agent commands through Makefile targets in the template and this
  repository.
- Add integration and negative tests for the one-task workflow and approval
  boundaries.
- Update concise workflow and README documentation.

## Out of Scope

- Multi-agent orchestration.
- External LLM calls, paid APIs, vector stores, databases, queues, brokers,
  Redis, or new production infrastructure.
- Changes to the project task state machine or A0/A1/A2 approval rules.
- Changes to application profile business skeletons unrelated to agent workflow.

## Acceptance Criteria

- [x] `AGENTS.md` is short and points to canonical `.agents/` guidance.
- [x] Required canonical skills exist and have validated metadata.
- [x] Skills reference real commands and do not bypass task transitions or
  approvals.
- [x] `.codex/` remains a thin adapter to canonical skills.
- [x] Context map validation and deterministic context resolution work.
- [x] Context excludes secrets, build artifacts, dependency directories, and
  traversal outside the project root.
- [x] `make agent-status`, `make agent-context`, and
  `make validate-agent-skills` work.
- [x] Pre-task, pre-review, and post-task hooks work through project CLI logic.
- [x] A0 one-task workflow passes in a generated project.
- [x] A1 completion without human approval fails.
- [x] A2 start without human approval fails.
- [x] Fullstack context routing covers frontend, backend, API contract, and
  excludes.
- [x] Existing golden paths, Copier update, project-state validation, and
  fullstack-production regressions pass.
- [x] Documentation describes the actual commands without duplicating the full
  skill bodies.

## Verification

- `make validate-project` passed.
- `make validate-agent-skills` passed.
- `make agent-context TASK=T-009 FORMAT=json` passed.
- `make agent-pre-task TASK=T-009` passed.
- `make agent-pre-review TASK=T-009` passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_one_task_workflow_golden_path.py` passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` passed once for the full 19-test regression suite. A later repeated full-suite run inside pre-review hit `/tmp` ENOSPC, so root `make check` was scoped to a fast maintainer gate and the full suite remains available via `make test-template`.

## Documentation Impact

Update `AGENTS.md`, `README.md`, `.agents/README.md`, `.codex/README.md`,
template workflow documentation, and ownership notes for the executable agent
layer.

## Completion Notes

Implemented canonical `.agents/` skills and context map, a thin `.codex/`
adapter, deterministic `tools/agent.py` commands, Make targets, hook wrappers,
documentation updates, and agent workflow regression tests. The task is ready
for human A1 review and must not be marked `done` until approval is recorded.
