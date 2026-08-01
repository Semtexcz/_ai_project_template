---
id: T-019

title: Replace internal tools with Pydantic and Typer

status: ready

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

# T-019: Replace Internal Tools With Pydantic and Typer

## Goal

Replace the repository's current internal Python tool implementation patterns
with Pydantic-based models and Tiangolo-maintained CLI alternatives such as
Typer.

## Context

The template's project and agent tooling currently rely on standard-library
`argparse` command wiring and `dataclass` model objects. The generated project
already includes Pydantic usage in the backend and the template declares Typer
as a root dependency, so the internal tool layer should use those same
well-supported conventions instead of maintaining parallel parsing and model
validation patterns.

## Scope

- Replace `argparse` command surfaces in internal project and agent tools with
  Typer while preserving existing Makefile command behavior and exit semantics.
- Replace internal task, state, and context data carriers that need validation
  with Pydantic models.
- Keep generated project lifecycle commands compatible with the existing
  `make task-*`, `make agent-*`, `make validate-project`, and
  `make sync-project-docs` interfaces.
- Add or update focused tests for CLI behavior, validation failures, and
  generated template output.
- Update documentation that describes the internal tool stack or command
  behavior.

## Out of Scope

- Changing the public task lifecycle, approval workflow, or one-active-task
  rule.
- Replacing FastAPI, Pydantic Settings, Nuxt, pnpm, or other unrelated template
  dependencies.
- Adding production runtime services, databases, queues, brokers, Redis, or
  external infrastructure.

## Acceptance Criteria

- [ ] Internal project and agent CLIs are implemented with Typer or another
  appropriate Tiangolo-maintained alternative.
- [ ] Internal structured state and task validation uses Pydantic where it
  improves correctness over ad hoc dictionaries or dataclasses.
- [ ] Existing Makefile targets and documented commands remain backward
  compatible for generated projects.
- [ ] Negative tests cover invalid project state, invalid task metadata, and
  CLI argument errors.
- [ ] `make validate-project`, `make validate-agent-skills`, and focused pytest
  coverage pass.

## Verification

- Pending.

## Documentation Impact

Document the internal tool-stack change and any new conventions for future
tooling changes.

## Completion Notes

Pending.
