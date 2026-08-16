---
id: T-022

title: Refactor agent skill architecture

status: in-progress

priority: 1

milestone: M-08

depends_on: []

approval_level: A0

approval_status: not-required

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-022: Refactor Agent Skill Architecture

## Goal

Separate reusable engineering skills from managed project governance so
lightweight projects retain useful agent capabilities without inheriting the
managed task lifecycle.

## Context

Lightweight governance currently excludes `.agents/` and `.codex/`, which
removes reusable skills along with lifecycle-specific project-management
machinery. Skills should represent reusable capabilities, while governance
should control project-management process.

## Scope

- Render core engineering skills for lightweight and managed projects.
- Isolate managed lifecycle skills from lightweight projects.
- Add missing core skills for orientation, verification, documentation impact,
  ADR decisions, and learning capture.
- Add capability-specific skills only for template-specific workflows.
- Keep `.agents/` canonical and `.codex/` as a thin adapter.
- Update context routing, validation, tests, and documentation.

## Out of Scope

- Adding a new orchestration workflow engine.
- Adding language/framework-generic skills with no template-specific value.
- Changing approval boundaries or adding external infrastructure.

## Acceptance Criteria

- [ ] Core engineering skills are independent from managed governance.
- [ ] Lightweight generated projects retain core skills without managed state
  files.
- [ ] Managed lifecycle skills remain managed-only and functional.
- [ ] Capability skills render only for relevant profiles.
- [ ] Context routing works without assuming active task state.
- [ ] Codex adapters delegate to canonical `.agents` skills.
- [ ] Relevant tests and documentation are updated.
- [ ] `make check` and `make release-check` pass.

## Verification

- `make validate-agent-skills` passed.
- `make validate-template-docs` passed.
- `make validate-project` passed.
- `make check` passed: 23 tests in 215.16 seconds.
- Focused static tests passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_template_static.py -k 'not non_mutating'`
  passed, 16 tests.
- Focused managed-skill negative test passed:
  `tests/test_agent_one_task_workflow_golden_path.py::test_agent_negative_scenarios`.
- Representative render checks passed for `script + local + lightweight`,
  `backend + shared + lightweight`, `fullstack + local + lightweight`, and
  `fullstack + production + managed`; each rendered project passed
  `make validate-agent-skills`.
- `make release-check` was attempted. It did not complete in this environment
  because Node/Corepack is unavailable (`/bin/sh: 1: corepack: not found`) for
  frontend/full-stack golden paths. A stale test path in
  `test_agent_negative_scenarios` was fixed and rerun successfully.

## Documentation Impact

Required. The root README, agent-layer docs, generated workflow/architecture
docs, and adapter docs must describe the new skill architecture and remove
stale statements tying `.agents/` only to managed governance.

## Completion Notes

Split canonical skills into core, managed, and capability groups. Lightweight
projects now render core `.agents` skills, thin `.codex` adapters, and
`tools/agent.py` for skill validation without rendering managed state files or
lifecycle commands. Managed projects render lifecycle skills under
`.agents/managed/skills`, while full-stack and production profiles render only
their relevant capability skills.
