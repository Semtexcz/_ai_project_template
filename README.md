# AI Project Golden Path Template

Opinionated Copier template for Python, FastAPI, Vue, Nuxt, TypeScript, Docker, GitHub Actions, documentation-as-code, and AI-assisted development.

## Status

<!-- project-status:start -->
| Item | Value |
|---|---|
| Project type | template |
| Runtime level | local |
| Phase | delivery |
| Milestone | M-07 |
| Active task | None |
| Approval | None |
| Next gate | production-runtime-golden-path |
| Recommended next action | No ready task exists. Create one task addressing gate production-runtime-golden-path. |
<!-- project-status:end -->

## Use

Script:

```bash
copier copy --defaults --data project_type=script --data runtime_level=local . ../my-project
cd ../my-project
make setup
make check
make build
```

Shared library:

```bash
copier copy --defaults --data project_type=library --data runtime_level=shared . ../my-library
cd ../my-library
make setup
make check
make build
```

Shared frontend:

```bash
copier copy --defaults --data project_type=frontend --data runtime_level=shared . ../my-frontend
cd ../my-frontend
make setup
make check
make build
make run
```

Local full-stack:

```bash
copier copy --defaults --data project_type=fullstack --data runtime_level=local . ../my-fullstack
cd ../my-fullstack
make setup
make api-check
make check
make build
make run
```

## Verify Template

```bash
uv run pytest
```

Targeted maintainer checks:

```bash
make agent-status
make agent-context TASK=<id>
make agent-pre-task TASK=<id>
make agent-pre-review TASK=<id>
make agent-post-task TASK=<id>
make project-status
make sync-project-docs
make validate-project
make test-template
make test-copier-update
```

## Design Decisions

- [ADR-0001: Use Copier as the update mechanism](docs/decisions/ADR-0001-use-copier.md)
- [ADR-0002: Keep `.agents` canonical and `.codex` thin](docs/decisions/ADR-0002-agent-layer.md)
- [ADR-0003: Use feature-oriented modular monoliths](docs/decisions/ADR-0003-modular-monolith.md)
