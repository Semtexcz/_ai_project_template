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

Start from the focused checks for the changed surface. In a governed project the
single canonical local gate is `make agent-pre-review TASK=<id>`, which runs the
project's `make check` once; do not run `make check` separately right before it.
Exhaustive confidence beyond that gate belongs to CI, which runs after the push:
it is required but asynchronous, so the implementation session ends at the pushed
pull request and does not wait for or poll CI.
