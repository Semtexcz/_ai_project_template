# Release-Candidate Remediation Audit

Audit date: 2026-07-31

Verdict: RC-001 through RC-006 remediated in implementation and covered by
negative regression tests. Final release gate verification is recorded in this
report and should be rerun on a fresh independent audit before release.

## Tasks Created

| Task | Approval | Status | Scope |
|---|---|---|---|
| T-011 | A2 / approved | done | RC-001 transactional project mutations |
| T-012 | A2 / approved | done | RC-002 production inspection/status and RC-005 security headers |
| T-013 | A1 / approved | done | RC-003, RC-004, RC-006 release hygiene and release gate |
| T-014 | A1 / approved | done | Targeted remediation audit |

## Findings Remediation

### RC-001

Original reproduction:

- A failed mutating workflow command could persist task metadata before final
  validation. This was reproduced again while preparing T-011: an initial
  `make task-ready TASK=T-011` failed validation because the task milestone did
  not match the current project milestone, but the task status had already been
  changed to `ready`.

Root cause:

- `template/tools/project.py` performed task and state file writes before
  validating the final project state and dashboard drift. There was no shared
  rollback path for approval or lifecycle transitions.

Fix:

- Added a shared transactional mutation path for approval, ready, start,
  review, complete, block, unblock, and cancel.
- The mutation sequence is now candidate mutation, validation, dashboard
  rendering, atomic multi-file commit, final validation, and rollback on any
  failure.
- Added `task-unblock` and `task-cancel` Make targets in the root and generated
  projects.
- Disabled Python bytecode writes for project/agent workflow Make targets.

Regression test:

- `tests/test_project_state_validation_golden_path.py::test_mutating_task_commands_are_transactional_on_failure`
- `tests/test_project_state_validation_golden_path.py::test_failed_approval_does_not_persist_metadata`

Result: PASS

### RC-002

Original reproduction:

- In a generated fullstack-production project, `make image-inspect` and
  `make prod-status` failed with "No rule to make target".

Root cause:

- `template/Makefile.jinja` exposed image build/up/smoke/down commands but had
  no user-facing inspection or status commands, and `tools/fullstack.py` had no
  Docker image or Compose status inspection implementation.

Fix:

- Added `make image-inspect` for fullstack-production.
- Added image checks for backend and frontend image existence, non-root user,
  command or entrypoint, forbidden dev/reload/HMR terms, expected exposed
  ports, and basic metadata.
- Added `make prod-status` with Compose service state, health, image, and port
  output. It waits briefly for healthy services and fails for stopped or
  unhealthy stacks.

Regression test:

- `tests/test_fullstack_production_golden_path.py::test_production_inspection_and_header_negative_checks`
- `tests/test_fullstack_production_golden_path.py::test_fullstack_production_golden_path`

Result: PASS

### RC-003

Original reproduction:

- The audit found tracked Python bytecode under `template/tools/__pycache__/`.
- Generated projects inherited the template cache artifact.

Root cause:

- Cache artifacts were tracked and the template lacked sufficient static
  release hygiene coverage to reject them.

Fix:

- Removed tracked `__pycache__` and `.pyc` files.
- Added root `.gitignore`.
- Expanded generated `.gitignore` to cover Python caches, build outputs, Node
  outputs, local test artifacts, logs, and generated API artifacts.
- Added static release hygiene checks over `git ls-files`.
- Added render-only checks across script-local, library-shared, backend-shared,
  frontend-shared, fullstack-local, and fullstack-production to ensure generated
  projects do not inherit cache artifacts.

Regression test:

- `tests/test_template_static.py::test_release_hygiene_rejects_committed_artifacts_and_local_paths`
- `tests/test_template_static.py::test_release_hygiene_gitignore_and_gate_are_declared`
- `tests/test_template_static.py::test_rendered_projects_do_not_include_cache_artifacts`

Result: PASS

### RC-004

Original reproduction:

- Root `make check` ran only a fast subset and there was no distinct full
  release-candidate gate.

Root cause:

- Maintainer commands did not distinguish quick pre-review feedback from full
  release proof.

Fix:

- Added `make release-check`, which runs project validation, agent skill
  validation, and the full pytest release-candidate suite.
- Added CI coverage for `make release-check`.
- Documented `make check` as fast local/pre-review and `make release-check` as
  the full release-candidate gate.

Regression test:

- `tests/test_template_static.py::test_release_hygiene_gitignore_and_gate_are_declared`
- Full command: `make release-check`

Result: PASS

### RC-005

Original reproduction:

- Source search found no explicit production security header baseline in the
  frontend runtime or production smoke tests.

Root cause:

- The production runtime used Nuxt output directly without a local header
  contract and relied on no documented reverse proxy/ingress delegation.

Fix:

- Implemented security headers directly in `frontend/nuxt.config.ts` route
  rules:
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy` with `default-src 'self'`, `object-src 'none'`,
    `base-uri 'self'`, and `frame-ancestors 'none'`
- CSP allows Nuxt hydration with inline scripts and styles.
- Documentation explicitly states TLS and HSTS remain external ingress/reverse
  proxy responsibilities.
- Production smoke asserts the required response headers.

Regression test:

- `tests/test_fullstack_production_golden_path.py::test_production_inspection_and_header_negative_checks`
- `tests/test_fullstack_production_golden_path.py::test_fullstack_production_golden_path`

Result: PASS

### RC-006

Original reproduction:

- Running tests created `tests/__pycache__/` files that appeared in repository
  state.

Root cause:

- The repository lacked root ignore coverage and workflow commands could create
  Python bytecode cache while running agent/project tooling.

Fix:

- Added root `.gitignore` for cache and build artifacts.
- Set `PYTHONDONTWRITEBYTECODE=1` on project and agent Make targets.
- Added static checks and post-suite artifact checks.

Regression test:

- `tests/test_template_static.py::test_release_hygiene_rejects_committed_artifacts_and_local_paths`
- `git ls-files '*__pycache__*' '*.pyc' '*.pyo'`
- `find . -path './.git' -prune -o -path '*/__pycache__/*' -o -name '*.pyc' -print`

Result: PASS

## Verification

Commands already executed during remediation:

```text
UV_CACHE_DIR=/tmp/t011-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_project_state_validation_golden_path.py
PASS: 5 passed

UV_CACHE_DIR=/tmp/t011-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_agent_one_task_workflow_golden_path.py tests/test_template_static.py
PASS: 7 passed

UV_CACHE_DIR=/tmp/t012-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_production_golden_path.py::test_production_inspection_and_header_negative_checks
PASS: 1 passed

UV_CACHE_DIR=/tmp/t012-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_fullstack_production_golden_path.py
PASS: 2 passed

UV_CACHE_DIR=/tmp/t013-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_template_static.py
PASS: 6 passed

UV_CACHE_DIR=/tmp/t013-uv-cache UV_LINK_MODE=copy make check
PASS: 11 passed

UV_CACHE_DIR=/tmp/t013-uv-cache UV_LINK_MODE=copy make release-check
PASS: 25 passed in 310.37s

UV_CACHE_DIR=/tmp/t014-uv-cache UV_LINK_MODE=copy make release-check
PASS after clearing prior pytest temporary directories from /tmp: 25 passed in 336.85s

git ls-files '*__pycache__*' '*.pyc' '*.pyo'
PASS: no output

find . -path './.git' -prune -o -path '*/__pycache__/*' -o -name '*.pyc' -print
PASS: no output
```

Required matrix:

```text
RC-001: PASS
RC-002: PASS
RC-003: PASS
RC-004: PASS
RC-005: PASS
RC-006: PASS
make release-check: PASS
all profile regressions: PASS
Copier update: PASS
project workflow: PASS
agent workflow: PASS
git status: DIRTY
```

The working tree is intentionally dirty with remediation source changes,
project lifecycle updates, and this audit report. It contains no tracked or
untracked cache artifacts at the time this report was written.

## Remaining Risks

- Docker, network, and Playwright verification required approved external
  access in this environment.
- One final `make release-check` attempt failed because `/tmp` was full from
  previous pytest-generated temporary projects. After deleting
  `/tmp/pytest-of-semtex`, the same gate passed. This was an environment
  capacity issue, not a test or product regression.
- TLS and HSTS are not locally solved by the generated containers; they remain
  explicit external ingress or reverse proxy responsibilities.
- T-014 received human A1 approval and was completed after this report was
  finalized.

## Recommendation

Run a fresh independent release-candidate audit.
