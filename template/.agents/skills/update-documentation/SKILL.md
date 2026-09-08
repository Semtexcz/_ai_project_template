---
name: update-documentation
version: 1
purpose: Decide whether a change updates durable project knowledge and edit the right documents.
triggers: [update docs, documentation impact, docs needed]
inputs:
  required:
    - change_summary
reads:
  - README.md
  - project/brief.md
  - docs/architecture.md
  - docs/workflow.md
  - docs/quality.md
  - docs/decisions/
commands:
  - make validate-docs
outputs:
  - documentation update or documented no-impact reason
approval_boundary:
  may_approve: false
stop_conditions:
  - documentation owner is unclear
  - change requires an ADR first
  - documentation validation fails
---

# Update Documentation

Evaluate whether the implementation changed durable project knowledge. Update
documentation for new architecture boundaries, runtime behavior, external
dependencies, public workflows, validation processes, deployment assumptions,
durable constraints, planning/status drift, milestone progression,
roadmap/backlog changes, next-task changes, and resolved or deferred decision
changes.

Reconcile planning/status artifacts with the post-change repository state:

- Identify the planning/status artifacts that actually exist in this
  repository. Depending on governance and project customization these may
  include a roadmap, milestones, a backlog, project status, next-task
  statements, deferred decisions, or phase/status documentation. Handle
  lightweight or custom projects gracefully when only some of these artifacts
  exist, and do not assume a fixed roadmap path.
- Reconcile them with what the change actually delivered. Do not update them
  mechanically to preserve previous ordering. Prefer truthful current-state
  documentation over preserving the previous backlog order.
- If no update is required, report why instead of creating meaningless
  documentation.

Documentation should capture durable knowledge, not implementation noise.
