---
id: T-008

title: Make fullstack-production golden path executable

status: done

priority: 1

milestone: M-07

depends_on: [T-007]

approval_level: A2

approval_status: approved

approved_by: <human>

approved_at: 2026-07-31T17:42:57+02:00

blocked_reason:

unblock_action:
---

# T-008: Make Fullstack-Production Golden Path Executable

## Goal

Make the `fullstack-production` Copier profile generate, build, run, and verify
deployable local OCI artifacts for backend and frontend in a production-like
environment.

## Context

The template already has executable and integration-tested golden paths for
`script-local`, `library-shared`, `backend-shared`, `frontend-shared`,
`fullstack-local`, Copier update, and project workflow validation. The next
gate is `production-runtime-golden-path`, which requires the first real
production runtime profile without creating cloud infrastructure or deploying
externally.

This A2 task requires explicit human approval before implementation starts.
The AI agent must not run the approval command or record a human approval.

## Scope

- Reproduce the current `fullstack-production` generated project behavior in a
  clean temporary project.
- Verify setup, API contract checks, quality checks, and build behavior before
  changing the template.
- Add or fix production-only Copier conditions, backend and frontend image
  builds, production process startup, runtime environment configuration,
  health/readiness checks, graceful shutdown behavior, production Compose
  orchestration, smoke checks, browser E2E verification, CI coverage, and
  operating documentation.
- Keep the flow local and CI-compatible with no external paid services and no
  actual deployment.

## Out of Scope

- Kubernetes, Terraform, cloud provisioning, or automatic deployment.
- PostgreSQL, Redis, queues, brokers, object storage, or external observability
  platforms.
- Public container registries or real production secrets.
- Unnecessary changes to application module architecture, OpenAPI contracts,
  generated TypeScript client ownership, task workflow, lifecycle phases, or
  existing local/shared golden paths.

## Acceptance Criteria

- [x] A clean `fullstack-production` project can be generated non-interactively.
- [x] Generated project `make setup`, `make api-check`, `make check`, and
  `make build` pass.
- [x] Backend production image builds with a separate runtime stage and no
  development server command.
- [x] Frontend production image builds with a separate runtime stage and no
  Nuxt development server or HMR.
- [x] Production-like orchestration starts backend and frontend without
  host-mounted source code or root runtime processes where practical.
- [x] Health and readiness checks pass against the running production-like
  stack.
- [x] API contract smoke checks pass against the running production-like stack.
- [x] Browser E2E passes against the running production-like stack.
- [x] Graceful shutdown is exercised by the production workflow.
- [x] CI verifies the production golden path without external infrastructure.
- [x] Documentation explicitly describes what `runtime_level=production` means
  and does not mean.

## Verification

Executed:

```bash
make project-status
make task-start TASK=T-008
UV_CACHE_DIR=/tmp/t008-repo-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_template_static.py
UV_CACHE_DIR=/tmp/t008-repo-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_production_golden_path.py
UV_CACHE_DIR=/tmp/t008-repo-uv-cache UV_LINK_MODE=copy uv run pytest
make validate-project
```

Generated project target flow:

```bash
make setup
make api-check
make check
make build
make image-build
make prod-up
make prod-smoke
make e2e-production
make prod-down
```

## Documentation Impact

Update generated project operations and release documentation to describe the
local production artifact workflow, runtime configuration, health/readiness
contract, release checks, graceful shutdown, and the explicit limits of the
production profile.

## Completion Notes

Implemented the `fullstack-production` runtime artifact path. Pre-change
reproduction showed that generation, setup, API check, and build could pass, but
the production Compose file still used `fastapi dev`, `pnpm dev`, host-mounted
frontend source, no frontend image, and root/default image users. The generated
`make check` path also exposed backend Pyright environment resolution issues.

The template now renders backend and frontend production images with separate
build/runtime stages, non-root runtime users, Docker ignore files, production
Compose orchestration, healthchecks, production smoke checks, browser E2E, and
CI coverage. Generated documentation explicitly describes the production
profile's meaning and limits.
