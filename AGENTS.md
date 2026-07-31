# AGENTS.md

## Required Start

Run or read the agent-oriented project status before changing files:

```bash
make agent-status
```

Respect exactly one active task. Then load only the context recommended by:

```bash
make agent-context TASK=<id>
```

## Project Workflow

- Use `make task-ready`, `make task-start`, `make task-review`,
  `make task-complete`, and `make task-block` for state changes.
- Do not bypass the task lifecycle by silently editing task status.
- Do not autonomously run `make task-approve`; approval commands are only for a
  human.
- Run `make agent-pre-review TASK=<id>` before moving a task to review.
- After project or task changes, run `make sync-project-docs` when generated
  dashboards need refresh.
- Finish by running `make validate-project`.

Canonical agent procedures are in `.agents/`. Codex-specific adapter notes are
in `.codex/`. Project-specific context is in `project/` and `docs/`.

## Boundaries

Do not add production runtime, databases, queues, brokers, Redis, or external
infrastructure unless a later approved task explicitly scopes that work.
