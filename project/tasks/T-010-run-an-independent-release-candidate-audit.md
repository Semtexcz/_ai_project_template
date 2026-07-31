---
id: T-010

title: Run an independent release-candidate audit

status: done

priority: 1

milestone: M-07

depends_on: [T-009]

approval_level: A1

approval_status: approved

approved_by: Daniel Kopecký

approved_at: 2026-07-31T20:08:46+02:00

blocked_reason:

unblock_action:
---

# T-010: Run an Independent Release-Candidate Audit

## Goal

Independently audit the release-candidate software project template for first
real-world use readiness across generation, update, project workflow, agent
workflow, CI, documentation, release hygiene, and production runtime behavior.

## Context

The template has completed implementation tasks for all declared profiles,
Copier update safety, project workflow validation, production runtime, and
agent workflow. This task validates those claims from the perspective of an
independent release-candidate auditor.

## Scope

- Record repository, environment, lifecycle, and approval baseline.
- Reproduce clean generation and user workflows for declared profiles.
- Exercise positive and negative checks for project state, approvals, agent
  hooks, context security, generated API client drift, production runtime, CI
  parity, documentation accuracy, and release hygiene.
- Write a final audit report with reproducible findings, severity, evidence,
  impact, remediation guidance, and release verdict.
- Move this task to `review` when the audit report is complete.

## Out of Scope

- Fixing template implementation defects discovered during the audit.
- Lowering validation strictness or editing tests to pass.
- Publishing packages, container images, tags, releases, or deployments.
- Granting A1/A2 approval or marking this task `done`.

## Acceptance Criteria

- [x] Baseline repository state, environment versions, lifecycle status, and
  approvals are recorded.
- [x] Each declared profile is independently generated and audited in a clean
  temporary directory as far as the local environment permits.
- [x] Required workflow, approval, agent, context, hook, Copier update,
  production runtime, CI, documentation, release hygiene, determinism, and
  mutation checks are performed or explicitly listed as unverified with reason.
- [x] Findings use the required Critical/High/Medium/Low severity taxonomy and
  include reproducible evidence.
- [x] A final audit report is committed to the project as an audit artifact.
- [x] This task is moved to `review` without human A1 approval and without
  being marked `done`.

## Verification

- `make project-status` passed and recorded T-010 as active, A1 / pending.
- `make validate-project` passed.
- `make validate-agent-skills` passed.
- `make agent-context TASK=T-010 FORMAT=json` passed.
- `UV_CACHE_DIR=/tmp/uv-cache UV_TOOL_DIR=/tmp/uv-tools UV_LINK_MODE=copy uv run pytest` passed with 19 tests after approved network/socket/container access.
- Clean Copier generation passed for `script-local`, `library-shared`,
  `backend-shared`, `frontend-shared`, `fullstack-local`, and
  `fullstack-production`.
- Negative checks reproduced invalid Copier choice failure, context secret
  exclusion, invalid task state failure, missing production targets, approval
  partial mutation, and tracked pycache hygiene failure.
- Final report: `audits/release-candidate-audit.md`.

## Documentation Impact

Added `audits/release-candidate-audit.md`.

## Completion Notes

Independent RC audit completed with verdict `REWORK REQUIRED`. The task is
ready for review, remains A1 / pending, and must not be approved or marked done
by an agent.
