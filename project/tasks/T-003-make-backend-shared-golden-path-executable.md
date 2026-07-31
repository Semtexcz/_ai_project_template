---
id: T-003
title: Make backend-shared golden path executable
status: done
priority: 1
milestone: M-01
depends_on: [T-001, T-002]
approval_level: A1
approval_status: approved
approved_by: Project owner
approved_at: 2026-07-31T10:00:00+02:00
blocked_reason:
unblock_action:
---

# T-003: Make Backend-Shared Golden Path Executable

## Goal

Make the template generate a `backend-shared` project that passes setup, check,
build, runtime startup, health, readiness, OpenAPI, and clean artifact execution
without manual edits.

## Context

`script-local` and `library-shared` are already executable and covered by
integration tests. The next lifecycle gate is `backend-shared-golden-path`.

## Scope

- Fix backend Copier output for `project_type=backend` and `runtime_level=shared`.
- Provide a stateless FastAPI application skeleton with health, readiness, and OpenAPI.
- Ensure `make setup`, `make check`, `make build`, `make dev`, and `make run` work.
- Add backend tests for app creation, endpoint contracts, OpenAPI, 404 behavior, and invalid configuration.
- Add an end-to-end template integration test that starts a real backend process.
- Add a targeted template CI job for the backend golden path.
- Update relevant README and project state.

## Out of Scope

- Frontend and full-stack golden paths.
- Databases, Redis, queues, schedulers, and external infrastructure services.
- Production deployment, Kubernetes, cloud provisioning, and release automation.
- TypeScript OpenAPI client generation.
- Copier update behavior.
- Expanded Kanban validation or lifecycle model changes.

## Acceptance Criteria

- `backend-shared` renders non-interactively.
- Generated `backend-shared` passes `make setup`, `make check`, and `make build`.
- Ruff format, Ruff lint, Pyright, pytest, project validation, and OpenAPI checks run.
- The backend starts with `make run` on a caller-selected port.
- `/health`, `/ready`, and `/openapi.json` respond from a real server process.
- Wheel and sdist artifacts are created under `backend/dist/`.
- The wheel installs into a clean environment and can run the app.
- `script-local` and `library-shared` golden-path tests still pass.
- CI has a dedicated `backend-shared-golden-path` job.

## Verification

- `uv run pytest tests/test_script_local_golden_path.py`
- `uv run pytest tests/test_library_shared_golden_path.py`
- `uv run pytest tests/test_backend_shared_golden_path.py`
- Fresh manual `backend-shared` generation, `make setup`, `make check`,
  `make build`, `make run`, endpoint smoke test, clean wheel install, and
  installed-wheel runtime smoke test.

## Documentation Impact

Generated backend README documents `make setup`, `make dev`, `make run`,
`make check`, `make build`, endpoint URLs, the FastAPI entry point, and build
artifacts. It explicitly does not claim production deployment.

## Completion Notes

Implemented a tested `backend-shared` golden path:

- generated backend passes `make setup`, `make check`, and `make build`,
- `make run` starts Uvicorn with `app.main:app` and caller-selected host/port,
- `/health`, `/ready`, and `/openapi.json` are covered by backend tests and a real-process integration test,
- wheel and sdist are built under `backend/dist/`,
- the wheel installs into a clean environment and runs the app,
- CI has a dedicated `backend-shared-golden-path` job,
- `script-local` and `library-shared` golden-path tests still pass.
