---
id: T-005
title: Make fullstack-local golden path executable with generated OpenAPI client
status: done
priority: 1
milestone: M-01
depends_on: [T-001, T-002, T-003, T-004]
approval_level: A1
approval_status: approved
approved_by: Project owner
approved_at: 2026-07-31T10:00:00+02:00
blocked_reason:
unblock_action:
---

# T-005: Make Fullstack-Local Golden Path Executable With Generated OpenAPI Client

## Goal

Make `fullstack-local` generate a connected FastAPI and Nuxt application whose
frontend client is generated from the actual backend OpenAPI contract.

## Context

The script, library, backend, and frontend golden paths are already covered by
template integration tests. The next gate is the local full-stack OpenAPI
contract path.

## Scope

- Add a minimal FastAPI `GET /api/system/info` contract with a Pydantic response model.
- Export deterministic OpenAPI from the real FastAPI app.
- Generate a TypeScript SDK and types for Nuxt from that schema.
- Add `make api-schema`, `make api-generate`, `make api-check`, `make dev`,
  `make run`, `make check`, `make build`, and `make e2e` support for fullstack.
- Wire Nuxt runtime config to the generated client without manual API type copies.
- Add component, backend contract, integration, browser E2E, negative drift, and
  runtime failure coverage.
- Add targeted CI for `fullstack-local`.
- Update README and project state.

## Out of Scope

- Copier update behavior.
- Production runtime or deployment.
- Databases, Redis, message brokers, object storage, Docker Compose, Kubernetes,
  or cloud services.
- CRUD examples or Todo application work.
- Expanded workflow validation, lifecycle model, or agent skill changes.

## Acceptance Criteria

- `fullstack-local` renders non-interactively and needs no manual edits.
- `make setup`, `make api-schema`, `make api-generate`, `make api-check`,
  `make check`, and `make build` pass in a clean generated project.
- `make api-check` detects generated client drift.
- Frontend API types and SDK calls come from generated OpenAPI output.
- Built backend and built Nuxt frontend run together through `make run`.
- Browser E2E verifies data returned by the real backend.
- Runtime API integration failure makes browser E2E fail.
- Existing script, library, backend, and frontend golden paths still pass.
- CI includes a targeted `fullstack-local-golden-path` job.

## Verification

- `uv run pytest tests/test_fullstack_local_golden_path.py`
- `uv run pytest tests/test_script_local_golden_path.py`
- `uv run pytest tests/test_library_shared_golden_path.py`
- `uv run pytest tests/test_backend_shared_golden_path.py`
- `uv run pytest tests/test_frontend_shared_golden_path.py`
- Manual clean `fullstack-local` generation, `make setup`, `make api-check`,
  `make check`, `make build`, `make run`, backend endpoint checks, and Playwright E2E.

## Documentation Impact

Generated README documents backend/frontend locations, OpenAPI export, generated
client location, API base URL configuration, build/run/check commands, and the
current project dashboard.

## Completion Notes

Implemented the local full-stack OpenAPI contract path:

- `GET /api/system/info` uses an explicit Pydantic response model and operation ID.
- `make api-schema` writes deterministic `artifacts/openapi.json`.
- `make api-generate` creates `frontend/shared/api/generated/`.
- `make api-check` compares a temp generated client against the working generated client.
- Nuxt reads `NUXT_PUBLIC_API_BASE_URL` and calls generated `getSystemInfo`.
- Built runtime and Playwright E2E verify backend data in the browser.
- Negative contract drift and runtime integration failure are covered.
- Recommended next gate: `copier-update-golden-path`.
