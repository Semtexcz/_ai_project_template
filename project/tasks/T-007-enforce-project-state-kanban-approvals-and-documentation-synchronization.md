---
id: T-007

title: Enforce project state, Kanban, approvals and documentation synchronization

status: review

priority: 1

milestone: M-07

depends_on: [T-006]

approval_level: A1

approval_status: pending

approved_by:

approved_at:

blocked_reason:

unblock_action:
---

# T-007: Enforce Project State, Kanban, Approvals and Documentation Synchronization

## Goal

Make project state, task metadata, generated Kanban, project index, README
dashboard, approvals, blockers, dependencies, and recommended next action
validate from one deterministic source-of-truth model.

## Context

The existing golden paths are implemented, but `project/state.yaml`, task files,
the board, index, and README can drift silently. Humans and AI agents need a
single reliable view before starting work.

## Scope

- Validate `project/state.yaml` schema.
- Validate task frontmatter schema, dependencies, approvals, blockers, Definition
  of Ready, Definition of Done, and one active task.
- Add controlled task lifecycle commands.
- Generate README status, project index status, and Kanban from state plus task
  frontmatter.
- Detect generated document drift and broken internal Markdown links.
- Add integration and negative tests for project-state validation.
- Document deterministic commands and approval boundaries.

## Out of Scope

- Production runtime.
- Databases, Redis, queues, brokers, or infrastructure services.
- Web Kanban UI.
- General workflow engine.
- Copier ownership model changes unless required by validation.
- Broader operationalization of agent skills.

## Acceptance Criteria

- [x] `project/state.yaml` has explicit schema validation.
- [x] Task frontmatter has explicit schema validation.
- [x] Invalid lifecycle transitions are rejected.
- [x] Definition of Ready and Definition of Done are validated.
- [x] Dependencies and direct or indirect cycles are validated.
- [x] At most one in-progress task can exist.
- [x] A1 and A2 approval rules are enforced.
- [x] Blocked tasks require blocker metadata.
- [x] README, project index, and Kanban are generated deterministically.
- [x] Drift and broken internal Markdown links are detected.
- [x] Positive and negative project workflow tests pass.
- [x] Existing golden-path tests remain enabled.

## Verification

Executed:

```bash
make project-status
make sync-project-docs
make validate-project
UV_CACHE_DIR=/tmp/uv-cache UV_LINK_MODE=copy uv run pytest tests/test_project_state_validation_golden_path.py
UV_CACHE_DIR=/tmp/uv-cache UV_LINK_MODE=copy uv run pytest tests/test_template_static.py tests/test_project_state_validation_golden_path.py
UV_CACHE_DIR=/tmp/uv-cache UV_LINK_MODE=copy uv run pytest tests/test_script_local_golden_path.py tests/test_library_shared_golden_path.py tests/test_backend_shared_golden_path.py tests/test_frontend_shared_golden_path.py tests/test_fullstack_local_golden_path.py tests/test_copier_update_golden_path.py
```

## Documentation Impact

README, `docs/workflow.md`, generated project docs, and `AGENTS.md` describe the
deterministic project status commands, lifecycle transitions, and human approval
boundary.

## Completion Notes

Implemented deterministic project-state validation, controlled task transitions,
generated README/index/board synchronization, next-action selection, Markdown
link validation, CI coverage, and focused documentation. Moved to review; do not
mark this A1 task `done` until a human approval is recorded through the approval
command.
