# Skill: complete-task

Purpose: close the active task and select the next step.

Use when: acceptance criteria and Definition of Done are met.

Do not use when: required checks or approvals are missing.

Inputs: active task, validation output, state, board.

Procedure:

1. Mark acceptance criteria complete.
2. Move task to `done` or `review`.
3. Select the next task or propose one.
4. Sync dashboards.

Outputs: updated task, board, state, README dashboard.

Allowed changes: project workflow files.

Validation: `make sync-project-docs && make validate-project`.
