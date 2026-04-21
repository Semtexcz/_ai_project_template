# Copier Template Usage

## Purpose

This repository is a Copier template for AI-first software projects.
It intentionally preserves the project management and agent-collaboration structure instead of only scaffolding code.

## Generate a Project

Install Copier, then generate a new project from this repository:

```bash
copier copy /path/to/_ai_project_template /path/to/new-project
```

Copier will prompt for a small set of values:

- `project_name` — project title shown in docs and README
- `project_slug` — repository and CLI-facing slug
- `package_name` — Python package name under `src/`
- `project_description` — short summary for README and package metadata
- `author_name` and `author_email` — Poetry package metadata
- `python_version` — shared Python version for tooling and CI
- `initial_version` — initial package version

## Update an Existing Generated Project

Generated projects should keep the Copier answers file committed.
To pull in template updates later:

```bash
copier update
```

Review changes carefully, especially if the generated project has modified:

- `AGENTS.md`
- `docs/`
- `product/`
- `project/`
- `pyproject.toml`

## Parameterization Decisions

This template deliberately keeps parameterization small.
Only identity and packaging details vary between projects.

Kept static on purpose:

- AI-agent workflow files
- architecture and backlog structure
- task and feature templates
- Poetry-based tooling layout
- CI baseline

Not parameterized on purpose:

- feature/task naming conventions
- documentation directory structure
- testing strategy shape
- language or framework selection

If broader customization becomes necessary, prefer adding a second specialized template rather than turning this one into a highly branched meta-template.
