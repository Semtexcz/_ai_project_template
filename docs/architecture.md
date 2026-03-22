# Architecture

## Purpose

This repository is designed for AI-assisted development.
Use this file to understand where code belongs and which boundaries must be preserved.

## Layers

- `docs/`, `product/`, `project/`
  - requirements, planning, and workflow
  - no runtime logic

- `src/<package_name>/`
  - application code
  - all runtime behavior belongs here

- `tests/`
  - validation of behavior
  - unit, integration, e2e

- `scripts/`
  - project helper scripts
  - not main application logic unless explicitly intended

## Rules

- Do not put application logic in markdown files, tests, or scripts.
- Keep modules small and explicit.
- Prefer minimal safe changes.
- Do not refactor unrelated code.
- Preserve module boundaries.

## Preferred Structure in `src/<package_name>/`

- `domain/` — core logic
- `services/` — orchestration
- `adapters/` — external systems, filesystem, APIs
- `cli/` — command-line interface
- `models/` — shared data structures
- `utils/` — small generic helpers

## Boundary Rules

- `domain/` must not depend on CLI or external providers.
- `services/` may coordinate domain and adapters.
- `adapters/` handle external I/O.
- `cli/` should stay thin.
- `utils/` must not become a dumping ground.

## Testing Strategy

Prefer:

1. unit tests
2. integration tests
3. e2e tests

Test behavior, not implementation details.

## Change Rule

Before making changes, identify:

- related feature
- related task
- affected modules
- required tests

Modify only the minimum relevant files.
