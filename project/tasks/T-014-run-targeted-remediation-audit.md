---
id: T-014

title: Run targeted remediation audit

status: review

priority: 1

milestone: M-08

depends_on: [T-013]

approval_level: A1

approval_status: approved

blocked_reason: null

unblock_action: null

approved_by: <human>

approved_at: 2026-07-31T21:10:51+02:00
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

- [x] RC-001 through RC-006 each have reproduction, root cause, fix, regression
  test, and pass/fail result recorded.
- [x] `make release-check` passes.
- [x] Project workflow, agent workflow, Copier update, context security, and
  all profile regressions pass.
- [x] Git status and any unverified risks are explicitly reported.

## Verification

- Added `audits/release-candidate-remediation-audit.md`.
- `UV_CACHE_DIR=/tmp/t014-uv-cache UV_LINK_MODE=copy make release-check`
  passed after clearing prior pytest temporary directories from `/tmp`: 25
  tests passed in 336.85s.
- `git ls-files '*__pycache__*' '*.pyc' '*.pyo'` returned no output.
- `find . -path './.git' -prune -o -path '*/__pycache__/*' -o -name '*.pyc' -print` returned no output.
- `make validate-project` passed.
- `make validate-agent-skills` passed.

## Documentation Impact

Added the targeted remediation audit report.

## Completion Notes

Targeted remediation audit completed for RC-001 through RC-006. The report
records original reproductions, root causes, fixes, regression tests, command
results, remaining risks, and the required recommendation.
