---
id: T-020

title: Introduce lightweight progressive governance

status: done

priority: 1

milestone: M-08

depends_on: []

approval_level: A0

approval_status: not-required

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-020: Introduce Lightweight Progressive Governance

## Goal

Refactor the template so generated projects default to lightweight AI-first
development while preserving the current managed project lifecycle as an
optional governance mode.

## Context

The current template strongly couples the AI engineering baseline to managed
project governance. New projects should be able to start with minimal durable
context, build the smallest useful vertical slice, and add stronger process
constraints only when complexity or risk justifies them.

## Scope

- Add independent governance and workflow-mode configuration axes.
- Make lightweight governance the default for generated projects.
- Preserve managed lifecycle, approvals, dashboards, and project-state tooling
  behind an explicit managed mode.
- Make ordinary reversible implementation work autonomous when checks pass.
- Ensure `make check` validates without mutating tracked files.
- Update tests and documentation for generation, migration, agent workflows,
  approval boundaries, and validation purity.

## Out of Scope

- Removing useful managed-mode capabilities.
- Adding production runtime services, databases, queues, brokers, Redis, or
  external infrastructure.
- Changing project type or runtime-level semantics except where needed to keep
  them independent from governance.

## Acceptance Criteria

- [x] Lightweight governance exists and is the default.
- [x] Managed governance preserves the existing lifecycle machinery.
- [x] Workflow strictness is configurable.
- [x] `make check` is non-mutating.
- [x] Relevant generated-project tests and documentation are updated.
- [x] Repository validation passes.

## Verification

- `make validate-template-docs` passed.
- `make validate-project` passed.
- `make validate-agent-skills` passed.
- `make check` passed and left the same `git status --porcelain` output before
  and after the run.
- `make release-check` passed: 34 tests in 3331.92 seconds.
- Focused generated-project checks passed for governance rendering,
  backend-shared, frontend-shared, fullstack-local, managed workflow, and Copier
  update compatibility during implementation.

## Documentation Impact

Update root, template, architecture, profile, workflow, approval, check purity,
and migration documentation to match the new progressive governance behavior.

## Completion Notes

Added independent `governance` and `workflow_mode` Copier axes. Lightweight is
the default and renders only the AI engineering kernel plus durable project
context. Managed governance preserves project state, lifecycle commands,
dashboards, dependencies, agent context, and approval metadata. `make check` is
now validation-only; mutating actions are explicit commands such as
`make format`, `make api-generate`, and managed `make sync-project-docs`.
