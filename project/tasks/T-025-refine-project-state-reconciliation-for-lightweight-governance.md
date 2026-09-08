---
id: T-025

title: Refine project-state reconciliation for lightweight governance

status: review

priority: 1

milestone: M-08

depends_on: []

approval_level: A1

approval_status: pending

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-025: Refine Project State Reconciliation for Lightweight Governance

## Goal

Refine the generated project-state reconciliation policy so lightweight
projects stay lightweight while managed projects keep stronger reconciliation
behavior, and represent this template-governance change in the repository's
managed task lifecycle.

## Context

The current reconciliation policy is rendered into both lightweight and
managed generated projects and requires behavior such as re-evaluating the next
meaningful task and ending every report with a `Project State Check`. That is
too strong for lightweight projects that may not use roadmaps, backlogs,
milestones, or a task lifecycle. The policy must keep managed deterministic
state authoritative without becoming a second lifecycle engine.

## Scope

- Render shared reconciliation guidance for all generated profiles: reconcile
  durable planning/status artifacts only when they exist and a change
  materially affects them; remove stale claims; never mechanically advance a
  roadmap or backlog.
- Render managed-only requirements: roadmap/milestone/task-level
  reconciliation, next-task re-evaluation where appropriate, and a concise
  `Project State Check` report footer.
- Keep lightweight generated output free of mandatory task selection,
  next-task statements, roadmap thinking, and the `Project State Check` footer.
- Keep `update-documentation` and `review-change` skills artifact-aware without
  mutating managed task state or generated boards directly.
- Update rendering tests so lightweight and managed generated projects are
  asserted separately.
- Add the change to the repository's own managed task lifecycle with A1
  approval pending.

## Out of Scope

- Replacing the managed task lifecycle or approval model.
- Adding a new orchestration engine.
- Changing generated project runtime behavior.

## Acceptance Criteria

- [x] Lightweight generated projects do not contain managed-only next-task
  requirements or a mandatory `Project State Check`.
- [x] Managed generated projects keep stronger reconciliation behavior and the
  concise `Project State Check`.
- [x] Shared reconciliation guidance applies to both profiles when planning
  artifacts exist.
- [x] Skills and docs do not mutate managed task state or boards directly.
- [x] Lightweight and managed render tests assert the differing behavior
  explicitly.
- [x] This work is tracked as an A1 managed task left in review with approval
  pending.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest
  tests/test_template_static.py::test_project_state_reconciliation_renders_governance_split`
  passed: 1 test in 7.21s.
- `UV_CACHE_DIR=/tmp/uv-cache make check` passed: 24 tests in 94.92s.
- `make validate-agent-skills` passed.
- `make validate-project` passed.
- `make validate-template-docs` passed.

## Documentation Impact

Update generated `AGENTS.md`, generated workflow documentation, and the core
`update-documentation` and `review-change` skills; add a changelog entry and an
UPGRADING note.

## Completion Notes

Generated `AGENTS.md` and `docs/workflow.md` now render governance-aware
project-state reconciliation: all profiles share the guidance to reconcile
durable planning/status artifacts only when they exist and are affected;
managed profiles additionally reconcile roadmap/milestone/task-level planning,
re-evaluate the next meaningful task, and end reports with a `Project State
Check`; lightweight profiles explicitly stay free of mandatory task selection,
next-task statements, roadmap thinking, and report footers. The
`update-documentation` and `review-change` skills now state that reconciliation
never mutates managed task/approval state or generated boards. This task is
tracked under the repository's own managed lifecycle as an A1 item in review
with human approval pending.
