---
name: capture-learning
version: 1
purpose: Convert repeated project experience into durable guardrails only when justified.
triggers: [capture learning, add guardrail, repeated failure, project lesson]
inputs:
  required:
    - observed_problem
reads:
  - AGENTS.md
  - docs/architecture.md
  - docs/workflow.md
  - docs/quality.md
  - docs/decisions/
  - Makefile
commands:
  - make validate-docs
  - make check
outputs:
  - no-change decision or proposed guardrail
  - verification evidence when a guardrail is added
approval_boundary:
  may_approve: false
stop_conditions:
  - problem is speculative or one-off
  - existing guardrail already covers the failure
  - proposed guardrail cannot be verified
---

# Capture Learning

Use this skill when repeated experience shows the project keeps solving the
same failure through prompts. Decide whether the lesson should become nothing,
documentation, an ADR, a test, linter rule, validation script, Make target, CI
guardrail, or agent instruction.

Prefer executable guardrails over durable documentation, and durable
documentation over agent instructions. Avoid adding textual rules when behavior
can be enforced deterministically.
