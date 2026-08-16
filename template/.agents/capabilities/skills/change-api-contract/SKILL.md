---
name: change-api-contract
version: 1
purpose: Coordinate backend API contract changes with generated client consistency.
triggers: [change api contract, openapi change, generated client]
inputs:
  required:
    - contract_change
reads:
  - docs/architecture.md
  - docs/quality.md
  - backend/src/app/
  - frontend/shared/api/
  - artifacts/openapi.json
commands:
  - make api-schema
  - make api-check
  - make test
  - make check
outputs:
  - synchronized backend contract and client artifacts
  - verification results
approval_boundary:
  may_approve: false
stop_conditions:
  - contract intent is unclear
  - generated client is stale
  - backend or frontend verification fails
---

# Change API Contract

Use this skill for full-stack changes that affect the backend public API or the
generated frontend client. Change the backend contract first, export OpenAPI,
update or check the generated client through existing commands, then run
backend and frontend verification.

Do not hand-edit generated client artifacts when a deterministic generator owns
them.
