---
id: T-024

title: Enforce small single-responsibility Python modules

status: review

priority: 1

milestone: M-08

depends_on: []

approval_level: A1

approval_status: pending

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-024: Enforce Small Single-Responsibility Python Modules

## Goal

Add an enforceable repository-wide architecture invariant for atomic,
single-responsibility Python modules.

## Context

The existing agent lifecycle already centralizes architecture guidance, review
readiness, deterministic checks, and generated-template validation. The module
size rule should use that system instead of adding a parallel workflow.

## Scope

- Document the module design rule in root agent instructions and canonical
  architecture documentation.
- Integrate module-responsibility checks into implementation and review skills.
- Add deterministic tooling that reports Python module size, warns above the
  soft limit, and fails above the hard limit unless an exception is documented.
- Wire the checker into the existing Makefile validation lifecycle.
- Add focused tests and generated-template coverage.

## Out of Scope

- Introducing a parallel agent workflow.
- Adding production runtime, services, databases, queues, or external
  infrastructure.
- Mechanically splitting cohesive modules solely to satisfy line-count targets.

## Acceptance Criteria

- [x] Agents are instructed to prefer cohesive, single-responsibility modules.
- [x] Python modules at 301-500 LOC produce warnings but do not fail checks.
- [x] Handwritten Python modules above 500 LOC fail without an explicit
  documented exception.
- [x] Exclusions and exceptions are configured explicitly and tested.
- [x] The normal validation lifecycle runs the architecture checker.
- [x] Generated template projects contain and can run the rule.

## Verification

- `python -m py_compile template/tools/architecture.py` passed.
- `python template/tools/architecture.py` passed: 46 modules, 3 warnings, 0
  errors. The warnings are `template/tools/fullstack.py` and documented
  exceptions for legacy template-owned lifecycle tools.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_architecture_checker.py`
  passed: 6 tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_template_static.py`
  passed after approved network access except for an intermediate generated
  setup DNS failure before rerun; final coverage is included in `make check`.
- `UV_CACHE_DIR=/tmp/uv-cache make check` passed after approved network access:
  23 tests.
- `UV_CACHE_DIR=/tmp/uv-cache UV_LINK_MODE=copy uv run pytest
  tests/test_script_local_golden_path.py tests/test_library_shared_golden_path.py
  tests/test_backend_shared_golden_path.py` passed after approved network
  access: 3 tests.
- `UV_CACHE_DIR=/tmp/uv-cache UV_LINK_MODE=copy uv run pytest
  tests/test_copier_update_golden_path.py` passed 2 tests and failed
  `test_copier_update_golden_path` in generated full-stack `make setup` because
  `corepack` is not installed in this environment.

## Documentation Impact

Update canonical architecture and quality documentation with the policy,
thresholds, exceptions, manual command, and Definition of Done participation.

## Completion Notes

Added a deterministic architecture checker, `quality.yaml` policy, Makefile
integration, generated-project propagation, agent implementation/review skill
guidance, and architecture documentation/ADR coverage. The 300 LOC threshold is
warning-only; the 500 LOC threshold fails unless a documented exception with a
reason is configured.
