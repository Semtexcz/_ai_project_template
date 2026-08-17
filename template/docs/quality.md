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
- Python module design is checked through `make check-architecture`.
- `make check` is the fast local/pre-review gate for the generated project.
- The template repository has a separate full release-candidate gate across
  every generated profile and workflow.

## Module Design

Prefer handwritten Python modules with one clear primary responsibility. Source
LOC is a review signal, not the architecture itself: `<= 200` LOC is the target,
`301-500` LOC is a warning that decomposition should be considered, and `> 500`
LOC is the deterministic hard limit.

`make check-architecture` runs `tools/architecture.py` with `quality.yaml`. The
checker counts non-blank, non-comment physical lines in `.py` files; docstrings
and executable statements count as source. It excludes configured paths where
the rule is inappropriate, such as tests, migrations, generated output, vendor
code, build artifacts, and caches.

Warnings above 300 LOC do not fail CI. A handwritten module above 500 LOC fails
unless `quality.yaml` contains an explicit exception with a path and reason.
Use exceptions only for generated code or genuinely exceptional cohesive files.
Do not split modules by arbitrary line slicing; split only along meaningful
domain or architectural boundaries.

## Test Expectations

- Domain rules have unit tests.
- Database adapters have integration tests once a database exists.
- Main workflows have E2E tests for frontend or full-stack projects.
- Authorization has negative tests once authorization exists.
- External calls have timeouts and test doubles.
- Migrations are tested once migrations exist.

## Security Baseline

- No committed secrets.
- No destructive data action without explicit human approval.
- Dependencies are updated intentionally.
- Sensitive data handling requires explicit requirements.

## Observability

Critical operations should be diagnosable. Production projects require logs, readiness checks, rollback, incident workflow, and tested restore for stateful systems.

## Production Runtime Checks

Production full-stack projects verify the runtime artifact path with:

```bash
make image-build
make image-inspect
make prod-up
make prod-status
make prod-smoke
make e2e-production
make prod-down
```

These checks prove local OCI image buildability, production process startup,
image metadata, non-root runtime users, absence of development runtime
commands, health/readiness, API contract availability, browser behavior,
frontend security headers, and graceful Compose shutdown. They do not replace
environment-specific deployment, capacity, backup, compliance validation, or
the external TLS/HSTS ingress contract.
