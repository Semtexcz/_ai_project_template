---
id: T-013

title: Remediate RC-003 RC-004 and RC-006 release hygiene and gate

status: backlog

priority: 1

milestone: M-08

depends_on: [T-012]

approval_level: A1

approval_status: pending

blocked_reason:

unblock_action:
---

# T-013: Remediate RC-003 RC-004 and RC-006 Release Hygiene and Gate

## Goal

Remove release hygiene defects and add an unambiguous full release gate.

## Context

The release-candidate audit found tracked bytecode in the template, cache noise
after test runs, and an ambiguous maintainer gate where `make check` is fast but
not the complete release proof. These issues need one hygiene and release-gate
remediation path.

## Scope

- Reproduce tracked Python cache artifacts and test-created worktree noise.
- Remove tracked `__pycache__` and `.pyc` files.
- Fix `.gitignore` in the template and generated projects.
- Add a static release hygiene check rejecting committed caches, build
  artifacts, local absolute paths, and obvious release debris.
- Verify generated projects do not inherit template cache artifacts.
- Add `make release-check` as the complete release-candidate gate.
- Document `make check` as a fast local/pre-review gate and
  `make release-check` as the full release gate.

## Out of Scope

- Weakening existing checks or hiding test failures.
- External deployment, publishing, release tags, or image pushes.

## Acceptance Criteria

- [ ] The repository has no tracked cache artifacts.
- [ ] Running the test suite does not leave unexpected Git diff.
- [ ] Generated projects contain no inherited cache artifacts.
- [ ] `make release-check` runs every release-candidate suite and propagates
  errors without `|| true`.
- [ ] Documentation accurately distinguishes `make check` and
  `make release-check`.

## Verification

- Run targeted release hygiene tests.
- Run generated profile hygiene assertions.
- Run `make release-check`.
- Run `make sync-project-docs` and `make validate-project`.

## Documentation Impact

Update maintainer and generated project documentation for release hygiene and
release gate semantics.

## Completion Notes

Pending implementation.
