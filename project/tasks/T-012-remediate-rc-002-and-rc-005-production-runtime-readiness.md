---
id: T-012

title: Remediate RC-002 and RC-005 production runtime readiness

status: done

priority: 1

milestone: M-08

depends_on: [T-011]

approval_level: A2

approval_status: approved

blocked_reason: null

unblock_action: null

approved_by: <human>

approved_at: 2026-07-31T20:33:07+02:00
---

# T-012: Remediate RC-002 and RC-005 Production Runtime Readiness

## Goal

Make the fullstack-production profile expose reproducible production inspection
and status commands and enforce a documented frontend security header baseline.

## Context

The release-candidate audit found that the production profile builds and runs
containers but lacks user-facing inspection and status commands. It also found
no explicit production security header contract, leaving the profile short of a
minimal production runtime baseline.

## Scope

- Reproduce missing `make image-inspect` and `make prod-status` in a generated
  fullstack-production project.
- Add real `image-inspect` checks for backend and frontend image existence,
  non-root runtime users, entrypoint or command, no dev server/reload/HMR
  runtime, expected exposed ports, and basic image metadata.
- Add `prod-status` output for Compose services, health, images, and ports, and
  make it fail when the stack is not healthy.
- Implement minimal production security headers in the frontend runtime unless
  a stricter local implementation proves infeasible.
- Add positive and negative tests and CI coverage for production inspection,
  status, and required headers.

## Out of Scope

- External deployment, image push, release tags, cloud ingress, Kubernetes, or
  public TLS/HSTS claims.
- Adding databases, queues, Redis, brokers, or external infrastructure.

## Acceptance Criteria

- [x] `make image-inspect` passes on healthy generated production images and
  fails on mutated insecure images or dev commands.
- [x] `make prod-status` shows service state, health, images, and ports and
  fails on a stopped or unhealthy stack.
- [x] Required production security headers are present without breaking Nuxt
  hydration.
- [x] CI exercises the new production inspection, status, and header tests.

## Verification

- Reproduced RC-002 with generated fullstack-production: `make image-inspect`
  and `make prod-status` both failed with "No rule to make target".
- Reproduced RC-005 with source search showing no security header contract in
  generated frontend runtime.
- `UV_CACHE_DIR=/tmp/t012-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_production_golden_path.py::test_production_inspection_and_header_negative_checks` passed.
- `UV_CACHE_DIR=/tmp/t012-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_production_golden_path.py` passed after approved Docker/socket/network access.
- `UV_CACHE_DIR=/tmp/t012-uv-cache UV_LINK_MODE=copy make check` passed.
- `make validate-project` passed.
- `make validate-agent-skills` passed.

## Documentation Impact

Documented `image-inspect`, `prod-status`, and the production security header
contract in generated README, workflow, quality, and architecture docs.

## Completion Notes

Implemented production inspection and status commands in generated
fullstack-production projects. Added Docker image contract inspection,
Compose status/health reporting with retry, frontend security headers via Nuxt
route rules, production smoke header assertions, and positive/negative
regression coverage.
