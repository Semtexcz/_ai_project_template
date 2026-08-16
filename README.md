# AI Project Golden Path Template

Copier template for AI-first software projects that should start small, ship a
useful vertical slice quickly, and add stronger process constraints only when
complexity or risk justifies them. It generates Python scripts and libraries,
FastAPI backends, Nuxt frontends, and full-stack projects with optional
production-like local runtime checks.

Use this repository when you want a project scaffold that already knows how to:

- choose a profile from `project_type` and `runtime_level`
- choose `governance=lightweight` or `governance=managed`
- choose `workflow_mode=local`, `branch`, or `pr`
- use reusable core agent skills without opting into managed task lifecycle
- keep technical guardrails executable through Make targets and tests
- preserve managed task state, dashboards, and approvals when explicitly enabled
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
| Last completed task | [T-021](project/tasks/T-021-fix-lightweight-render-matrix-ci.md) |
| Active task | None |
| Approval | None |
| Waiting | A1 approval pending: T-023 |
| Blocker | None |
| Next gate | release-candidate-remediation |
| Recommended next action | Human A1 approval is required for T-023 before completion. |
| Next action command | `make task-approve TASK=T-023 APPROVED_BY="<human>"` |
<!-- project-status:end -->

## Quick Start

Create a local script project with the default lightweight governance:

```bash
copier copy --defaults --data project_type=script --data runtime_level=local . /tmp/golden-script
cd /tmp/golden-script
make setup
make check
make build
```

Create a managed production-profile full-stack project with strict PR workflow:

```bash
copier copy --defaults \
  --data project_type=fullstack \
  --data runtime_level=production \
  --data governance=managed \
  --data workflow_mode=pr \
  . /tmp/golden-fullstack
cd /tmp/golden-fullstack
make setup
make check
make build
```

## Architecture

Copier renders `template/` from independent axes:

- `project_type`: `script`, `library`, `backend`, `frontend`, or `fullstack`
- `runtime_level`: `local`, `shared`, or `production`
- `governance`: `lightweight` or `managed`
- `workflow_mode`: `local`, `branch`, or `pr`

The AI engineering kernel is common: build, test, lint, typecheck, docs
validation, reusable core skills under `.agents/skills`, a thin `.codex`
adapter, profile-specific API/client drift checks, and production artifact
checks where selected. Lightweight governance renders durable project context
without managed task state. Managed governance also renders project state, task
lifecycle skills, boards, dashboard generation, dependencies, and approval
metadata.

The generated project owns product docs and durable project knowledge. The
template owns scaffolding, Make targets, workflow tools, agent instructions,
profile rules, and update behavior. See [Template Architecture](docs/template-architecture.md)
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
make validate-project
make validate-template-docs
make check
```

`make check` is pure validation and must not modify tracked files. Use
`make sync-project-docs` explicitly when this managed template repository's
generated dashboards need refresh.

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

After reviewed template changes are merged to `main`, run
`make template-release BUMP=<major|minor|patch>` to update
`project/state.yaml.template.version`, commit the version change, and create
the matching annotated Git tag used by Copier.

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
