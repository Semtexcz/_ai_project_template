# Profile Matrix

Profiles are the product of two Copier answers:

- `project_type`: `script`, `library`, `backend`, `frontend`, `fullstack`
- `runtime_level`: `local`, `shared`, `production`

Presets may set these values, but they are not a third source of truth.

## Project Types

| `project_type` | Generated runtime | Included stack | Not included |
|---|---|---|---|
| `script` | Python CLI package | `src/`, pytest, Ruff, Pyright, `make run`, package build | FastAPI, Nuxt, OpenAPI client, Docker runtime |
| `library` | Python import package | `src/`, `py.typed`, public API test, pytest, Ruff, Pyright, package build | CLI entry point, FastAPI, Nuxt, OpenAPI client |
| `backend` | FastAPI service | `backend/`, health/readiness routes, OpenAPI endpoint, backend tests, wheel build | Frontend, generated OpenAPI client |
| `frontend` | Nuxt application | `frontend/`, ESLint, typecheck, Vitest, build/run targets | Backend, generated OpenAPI client |
| `fullstack` | FastAPI backend and Nuxt frontend | `backend/`, `frontend/`, OpenAPI schema export, generated TypeScript client, Vitest, Playwright | External database, queue, broker, cloud deployment |

## Runtime Levels

| `runtime_level` | Meaning | Adds | Does not imply |
|---|---|---|---|
| `local` | Developer-local execution | Minimal setup, local run/build/check targets | Shared environment hardening or production artifacts |
| `shared` | Buildable shared-environment baseline | Packaged backend/library artifacts or built frontend server output | Cloud deployment, registry push, HA, secrets management |
| `production` | Locally verifiable production-like artifacts where supported | OCI image targets, inspection, Compose smoke/status targets for supported runtimes | External release, TLS/HSTS termination, database backups, Kubernetes |

## Golden Path Profiles

| Profile | What must be true |
|---|---|
| `script-local` | Python CLI package can set up, check, build, and run locally. |
| `library-shared` | Python library package can build installable artifacts with typed public API checks. |
| `backend-shared` | FastAPI service can check, build, run from source, and run from the built wheel. |
| `frontend-shared` | Nuxt application can install, check, build, and run the built server output. |
| `fullstack-local` | Backend and frontend can check together, keep the generated client synchronized, build, and run locally. |
| `fullstack-production` | Full-stack artifacts can build, inspect, run through Compose, smoke test, and shut down locally. |

## Common Generated Project Layer

Every profile includes:

- `README.md` with current dashboard and one next action command
- `project/state.yaml`, `project/index.md`, `project/board.md`, `project/roadmap.md`
- `project/tasks/T-001-initialize-project.md`
- `docs/product.md`, `docs/architecture.md`, `docs/workflow.md`, `docs/quality.md`
- `tools/project.py` plus Make targets for status, sync, validation, and task transitions
- `AGENTS.md`, `.agents/`, and `.codex/` instructions for AI-assisted work

## Profile-Specific Documentation

Generated `README.md` and `docs/architecture.md` describe only the selected
profile. For example, `script-local` documentation must not describe FastAPI,
Nuxt, generated OpenAPI clients, or OCI images. `fullstack-production`
documentation may describe all generated runtime pieces plus the local
production-like verification contract.
