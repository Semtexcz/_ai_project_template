---
id: T-014

title: Run targeted remediation audit

status: backlog

priority: 1

milestone: M-08

depends_on: [T-013]

approval_level: A1

approval_status: pending

blocked_reason:

unblock_action:
---

# T-014: Run Targeted Remediation Audit

## Goal

Independently verify that RC-001 through RC-006 are closed by real fixes and
negative regression evidence.

## Context

After the remediation implementation tasks are complete, the project needs a
separate audit pass focused on the original six release-candidate findings. The
audit must prove both the positive golden paths and the new negative regression
checks.

## Scope

- Re-run each original RC-001 through RC-006 reproduction.
- Verify the new regression tests fail against the old behavior and pass
  against the remediated implementation.
- Run the full release gate and required golden paths.
- Record exact verification commands, results, remaining risks, and release
  recommendation.

## Out of Scope

- Implementing new remediation changes beyond narrow fixes for audit failures.
- Granting A1 or A2 approval.
- Deployment, publishing, image push, or release tagging.

## Acceptance Criteria

- [ ] RC-001 through RC-006 each have reproduction, root cause, fix, regression
  test, and pass/fail result recorded.
- [ ] `make release-check` passes.
- [ ] Project workflow, agent workflow, Copier update, context security, and
  all profile regressions pass.
- [ ] Git status and any unverified risks are explicitly reported.

## Verification

- Run all commands required by the release-candidate audit remediation plan.
- Run `make sync-project-docs` and `make validate-project`.

## Documentation Impact

Add or update the targeted remediation audit report.

## Completion Notes

Pending implementation.
