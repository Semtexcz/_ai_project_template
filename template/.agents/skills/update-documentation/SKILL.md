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
  - .agents/context-map.yaml
  - docs/decisions/index.md
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

Reconcile durable planning/status artifacts only when they actually exist and
the change materially affects them:

- Identify the planning/status artifacts this repository actually keeps.
  Depending on governance and customization these may include a roadmap,
  milestones, a backlog, project status, next-task statements, deferred
  decisions, or phase/status documentation. Handle lightweight or custom
  projects gracefully when only some of these artifacts exist, or none at all,
  and do not assume a fixed roadmap path.
- Reconcile them with what the change actually delivered. Remove stale claims,
  mark complete only work actually delivered, and never update them
  mechanically to preserve previous ordering. Prefer truthful current-state
  documentation over preserving the previous backlog order.
- Lightweight projects do not require task selection, next-task statements, or
  a `Project State Check` footer.
- If no update is required, report why instead of creating meaningless
  documentation.

This skill keeps durable documentation truthful; it is not a lifecycle engine.
Never mutate managed task/approval state or generated boards directly. Managed
projects change task state through lifecycle commands and refresh generated
dashboards with `make sync-project-docs`.

Documentation should capture durable knowledge, not implementation noise.
