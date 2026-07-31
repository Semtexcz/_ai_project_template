---
id: T-001
title: Make script-local golden path executable
status: done
priority: 1
milestone: M-01
depends_on: []
approval_level: A0
approval_status: not-required
approved_by:
approved_at:
blocked_reason:
unblock_action:
---

# T-001: Make Script-Local Golden Path Executable

## Goal

Make the template generate a `script-local` project that passes setup, check, and build without manual edits.

## Scope

- Fix non-interactive Copier generation for the guaranteed path.
- Fix shared Python tooling that blocks `script-local`.
- Add a real `make build` for Python script projects.
- Add an integration test that generates and validates `script-local`.
- Update CI and concise command documentation.

## Acceptance Criteria

- `copier copy --defaults --data project_type=script --data runtime_level=local ...` succeeds.
- Generated `script-local` passes `make setup`.
- Generated `script-local` passes `make check`.
- Generated `script-local` passes `make build`.
- Template tests include an end-to-end `script-local` integration test.
- CI runs the same golden path.

## Verification

- `uv run pytest`
- Fresh manual generation into `/tmp`
- `make setup`
- `make check`
- `make build`

## Documentation Impact

Update only the relevant README command snippets.

## Completion Notes

Implemented a tested `script-local` golden path:

- non-interactive Copier generation uses `--defaults`,
- generated `script-local` passes `make setup`, `make check`, and `make build`,
- `make check` runs project validation, Ruff format check, Ruff lint, Pyright, and pytest,
- `make build` creates sdist and wheel artifacts through `uv build`,
- CI has a dedicated `script-local` golden-path job.
