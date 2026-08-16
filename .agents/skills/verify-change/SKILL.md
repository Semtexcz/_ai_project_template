---
name: verify-change
version: 1
purpose: Select and run the relevant deterministic validation path for a change.
triggers: [verify change, run checks, validation path]
inputs:
  required:
    - change_summary
reads:
  - .agents/context-map.yaml
  - docs/quality.md
  - docs/workflow.md
  - Makefile
commands:
  - make validate-docs
  - make validate-agent-skills
  - make check
outputs:
  - validation plan
  - command results
  - residual unverified risks
approval_boundary:
  may_approve: false
stop_conditions:
  - change type cannot be determined
  - required validation command is unavailable
  - deterministic checks fail
---

# Verify Change

Use this skill to route a change to existing deterministic checks. Do not
duplicate validation logic inside the skill when a Make target or executable
guardrail already exists.

Choose focused checks first, then broader checks. Examples:

- Python change: focused tests, lint/typecheck, `make check`.
- API contract change: backend tests, OpenAPI/client checks, `make check`.
- Docker/runtime change: build, inspect, smoke test, `make check`.
- Documentation-only change: documentation validation, `make check`.

Report commands run, results, and any risk that remains unverified.
