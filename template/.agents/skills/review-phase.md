# Skill: review-phase

Purpose: decide whether the project can move to the next lifecycle phase.

Use when: milestone exit criteria may be complete or a gate blocks work.

Do not use when: a task is incomplete and no phase decision is needed.

Inputs: lifecycle, roadmap, requirements, architecture, ADR index, board, active task.

Procedure:

1. Check current phase goal and exit criteria.
2. Identify soft and hard gate gaps.
3. For each hard gap, propose the smallest task that removes it.
4. If criteria pass, update `project/state.yaml` and dashboards.

Outputs: phase decision and next task.

Allowed changes: project state, roadmap status, task metadata.

Validation: `make sync-project-docs && make validate-project`.
