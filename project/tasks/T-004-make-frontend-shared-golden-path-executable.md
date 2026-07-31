---
id: T-004
title: Make frontend-shared golden path executable
status: done
priority: high
approval: A1
depends_on: [T-001, T-002, T-003]
---

# T-004: Make Frontend-Shared Golden Path Executable

## Goal

Make the template generate a standalone `frontend-shared` Nuxt application that
passes setup, check, build, production-build startup, and HTTP smoke testing
without manual edits.

## Context

`script-local`, `library-shared`, and `backend-shared` are already executable and
covered by integration tests. The next lifecycle gate is
`frontend-shared-golden-path`.

## Scope

- Fix frontend Copier output for `project_type=frontend` and `runtime_level=shared`.
- Ensure `make setup`, `make check`, `make build`, `make dev`, and `make run` use
  the correct `frontend/` working directory.
- Provide a small feature-oriented Nuxt app with a tested `welcome` feature.
- Add ESLint, Nuxt typecheck, Vitest, lockfile, and runtime smoke coverage.
- Add an end-to-end template integration test that starts the built Nuxt server.
- Add targeted CI for the frontend shared golden path.
- Update relevant README and project state.

## Out of Scope

- Full-stack golden path.
- Backend dependencies, databases, Docker, Redis, queues, and external APIs.
- Generated TypeScript OpenAPI client.
- Production CDN, cloud hosting, deployment, and operational runtime.
- Copier update behavior.
- Expanded project validation and agent skill lifecycle changes.

## Acceptance Criteria

- `frontend-shared` renders non-interactively.
- Generated `frontend-shared` passes `make setup`, `make check`, and `make build`.
- ESLint, Nuxt typecheck, Vitest, and project validation run during `make check`.
- `make build` creates `frontend/.output/server/index.mjs`.
- `make run` starts the already built Nuxt server on caller-selected host and port.
- A real HTTP request to `/` returns HTML containing the generated project name and
  `project/index.md`.
- The main feature has component and utility/composable tests, including a
  meaningful negative or edge case.
- CI has a dedicated `frontend-shared-golden-path` job.
- Existing script, library, and backend golden-path tests still pass.

## Verification

- `uv run pytest tests/test_frontend_shared_golden_path.py`
- `uv run pytest tests/test_script_local_golden_path.py`
- `uv run pytest tests/test_library_shared_golden_path.py`
- `uv run pytest tests/test_backend_shared_golden_path.py`
- Fresh manual `frontend-shared` generation, `make setup`, `make check`,
  `make build`, `make run`, and root HTTP smoke test.

## Documentation Impact

Generated frontend README documents `make setup`, `make dev`, `make run`,
`make check`, `make build`, the Nuxt app location, `.output/`, the built server
entry point, and the absence of backend/OpenAPI client functionality in this
profile.

## Completion Notes

Implemented a tested `frontend-shared` golden path:

- generated frontend passes `make setup`, `make check`, and `make build`,
- `make setup` installs dependencies inside `frontend/` and can use frozen lockfile
  flags in CI,
- `make run` starts `frontend/.output/server/index.mjs` without HMR,
- `/` is covered by a real-process HTTP smoke test,
- ESLint, Nuxt typecheck, Vitest, and project validation run through `make check`,
- CI has a dedicated `frontend-shared-golden-path` job,
- recommended next gate: `fullstack-local-openapi-contract`.
