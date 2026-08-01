---
id: T-015

title: Make template and generated-project documentation self-explanatory

status: review

priority: 1

milestone: M-08

depends_on: [T-014]

approval_level: A1

approval_status: approved

blocked_reason: null

unblock_action: null

approved_by: <human>

approved_at: 2026-08-01T10:17:58+02:00
---

# T-015: Make Template and Generated-Project Documentation Self-Explanatory

## Goal

Make the template README and generated-project README useful as standalone
entry points months after last context, including purpose, structure,
architecture, workflow, state, and exactly one concrete next action.

## Context

The template already has executable golden paths and a project workflow. The
remaining release-candidate gap is documentation that explains what exists,
what is generated for each profile, and how a generated project should decide
its next step from the state/task model.

## Scope

- Update template entrypoint documentation and focused reference docs.
- Add concise D2 diagrams for the major template subsystems.
- Update generated-project README and architecture docs so they describe only
  the selected profile and current generated runtime.
- Add deterministic documentation validation targets for the template and
  generated projects.
- Extend integration tests across script-local, backend-shared,
  fullstack-local, and fullstack-production profiles and required state
  scenarios.

## Out of Scope

- External release, publishing, or tagging.
- New runtime infrastructure, workflows, or independent sources of truth.
- LLM-based prose evaluation.
- Exhaustive file catalogs or empty profile-irrelevant docs.

## Acceptance Criteria

- [x] Template README, architecture, profile matrix, development guide, and D2
  diagrams are present and navigable.
- [x] Generated README reports product purpose, profile/stack, runtime
  architecture, phase, milestone, last completed task, active/waiting/blocked
  state, next gate, exactly one next action with a command, and links to core
  docs.
- [x] Generated architecture docs distinguish current generated architecture
  from possible future extensions.
- [x] `make validate-template-docs` and generated `make validate-docs` provide
  deterministic checks for links, commands, profile drift, state dashboard,
  placeholders, personal paths, stale examples, and documentation drift.
- [x] `make validate-project` includes generated documentation validation.
- [x] Integration tests cover the requested profiles and state scenarios,
  including negative mutations that break the new checks.
- [x] `make release-check` passes without changing existing golden paths.

## Verification

- `make validate-template-docs` passed.
- `make validate-project` passed.
- `UV_CACHE_DIR=/tmp/t015-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_template_static.py tests/test_project_state_validation_golden_path.py`
  passed: 13 tests.
- `UV_CACHE_DIR=/tmp/t015-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_script_local_golden_path.py`
  passed after a formatting fix.
- `UV_CACHE_DIR=/tmp/t015-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_copier_update_golden_path.py`
  passed: 3 tests.
- `UV_CACHE_DIR=/tmp/t015-release-uv-cache UV_LINK_MODE=copy make release-check`
  passed outside the sandbox: 27 tests passed in 312.17s.

## Documentation Impact

Updated template entrypoint docs, generated-project README and architecture
templates, quality wording, D2 diagrams, Make validation targets, deterministic
documentation validators, and integration tests that cover positive profiles
and negative documentation mutations.

## Completion Notes

T-015 is implemented and ready for A1 review. A1 approval remains pending and
was not granted by the agent.
