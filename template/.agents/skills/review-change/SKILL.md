---
name: review-change
version: 1
purpose: Review the actual diff for correctness, risk, and readiness.
triggers: [review change, inspect diff, pre review, ready for review]
inputs:
  required:
    - requested_intent
reads:
  - AGENTS.md
  - .agents/context-map.yaml
  - project/brief.md
  - docs/architecture.md
  - docs/quality.md
  - docs/workflow.md
commands:
  - git diff --stat
  - git diff
  - make validate-docs
  - make validate-agent-skills
  - make check
outputs:
  - findings ordered by severity
  - residual risks and test gaps
  - readiness recommendation
approval_boundary:
  may_approve: false
stop_conditions:
  - requested intent is unclear
  - unsafe diff
  - failing checks
  - missing verification evidence
---

# Review Change

Inspect the diff itself before declaring readiness. Evaluate correctness against
the requested intent, architecture invariants, unnecessary complexity,
regressions, test coverage, documentation impact, security and risk
implications, and accidental unrelated changes.

Report findings before summaries or readiness statements. In managed projects,
task acceptance criteria may add context, but lifecycle transitions remain
outside this core review skill.

Include planning/status readiness in the Definition of Done:

- Does any roadmap, backlog, milestone, next-task, deferred-status, or other
  planning statement contradict the actual post-change repository state?
- Is completed work marked complete only when it was actually delivered?
- Is next-task wording still justified by the current repository state?
- Were stale deferred or open statements removed or updated?

Treat material planning/status drift as a readiness finding. Do not make every
incidental documentation mismatch a blocker; only material contradictions
between the actual repository state and durable planning/status documentation
should affect readiness.
