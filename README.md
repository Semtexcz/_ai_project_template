# AI Project Golden Path Template

Opinionated Copier template for Python, FastAPI, Vue, Nuxt, TypeScript, Docker, GitHub Actions, documentation-as-code, and AI-assisted development.

## Status

| Item | Current State |
|---|---|
| Template version | 0.1.0 |
| Supported project types | script, library, backend, frontend, fullstack |
| Supported runtime levels | local, shared, production |
| Current focus | Bootstrap complete template skeleton |

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

## Verify Template

```bash
uv run pytest
```

## Design Decisions

- [ADR-0001: Use Copier as the update mechanism](docs/decisions/ADR-0001-use-copier.md)
- [ADR-0002: Keep `.agents` canonical and `.codex` thin](docs/decisions/ADR-0002-agent-layer.md)
- [ADR-0003: Use feature-oriented modular monoliths](docs/decisions/ADR-0003-modular-monolith.md)
