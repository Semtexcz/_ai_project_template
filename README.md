# AI Project Golden Path Template

Copier template for small-to-medium software projects that need executable
defaults, lightweight project governance, and AI-agent instructions from the
first commit. It generates Python scripts and libraries, FastAPI backends, Nuxt
frontends, and full-stack projects with optional production-like local runtime
checks.

Use this repository when you want a project scaffold that already knows how to:

- choose a profile from `project_type` and `runtime_level`
- keep project state in `project/state.yaml` plus task frontmatter
- synchronize README, project index, and board dashboards
- validate internal documentation links, Make commands, and profile drift
- support Copier updates without replacing product-owned files

## Current Status

<!-- project-status:start -->
| Item | Value |
|---|---|
| Project type | template |
| Runtime level | local |
| Phase | delivery |
| Milestone | M-08 |
| Last completed task | [T-014](project/tasks/T-014-run-targeted-remediation-audit.md) |
| Active task | None |
| Approval | None |
| Waiting | A1 approval pending: T-015 |
| Blocker | None |
| Next gate | release-candidate-remediation |
| Recommended next action | Human A1 approval is required for T-015 before completion. |
| Next action command | `make task-approve TASK=T-015 APPROVED_BY="<human>"` |
<!-- project-status:end -->

## Quick Start

Create a local script project:

```bash
copier copy --defaults --data project_type=script --data runtime_level=local . /tmp/golden-script
cd /tmp/golden-script
make setup
make check
make build
```

Create a production-profile full-stack project:

```bash
copier copy --defaults --data project_type=fullstack --data runtime_level=production . /tmp/golden-fullstack
cd /tmp/golden-fullstack
make setup
make check
make build
```

## Architecture

Copier renders `template/` using two independent axes:

- `project_type`: `script`, `library`, `backend`, `frontend`, or `fullstack`
- `runtime_level`: `local`, `shared`, or `production`

The generated project owns its product docs and project state. The template owns
the scaffolding, Make targets, workflow tools, agent instructions, profile
rules, and update behavior. See [Template Architecture](docs/template-architecture.md)
for the full system view and [Profile Matrix](docs/profile-matrix.md) for what
each profile includes.

## Maintainer Workflow

Before changing this template, use the project lifecycle:

```bash
make agent-status
make agent-context TASK=<id>
make task-start TASK=<id>
```

During implementation:

```bash
make sync-project-docs
make validate-project
make validate-template-docs
make check
```

Before review:

```bash
make agent-pre-review TASK=<id>
make task-review TASK=<id>
```

Full release-candidate validation:

```bash
make release-check
```

`make check` is the fast maintainer subset. `make release-check` runs the full
pytest suite, including all golden paths, Copier update, workflow, production
runtime inspection, and documentation validation.

## Navigation

| Need | Open |
|---|---|
| Template architecture | [docs/template-architecture.md](docs/template-architecture.md) |
| Profile contents | [docs/profile-matrix.md](docs/profile-matrix.md) |
| Template development and release safety | [docs/template-development.md](docs/template-development.md) |
| Current project dashboard | [project/index.md](project/index.md) |
| Kanban board | [project/board.md](project/board.md) |
| Roadmap | [project/roadmap.md](project/roadmap.md) |
| Agent procedures | [AGENTS.md](AGENTS.md) |
| Copier update ADR | [docs/decisions/ADR-0001-use-copier.md](docs/decisions/ADR-0001-use-copier.md) |
| Agent layer ADR | [docs/decisions/ADR-0002-agent-layer.md](docs/decisions/ADR-0002-agent-layer.md) |
| Modular monolith ADR | [docs/decisions/ADR-0003-modular-monolith.md](docs/decisions/ADR-0003-modular-monolith.md) |
