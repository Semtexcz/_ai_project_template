---
type: quality
status: active
source_of_truth_for:
  - quality-gates
read_when:
  - prepare-task
  - implement-change
  - review-change
update_when:
  - test-strategy-change
  - runtime-level-change
---

# Quality

## Baseline

- Formatting and linting run through `make lint`.
- Type checking runs through `make typecheck`.
- Tests run through `make test`.
- Full verification runs through `make check`.

## Test Expectations

- Domain rules have unit tests.
- Database adapters have integration tests once a database exists.
- Main workflows have E2E tests for frontend or full-stack projects.
- Authorization has negative tests once authorization exists.
- External calls have timeouts and test doubles.
- Migrations are tested once migrations exist.

## Security Baseline

- No committed secrets.
- No destructive data action without A2 approval.
- Dependencies are updated intentionally.
- Sensitive data handling requires explicit requirements.

## Observability

Critical operations should be diagnosable. Production projects require logs, readiness checks, rollback, incident workflow, and tested restore for stateful systems.

## Production Runtime Checks

Production full-stack projects verify the runtime artifact path with:

```bash
make image-build
make prod-up
make prod-smoke
make e2e-production
make prod-down
```

These checks prove local OCI image buildability, production process startup,
health/readiness, API contract availability, browser behavior, and graceful
Compose shutdown. They do not replace environment-specific deployment,
capacity, security, backup, or compliance validation.
