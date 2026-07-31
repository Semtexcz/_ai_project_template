# Skill: choose-next-task

Purpose: select exactly one next main task.

Use when: a task completes, project state is blocked, or no active task exists.

Do not use when: an A2 decision is needed and has not been approved.

Inputs: `project/state.yaml`, roadmap, requirements, board, tasks.

Procedure:

1. Check phase and milestone exit criteria.
2. Find the first unsatisfied hard gate.
3. Prefer blockers, security/data risks, critical hypotheses, phase exit criteria, then user value.
4. Pick the smallest ready unblocked task.
5. Update `project/state.yaml`, task status, board, README, and project index.

Outputs: one active task and synchronized dashboards.

Allowed changes: project state and task metadata.

Validation: `make sync-project-docs && make validate-project`.
