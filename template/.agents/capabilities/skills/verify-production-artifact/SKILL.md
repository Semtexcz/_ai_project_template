---
name: verify-production-artifact
version: 1
purpose: Verify production runtime artifacts through existing build, inspect, readiness, and smoke commands.
triggers: [verify production artifact, production build, runtime smoke]
inputs:
  required:
    - artifact_change
reads:
  - docs/architecture.md
  - docs/quality.md
  - docs/workflow.md
  - compose.yaml
  - backend/Dockerfile
  - frontend/Dockerfile
commands:
  - make build
  - make image-build
  - make image-inspect
  - make prod-up
  - make prod-status
  - make prod-smoke
  - make e2e-production
  - make prod-down
  - make check
outputs:
  - production artifact verification results
  - readiness and smoke-test evidence
approval_boundary:
  may_approve: false
stop_conditions:
  - Docker or Compose is unavailable
  - build or inspection fails
  - readiness or smoke checks fail
  - services cannot be shut down cleanly
---

# Verify Production Artifact

Use this skill for production runtime changes. Orchestrate the existing
deterministic commands for build, image inspection, service start, readiness,
smoke testing, E2E checks where applicable, and shutdown.

Do not duplicate runtime logic in the skill. If a Make target already encodes
the check, run that target and report the result.
