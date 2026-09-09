# Changelog

## Unreleased

- Reworked the template release workflow into a PR-only, two-phase flow: `make template-release-prepare BUMP=<major|minor|patch>` creates an ordinary, reviewable `chore(release): vX.Y.Z` version commit on a non-`main` release branch (no tag, no push), and `make template-release-tag` creates the annotated release tag only after that commit is merged to `main` and local `main` equals `origin/main`. Publication pushes only the intended tag (`git push origin vX.Y.Z`). Direct release commits on `main`, `git update-ref` branch advancement by release tooling, and the `git push origin main --follow-tags` publication recommendation are removed.
- Added a supported Copier update workflow for projects generated from a versioned Git template source.
- Documented the template-owned, project-owned, and merge-sensitive file ownership model.
- Added a targeted two-version Copier update integration test using temporary Git commits and tags.
- Recorded template version metadata in generated projects through `.template-version` rendered from the Copier Git ref.
- Current limitation: update safety is tested for the fullstack-local golden path; future structural migrations require explicit migration tests.
- Refined generated project-state reconciliation so managed projects keep stronger reconciliation (including a `Project State Check`) while lightweight projects only keep durable planning/status artifacts truthful when present.
- Agent efficiency v1: three-tier context loading, skill-aware `make agent-context TASK=<id> SKILL=<skill>`, `files` vs `search_roots` context-map semantics (schema v2), deterministic `budget` with omission reporting, branch-aware changed-file detection, change-aware recommended checks, one canonical full `make check` gate in `agent-pre-review`, a resume/review-fix `MODE=resume`, and concise durable task-record guidance.
- Simplified the managed approval lifecycle for GitHub-backed projects: in `workflow_mode: pr` the human GitHub merge of a task's pull request is the A1 approval/completion boundary (and A2's completion boundary). Agents move A1/A2 work to `review`, associate one task id (`T-###`) per pull request, and stop; `make pr-validate` checks pre-merge structural readiness; A1 `task-approve` and A1/A2 `task-complete` are rejected in `pr` mode; boards/dashboards derive the completed view; and no post-merge lifecycle command or cleanup pull request is required. `local`/`branch` mode keeps the explicit human `task-approve` + `task-complete` fallback, and historical `done` approval metadata remains valid.

## 0.1.0 - 2026-07-31

- Initial golden-path template repository for Python, FastAPI, Nuxt, TypeScript, Docker, GitHub Actions, documentation-as-code, and AI-agent workflows.
- Added Copier questions for project type and runtime level.
- Added generated project dashboard, state validation, Kanban synchronization, and agent context map.
