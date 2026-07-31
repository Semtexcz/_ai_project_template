---
id: T-011

title: Remediate RC-001 transactional project mutations

status: done

priority: 1

milestone: M-08

depends_on: [T-010]

approval_level: A2

approval_status: approved

blocked_reason: null

unblock_action: null

approved_by: <human>

approved_at: 2026-07-31T20:18:58+02:00
---

# T-011: Remediate RC-001 Transactional Project Mutations

## Goal

Make every mutating project task command all-or-nothing so failed workflow
commands cannot persist partial task, project state, or dashboard changes.

## Context

The release-candidate audit found that `make task-approve` can persist approval
metadata even when the command ultimately fails validation. The same mutation
ordering must be audited and fixed across all task lifecycle commands because
the project governance model depends on byte-for-byte reliable rollback.

## Scope

- Reproduce RC-001 against the current approval mutation path.
- Implement a shared transactional mutation mechanism for approval, ready,
  start, review, complete, block, unblock, and cancel commands.
- Preserve the lifecycle and approval rules, including A2 start boundaries.
- Add negative tests for validation failure, dashboard rendering failure, write
  failure, and final validation failure.
- Assert failed mutations leave task files, `project/state.yaml`, README,
  `project/index.md`, and `project/board.md` byte-for-byte unchanged.

## Out of Scope

- Changing the A0/A1/A2 governance model.
- Granting A1 or A2 approval.
- Releasing, tagging, publishing, or deploying artifacts.

## Acceptance Criteria

- [x] Every mutating task command uses the shared transaction path.
- [x] Failed mutations leave no approval metadata, temporary files, or partial
  dashboard updates.
- [x] Positive workflow behavior still passes for A0, A1, A2, and agent
  one-task workflows.
- [x] Regression tests prove the original RC-001 failure is closed.

## Verification

- Pre-fix reproduction was observed while preparing T-011: failed
  `make task-ready TASK=T-011` persisted `status: ready` before validation
  rejected the milestone mismatch.
- `UV_CACHE_DIR=/tmp/t011-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_project_state_validation_golden_path.py` passed.
- `UV_CACHE_DIR=/tmp/t011-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_agent_one_task_workflow_golden_path.py tests/test_template_static.py` passed after approved network access for generated project setup.
- `UV_CACHE_DIR=/tmp/t011-uv-cache UV_LINK_MODE=copy make check` passed.

## Documentation Impact

Updated generated project workflow documentation and agent command references
for `task-unblock`, `task-cancel`, and transactional task mutations.

## Completion Notes

Implemented shared transactional task mutations in `template/tools/project.py`.
Approval, ready, start, review, complete, block, unblock, and cancel commands now
validate a candidate state, render dashboards, commit control files together,
run final validation, and roll back byte-for-byte on failure. Added regression
coverage for validation, dashboard rendering, write, and final validation
failures.
