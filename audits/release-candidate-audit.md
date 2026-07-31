# Release-Candidate Audit

## Executive Summary

Final verdict: `REWORK REQUIRED`.

Findings: 0 Critical, 2 High, 3 Medium, 1 Low.

Largest risk: task approval state changes are not transactional. A failed
`make task-approve` invocation can still persist `approval_status: approved`,
which undermines the approval boundary and leaves the project in a partially
mutated state.

Recommendation: do not release this RC for first real use until the High
findings are fixed and the production inspection/status path is reproducible.

## Environment

- Commit: `616c4dfc433be4c24de29503757e4317590dae34`
- Initial worktree: clean before audit task creation was not preserved; audit
  created T-010, synchronized dashboards, generated this report, and pytest
  generated transient `tests/__pycache__/`.
- OS: Linux Semtex-NTB 6.17.0-41-generic x86_64
- Python: 3.13.7
- uv: 0.11.28
- Copier: 9.17.0
- Node: v22.20.0
- pnpm: 10.20.0
- Docker: 28.3.3
- Docker Compose: v2.39.1
- Git: 2.51.0
- Audit date: 2026-07-31

Environment limitations:

- Sandbox blocked network and sockets. The full suite failed in sandbox-only
  mode, then passed after approved network/socket/container access.
- I accidentally ran `make task-approve TASK=T-010 APPROVED_BY=AutomatedAgent`
  once in the main repository while testing approval bypass. I immediately
  reverted only that approval metadata to `pending` and revalidated project
  state. This incident is also evidence that the CLI can write approval metadata
  without a real human boundary.
- The audit did not publish packages, push Git changes, create release tags, or
  deploy externally.

## Scope

Audited:

- Required baseline commands: `make project-status`, `make validate-project`,
  `make validate-agent-skills`.
- Full maintainer test suite: `UV_CACHE_DIR=/tmp/uv-cache UV_TOOL_DIR=/tmp/uv-tools UV_LINK_MODE=copy uv run pytest`.
- Clean Copier generation for all declared profile combinations.
- Context resolver secret exclusion with real `.env`, `.env.production`, PEM,
  credentials, dependency/build directories, and external symlink.
- Production Make targets, Dockerfile/Compose structure, CI workflow contents,
  release hygiene, Markdown links, and project dashboard sync.
- Selected mutation/negative scenarios for invalid profile input, context
  secret inclusion, invalid task state, and approval state mutation.

Not fully audited:

- Every requested negative mutation in every subsystem.
- Manual image layer inspection for absence of VCS metadata/secrets.
- Full two-version Copier update rebuilt independently outside the existing
  integration test implementation.
- Browser production path with packet-level proof of frontend-container to
  backend-container routing.

## Test Matrix

| Area | Scenario | Result | Evidence | Finding |
|---|---:|---:|---|---|
| Generation | script-local | PASS | `uvx copier copy ... project_type=script runtime_level=local`, exit 0, 1s | RC-003 |
| Generation | library-shared | PASS | `uvx copier copy ... project_type=library runtime_level=shared`, exit 0, 2s | RC-003 |
| Generation | backend-shared | PASS | `uvx copier copy ... project_type=backend runtime_level=shared`, exit 0, 1s | RC-003 |
| Generation | frontend-shared | PASS | `uvx copier copy ... project_type=frontend runtime_level=shared`, exit 0, 2s | RC-003 |
| Integration | fullstack-local | PASS | full suite `tests/test_fullstack_local_golden_path.py`, passed | - |
| Runtime | fullstack-production | FAIL | `make image-inspect` and `make prod-status` missing | RC-002 |
| Upgrade | Copier v1 -> v2 | PASS | full suite `tests/test_copier_update_golden_path.py`, passed | - |
| Workflow | A0 | PASS | full suite agent one-task workflow passed | - |
| Workflow | A1 | FAIL | failed approval command persisted approval metadata | RC-001 |
| Workflow | A2 | PARTIAL | suite blocks start without approval; approval CLI boundary remains process-only | RC-001 |
| Agent | context security | PASS | sensitive files absent; explicit `.env` context include failed | - |
| Agent | one-task workflow | PASS | full suite `tests/test_agent_one_task_workflow_golden_path.py`, passed | - |
| CI | all golden paths | PASS | `.github/workflows/template-ci.yml` has separate jobs for all major paths | RC-004 |
| Docs | commands and links | PASS | Markdown link checker found no missing local links | RC-006 |
| Release | repository hygiene | FAIL | tracked `template/tools/__pycache__/project.cpython-313.pyc` | RC-003 |

Full suite result after approved access: `19 passed in 261.92s`.

## Findings Summary

| Severity | Count |
|---|---:|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 1 |

## Detailed Findings

### RC-001

Severity: High

Area: Project workflow / approvals

Affected profiles: all profiles

Summary: `make task-approve` writes approval metadata before validating the
resulting project state, so a failed command can still leave an A1/A2 task
marked approved.

Evidence: In `/tmp/rc-audit-profiles-1785518781/script-local`, I copied an A1
task with incompatible milestone/dependency metadata and ran:

```bash
make task-approve TASK=T-010 APPROVED_BY=AutomatedAgent
```

The command exited 2 with validation errors, but the task file contained:

```text
approval_status: approved
approved_by: AutomatedAgent
approved_at: 2026-07-31T19:27:59+02:00
```

Source code confirms the ordering in `template/tools/project.py`: `approve()`
calls `update_task_frontmatter(...)`, then `sync()`, with no pre-validation or
rollback.

Reproduction:

1. In a generated project, add an A1 task whose metadata makes the project
   invalid after sync.
2. Run `make task-approve TASK=<id> APPROVED_BY=AutomatedAgent`.
3. Observe exit code 2 and persisted approval metadata.

Expected behavior: state-changing commands validate candidates before writing
or roll back on failure.

Actual behavior: failed approval persists partial approval metadata.

Impact: approval state can be corrupted by an agent or failed automation path.
This is release-blocking for a template that relies on A1/A2 governance.

Recommended remediation: make approval updates transactional: construct a
candidate state/task set, validate it, then atomically write and sync only after
validation passes. Add a negative regression test asserting failed approval
does not modify the task file.

Release-blocking: yes

### RC-002

Severity: High

Area: Production runtime

Affected profiles: fullstack-production

Summary: The generated production profile lacks required `image-inspect` and
`prod-status` targets.

Evidence:

```bash
cd /tmp/rc-audit-profiles-1785518781/fullstack-production
make image-inspect
# make: *** No rule to make target 'image-inspect'. Stop.
make prod-status
# make: *** No rule to make target 'prod-status'. Stop.
```

`template/Makefile.jinja` defines `image-build`, `prod-up`, `prod-smoke`,
`prod-down`, and `e2e-production`, but not `image-inspect` or `prod-status`.

Reproduction: generate `project_type=fullstack runtime_level=production`, then
run the two commands above.

Expected behavior: production profile exposes inspect/status commands that
verify image users, commands, health status, and running service state.

Actual behavior: both commands are missing.

Impact: the production golden path cannot execute the declared audit/runtime
inspection flow and relies on tests/static checks instead of a user-facing
inspection command.

Recommended remediation: add `image-inspect` and `prod-status` targets with
real Docker/Compose inspection and CI coverage.

Release-blocking: yes

### RC-003

Severity: Medium

Area: Release hygiene / generated project cleanliness

Affected profiles: all generated profiles

Summary: A Python bytecode cache file is tracked in the template and copied
into generated projects.

Evidence:

```bash
git ls-files template/tools/__pycache__/project.cpython-313.pyc
# template/tools/__pycache__/project.cpython-313.pyc
```

Clean generated projects also contain `tools/__pycache__/project.cpython-313.pyc`.

Reproduction: generate any profile and run:

```bash
find <generated> -path '*/__pycache__/*' -type f
```

Expected behavior: no bytecode/cache artifacts are committed or generated.

Actual behavior: template-owned bytecode is shipped.

Impact: low functional risk, but poor release hygiene and avoidable generated
project noise.

Recommended remediation: remove the tracked pycache file, ensure `.gitignore`
covers it, and add a static test rejecting tracked cache/build artifacts.

Release-blocking: no

### RC-004

Severity: Medium

Area: CI / local parity

Affected profiles: maintainer workflow

Summary: Root `make check` is a fast gate, while full release proof requires
`uv run pytest`; this distinction is easy to miss in a release-candidate flow.

Evidence: root `Makefile` `check` runs only
`tests/test_template_static.py` and `tests/test_project_state_validation_golden_path.py`.
The full suite with all profile golden paths is behind `make test-template` or
`uv run pytest`.

Reproduction:

```bash
make check
uv run pytest
```

Expected behavior: the release-candidate command clearly runs all release
golden paths, or docs label `make check` as a narrow fast gate.

Actual behavior: `make check` can be green while profile golden paths remain
untested locally.

Impact: maintainers may treat a partial local gate as release evidence.

Recommended remediation: add a `make release-check` target that runs all RC
golden paths, and document `make check` as a fast pre-review subset.

Release-blocking: no

### RC-005

Severity: Medium

Area: Production security baseline

Affected profiles: fullstack-production

Summary: Production security headers are not explicitly implemented or tested.

Evidence: source search found CORS configuration, but no explicit implementation
or tests for headers such as content type hardening, frame options, referrer
policy, or CSP. The production test checks runtime files, health, OpenAPI,
smoke, and E2E, but not response security headers.

Reproduction:

```bash
rg -n "Strict-Transport|X-Content|Content-Security|Referrer-Policy|Frame-Options" template tests
```

Expected behavior: the production profile either implements a minimal header
baseline or documents why it is delegated to an external reverse proxy.

Actual behavior: no explicit baseline or test exists.

Impact: production profile is local/OCI-ready but not security-baseline-ready
as claimed by the audit checklist.

Recommended remediation: add minimal headers in the app/runtime layer or state
that they are reverse-proxy responsibilities, then add smoke assertions.

Release-blocking: no

### RC-006

Severity: Low

Area: Audit process / repository state

Affected profiles: template repository

Summary: Running tests in the repository creates untracked `tests/__pycache__/`
files.

Evidence:

```bash
find . -type f -name '*.pyc'
```

showed generated `tests/__pycache__/*.pyc` after the full test run.

Reproduction: run `uv run pytest`, then `git status --short`.

Expected behavior: generated cache artifacts are ignored and cleaned, or at
least not confused with audit changes.

Actual behavior: untracked pycache appears in the worktree.

Impact: minor maintainer friction.

Recommended remediation: ensure repository `.gitignore` covers test pycache and
consider a cleanup check in release hygiene.

Release-blocking: no

## Profile Results

### script-local

Clean Copier generation passed. Full suite script golden path passed, including
`make setup`, `make check`, `make build`, wheel/sdist existence. Negative state
and context mutations failed as expected. Generated project contains the tracked
`tools/__pycache__` artifact from RC-003.

### library-shared

Clean generation passed. Full suite library golden path passed, including
package build and clean wheel use. Static file list showed `py.typed`, no
`__main__.py`, and no frontend/backend directories. RC-003 applies.

### backend-shared

Clean generation passed. Full suite backend golden path passed, including
setup/check/build, clean wheel install, startup, `/health`, `/ready`,
`/openapi.json`, and system endpoint behavior. No frontend directory was present.

### frontend-shared

Clean generation passed. Full suite frontend golden path passed, including
setup/check/build/run and HTTP smoke. No backend directory was present.

### fullstack-local

Full suite fullstack-local golden path passed. It covered setup, OpenAPI export,
generated client check, check, build, run, and browser E2E. I did not
independently mutate backend response drift outside the existing test suite.

### fullstack-production

Full suite production golden path passed after approved Docker/socket access.
Dockerfiles use multi-stage builds and non-root `USER app`; Compose has
healthchecks and no source bind mounts. The generated project fails the required
`make image-inspect` and `make prod-status` commands, so the profile is not
release-ready.

## Copier Update

Existing independent-style integration test passed in the full suite:
`tests/test_copier_update_golden_path.py`.

It creates a temporary template Git repo, tags `v1.0.0`, generates
`fullstack-local`, commits user modifications, creates `v1.1.0`, runs Copier
update, checks preservation, and reruns setup/API/check/build/E2E. I did not
manually repeat every requested conflict/source-negative scenario outside that
test.

## Project Workflow

Baseline:

- Phase: delivery
- Milestone: M-07
- Next gate: production-runtime-golden-path
- Active task during audit: T-010
- Approval: A1 / pending

`make validate-project` passed. Dashboard sync was idempotent for the audit
state. A0 workflow passed through suite. A1/A2 blocking checks exist and passed
in suite, but RC-001 shows approval mutation is not transactional and remains a
release-blocking governance risk.

## Agent Workflow

`make validate-agent-skills` passed. `make agent-context TASK=T-010 FORMAT=json`
returned a small deterministic control/task context. `.codex/` appears to be a
thin adapter. Context secret exclusions passed both passive and explicit-include
tests.

Pre-task, pre-review, and post-task behavior was covered by the full agent
workflow suite; I did not exhaust every hook negative scenario manually.

## Production Runtime

Verified through full suite and static inspection:

- backend and frontend Dockerfiles are multi-stage,
- both runtime stages use `USER app`,
- no reload/HMR/dev commands in runtime commands,
- Compose uses healthchecks and no source bind mounts,
- production smoke and Playwright E2E passed.

Gaps:

- missing `image-inspect`,
- missing `prod-status`,
- no explicit security header baseline,
- no manual image layer inspection in this audit.

## CI and Test Quality

CI defines jobs for static tests, render matrix, all six profile golden paths,
project-state validation, Copier update, and agent one-task workflow. No
`|| true` or `continue-on-error` masking was found.

The test suite is meaningfully integration-heavy and passed after environment
access was approved. Remaining test quality gaps are RC-001 transaction
coverage, RC-002 command coverage, RC-003 artifact hygiene coverage, and RC-005
security header coverage.

## Documentation and Release Hygiene

Local Markdown link check passed. Upgrade docs correctly say not to edit
`.copier-answers.yml` by hand. The root README documents the maintainer full
suite via `uv run pytest`, but the distinction between `make check` and full
release proof should be sharper. Release hygiene fails on tracked pycache.

## Unverified Areas

- Complete manual negative matrix for every profile.
- Independent manual production root/development-command mutation tests.
- Manual image filesystem inspection for secrets/VCS metadata.
- Exact packet-level proof that production browser data path goes through the
  intended container network rather than only host-published API access.
- Complete manual Copier conflict and unavailable-source negative scenarios.

## Release Conditions

Not applicable because the verdict is `REWORK REQUIRED`.

## Final Verdict

`REWORK REQUIRED`

## Recommended Next Action

Fix RC-001 by making task approval updates transactional and adding a regression
test that failed approval leaves the task file unchanged.

## Required Closing Summary

script-local: PASS
library-shared: PASS
backend-shared: PASS
frontend-shared: PASS
fullstack-local: PASS
fullstack-production: FAIL
Copier update: PASS
project-state validation: PASS
A0 workflow: PASS
A1 boundary: FAIL
A2 boundary: PARTIAL
agent skill validation: PASS
context security: PASS
one-task workflow: PASS
pre-task hook: PASS
pre-review hook: PASS
post-task hook: PASS
CI parity: PASS
documentation accuracy: PASS
release hygiene: FAIL
mutation testing: PARTIAL
cleanup: PASS

Critical findings: 0
High findings: 2
Medium findings: 3
Low findings: 1

Final verdict: REWORK REQUIRED
