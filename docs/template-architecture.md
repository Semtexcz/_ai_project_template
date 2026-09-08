# Template Architecture

This repository is a Copier template plus optional project-control tooling. It
is not an application runtime by itself; it renders project runtimes from
profile answers and keeps generated projects understandable and updateable.

## Rendering Flow

Copier reads `copier.yml`, renders files from `template/`, applies exclusions,
and writes a generated project. The generated shape comes from five independent
concerns:

- AI engineering kernel: common executable guardrails, agent-facing invariants,
  docs, ADRs, and update safety
- `project_type`: Python package, FastAPI backend, Nuxt frontend, or full-stack
  combination
- `runtime_level`: local developer execution, shared build/run checks, or
  production-like local OCI artifact checks
- `governance`: lightweight durable context or managed project lifecycle
- `workflow_mode`: local, branch, or pull-request Git workflow strictness

Diagram: [template-flow.d2](diagrams/template-flow.d2)

## Profiles

The runtime profile axes are deliberately separate. Presets are conveniences
only; the authoritative values remain `project_type` and `runtime_level`.
Governance and workflow mode are independent from those axes. Valid conceptual
combinations include `script + local + lightweight`,
`backend + shared + lightweight`, `fullstack + local + lightweight`, and
`fullstack + production + managed`. See [Profile Matrix](profile-matrix.md) for
the current generated contents.

## Governance Modes

`governance=lightweight` is the default. It renders the AI engineering kernel,
technical checks, `project/brief.md`, product/architecture/workflow/quality
docs, and ADR scaffolding. It does not render a task state machine, approval
state, generated board, mandatory milestone gate, or generated dashboard.

`governance=managed` preserves the existing richer project-management system.
It has a single project state source:

- `project/state.yaml` stores phase, milestone, next gate, active task, and
  blocked flag.
- `project/tasks/*.md` stores task state, dependencies, approval level, and
  completion evidence.
- `tools/project.py` validates state and synchronizes generated dashboard
  blocks in README, project index, and board.

No separate task database or board source is introduced. The markdown files are
the project record; generated dashboard blocks are derived from them.

Diagram: [generated-project-workflow.d2](diagrams/generated-project-workflow.d2)

## Agent Layer

All generated projects include `AGENTS.md`, `.agents/`, `.codex/`, and
`tools/agent.py`. `.agents/` is canonical and tool-neutral. `.codex/` stays
thin and delegates to canonical skills.

The skill architecture is deliberately separated:

- core skills in `.agents/skills/` are reusable engineering capabilities and
  render for lightweight and managed projects
- managed lifecycle skills in `.agents/managed/skills/` render only for
  `governance=managed`
- capability skills in `.agents/capabilities/skills/` render only when the
  selected profile has that specialized workflow

Core skills use durable context such as `AGENTS.md`, `project/brief.md`,
architecture, workflow, quality, and ADR docs. They must not require
`project/state.yaml`, `project/index.md`, `project/board.md`, or active task
files. Managed projects may enrich the same core skills with active-task
context.

Core skills currently include `orient-project`, `implement-change`,
`verify-change`, `review-change`, `update-documentation`, `create-adr`,
`conventional-commit`, and `capture-learning`. Managed skills cover state
assessment, task choice, task preparation, task completion, and project
reassessment. Capability skills cover full-stack API contract changes and
production artifact verification where those workflows exist.

The managed agent entry commands are:

```bash
make agent-status
make agent-context TASK=<id>
make agent-pre-task TASK=<id>
make agent-pre-review TASK=<id>
make agent-post-task TASK=<id>
```

Lightweight projects do not render those lifecycle commands, but they do render
`make validate-agent-skills`.

## OpenAPI

Full-stack profiles generate a TypeScript client from the real FastAPI OpenAPI
schema. `make api-schema` loads the backend app and writes `artifacts/openapi.json`.
`make api-generate` writes generated frontend client files. `make api-check`
generates into a temporary directory and fails if the committed generated client
is stale.

Backend-only profiles expose OpenAPI through FastAPI but do not include a
frontend client. Script, library, and frontend-only profiles do not include the
generated OpenAPI client path.

## Production Runtime

Production is available only where a generated runtime can be verified locally.
For full-stack production, the template generates backend and frontend Docker
runtime stages plus Compose targets:

```bash
make image-build
make image-inspect
make prod-up
make prod-status
make prod-smoke
make prod-down
```

This means local OCI artifact verification, health/readiness checks, production
process commands, non-root runtime users, and smoke tests. It does not mean
cloud deployment, registry publishing, database operations, TLS termination, or
high-availability infrastructure.

Diagram: [runtime-profiles.d2](diagrams/runtime-profiles.d2)

## Updates

Copier update safety relies on `_skip_if_exists` for product-owned files such as
product docs, project brief, roadmap, requirements, existing task files, and
ADRs. Template-owned workflow tools, Make targets, agent instructions, and
scaffolding remain updateable.

Existing generated projects created before the governance answer existed should
choose a governance mode explicitly during upgrade. Use `governance=managed` to
preserve project state, task lifecycle, boards, and approval metadata. Use
`governance=lightweight` only after intentionally removing or archiving managed
project-control files. Copier will not safely infer that choice from local
customizations. Update behavior is tested by the Copier update golden path.

## Validation And Tests

Generated project validation:

```bash
make validate-docs
make validate-agent-skills
make check
```

Managed generated project validation also includes:

```bash
make sync-project-docs
make validate-project
make check
```

`make check` is validation-only. Mutating operations are explicit commands such
as `make format`, `make api-generate`, and managed `make sync-project-docs`.

Template validation:

```bash
make validate-template-docs
make validate-project
make validate-agent-skills
make check
```

`make release-check` is the template release-candidate gate. It includes static
template checks, generated project golden paths, Copier update checks, agent
workflow checks, project-state mutation checks, production runtime inspection,
and documentation drift checks.

Template release is a two-phase maintainer workflow that preserves the PR-only
`main` rule. `make template-release-prepare BUMP=<major|minor|patch>`
(implemented in `tools/template_release.py`, outside the rendered template
directory) validates, runs `make release-check`, and creates a normal
`chore(release): vX.Y.Z` commit on a non-`main` release branch. It never tags
or pushes and refuses to run on `main`; the version commit reaches `main` only
through the normal pull request and human merge. After the merge,
`make template-release-tag` runs on clean, up-to-date `main`, verifies local
`main` equals `origin/main` and that `HEAD` is the exact release commit, and
creates an annotated `vX.Y.Z` tag pointing at `HEAD`. Tagging creates no
commit, and a human publishes only the intended tag (`git push origin vX.Y.Z`)
before Copier can use it. Validation targets, task review, and task completion
do not create release commits or tags.
