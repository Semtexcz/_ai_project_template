---
id: T-013

title: Remediate RC-003 RC-004 and RC-006 release hygiene and gate

status: done

priority: 1

milestone: M-08

depends_on: [T-012]

approval_level: A1

approval_status: approved

blocked_reason: null

unblock_action: null

approved_by: <human>

approved_at: 2026-07-31T20:55:33+02:00
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

- [x] The repository has no tracked cache artifacts.
- [x] Running the test suite does not leave unexpected Git diff.
- [x] Generated projects contain no inherited cache artifacts.
- [x] `make release-check` runs every release-candidate suite and propagates
  errors without `|| true`.
- [x] Documentation accurately distinguishes `make check` and
  `make release-check`.

## Verification

- Reproduced RC-003/RC-006 via tracked and generated `__pycache__`/`.pyc`
  audit evidence, then removed tracked cache artifacts and added ignore/static
  coverage.
- Reproduced RC-004 from root `Makefile`: `make check` was a narrow subset
  with no full release gate target.
- `UV_CACHE_DIR=/tmp/t013-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_template_static.py` passed.
- `UV_CACHE_DIR=/tmp/t013-uv-cache UV_LINK_MODE=copy make check` passed.
- `UV_CACHE_DIR=/tmp/t013-uv-cache UV_LINK_MODE=copy make release-check` passed: 25 tests in 310.37s after approved Docker/socket/network access.
- `git ls-files '*__pycache__*' '*.pyc' '*.pyo'` returned no tracked cache artifacts.
- `find . -path './.git' -prune -o -path '*/__pycache__/*' -o -name '*.pyc' -print` returned no cache artifacts after the full suite.

## Documentation Impact

Updated root README and generated quality docs for release gate semantics.

## Completion Notes

Added root and generated `.gitignore` coverage, release hygiene static tests,
rendered-project cache assertions across all profiles, a full `make
release-check` target, and CI coverage for the release gate. The full release
gate now exercises all maintained profile and workflow tests and propagates
failures directly.
