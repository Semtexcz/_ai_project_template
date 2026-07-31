# Skill: review-change

Purpose: review changes for regressions, missing tests, and documentation impact.

Use when: before marking a task done or requesting human review.

Do not use when: there are no local changes.

Inputs: diff, active task, requirements, quality doc.

Procedure:

1. Inspect behavior changes first.
2. Check tests and validation output.
3. Check documentation and ADR impact.
4. Identify unresolved risks.

Outputs: review findings or approval to proceed.

Allowed changes: review-driven fixes within the task scope.

Validation: relevant checks pass.
