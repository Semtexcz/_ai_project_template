---
id: T-002
title: Make library-shared golden path executable
status: done
priority: 1
milestone: M-01
depends_on: [T-001]
approval: A0
---

# T-002: Make Library-Shared Golden Path Executable

## Goal

Make the template generate a `library-shared` project that passes setup, check, build, wheel installation, import, and public API verification without manual edits.

## Context

`script-local` is already executable and covered by an integration test. The next Python golden path is a distributable shared library.

## Scope

- Generate a minimal `src` layout Python library.
- Provide a small explicit public API.
- Include typed package marker metadata.
- Build wheel and sdist artifacts.
- Verify the built wheel from a clean consumer environment.
- Add a dedicated template integration test and CI job.
- Keep `script-local` green.

## Out of Scope

- PyPI publishing.
- Trusted publishing and release secrets.
- Backend, frontend, full-stack, and production profile fixes.
- Copier update behavior.

## Acceptance Criteria

- `library-shared` Copier generation is non-interactive.
- Generated project passes `make setup`, `make check`, and `make build`.
- Built wheel installs into a clean environment.
- Public package imports and exposes a usable public symbol.
- Wheel contains package files and excludes obvious internal project files.
- Existing `script-local` integration test still passes.

## Verification

- `uv run pytest tests/test_script_local_golden_path.py tests/test_library_shared_golden_path.py`
- Fresh manual `script-local` generation and `make setup && make check && make build`
- Fresh manual `library-shared` generation, `make setup && make check && make build`, clean wheel install, public import, and public API call

## Documentation Impact

Update only concise README guidance for building and locally verifying library wheels.

## Completion Notes

Implemented a tested `library-shared` golden path:

- generated library projects use `src` layout with `py.typed`,
- public API exports `__version__` and `package_name`,
- `make setup`, `make check`, and `make build` pass,
- `make build` replaces stale `dist/` and creates wheel plus sdist,
- integration test installs the built wheel into a clean consumer environment,
- integration test verifies wheel contents and public API usage,
- CI has a dedicated `library-shared` golden-path job.
