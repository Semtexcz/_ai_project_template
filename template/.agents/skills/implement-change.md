# Skill: implement-change

Purpose: implement the active task with the smallest coherent change.

Use when: the task is ready or in progress.

Do not use when: the ready-for-development gate is blocked for the main vertical slice.

Inputs: active task, relevant docs from `.agents/context-map.yaml`, code touched by the task.

Procedure:

1. Verify scope and approval level.
2. Read the smallest relevant code surface.
3. Implement.
4. Add or update tests according to risk.
5. Run focused checks, then `make check` when feasible.

Outputs: code/docs changes satisfying acceptance criteria.

Allowed changes: files required by the active task.

Validation: task-specific checks and `make check`.
