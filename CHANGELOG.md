# Changelog

## Unreleased

- Added a supported Copier update workflow for projects generated from a versioned Git template source.
- Documented the template-owned, project-owned, and merge-sensitive file ownership model.
- Added a targeted two-version Copier update integration test using temporary Git commits and tags.
- Recorded template version metadata in generated projects through `.template-version` rendered from the Copier Git ref.
- Current limitation: update safety is tested for the fullstack-local golden path; future structural migrations require explicit migration tests.

## 0.1.0 - 2026-07-31

- Initial golden-path template repository for Python, FastAPI, Nuxt, TypeScript, Docker, GitHub Actions, documentation-as-code, and AI-agent workflows.
- Added Copier questions for project type and runtime level.
- Added generated project dashboard, state validation, Kanban synchronization, and agent context map.
