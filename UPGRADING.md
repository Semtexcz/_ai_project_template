# Upgrading Generated Projects

This template uses Copier. Generated projects keep their answers in `.copier-answers.yml`.

## Standard Update

```bash
copier update
make sync-project-docs
make validate-project
make check
```

## Ownership Model

Template-owned:

- common workflow scripts
- generated dashboard blocks
- baseline CI workflows
- hook entrypoints

Project-owned:

- `docs/product.md`
- `project/brief.md`
- `project/roadmap.md`
- `project/requirements.md`
- `project/tasks/`
- ADRs and application code

Merge-sensitive:

- `README.md`
- `AGENTS.md`
- `docs/workflow.md`
- `docs/quality.md`
- `pyproject.toml`
- `package.json`
- `compose.yaml`

Do not accept an update that overwrites project knowledge without review.
