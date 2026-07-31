# Skill: reassess-project

Purpose: safely reopen an abandoned or stale project.

Use when: returning after a long pause or when docs and code disagree.

Do not use when: the current state was already validated in this session.

Inputs: README, state, board, roadmap, requirements, docs index, repository tree, test output.

Procedure:

1. Compare README, `project/state.yaml`, board, and actual repository.
2. Run available checks.
3. Identify stale docs and unfinished work.
4. Reassess phase and milestone.
5. Propose or create one active task that removes the largest gap.

Outputs: reassessment notes and one active task.

Allowed changes: project state, tasks, dashboards, and clearly stale project docs.

Validation: `make sync-project-docs && make validate-project`.
