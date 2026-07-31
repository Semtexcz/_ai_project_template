# Skill: initialize-project

Purpose: turn the generated placeholder project into a concrete project definition.

Use when: starting a new generated project.

Do not use when: the brief and first milestone are already approved.

Inputs: README, `project/state.yaml`, `project/brief.md`, `project/roadmap.md`, `project/requirements.md`, active task.

Procedure:

1. Replace placeholders in the brief with concrete problem, user, outcome, scope, non-goals, assumptions, and risks.
2. Keep only requirements that are verifiable for the current scope.
3. Update the active milestone.
4. Run `make sync-project-docs` and `make validate-project`.

Outputs: updated project knowledge and one active task.

Allowed changes: project docs and dashboard synchronization.

Validation: `make validate-project`.
