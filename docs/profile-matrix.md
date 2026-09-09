# Profile Matrix

Profiles are selected with independent Copier answers:

- `project_type`: `script`, `library`, `backend`, `frontend`, `fullstack`
- `runtime_level`: `local`, `shared`, `production`
- `governance`: `lightweight`, `managed`
- `workflow_mode`: `local`, `branch`, `pr`

Presets may set runtime profile values, but they are not a third source of
truth.

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

## Governance Modes

| `governance` | Default | Includes | Does not require |
|---|---|---|---|
| `lightweight` | Yes | AI engineering kernel, core `.agents/` skills, thin `.codex/` adapters, `project/brief.md`, docs, ADRs, technical checks | Task state machine, approval metadata, board/dashboard generation, milestones, ready-for-development gate |
| `managed` | No | Everything in lightweight plus `project/state.yaml`, tasks, lifecycle commands, managed skills, dashboards, dependencies, managed agent context, A0/A1/A2 approval metadata | Production deployment, paid services, or infrastructure beyond the selected runtime profile |

## Workflow Modes

| `workflow_mode` | Default | Agent Git behavior |
|---|---|---|
| `local` | Yes | Work may happen in the current local repository; commits, pushes, and PRs are optional unless requested. |
| `branch` | No | Work should happen on a dedicated branch; commits may be created, but push/PR is optional unless requested. |
| `pr` | No | Preserve strict branch -> commit -> push -> ready PR workflow and generated main-push CI guard where CI is rendered. In managed `pr` projects, the human GitHub merge of a task's pull request is the A1 approval/completion boundary (and A2's completion boundary); agents stop at `review`, and `make pr-validate` checks the pull request is structurally ready. |

## Golden Path Profiles

| Profile | What must be true |
|---|---|
| `script-local` | Python CLI package can set up, check, build, and run locally. |
| `library-shared` | Python library package can build installable artifacts with typed public API checks. |
| `backend-shared` | FastAPI service can check, build, run from source, and run from the built wheel. |
| `frontend-shared` | Nuxt application can install, check, build, and run the built server output. |
| `fullstack-local` | Backend and frontend can check together, keep the generated client synchronized, build, and run locally. |
| `fullstack-production` | Full-stack artifacts can build, inspect, run through Compose, smoke test, and shut down locally. |

## Common AI Engineering Kernel

Every profile includes:

- `README.md`
- `project/brief.md`
- `docs/product.md`, `docs/architecture.md`, `docs/workflow.md`, `docs/quality.md`
- `docs/decisions/`
- `AGENTS.md`
- `.agents/skills/` core skills and `.codex/` thin adapters
- `tools/agent.py` and `make validate-agent-skills`
- `Makefile` targets for setup, run/dev, test, lint, typecheck, check, build,
  and selected profile guardrails

Capability skills are generated only when relevant:

- `change-api-contract` for `project_type=fullstack`
- `verify-production-artifact` for `runtime_level=production`

Managed governance additionally includes:

- `README.md` dashboard with one next action command
- `project/state.yaml`, `project/index.md`, `project/board.md`, `project/roadmap.md`
- `project/tasks/T-001-initialize-project.md`
- `tools/project.py` plus Make targets for status, sync, validation, and task transitions
- `.agents/managed/skills/` lifecycle skills and managed hooks

## Profile-Specific Documentation

Generated `README.md` and `docs/architecture.md` describe only the selected
profile. For example, `script-local` documentation must not describe FastAPI,
Nuxt, generated OpenAPI clients, or OCI images. `fullstack-production`
documentation may describe all generated runtime pieces plus the local
production-like verification contract.
