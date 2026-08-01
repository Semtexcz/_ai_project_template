---
id: T-018

title: Add conventional commit agent skill

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

# T-018: Add Conventional Commit Agent Skill

## Goal

Add a dedicated agent skill that generates conventional commit messages with a
cheap model and a deterministic validator.

## Context

The project already defines agent skills and validation hooks, but it does not
provide a focused conventional-commit helper. A dedicated skill should let an
agent produce repository-appropriate conventional commit messages, use a lower
cost model for routine commit drafting, and verify the result with a
deterministic local validator. The requested inspiration is the GitHub
`awesome-copilot` conventional-commit skill, adapted to this repository's
skill structure and agent workflow.

## Scope

- Create a new skill for conventional commit generation under the repository's
  agent-facing skill structure.
- Configure the skill to use a cheaper model appropriate for routine commit
  drafting.
- Add a deterministic validator that checks the produced commit message format
  and repository-specific rules.
- Wire any required documentation, templates, or helper scripts into the skill.
- Add focused tests or validation coverage for the new skill assets and rules.

## Out of Scope

- Changing the project's overall Git workflow beyond what the skill needs.
- Rewriting existing task lifecycle or approval commands.
- Adding external services, hosted inference, or production infrastructure.

## Acceptance Criteria

- [x] A conventional-commit skill exists and is discoverable by the repository's
  agent tooling.
- [x] The skill instructions clearly scope when to use it and how it should
  produce commit messages.
- [x] The implementation uses a cheaper model configuration for commit drafting.
- [x] A deterministic validator rejects invalid commit messages and accepts valid
  ones.
- [x] Focused validation for the skill passes along with project validation.

## Verification

- `make validate-agent-skills` passed.
- `UV_CACHE_DIR=/tmp/t018-uv-cache uv run pytest tests/test_template_static.py::test_conventional_commit_skill_uses_cheap_model_and_validator tests/test_template_static.py::test_generated_project_has_single_state_source_and_dashboard_tools`
  passed.
- `UV_CACHE_DIR=/tmp/t018-uv-cache UV_LINK_MODE=copy uv run pytest tests/test_agent_one_task_workflow_golden_path.py::test_agent_negative_scenarios`
  passed after allowing generated-project dependency installation outside the
  sandbox.
- `make validate-project` passed.

## Documentation Impact

Updated `.agents/README.md` and `template/.agents/README.md` to note skill-local
agent metadata for model profiles and validator scripts.

## Completion Notes

Added a canonical `conventional-commit` skill with a `gpt-5-mini` model profile
and a deterministic local validator script. Generated projects now receive the
same canonical skill plus a thin Codex adapter in `template/.codex`. Agent
skill validation now enforces the cheap-model profile, validates skill-local
metadata, and smoke-tests the conventional-commit validator with valid and
invalid commit messages.
