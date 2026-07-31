# AGENTS.md

## Required Start

Run or read the project status before changing files:

```bash
make project-status
```

Then load `project/state.yaml`, `project/index.md`, and the active task under
`project/tasks/`.

## Project Workflow

- Use `make task-ready`, `make task-start`, `make task-review`,
  `make task-complete`, and `make task-block` for state changes.
- Do not bypass the task lifecycle by silently editing task status.
- Do not autonomously run `make task-approve`; approval commands are only for a
  human.
- After project or task changes, run `make sync-project-docs` when generated
  dashboards need refresh.
- Finish by running `make validate-project`.

## Boundaries

Do not add production runtime, databases, queues, brokers, Redis, or external
infrastructure unless a later approved task explicitly scopes that work.
