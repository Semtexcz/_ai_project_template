# Skill: assess-project-state

Purpose: determine whether project state, docs, and tasks agree.

Use when: starting work, resuming work, or before phase review.

Do not use when: only a narrow code formatting change is requested and state was already checked in the same session.

Inputs: README, `project/state.yaml`, `project/index.md`, `project/board.md`, active task.

Procedure:

1. Run `make project-status`.
2. Check that the active task exists and is actionable.
3. Check whether `make validate-project` passes.
4. Report the smallest task that would remove the most important gap.

Outputs: state assessment and recommended next step.

Allowed changes: none unless explicitly paired with another skill.

Validation: `make validate-project`.
