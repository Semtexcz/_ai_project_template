---
id: T-021

title: Fix lightweight render matrix CI

status: done

priority: 1

milestone: M-08

depends_on: []

approval_level: A0

approval_status: not-required

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-021: Fix Lightweight Render Matrix CI

## Goal

Fix the GitHub Actions render-matrix validation so lightweight generated
projects are not validated with managed-only Make targets.

## Context

PR #4 failed because render-matrix now generates lightweight projects by
default, but the workflow still runs `make sync-project-docs` and
`make validate-project`, which exist only in managed governance.

## Scope

- Update template CI render-matrix validation to use lightweight-compatible
  checks by default.
- Preserve managed governance validation coverage.
- Run focused local validation for the workflow and project state.

## Out of Scope

- Changing production runtime behavior.
- Reworking the governance implementation.
- Adding external infrastructure or services.

## Acceptance Criteria

- [x] Lightweight render-matrix entries do not call managed-only targets.
- [x] Managed render-matrix coverage still validates managed lifecycle tooling.
- [x] Relevant local validation passes.

## Verification

- `make validate-project` passed.
- `make validate-template-docs` passed.
- `make validate-agent-skills` passed.
- `make check` passed: 21 tests in 152.11 seconds.
- Focused static test passed:
  `tests/test_template_static.py::test_template_ci_render_matrix_respects_governance_modes`.
- Lightweight render-matrix simulation passed for `frontend + shared +
  lightweight` with `make validate-docs`.
- Managed render-matrix simulation passed for `fullstack + production +
  managed` with `make sync-project-docs`, `make validate-project`,
  `make validate-agent-skills`, and `make validate-docs`.

## Documentation Impact

No user-facing documentation change expected; this is CI wiring for existing
documented governance behavior.

## Completion Notes

Updated the root Template CI render-matrix job to pass `governance` explicitly,
render lightweight and managed coverage separately, and run managed-only Make
targets only when `matrix.governance == managed`. Also fixed generated
lightweight Makefiles so the `validate-docs` target is rendered outside the
managed-only block.
