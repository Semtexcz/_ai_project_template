---
id: T-006
title: Make Copier update safe and integration-tested
status: done
priority: 1
milestone: M-01
depends_on: [T-001, T-002, T-003, T-004, T-005]
approval_level: A2
approval_status: approved
approved_by: Project owner
approved_at: 2026-07-31T10:00:00+02:00
blocked_reason:
unblock_action:
---

# T-006: Make Copier Update Safe and Integration-Tested

## Goal

Make a project generated from one versioned Git tag of the template safely
update to a newer tag with standard `copier update`, preserving project-owned
content and surfacing merge conflicts.

## Context

The existing golden paths render and validate concrete project profiles. The
next gate verifies template lifecycle management: a generated project must not
depend on a non-updatable local `.` source and must keep project knowledge
during template upgrades.

Current prerequisite finding: `T-005` is in review in the project board while
`project/state.yaml` previously still listed it as active. This task records the
inconsistency and moves the active lifecycle focus to the Copier update gate.

## Scope

- Use a real temporary Git template repository with two commits and tags.
- Generate a `fullstack-local` project from `v1.0.0`.
- Customize project-owned docs, task content, README content, Makefile content,
  and application code.
- Update the generated project to `v1.1.0` using standard Copier metadata.
- Verify project-owned preservation, template-owned updates, merge-sensitive
  preservation, invalid tag failure, and conflict behavior.
- Document versioning, ownership, update commands, conflicts, and migration
  policy.
- Add targeted maintainer and CI entry points.

## Out of Scope

- Production runtime.
- Expanded project state validation.
- Agent skills operationalization.
- Database, queue, object storage, Kubernetes, or cloud infrastructure.
- A custom replacement for Copier update.

## Acceptance Criteria

- Update tests use a temporary Git template repository, two commits, and two
  SemVer tags.
- Answers metadata points to the temporary Git template source and the new tag
  after update.
- `.template-version` is created at copy time and updated after successful
  update.
- Project-owned brief, roadmap, task, and application code survive update.
- Template-owned tooling updates and a new template-owned file appears.
- Merge-sensitive README and Makefile content keep independent template and
  project changes.
- Conflicting README changes are not silently overwritten.
- Invalid target tags fail without marking metadata as updated.
- Updated fullstack-local project passes setup, API check, checks, build,
  runtime smoke, and browser E2E.
- Existing golden-path tests remain enabled.

## Verification

- `make test-copier-update`
- `make test-template`
- `uv run pytest tests/test_script_local_golden_path.py`
- `uv run pytest tests/test_library_shared_golden_path.py`
- `uv run pytest tests/test_backend_shared_golden_path.py`
- `uv run pytest tests/test_frontend_shared_golden_path.py`
- `uv run pytest tests/test_fullstack_local_golden_path.py`

## Documentation Impact

`UPGRADING.md` now documents the standard Git-source copy/update flow,
pre-update safety checks, post-update validation, conflict handling, and when
Copier migrations are appropriate. `docs/template-ownership.md` records the
template-owned, project-owned, and merge-sensitive file map.

## Completion Notes

Implemented the Copier update golden path with a temporary versioned Git
template repository. The task remains in review because it requires A2 approval
before it can be marked done.
