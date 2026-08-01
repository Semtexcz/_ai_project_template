---
id: T-017

title: Enforce agent PR workflow

status: review

priority: 1

milestone: M-08

depends_on: []

approval_level: A1

approval_status: pending

approved_by:

approved_at:

blocked_reason: null

unblock_action: null
---

# T-017: Enforce Agent PR Workflow

## Goal

Require agents to make project changes through a branch, commit, push, and
ready GitHub pull request instead of changing `main` directly.

## Context

The template already defines a controlled task lifecycle, but it does not
explicitly require agents to publish each change through a GitHub PR. Direct
changes to `main` reduce reviewability and weaken the project workflow.

## Scope

- Document the required branch, commit, push, and ready PR workflow for agents.
- Apply the same agent-facing rule to generated projects.
- Add CI checks that flag pushes to `main` when the pushed commit has no
  associated pull request.
- Add static tests for the instruction and CI guardrails.
- Refresh the generated frontend lockfile so release-check golden paths pass
  with frozen pnpm installs.

## Out of Scope

- Configuring GitHub branch protection or repository rulesets outside the repo.
- Adding production runtime, deployment infrastructure, or external services.
- Replacing the project task lifecycle or approval model.

## Acceptance Criteria

- [x] Root agent instructions require non-`main` branches, commits, pushes, and
  ready PRs for agent-made changes.
- [x] Generated project agent instructions contain the same PR workflow rule.
- [x] Root and generated CI include a `require-pr-for-main` guard.
- [x] Static tests verify the instruction text and CI guard shape.
- [x] Project validation and focused checks pass.

## Verification

- `UV_CACHE_DIR=/tmp/t017-uv-cache uv run pytest tests/test_template_static.py::test_agent_changes_require_ready_pull_request_workflow`
  passed.
- `UV_CACHE_DIR=/tmp/t017-uv-cache make check` passed: 15 tests.
- `UV_CACHE_DIR=/tmp/t017-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_frontend_shared_golden_path.py tests/test_fullstack_local_golden_path.py tests/test_fullstack_production_golden_path.py`
  passed: 4 tests.
- `make validate-project` passed.

## Documentation Impact

Update workflow documentation to explain that the CI guard is only a signal
unless GitHub branch protection or rulesets mark it as a required check.

## Completion Notes

Agent instructions now require non-`main` branches, commits, pushes to `origin`,
and ready GitHub PRs. Root and generated CI now include a `require-pr-for-main`
job that checks GitHub's commit-associated PR API for pushes to `main` and fails
when no PR is associated with the pushed commit. Frontend and fullstack profiles
now render profile-specific pnpm lockfiles so frozen installs match each
profile's package manifest.
