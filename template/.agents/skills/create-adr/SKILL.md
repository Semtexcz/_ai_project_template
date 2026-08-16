---
name: create-adr
version: 1
purpose: Record a significant architectural decision.
triggers: [create adr, architecture decision, decision record]
inputs:
  required:
    - decision
reads:
  - docs/architecture.md
  - docs/decisions/index.md
  - .agents/templates/adr.md
commands:
  - make validate-docs
outputs:
  - ADR justification or no-ADR decision
  - ADR document when justified
  - updated ADR index when present
approval_boundary:
  may_approve: false
stop_conditions:
  - decision is only an implementation detail
  - required approval is missing
  - documentation validation fails
---

# Create ADR

First decide whether an ADR is justified. Create one for durable choices such as
technology selection, architecture boundaries, persistence strategy,
communication patterns, significant dependencies, or expensive-to-reverse
decisions.

Do not create ADRs for ordinary implementation details, trivial refactors,
temporary experiments, or cheap obvious choices. In managed projects, link the
ADR to the task when useful, but the ADR process itself is governance-neutral.
