---
type: workflow
status: active
source_of_truth_for:
  - daily-change-loop
read_when:
  - implement-change
  - review-change
  - complete-task
update_when:
  - workflow-policy-change
---

# Workflow

## One Change Loop

Select a ready task -> load minimal context -> verify scope -> design the smallest coherent change -> implement -> test -> self-review -> human review when required -> merge -> release when relevant -> observe -> update project state.

## Definition of Ready

- The task has an owner, outcome, acceptance criteria, status `ready` or `in-progress`, priority, milestone, and approval level.
- The task names blockers, risks, and required context.
- The expected validation command is known.

## AI Agent Work

- Load `AGENTS.md`, `project/state.yaml`, `project/index.md`, and the active task first.
- Use `.agents/context-map.yaml` for additional context.
- Do not perform A2 actions without explicit approval.
- Prefer the smallest reversible change.

## Definition of Done

- Acceptance criteria are met.
- Required tests pass.
- Documentation impact is handled.
- ADR impact is checked.
- Task, board, state, and README dashboard are synchronized.
- A next task is selected or proposed.

## Release and Post-Release

Local projects may stop at verified checks. Shared and production projects need release notes, rollback notes, and post-release verification appropriate to their runtime level.
