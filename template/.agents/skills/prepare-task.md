# Skill: prepare-task

Purpose: make a task ready before implementation.

Use when: a task lacks acceptance criteria, scope, context, or validation.

Do not use when: implementation has already started and the task is materially changing scope.

Inputs: brief, requirements, architecture, active task.

Procedure:

1. Define outcome and non-goals.
2. Add acceptance criteria and validation commands.
3. Set approval level.
4. Mark blockers with an unblock step.

Outputs: a ready task.

Allowed changes: task file and related requirements.

Validation: `make validate-project`.
