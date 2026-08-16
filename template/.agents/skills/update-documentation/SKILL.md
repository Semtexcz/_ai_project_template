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
dependencies, public workflows, validation processes, deployment assumptions, or
durable constraints.

If documentation impact is none, report the reason instead of creating
meaningless documentation. Documentation should capture durable knowledge, not
implementation noise.
