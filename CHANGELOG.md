# Changelog

## Unreleased

- Reworked the template release workflow into a PR-only, two-phase flow: `make template-release-prepare BUMP=<major|minor|patch>` creates an ordinary, reviewable `chore(release): vX.Y.Z` version commit on a non-`main` release branch (no tag, no push), and `make template-release-tag` creates the annotated release tag only after that commit is merged to `main` and local `main` equals `origin/main`. Publication pushes only the intended tag (`git push origin vX.Y.Z`). Direct release commits on `main`, `git update-ref` branch advancement by release tooling, and the `git push origin main --follow-tags` publication recommendation are removed.
- Added a supported Copier update workflow for projects generated from a versioned Git template source.
- Documented the template-owned, project-owned, and merge-sensitive file ownership model.
- Added a targeted two-version Copier update integration test using temporary Git commits and tags.
- Recorded template version metadata in generated projects through `.template-version` rendered from the Copier Git ref.
- Current limitation: update safety is tested for the fullstack-local golden path; future structural migrations require explicit migration tests.

## 0.1.0 - 2026-07-31

- Initial golden-path template repository for Python, FastAPI, Nuxt, TypeScript, Docker, GitHub Actions, documentation-as-code, and AI-agent workflows.
- Added Copier questions for project type and runtime level.
- Added generated project dashboard, state validation, Kanban synchronization, and agent context map.
