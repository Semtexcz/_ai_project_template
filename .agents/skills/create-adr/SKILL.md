---
name: create-adr
version: 1
purpose: Record a significant architectural decision.
triggers: [create adr, architecture decision, decision record]
inputs:
  required:
    - decision
reads:
  - docs/decisions/index.md
  - .agents/templates/adr.md
commands:
  - make validate-project
outputs:
  - ADR document
  - updated ADR index
approval_boundary:
  may_approve: false
stop_conditions:
  - decision is only an implementation detail
  - required approval is missing
  - ADR index is missing
---

# Create ADR

Create an ADR only for durable architectural choices. Link it to the task and
update the ADR index when the generated project contains one.
