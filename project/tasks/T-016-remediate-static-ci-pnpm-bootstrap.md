---
id: T-016

title: Remediate static CI pnpm bootstrap

status: review

priority: 1

milestone: M-08

depends_on: [T-015]

approval_level: A1

approval_status: approved

blocked_reason: null

unblock_action: null

approved_by: <human>

approved_at: 2026-08-01T11:00:00+02:00
---

# T-016: Remediate Static CI Pnpm Bootstrap

## Goal

Make generated frontend and fullstack projects pass static CI when the runner
does not provide a global `pnpm` binary.

## Context

The static `uv run pytest` CI job generates frontend and fullstack projects and
then runs `make setup`. Those generated Makefiles invoke `pnpm` directly. On
the static runner, `pnpm` is not installed globally, so the setup target fails
before frontend dependencies can be installed.

## Scope

- Reproduce or inspect the failing generated `make setup` path.
- Update template-generated frontend/fullstack Makefiles to bootstrap package
  manager execution without requiring a global `pnpm`.
- Preserve existing `PNPM_INSTALL_FLAGS`, `PNPM_HOME`, and `PNPM_STORE_DIR`
  behavior expected by tests.
- Add or update focused tests for the generated command surface.

## Out of Scope

- Changing frontend framework, dependency versions, or lockfile strategy.
- Adding external infrastructure or CI-only setup steps outside the template.
- Replacing `pnpm` as the generated project package manager.

## Acceptance Criteria

- [x] Generated frontend and fullstack `make setup` works when no global `pnpm`
  binary is present but `corepack` is available.
- [x] Existing frontend/fullstack static golden-path tests pass.
- [x] Copier update golden path still passes.
- [x] Project validation passes.

## Verification

- `UV_CACHE_DIR=/tmp/t016-uv-cache uv run pytest tests/test_template_static.py`
  passed: 8 tests.
- `UV_CACHE_DIR=/tmp/t016-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_frontend_shared_golden_path.py`
  passed.
- `UV_CACHE_DIR=/tmp/t016-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_local_golden_path.py tests/test_copier_update_golden_path.py`
  passed: 4 tests.
- `UV_CACHE_DIR=/tmp/t016-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_production_golden_path.py`
  passed: 2 tests.
- `UV_CACHE_DIR=/tmp/t016-uv-cache UV_LINK_MODE=copy uv run pytest`
  passed: 28 tests in 294.63s.
- `make validate-project` passed.
- `make validate-agent-skills` passed.

## Documentation Impact

No user-facing setup command changed. Generated `.gitignore` now excludes the
local `.corepack/` cache directory used to bootstrap pinned pnpm.

## Completion Notes

Generated frontend/fullstack commands now use a Corepack-backed, overridable
`PNPM` wrapper with project-local `COREPACK_HOME`. Generated Python helpers use
the same default wrapper, and integration tests exercise `make e2e` instead of
assuming a global `pnpm` binary.
